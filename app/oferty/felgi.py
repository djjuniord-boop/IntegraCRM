"""FELGI z kopii pliku ofertowego xPartner (asortyment FELGA): rozpoznanie parametrów, szybkie polecenie, wyniki.
Oferta na same felgi albo komplet (felgi + opony z oferty opon + czujniki TPMS + montaż + depozyt) – decyzje
właściciela 2026-11-26 (DECYZJE.md). Tylko biblioteka standardowa (re, math)."""
import math
import re

from oferty import tpms as TP

ASORT = "FELGA"
# nazwa xPartner, np. „OBRĘCZ PEUGEOT 6.5X16 4X108 ET32/65.1 STRUKTURA”, „FELGA ALU 7X17 5X114.3 ET35/66”
ROZM_RE = re.compile(r"(\d{1,2}(?:[.,]\d{1,2})?)\s*[JX]\s*(\d{2})\b", re.I)
PCD_RE = re.compile(r"\b(\d{1,2})\s*[X×]\s*(\d{2,3}(?:[.,]\d{1,2})?)\b", re.I)
ET_RE = re.compile(r"\bET\s*(-?\d{1,3})(?:\s*/\s*(\d{2,3}(?:[.,]\d{1,2})?))?", re.I)


def _f(x):
    m = re.search(r"-?\d+(?:\.\d+)?", str(x if x is not None else "").replace(",", "."))   # „17"”, „57,1”
    return float(m.group()) if m else None


def _liczba(x):
    """6.5 -> '6.5', 7.0 -> '7', 114.30 -> '114.3' (do porównań i wyświetlania)."""
    v = _f(x)
    return "" if v is None else ("%g" % v)


def _attr(a, *klucze):
    for k in klucze:
        v = (a.get(k) or "").strip()
        if v:
            return v
    return ""


def parametry(p):
    """Szerokość, średnica, rozstaw śrub, ET, otwór centralny – z cech pliku, a gdy brak – z nazwy."""
    a = p.get("attrs") or {}
    n = (p.get("nazwa") or "").upper()
    sz, sr = _liczba(_attr(a, "Szerokość")), _liczba(_attr(a, "Średnica"))
    m = ROZM_RE.search(n)
    if m and (not sz or not sr):
        sz, sr = sz or _liczba(m.group(1)), sr or _liczba(m.group(2))
    pcd = _attr(a, "Rozstaw śrub").upper().replace(",", ".").replace(" ", "")
    mp = re.match(r"(\d{1,2})X(\d{2,3}(?:\.\d+)?)$", pcd)
    if not mp:
        mp = PCD_RE.search(ROZM_RE.sub(" ", n))
    pcd = "%sx%s" % (mp.group(1), _liczba(mp.group(2))) if mp else ""
    et, cb = _liczba(_attr(a, "ET", "Osadzenie ET")), _liczba(_attr(a, "Otwór centralny"))
    me = ET_RE.search(n)
    if me:
        et = et or _liczba(me.group(1))
        cb = cb or (_liczba(me.group(2)) if me.group(2) else "")
    return {"szer": sz, "sred": sr, "pcd": pcd, "et": et, "otwor": cb}


def rodzaj(p):
    a = p.get("attrs") or {}
    t = (_attr(a, "Typ") + " " + (p.get("nazwa") or "")).upper()
    if re.search(r"STAL|OBRĘCZ|OBRECZ|STEEL", t) and "ALU" not in t:
        return "stalowa"
    if "ALU" in t or "STOP" in t:
        return "aluminiowa"
    return ""


