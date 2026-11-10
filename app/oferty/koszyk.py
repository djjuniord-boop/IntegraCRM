"""KOSZYK xPartner – zamawianie opon z Panelu (metody API: getDeliveryData, getProduct, order).

Według dokumentacji xPartner (docs.xpartner.net.pl → XML API → Zamówienia; Przewodniki → Proces składania zamówienia):
- order: POST na ten sam adres API (login, pass, m=order w adresie), treść = surowy XML, nagłówek Content-Type: application/xml.
  <order> recipientId*, deliveryPlaceId* (int ≥1, z getDeliveryData), document* (Invoice|Receipt – obsługiwana tylko faktura),
  payment* (Transfer|Cash), comment (0..255, tylko dla operatora – wydłuża realizację), extInvoiceDescription (0..100,
  ^[a-zA-Z0-9 \\-/]*$ – na WZ, fakturze i liście przewozowym), extOrderNumber (0..35, ten sam wzór – na fakturze),
  <newDeliveryPlace> (tymczasowe miejsce dostawy: recipientId*, name* 1..76, street* 1..35, zipCode* 1..6, city* 1..25,
  country* 2 [ISO], vatin 0..13, email 0..40, phone 0..25, receivingPerson 0..76; xPartner usuwa je po realizacji),
  <products><product> productId* ≥1, quantity* ≥1 (price – opcjonalna; NIE wysyłamy, decyzja właściciela).
- Odpowiedź: success, <orders><order> orderNo, warehouseName, orderXP, extOrderNumber (może być kilka zamówień), <errors>.
- Przed wysłaniem: sprawdzenie stanów przez API (getProduct) – zalecane przez xPartner; order też sprawdza dostępność.
Decyzje właściciela: zawsze Faktura (Invoice) + przelew (Transfer), bez ceny w zamówieniu, adresy: z konta + jednorazowe.
"""
import re
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

from oferty import zamowienia as Z

API_URL = "https://xpartner.net.pl/index.php"
DOKUMENT, PLATNOSC = "Invoice", "Transfer"     # stałe – decyzja właściciela (2026-11-09)
WZOR_OPIS = re.compile(r"^[a-zA-Z0-9 \-/]*$")
LIMITY_ADRESU = {"name": (1, 76), "street": (1, 35), "zipCode": (1, 6), "city": (1, 25), "country": (2, 2),
                 "vatin": (0, 13), "email": (0, 40), "phone": (0, 25), "receivingPerson": (0, 76)}
PL = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻäöüÄÖÜéÉ", "acelnoszzACELNOSZZaouAOUeE")
MAX_SZT = 200   # bezpiecznik: więcej sztuk jednej opony = pomyłka w ilości


class Blad(Exception):
    pass


