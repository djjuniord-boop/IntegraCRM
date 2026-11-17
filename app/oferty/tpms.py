"""Czujniki TPMS z kopii pliku ofertowego xPartner: rozpoznanie rodzaju i marek aut z nazwy, szybkie polecenie, wyniki.
Samo wyszukiwanie i koszyk – bez ofert (decyzja właściciela 2026-11-17). Tylko biblioteka standardowa (re)."""
import re

# marki aut w nazwach czujników (nazwa w wynikach -> warianty zapisu)
MARKI_AUT = {
    "Alfa Romeo": ["ALFA"], "Audi": ["AUDI"], "BMW": ["BMW"], "Chevrolet": ["CHEVROLET"], "Chrysler": ["CHRYSLER"],
    "Citroën": ["CITROEN", "CITROËN"], "Dacia": ["DACIA"], "Dodge": ["DODGE"], "Fiat": ["FIAT"], "Ford": ["FORD"],
    "Honda": ["HONDA"], "Hyundai": ["HYUNDAI"], "Infiniti": ["INFINITI"], "Jaguar": ["JAGUAR"], "Jeep": ["JEEP"],
    "KIA": ["KIA"], "Land Rover": ["LAND ROVER", "LANDROVER", "RANGE ROVER"], "Lexus": ["LEXUS"], "Mazda": ["MAZDA"],
    "Mercedes": ["MERCEDES", "MB"], "Mini": ["MINI"], "Mitsubishi": ["MITSUBISHI"], "Nissan": ["NISSAN"], "Opel": ["OPEL"],
    "Peugeot": ["PEUGEOT"], "Porsche": ["PORSCHE"], "Renault": ["RENAULT"], "Seat": ["SEAT", "CUPRA"], "Skoda": ["SKODA", "ŠKODA"],
    "Subaru": ["SUBARU"], "Suzuki": ["SUZUKI"], "Tesla": ["TESLA"], "Toyota": ["TOYOTA"], "Volvo": ["VOLVO"],
    "VW": ["VW", "VOLKSWAGEN"],
}
# rodzina marek: czujnik „pod VW” pasuje zwykle też do Audi/Skody/Seata (pokazujemy w grupie „marka”)
ZAWORY = {"srebrny": "SREBRNY", "czarny": "CZARNY", "gumowy": "GUMOWY"}
AKCESORIA_SLOWA = ("ZESTAW", "ZAWÓR", "ZAWOR", "NAKRĘTKA", "NAKRETKA", "PROGRAMATOR", "MODUŁ", "MODUL", "NARZĘDZIE", "WENTYL", "USZCZELK")
RODZAJE = {"oe": "oryginał OE", "zam": "zamiennik pod markę", "uni": "uniwersalny", "nar": "akcesoria / narzędzia"}


def _k(x):
    """Do porównań: wielkie litery, same litery i cyfry (52933-D4100 == 52933D4100)."""
    return re.sub(r"[^A-Z0-9ĄĆĘŁŃÓŚŹŻ]", "", (x or "").upper())


def _slowa(nazwa):
    return re.findall(r"[A-Z0-9ĄĆĘŁŃÓŚŹŻË]+", (nazwa or "").upper())


def marki_z_nazwy(nazwa):
    n = " " + " ".join(_slowa(nazwa)) + " "
    return [m for m, warianty in MARKI_AUT.items() if any(" %s " % w in n or ("/%s" % w) in (nazwa or "").upper() for w in warianty)]


def rodzaj_z(p):
    n = (p.get("nazwa") or "").upper()
    a = p.get("attrs") or {}
    if "CZUJNIK" not in n or "NARZĘDZIA" in (a.get("Rodzaj") or "").upper() or any(s in n for s in ("PROGRAMATOR", "ZESTAW NAPRAWCZY")):
        return "nar"
    if re.search(r"\bUNI\b|UNIWERSAL|\bHYB|PROGRAMOW|MULTI|EZ-SENSOR|\bREDI\b", n):
        return "uni"
    if re.search(r"\bOEM?\b(?!-)", n) or (a.get("Producent") or "").upper() == "ORYGINAŁ":
        return "oe"
    return "zam"


def info(p):
    """Produkt z kopii pliku -> wiersz wyników TPMS."""
    a = p.get("attrs") or {}
    n = p.get("nazwa") or ""
    zaw = next((k for k, w in ZAWORY.items() if w in n.upper()), "")
    return {"id": int(p["id"]), "nazwa": n, "producent": (a.get("Producent") or "").strip() or "–", "rodzaj": rodzaj_z(p),
            "demo": bool(re.search(r"\bDEMO\b", n.upper())), "marki": marki_z_nazwy(n), "zawor": zaw,
            "stan": int(p.get("ilosc") or 0), "magazyny": p.get("magazyny") or {}, "netto": float(p.get("netto") or 0),
            "brutto_zak": float(p.get("brutto_zak") or 0), "netto_kat": float(p.get("netto_kat") or 0), "_k": _k(n)}


