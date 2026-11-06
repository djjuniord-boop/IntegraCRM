"""ZAMÓWIENIA xPartner – podgląd zamówień otwartych i faktur z konta xPartner pracownika (tylko odczyt).

Metody API (docs.xpartner.net.pl): getOpenOrders, getInvoices (od 2026-02-01), getInvoice (KSeF FA(3)).
Ten sam kod w aplikacji Android: mobile/www/zamowienia.js (test zgodności pilnuje, że liczą to samo).
Listy przewozowe (wysłane opony) wymagają tokenu głównego konta – na razie nie ma (zob. README).
"""
import datetime
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

API_URL = "https://xpartner.net.pl/index.php"
STATUSY = {1: "W kolejce", 2: "Przesłane", 3: "Oczekujące", 4: "Wczytane", 5: "Błąd", 6: "Zrealizowane"}
FAKTURA_NR = re.compile(r"^[A-Z]{2}\d{7}/\d{2}$")
FAKTURY_OD = "2026-02-01"          # xPartner: faktury najwcześniej od tej daty
FORMY_PLATNOSCI = {"1": "gotówka", "2": "karta", "3": "bon", "4": "czek", "5": "kredyt", "6": "przelew", "7": "mobilna"}


class Blad(Exception):
    pass


def _lok(tag):
    """Nazwa elementu bez przestrzeni nazw (KSeF ma xmlns)."""
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _dz(el, nazwa):
    for c in list(el) if el is not None else []:
        if _lok(c.tag) == nazwa:
            return c
    return None


def _t(el, nazwa, dom=""):
    c = _dz(el, nazwa)
    return (c.text or "").strip() if c is not None and c.text else dom


def _gr(x):
    """Zaokrąglenie do groszy „połówka w górę” – tak samo jak Math w zamowienia.js."""
    return int(x * 100 + (0.5 if x >= 0 else -0.5)) / 100


def _f(v):
    try:
        return _gr(float(str(v).replace(",", ".")))
    except (TypeError, ValueError):
        return 0.0


def _i(v):
    try:
        return int(float(str(v).replace(",", ".")))
    except (TypeError, ValueError):
        return 0


def _wszystkie(el, nazwa):
    return [c for c in el.iter() if _lok(c.tag) == nazwa] if el is not None else []