def ascii_xp(s, limit):
    """Tekst do pól extInvoiceDescription / extOrderNumber: bez polskich liter i znaków spoza ^[a-zA-Z0-9 -/]$."""
    s = str(s or "").translate(PL)
    s = re.sub(r"[^a-zA-Z0-9 \-/]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()[:limit].strip()
    assert WZOR_OPIS.match(s)
    return s


# ---------------------------------------------------------------- adresy z konta xPartner
def czytaj_adresy(root):
    out = []
    for r in Z._wszystkie(Z._dz(root, "recipients"), "recipient"):
        rid = Z._i(Z._t(r, "recipientId"))
        for d in Z._wszystkie(Z._dz(r, "deliveryPlaces"), "deliveryPlace"):
            out.append({"recipientId": rid, "deliveryPlaceId": Z._i(Z._t(d, "deliveryPlaceId")), "odbiorca": Z._t(r, "name"),
                        "name": Z._t(d, "name"), "street": Z._t(d, "street"), "zipCode": Z._t(d, "zipCode"), "city": Z._t(d, "city")})
    return [a for a in out if a["recipientId"] >= 1 and a["deliveryPlaceId"] >= 1]


def _wroclaw(a):
    return Z._norm(a["name"]) == "latex serwis wroclaw"


def _opole(a):
    return "krapkowicka 18" in Z._norm(a["street"])


def adresy(cfg, oddzialy=None):
    """Miejsca dostawy z konta xPartner zalogowanego; tylko adres oddziału (decyzja właściciela):
    Wrocław = LATEX SERWIS WROCLAW, Opole = Krapkowicka 18a; inne adresy – jako jednorazowe."""
    lst = czytaj_adresy(Z.api_xml(cfg, "getDeliveryData"))
    od = " ".join(oddzialy or []).lower()
    reguly = ([_wroclaw] if "wroc" in od or not od else []) + ([_opole] if "opole" in od or not od else [])
    out = [a for a in lst if any(r(a) for r in reguly)]
    if not out:
        raise Blad("Brak adresu dostawy Twojego oddziału na koncie xPartner – zamawianie wstrzymane, zgłoś administratorowi.")
    return out


# ---------------------------------------------------------------- odświeżenie cen i stanów (getProduct)
def odswiez(cfg, pozycje, get_product):
    """[{id, ilosc}] -> aktualne dane z xPartner (cena zakupu, stan, magazyny); ok=False gdy za mało lub brak."""
    def jeden(x):
        pid, il = int(x["id"]), int(x.get("ilosc") or 0)
        try:
            p = get_product(cfg, pid)
        except Exception as e:
            return {"id": pid, "ilosc": il, "ok": False, "blad": "Brak odpowiedzi xPartner (%s)" % e.__class__.__name__}
        if not p or float(p.get("netto") or 0) <= 0:
            return {"id": pid, "ilosc": il, "ok": False, "blad": "Opona niedostępna do zamówienia w xPartner"}
        stan = int(p.get("ilosc") or 0)
        mag = {k: v for k, v in (p.get("magazyny") or {}).items() if v}
        return {"id": pid, "ilosc": il, "nazwa": p.get("nazwa", ""), "netto": round(float(p["netto"]), 2),
                "brutto": round(float(p.get("brutto_zak") or p["netto"] * 1.23), 2), "netto_kat": round(float(p.get("netto_kat") or 0), 2),
                "stan": stan, "magazyny": mag, "ok": 1 <= il <= stan and il <= MAX_SZT,
                "blad": "Maks. %d szt. jednej opony" % MAX_SZT if il > MAX_SZT else ("" if il <= stan else "W xPartner jest tylko %d szt." % stan)}
    with ThreadPoolExecutor(6) as ex:
        return list(ex.map(jeden, pozycje))


# ---------------------------------------------------------------- zamówienie
def _el(tag, val):
    v = str(val).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return "<%s>%s</%s>" % (tag, v, tag)


def sprawdz_adres(a):
    out = {}
    for k, (mn, mx) in LIMITY_ADRESU.items():
        v = re.sub(r"\s+", " ", str(a.get(k) or "")).strip()
        if k == "country":
            v = (v or "PL").upper()
        if k == "zipCode":   # format z przykładu dokumentacji: same cyfry (64100)
            v = re.sub(r"\D", "", v)
            if len(v) != 5:
                raise Blad("Adres jednorazowy: kod pocztowy musi mieć 5 cyfr (np. 50-425).")
        if not mn <= len(v) <= mx:
            nazwy = {"name": "Nazwa", "street": "Ulica i numer", "zipCode": "Kod pocztowy", "city": "Miasto", "country": "Kraj",
                     "vatin": "NIP", "email": "E-mail", "phone": "Telefon", "receivingPerson": "Osoba odbierająca"}
            raise Blad("Adres jednorazowy: „%s” %s." % (nazwy[k], "jest wymagane" if not v else "jest za długie (maks. %d znaków)" % mx))
        out[k] = v
    return out


def order_xml(d):
    """Dane z koszyka -> XML metody order (kolejność i nazwy jak w przykładzie dokumentacji)."""
    rid, did = int(d.get("recipientId") or 0), int(d.get("deliveryPlaceId") or 0)
    if rid < 1 or did < 1:
        raise Blad("Wybierz adres dostawy.")
    poz = [(int(p["id"]), int(p["ilosc"])) for p in d.get("pozycje") or []]
    if not poz or any(pid < 1 or not 1 <= il <= MAX_SZT for pid, il in poz):
        raise Blad("Koszyk jest pusty albo ma złą ilość (1–%d szt. jednej opony)." % MAX_SZT)
    comment = re.sub(r"\s+", " ", str(d.get("uwagi") or "")).strip()
    if len(comment) > 255:
        raise Blad("Uwagi są za długie (maks. 255 znaków).")
    x = ['<?xml version="1.0" encoding="UTF-8"?>', "<order>", _el("recipientId", rid), _el("deliveryPlaceId", did),
         _el("document", DOKUMENT), _el("payment", PLATNOSC), _el("comment", comment),
         _el("extInvoiceDescription", ascii_xp(d.get("opis"), 100)), _el("extOrderNumber", ascii_xp(d.get("numer"), 35))]
    if d.get("nowy_adres"):
        a = sprawdz_adres(d["nowy_adres"])
        x.append("<newDeliveryPlace>" + _el("recipientId", rid) + "".join(_el(k, a[k]) for k in LIMITY_ADRESU) + "</newDeliveryPlace>")
    x.append("<products>" + "".join("<product>%s%s</product>" % (_el("productId", pid), _el("quantity", il)) for pid, il in poz) + "</products>")
    x.append("</order>")
    return "".join(x)


def czytaj_wynik(dane):
    try:
        root = ET.fromstring(dane)
    except ET.ParseError:
        raise Blad("Nieprawidłowa odpowiedź xPartner – sprawdź w xPartner, czy zamówienie powstało, zanim zamówisz ponownie.")
    ok = (Z._t(root, "success") or Z._t(root, "orderResult")).lower() == "true"
    bledy = [(e.text or "").strip() for e in Z._wszystkie(Z._dz(root, "errors"), "error") if (e.text or "").strip()]
    zam = [{"nr": Z._t(o, "orderXP") or Z._t(o, "orderXp") or Z._t(o, "orderNo"), "magazyn": Z._t(o, "warehouseName"),
            "nr_zew": Z._t(o, "extOrderNumber")} for o in Z._wszystkie(Z._dz(root, "orders"), "order")]
    if zam:   # także częściowy sukces (podział na magazyny) – numery zawsze pokazujemy, błędy jako ostrzeżenie
        return zam, ([] if ok else ["xPartner zgłosił problem – sprawdź zamówienia w xPartner."]) + bledy
    raise Blad("xPartner nie przyjął zamówienia: " + ("; ".join(bledy) or "brak szczegółów")
               + ". Zanim zamówisz ponownie, sprawdź w xPartner, czy zamówienie nie powstało.")


def wyslij(cfg, xml_txt, timeout=60):
    from oferty import xp
    try:   # przez pośrednika na serwerze: sprawdza prawo do zamawiania i zapisuje zamówienie w dzienniku
        return xp.zapytanie(cfg, "order", body=xml_txt, timeout=timeout)
    except xp.BrakOdpowiedzi as e:
        raise Blad("%s – sprawdź w xPartner („📦 Zamówienia”), czy zamówienie powstało, zanim zamówisz ponownie." % e)
    except xp.Blad as e:   # odmowa przed wysłaniem do xPartner (uprawnienia, brak loginu) – zamówienie nie powstało
        raise Blad(str(e))