def info(p, marza_proc=13.0, vat_proc=23.0, cena=None):
    """Produkt z kopii pliku -> kafelek wyników. Cena oferty = zakup netto + marża felg + VAT, w górę do pełnych zł;
    cena(netto) – sposób liczenia z Ustawień → Felgi (marża % albo progi kwotowe, zaokrąglenie)."""
    a = p.get("attrs") or {}
    n = p.get("nazwa") or ""
    netto = float(p.get("netto") or 0)
    if cena:
        cena = cena(netto) if netto > 0 else 0.0
    else:
        cena = float(math.ceil(round(netto * (1 + marza_proc / 100) * (1 + vat_proc / 100), 2) - 1e-9)) if netto > 0 else 0.0
    oe = re.search(r"\b(\d{7,12})\b", n)
    return dict(parametry(p), id=int(p["id"]), nazwa=n, producent=_attr(a, "Producent") or "–", model=_attr(a, "Model"),
                przeznaczenie=_attr(a, "Przeznaczenie"), rodzaj=rodzaj(p), marki=TP.marki_z_nazwy(n + " " + _attr(a, "Model")),
                demo=bool(re.search(r"\bDEMO\b", n.upper())), kod=(p.get("kod") or "").strip(), oe=oe.group(1) if oe else "",
                stan=int(p.get("ilosc") or 0), magazyny=p.get("magazyny") or {}, netto=netto,
                brutto_zak=float(p.get("brutto_zak") or 0), cena=cena, foto=p.get("foto") or "")


def zapytanie(txt):
    """Szybkie polecenie felg -> kryteria. Np. „5x108 R16 ET32 peugeot 4 szt”, „alu 7x17 5x114.3”, „190362”."""
    t = " " + (txt or "").lower().replace(",", ".") + " "
    q = {"ilosc": 4, "pcd": "", "sred": "", "szer": "", "et": "", "otwor": "", "rodzaj": "", "marki": [], "slowa": [], "demo": "", "indeks": 0}
    m = re.search(r"(?:^|\s)(\d{1,3})\s*(?:szt\.?|sztuk|kpl)(?=\s|$)", t)
    if m:
        q["ilosc"] = max(1, min(40, int(m.group(1))))
        t = t[:m.start()] + " " + t[m.end():]
    m = re.search(r"(?:^|\s)et\s*(-?\d{1,3})(?:\s*/\s*(\d{2,3}(?:\.\d{1,2})?))?(?=\s|$)", t)
    if m:
        q["et"] = m.group(1)
        if m.group(2):
            q["otwor"] = _liczba(m.group(2))
        t = t[:m.start()] + " " + t[m.end():]
    m = re.search(r"(?:^|\s)(\d{1,2}(?:\.\d{1,2})?)\s*[jx]\s*(?:r\s*)?(\d{2})(?:\"|\s|$)", t)   # 7x17, 6.5j16
    if m and 4 <= (_f(m.group(1)) or 0) <= 13 and 12 <= int(m.group(2)) <= 24:
        q["szer"], q["sred"] = _liczba(m.group(1)), m.group(2)
        t = t[:m.start()] + " " + t[m.end():]
    m = re.search(r"(?:^|\s)([3-8])\s*x\s*(\d{2,3}(?:\.\d{1,2})?)(?=\s|$)", t)   # rozstaw 5x112, 4x108
    if m and 90 <= (_f(m.group(2)) or 0) <= 210:
        q["pcd"] = "%sx%s" % (m.group(1), _liczba(m.group(2)))
        t = t[:m.start()] + " " + t[m.end():]
    m = re.search(r"(?:^|\s)(?:r\s*|fi\s*)?(1[2-9]|2[0-4])(?:\"|''|cal\w*)?(?=\s|$)", t)
    if m and not q["sred"]:
        q["sred"] = m.group(1)
        t = t[:m.start()] + " " + t[m.end():]
    m = re.search(r"(?:^|\s)(?:otw[oó]r\s*|cb\s*|fi\s*)?(\d{2,3}\.\d{1,2})(?=\s|$)", t)
    if m and 50 <= (_f(m.group(1)) or 0) <= 175:
        q["otwor"] = _liczba(m.group(1))
        t = t[:m.start()] + " " + t[m.end():]
    if re.search(r"stal|obr[eę]cz", t):
        q["rodzaj"] = "stalowa"
    elif re.search(r"\balu|aluminiow|stop", t):
        q["rodzaj"] = "aluminiowa"
    if re.search(r"bez\s+demo", t):
        q["demo"] = "bez"
    elif re.search(r"\bdemo\b|demont", t):
        q["demo"] = "tylko"
    m = re.search(r"(?:^|\s)(\d{5,7})(?=\s|$)", t)
    if m and not (q["pcd"] or q["sred"]):
        q["indeks"] = int(m.group(1))
    q["marki"] = TP.marki_z_nazwy(t)
    T = TP._up(t)
    for mk in q["marki"]:
        for w in TP.MARKI_AUT[mk]:
            T = re.sub(r"(?<![A-Z0-9])" + re.escape(TP._up(w)) + r"(?![A-Z0-9])", " ", T)
    pomin = {"FELGA", "FELGI", "FELG", "OBRECZ", "OBRĘCZ", "OBRECZE", "OBRĘCZE", "ALU", "ALUMINIOWE", "ALUMINIOWA", "STALOWE",
             "STALOWA", "STALOWKI", "STALÓWKI", "DEMO", "BEZ", "DO", "POD", "NA", "I", "Z", "W", "KPL", "SZT", "R", "ET", "CB", "FI"}
    q["slowa"] = [w for w in re.findall(r"[A-Z0-9ĄĆĘŁŃÓŚŹŻ]{3,}", T) if w not in pomin and not w.isdigit()
                  and not re.match(r"(STAL|ALU|OBR[EĘ]CZ|FELG|KOŁ|KOL)", w)]   # „stal”, „alufelgi”, „stalówki” = rodzaj, nie słowo z nazwy
    return q