def zapytanie(txt, producenci=()):
    """Szybkie polecenie TPMS -> kryteria. Np. „kia sportage 4 szt”, „52933D4100”, „opel s016 bez demo”, „uniwersalny srebrny”."""
    t = (txt or "").lower()
    q = {"ilosc": 4, "rodzaje": [], "demo": "", "zawor": "", "producent": "", "marki": [], "slowa": [], "akcesoria": False}
    m = re.search(r"(?:^|\s)(\d{1,3})\s*(?:szt|sztuk|x\b)", t)
    if m:
        q["ilosc"] = max(1, min(200, int(m.group(1))))
        t = t[:m.start()] + " " + t[m.end():]
    if re.search(r"bez\s+demo", t):
        q["demo"] = "bez"
        t = re.sub(r"bez\s+demo", " ", t)
    elif re.search(r"\bdemo\b|demont", t):
        q["demo"] = "tylko"
    for wz, r in ((r"orygina|\boem?\b(?!-)", "oe"), (r"zamienn", "zam"), (r"uniwersal|programowal|\buni\b|hybryd|hybrid", "uni")):
        if re.search(wz, t):
            q["rodzaje"].append(r)
    for k in ZAWORY:
        if k in t:
            q["zawor"] = k
    T = t.upper()
    if any(s in T for s in AKCESORIA_SLOWA):
        q["akcesoria"] = True
    pk = {_k(x): x for x in producenci if x and x != "–"}
    for x in sorted(producenci, key=len, reverse=True):   # producent z kilku słów / z kreską („T-PRO”)
        if x and x != "–" and len(_k(x)) >= 3 and re.search(r"(?<![A-Z0-9])" + r"[\s\-]*".join(map(re.escape, _slowa(x))) + r"(?![A-Z0-9])", T):
            q["producent"] = x
            T = re.sub(r"(?<![A-Z0-9])" + r"[\s\-]*".join(map(re.escape, _slowa(x))) + r"(?![A-Z0-9])", " ", T)
            break
    for w in _slowa(T):
        if w in ("TPMS", "CZUJNIK", "CZUJNIKI", "CZUJNIKA", "SZT", "BEZ", "DEMO", "DO", "POD", "I", "Z", "W", "NA") or w in ZAWORY.values():
            continue
        if re.match(r"^(ORYGINA|OEM?$|ZAMIENN|UNIWERSAL|PROGRAMOWAL|UNI$|HYBRYD|SREBRN|CZARN|GUMOW)", w):
            continue
        marka = next((mk for mk, war in MARKI_AUT.items() if w in [x.replace(" ", "") for x in war]), None)
        if marka:
            if marka not in q["marki"]:
                q["marki"].append(marka)
            continue
        if _k(w) in pk and not q["producent"]:
            q["producent"] = pk[_k(w)]
            continue
        if len(_k(w)) >= 2:
            q["slowa"].append(_k(w))
    # „land rover”, „alfa romeo” – dwa słowa
    for mk in ("Land Rover", "Alfa Romeo"):
        if mk.upper() in T and mk not in q["marki"]:
            q["marki"].append(mk)
            q["slowa"] = [s for s in q["slowa"] if s not in ("LAND", "ROVER", "ALFA", "ROMEO")]
    return q


def szukaj(produkty, txt):
    """Wyniki TPMS dla polecenia: grupa 1 – pasuje dokładnie, 2 – ta sama marka auta, 3 – uniwersalne (przy szukaniu po aucie).
    Filtry z polecenia (rodzaj, demo, zawór, producent) dotyczą wszystkich grup; akcesoria tylko, gdy o nie pytano."""
    lista = [info(p) for p in produkty if float(p.get("netto") or 0) > 0]
    q = zapytanie(txt, sorted({x["producent"] for x in lista}))
    wyn = []
    for x in lista:
        if (x["rodzaj"] == "nar") != q["akcesoria"]:
            continue
        if q["rodzaje"] and x["rodzaj"] not in q["rodzaje"] and not (x["rodzaj"] == "uni" and q["marki"] and not q["rodzaje"]):
            continue
        if q["demo"] == "bez" and x["demo"] or q["demo"] == "tylko" and not x["demo"]:
            continue
        if q["zawor"] and x["zawor"] and x["zawor"] != q["zawor"]:
            continue
        if q["producent"] and x["producent"] != q["producent"]:
            continue
        slowa_ok = all(s in x["_k"] for s in q["slowa"])
        marka_ok = bool(set(q["marki"]) & set(x["marki"]))
        if q["marki"]:
            if marka_ok and slowa_ok:
                g = 1
            elif marka_ok:
                g = 2
            elif x["rodzaj"] == "uni" and (not q["rodzaje"] or "uni" in q["rodzaje"]):
                g = 3
            else:
                continue
        elif q["slowa"]:
            if not slowa_ok:
                continue
            g = 1
        else:
            g = 1
        wyn.append(dict(x, grupa=g))
    wyn.sort(key=lambda x: (x["grupa"], x["stan"] < q["ilosc"], x["brutto_zak"]))
    for x in wyn:
        x.pop("_k", None)
    return wyn, q