def api_xml(cfg, metoda, **params):
    if not cfg.get("login") or not cfg.get("password"):
        raise Blad("Twoje konto nie ma jeszcze loginu API xPartner – poproś administratora (UŻYTKOWNICY → konto → xPartner).")
    q = {"a": "b2b_xmlApi", "login": cfg["login"], "pass": cfg["password"], "m": metoda}
    q.update({k: v for k, v in params.items() if v not in (None, "")})
    req = urllib.request.Request(API_URL + "?" + urllib.parse.urlencode(q), headers={"User-Agent": "PanelLatexSerwis-Oferty"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            dane = r.read()
    except Exception as e:
        raise Blad("Brak połączenia z xPartner: %s" % e.__class__.__name__)
    return parsuj(dane)


def parsuj(dane):
    try:
        root = ET.fromstring(dane)
    except ET.ParseError:
        raise Blad("Nieprawidłowa odpowiedź xPartner (nie XML) – sprawdź login/hasło.")
    ok = (_t(root, "success") or _t(root, "productResult")).lower()
    bledy = [(e.text or "").strip() for e in _wszystkie(_dz(root, "errors"), "error") if (e.text or "").strip()]
    if ok == "false" or (bledy and ok != "true"):
        raise Blad("xPartner: " + ("; ".join(bledy) or "operacja nieudana"))
    return root


def _adres(el):
    if el is None:
        return {}
    return {k: _t(el, k) for k in ("name", "street", "zipCode", "city", "receivingPerson") if _t(el, k)}


def czytaj_zamowienia(root):
    out = [_zamowienie(o) for o in _wszystkie(_dz(root, "orders"), "order")]
    out.sort(key=lambda z: z["data"], reverse=True)
    return out


def _zamowienie(o):
    st = _i(_t(o, "status"))
    poz = []
    for p in _wszystkie(_dz(o, "products"), "product"):
        poz.append({"lp": _i(_t(p, "lineNumber")), "id": _i(_t(p, "productId")), "nazwa": _t(p, "productName"),
            "jedn": _t(p, "unit") or "szt", "ilosc": _i(_t(p, "quantity")), "zostalo": _i(_t(p, "quantityRemaining")),
            "dostepne": _i(_t(p, "quantityAvailable")), "cena": _f(_t(p, "unitNetPrice"))})
    return {"nr": _t(o, "orderXp"), "nr_erp": _t(o, "orderErp"), "nr_zew": _t(o, "extOrderNumber"),
                "waluta": (_t(o, "currency") or "pln").upper(), "netto": _f(_t(o, "totalNetPrice")),
                "data": _t(o, "createdAt"), "kto": _t(o, "createdBy"), "wazne_do": _t(o, "expirationDate"),
                "status": st, "status_txt": STATUSY.get(st, str(st or "?")), "magazyn": _t(o, "warehouseName"),
                "komentarz": _t(o, "comment"), "odbiorca": _adres(_dz(o, "recipient")), "dostawa": _adres(_dz(o, "deliveryPlace")),
                "pozycje": poz, "szt": sum(x["ilosc"] for x in poz), "do_wydania": sum(x["zostalo"] for x in poz)}


def czytaj_faktury(root):
    out = [{"nr": _t(f, "documentNumber"), "data": _t(f, "documentDate"), "platnosc": _t(f, "paymentMethod"),
            "magazyn": _t(f, "warehouse")} for f in _wszystkie(_dz(root, "invoices"), "invoice")]
    out.sort(key=lambda f: (f["data"], f["nr"]), reverse=True)
    return out


def czytaj_fakture(root):
    """Faktura KSeF FA(3) -> numer, daty, kwoty, pozycje (tylko to, co potrzebne do podglądu)."""
    fak = next((c for c in root.iter() if _lok(c.tag) == "Faktura"), None)
    if fak is None:
        raise Blad("Brak faktury w odpowiedzi xPartner.")
    fa = _dz(fak, "Fa")
    netto = _gr(sum(_f(c.text) for c in list(fa) if re.match(r"P_13_\d+$", _lok(c.tag))))
    vat = _gr(sum(_f(c.text) for c in list(fa) if re.match(r"P_14_\d+$", _lok(c.tag))))
    plat = _dz(fa, "Platnosc")
    zam = next((c for c in fa.iter() if _lok(c.tag) == "NrZamowienia"), None)
    poz = []
    for w in [c for c in list(fa) if _lok(c.tag) == "FaWiersz"]:
        ilosc, cena, wart = _f(_t(w, "P_8B")), _f(_t(w, "P_9A")), _f(_t(w, "P_11"))
        poz.append({"lp": _i(_t(w, "NrWierszaFa")), "nazwa": _t(w, "P_7"), "indeks": _t(w, "Indeks"), "jedn": _t(w, "P_8A"),
                    "ilosc": ilosc, "cena": cena, "wartosc": wart, "vat": _t(w, "P_12")})
    return {"nr": _t(fa, "P_2"), "data": _t(fa, "P_1"), "wz": _t(fa, "WZ"), "ksef": _t(_dz(root, "invoice"), "KsefNumber"),
            "netto": netto, "vat": vat, "brutto": _f(_t(fa, "P_15")), "waluta": _t(fa, "KodWaluty") or "PLN",
            "termin": _t(_dz(plat, "TerminPlatnosci"), "Termin") if plat is not None else "",
            "forma": FORMY_PLATNOSCI.get(_t(plat, "FormaPlatnosci"), _t(plat, "FormaPlatnosci")) if plat is not None else "",
            "zamowienie": (zam.text or "").strip() if zam is not None and zam.text else "", "pozycje": poz}


ZAM_XP = re.compile(r"^\d{11}$")
ZAM_ERP = re.compile(r"^\d{9}/\d{2}$")
_PAMIEC = {}   # (login, faktura) -> numery zamówień; (login, zamówienie) -> zamówienie zrealizowane (już się nie zmienia)


def numery_zamowien(root):
    """Numery zamówień z faktury KSeF (bywa kilka; tylko poprawne numery xPartner/ERP)."""
    out = []
    for c in root.iter():
        if _lok(c.tag) == "NrZamowienia" and c.text:
            n = c.text.strip()
            if (ZAM_XP.match(n) or ZAM_ERP.match(n)) and n not in out:
                out.append(n)
    return out


def czytaj_zamowienie(root):
    o = _dz(root, "order")
    if o is None:
        raise Blad("Brak zamówienia w odpowiedzi xPartner.")
    return _zamowienie(o)


def _pozycje_faktury(root):
    """Pozycje faktury w kształcie pozycji zamówienia (do zamówień zamkniętych, które przychodzą bez pozycji)."""
    try:
        f = czytaj_fakture(root)
    except Blad:
        return []
    return [{"lp": p["lp"], "id": _i(p["indeks"]), "nazwa": p["nazwa"], "jedn": p["jedn"] or "szt", "ilosc": _i(p["ilosc"]),
             "zostalo": 0, "dostepne": 0, "cena": p["cena"]} for p in f["pozycje"]]


def zamkniete(cfg, od, do, rownolegle=6):
    """Zamówienia z faktur z okresu (xPartner nie ma listy zamówień zamkniętych): faktura -> numer -> getOrder."""
    import concurrent.futures as cf
    login = cfg.get("login", "")
    fak = czytaj_faktury(api_xml(cfg, "getInvoices", documentDateFrom=od, documentDateTo=do))

    def nr_z_faktury(f):
        k = (login, "F", f["nr"])
        if k not in _PAMIEC:
            if FAKTURA_NR.match(f["nr"]):
                r = api_xml(cfg, "getInvoice", invoiceNumber=f["nr"])
                _PAMIEC[k] = (numery_zamowien(r), _pozycje_faktury(r))
            else:
                _PAMIEC[k] = ([], [])
        return f, _PAMIEC[k]

    def zam(n):
        k = (login, "Z", n)
        if k in _PAMIEC:
            return _PAMIEC[k]
        z = czytaj_zamowienie(api_xml(cfg, "getOrder", **({"orderXp": n} if ZAM_XP.match(n) else {"orderErp": n})))
        if z["status"] == 6:
            _PAMIEC[k] = z
        return z

    faktury_zam, poz_faktur, ile_zam, bledy = {}, {}, {}, 0
    with cf.ThreadPoolExecutor(rownolegle) as ex:
        for fu in [ex.submit(nr_z_faktury, f) for f in fak]:
            try:
                f, (nry, poz) = fu.result()
            except Blad:
                bledy += 1
                continue
            poz_faktur[f["nr"]], ile_zam[f["nr"]] = poz, len(nry)
            for n in nry:
                faktury_zam.setdefault(n, []).append(f["nr"])
        wyn = {}
        for n, fu in [(n, ex.submit(zam, n)) for n in faktury_zam]:
            try:
                wyn[n] = fu.result()
            except Blad:
                bledy += 1
    out, byly = [], set()
    for n, z in wyn.items():
        if z["nr"] in byly:
            continue
        byly.add(z["nr"])
        fk = sorted({x for m in (z["nr"], z["nr_erp"], n) for x in faktury_zam.get(m, [])})
        z = dict(z, faktury=fk)
        if not z["pozycje"]:   # xPartner nie podaje pozycji zamówień zamkniętych – bierzemy je z faktury
            z["pozycje"] = [p for x in fk for p in poz_faktur.get(x, [])]
            z["szt"] = sum(p["ilosc"] for p in z["pozycje"])
            z["poz_z_faktury"] = "wspolna" if any(ile_zam.get(x, 0) > 1 for x in fk) else "tak"
        out.append(z)
    out.sort(key=lambda z: z["data"], reverse=True)
    return {"zamowienia": out, "faktur": len(fak), "bledy": bledy}


def okres(od, do, dzis=None):
    """Zakres dat faktur: domyślnie ostatnie 30 dni, nie wcześniej niż FAKTURY_OD, maks. 1 rok."""
    dzis = dzis or datetime.date.today()
    try:
        d2 = datetime.date.fromisoformat(do) if do else dzis
    except ValueError:
        raise Blad("Zła data „do” (RRRR-MM-DD).")
    try:
        d1 = datetime.date.fromisoformat(od) if od else d2 - datetime.timedelta(days=30)
    except ValueError:
        raise Blad("Zła data „od” (RRRR-MM-DD).")
    d1 = max(d1, datetime.date.fromisoformat(FAKTURY_OD), d2 - datetime.timedelta(days=366))
    if d1 > d2:
        raise Blad("Data „od” jest późniejsza niż „do”.")
    return d1.isoformat(), d2.isoformat()


def handle(route, q, cfg, admin=False):
    """/api/zamowienia, /api/faktury?od=&do=, /api/faktura?nr= -> (kod, odpowiedź)."""
    try:
        if route == "/api/zamowienia":
            z = czytaj_zamowienia(api_xml(cfg, "getOpenOrders"))
            return 200, {"zamowienia": z, "czas": datetime.datetime.now().strftime("%H:%M")}
        if route in ("/api/faktury", "/api/faktura") and not admin:
            return 403, {"error": "Faktury widzi administrator."}
        if route == "/api/faktury":
            od, do = okres(q.get("od", ""), q.get("do", ""))
            return 200, {"faktury": czytaj_faktury(api_xml(cfg, "getInvoices", documentDateFrom=od, documentDateTo=do)), "od": od, "do": do}
        if route == "/api/zamkniete":
            od, do = okres(q.get("od", ""), q.get("do", ""))
            w = zamkniete(cfg, od, do)
            w.update(od=od, do=do, czas=datetime.datetime.now().strftime("%H:%M"))
            return 200, w
        if route == "/api/faktura":
            nr = (q.get("nr") or "").strip().upper()
            if not FAKTURA_NR.match(nr):
                return 400, {"error": "Zły numer faktury."}
            return 200, czytaj_fakture(api_xml(cfg, "getInvoice", invoiceNumber=nr))
    except Blad as e:
        return 502, {"error": str(e)}
    return 404, {"error": "Nie znaleziono"}