def pasuje(f, q):
    if q.get("indeks"):
        return f["id"] == q["indeks"] or f["kod"] == str(q["indeks"])
    if q.get("pcd") and f["pcd"] != q["pcd"]:
        return False
    for k in ("sred", "szer", "otwor"):
        if q.get(k) and _liczba(f[k]) != _liczba(q[k]):
            return False
    if q.get("et") and f["et"] != _liczba(q["et"]):
        return False
    if q.get("rodzaj") and f["rodzaj"] != q["rodzaj"]:
        return False
    if q.get("demo") == "bez" and f["demo"] or q.get("demo") == "tylko" and not f["demo"]:
        return False
    if q.get("marki") and not (set(f["marki"]) & TP.rodzina(q["marki"])):
        return False
    tekst = TP._k(" ".join([f["nazwa"], f["producent"], f["model"], f["kod"]]))
    return all(TP._k(w) in tekst for w in q.get("slowa") or [])


def szukaj(items, txt, marza_proc=13.0, vat_proc=23.0, cena=None):
    """Lista felg dla szybkiego polecenia (najpierw dostępne w potrzebnej ilości, potem po cenie)."""
    q = zapytanie(txt)
    lista = [info(p, marza_proc, vat_proc, cena) for p in items]
    lista = [f for f in lista if f["cena"] > 0 and pasuje(f, q)]
    # wpisana marka auta najpierw (VW), dopiero potem pokrewne z tej samej grupy (Audi, Skoda, Seat – ten sam rozstaw)
    lista.sort(key=lambda f: (bool(q["marki"]) and not (set(f["marki"]) & set(q["marki"])), f["stan"] < q["ilosc"], f["cena"], f["nazwa"]))
    return lista[:3000], q   # cała lista (kafelki pokazują się porcjami); filtry producentów z pełnej listy


# ---------- oferta (same felgi albo komplet) ----------
def oferta(cfg, felga, il, opona=None, il_op=0, czujnik=None, il_cz=0, montaz=False, typ="osobowy", depozyt="",
           cena_czujnika=0.0, cena_montazu=None):
    """Pozycje jednej propozycji (ceny brutto). felga – z info() (cena już po rabacie / ręczna); opona – z oferty opon
    (nazwa, cena_brutto); il_cz – koła z czujnikami TPMS: obsługa TPMS (cennik usług) i – gdy wybrany czujnik – czujniki;
    montaz – wymiana za koło: cena_montazu albo cennik usług (średnica felgi, typ auta); depozyt – '' / 'opony' / 'kola'.
    Każda pozycja ma rodzaj „k”: felga / opona / czujnik / tpms / montaz / przech."""
    poz = []
    il = max(1, min(40, int(il or 4)))
    poz.append({"k": "felga", "nazwa": "Felga %s" % felga["nazwa"], "opis": opis_felgi(felga), "q": il, "c": felga["cena"], "id": felga["id"],
                "kod": felga.get("kod") or "", "foto": felga.get("foto") or ""})
    if opona and il_op:
        poz.append({"k": "opona", "nazwa": "Opona %s" % opona["nazwa"], "opis": "", "q": int(il_op), "c": float(opona["cena_brutto"]), "id": opona["id"],
                    "kod": str(opona.get("kod") or "")})
    il_cz = max(0, min(40, int(il_cz or 0)))
    if czujnik and il_cz:
        poz.append({"k": "czujnik", "nazwa": "Czujnik ciśnienia TPMS %s" % czujnik["nazwa"], "opis": "", "q": il_cz, "c": float(cena_czujnika),
                    "id": czujnik["id"], "kod": str(czujnik.get("kod") or "")})
    if il_cz and float(cfg.get("tpms_cena") or 0) > 0:
        poz.append({"k": "tpms", "nazwa": "Obsługa czujnika ciśnienia TPMS przy montażu", "opis": "", "q": il_cz, "c": float(cfg["tpms_cena"])})
    sr = sred(felga)
    if montaz:
        if cena_montazu is None:
            cen = cfg["wymiana_suv"] if typ == "suv" else cfg["wymiana_dost"] if typ == "dostawczy" else cfg["wymiana_kolo"]
            cena_montazu = float(cen.get(sr, 0) or 0)
        poz.append({"k": "montaz", "nazwa": "Montaż / wymiana kół (R%s)" % sr, "opis": "" if cena_montazu else "brak ceny w cenniku usług",
                    "q": il, "c": float(cena_montazu)})
    if depozyt in ("opony", "kola"):
        big = sr.isdigit() and int(sr) > 19
        poz.append({"k": "przech", "nazwa": "Przechowalnia %s – sezon" % ("opon" if depozyt == "opony" else "kół z felgami"), "opis": "",
                    "q": 1, "c": float(cfg["przech_%s_%s" % (depozyt, "pow19" if big else "do19")])})
    for p in poz:
        p["w"] = round(p["q"] * p["c"], 2)
    return poz, round(sum(p["w"] for p in poz), 2)


def sred(f):
    """Średnica felgi jako tekst bez części ułamkowej („17.0” -> „17”)."""
    return (f.get("sred") or "").split(".")[0]


def sred_opony(opona):
    """Średnica opony z rozmiaru albo nazwy: „225/40 R18”, „225/40ZR18”, „215/65 R16C” -> „18”, „16”."""
    for t in ((opona or {}).get("rozmiar") or "", (opona or {}).get("nazwa") or ""):
        m = re.search(r"\d{3}/\d{2}\s*Z?R\s*F?\s*(\d{2})", t.upper()) or re.search(r"\bR\s*(\d{2})C?\b", t.upper())
        if m:
            return m.group(1)
    return ""


def opis_felgi(f):
    cz = [f.get("rodzaj") or "", ("%sx%s\"" % (f["szer"], f["sred"])) if f.get("szer") and f.get("sred") else "",
          f.get("pcd") or "", ("ET%s" % f["et"]) if f.get("et") else "", ("otwór %s" % f["otwor"]) if f.get("otwor") else "",
          ("OE %s" % f["oe"]) if f.get("oe") else ""]
    return " · ".join(x for x in cz if x)
