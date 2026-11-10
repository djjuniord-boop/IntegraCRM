"""OFERTY OPON – silnik: wyszukiwanie opon w xPartner (XML API, productsList), oferta (XLSX, e-mail, ulotki).

Bez okna i bez bazy: dane konta (login API, ustawienia) i historię dostarcza okno.py przez KONTO i HIST.
Tylko biblioteka standardowa + openpyxl (dołączone do IntegraCRM.exe).
"""
import datetime
import json
import os
import re
import threading
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

from oferty import xp

VERSION = "panel"
OUT_DIR = os.path.join(os.path.expanduser("~"), "Documents", "Oferty opon")
API_URL = "https://xpartner.net.pl/index.php"

# uzupełnia okno.py po zalogowaniu: {"login": ..., "password": ..., "ustawienia": {...}, "zapisz": funkcja(dict)}
KONTO = {"login": "", "password": "", "ustawienia": {}, "zapisz": None, "oddzialy": [], "oddzialy_dane": {}, "kto": ""}
# historia ofert (baza): obiekt z metodami get(oid) -> dict|None, save(oid, klient, dane, szukaj), list(q) -> [dict]
HIST = None

DEFAULT_CFG = {
    "marza_proc": 5.0, "vat_proc": 23.0,
    # sposób liczenia ceny: "procent" (marża % od zakupu netto) albo "kwota" (dopłata zł brutto wg progów ceny zakupu brutto)
    "narzut_tryb": "procent",
    "progi": [{"do": 400, "kwota": 50}, {"do": 899, "kwota": 70}, {"do": None, "kwota": 90}],
    "min_stan": 50, "propozycji_na_sezon": 1,
    "tylko_standard": True,
    # cena wymiany brutto za 1 koło wg średnicy
    "wymiana_kolo": {"13": 40, "14": 40, "15": 42, "16": 44, "17": 50, "18": 55, "19": 60, "20": 65, "21": 70, "22": 75},
    "wymiana_suv": {"15": 55, "16": 55, "17": 60, "18": 65, "19": 70, "20": 80, "21": 90, "22": 100},
    "wymiana_dost": {"14": 55, "15": 60, "16": 65, "17": 70},
    "tpms_cena": 150,
    "przech_opony_do19": 120, "przech_opony_pow19": 160,
    "przech_kola_do19": 150, "przech_kola_pow19": 200,
    "kola_na_auto": 4,
    "klasy_ver": 2,
    "premium": ["BRIDGESTONE", "CONTINENTAL", "DUNLOP", "GOODYEAR", "METZELER", "MICHELIN", "NOKIAN", "PIRELLI", "PROMETEON", "TRELLEBORG", "VREDESTEIN", "YOKOHAMA"],
    "srednie": ["BFGOODRICH", "TOYO", "ALLIANCE", "SOLIDEAL", "NEXEN", "MITAS", "MAXAM", "KUMHO", "HANKOOK", "GENERAL", "FULDA", "FIRESTONE", "FALKEN", "COOPER", "CAMSO", "UNIROYAL", "KLEBER"],
    "budzet": ["SAILUN", "ROADX", "OPTIMO", "TRACMAX", "TRIANGLE", "FORTUNE", "WINDFORCE", "POWERTRAC", "DĘBICA", "BARUM", "GLOBGUM2", "KABAT", "KENDA", "LANVIGATOR", "MAXXIS", "PETLAS", "ROADHIKER", "STARMAXX", "TBBTIRES", "TRAXMAX", "TRAYAL", "TRAZANO", "VK TYRE", "APLUS"],
    "podpis": "Latex Serwis",
    "waznosc_dni": 7,
}

def load_cfg():
    cfg = json.loads(json.dumps(DEFAULT_CFG))
    user = dict(KONTO.get("ustawienia") or {})
    if user.get("klasy_ver") != DEFAULT_CFG["klasy_ver"]:
        for k in ("premium", "srednie", "budzet", "klasy_ver"):
            user.pop(k, None)
    cfg.update({k: v for k, v in user.items() if k in DEFAULT_CFG})
    cfg["login"], cfg["password"] = KONTO.get("login") or "", KONTO.get("password") or ""
    return cfg

def bkey(x):
    return re.sub(r"[^A-ZĄĆĘŁŃÓŚŹŻ0-9]", "", (x or "").upper())

def save_cfg(cfg):
    dane = {k: cfg[k] for k in DEFAULT_CFG if k in cfg}
    if KONTO.get("zapisz"):
        KONTO["zapisz"](dane)
    KONTO["ustawienia"] = dane

# ---------------------------------------------------------------- API
class ApiError(Exception):
    pass

def _txt(el, tag):
    x = el.find(tag)
    return (x.text or "").strip() if x is not None and x.text else ""

FOTO_TAG = re.compile(r"image|photo|picture|img|zdj|foto", re.I)
FOTO_URL = re.compile(r"^https://[^\s\"'<>]+$", re.I)

def _foto(p, attrs):
    """Adres zdjęcia opony, jeśli xPartner go podaje (pole o nazwie typu image/photo albo cecha z adresem obrazka).
    Tylko https – PDF nie pobiera niczego z adresów http ani lokalnych."""
    for c in p.iter():
        if c is not p and FOTO_TAG.search(c.tag or ""):
            for v in [c.text or ""] + list(c.attrib.values()):
                v = v.strip()
                if FOTO_URL.match(v):
                    return v
    for k, v in attrs.items():
        v = (v or "").strip()
        if FOTO_URL.match(v) and (FOTO_TAG.search(k) or re.search(r"\.(jpe?g|png|webp)(\?|$)", v, re.I)):
            return v
    return ""

def parse_products(xml_bytes):
    root = ET.fromstring(xml_bytes)
    ok = _txt(root, "success") or _txt(root, "productsResult")
    errs = [e.text for e in root.iter("error") if e.text]
    if ok.lower() != "true":
        raise ApiError("; ".join(errs) or "API zwróciło success=false (sprawdź login/hasło i uprawnienia subkonta)")
    count = int(_txt(root, "productsCount") or 0)
    out = []
    for p in root.iter("product"):
        attrs = {}
        for a in p.iter("attribute"):
            attrs[_txt(a, "name")] = _txt(a, "value")
        stock = {_txt(i, "warehouseName"): int(_txt(i, "quantity") or 0) for i in p.iter("item")}
        def num(t):
            try: return float(_txt(p, t).replace(",", "."))
            except ValueError: return 0.0
        out.append({
            "id": int(_txt(p, "productId") or 0),
            "kod": _txt(p, "manufacturerCode"), "ean": _txt(p, "ean"), "foto": _foto(p, attrs),
            "pola": sorted({c.tag for c in p}),
            "nazwa": _txt(p, "name"),
            "ilosc": int(_txt(p, "quantity") or 0),
            "netto": num("netDiscountPrice"), "brutto_zak": num("grossDiscountPrice"),
            "netto_kat": num("netListPrice"),
            "attrs": attrs, "magazyny": stock,
        })
    return count, out

def api_call(cfg, **params):
    q = {k: ("true" if v is True else "false" if v is False else v) for k, v in params.items()}
    try:
        data = xp.zapytanie(cfg, "productsList", q, timeout=30)   # przez pośrednika na serwerze (hasło tam)
    except xp.Blad as e:
        raise ApiError(str(e))
    try:
        return parse_products(data)
    except ET.ParseError:
        raise ApiError("Nieprawidłowa odpowiedź API (nie XML) – sprawdź login/hasło.")

CECHY = {}   # indeks -> cechy tylko z pliku ofertowego (EPREL, śnieg, lód) – API ich nie podaje, a oferta odświeża produkt z API
CECHY_PLIKU = ("Kod EPREL", "Przyczepność na śniegu", "Przyczepność na lodzie", "Hałas")

def zapamietaj_cechy(it):
    a = it.get("attrs") or {}
    c = {k: a[k] for k in CECHY_PLIKU if a.get(k)}
    if c:
        CECHY[it["id"]] = c

def search_size(cfg, size_txt):
    """Wszystkie produkty o danym rozmiarze: z kopii pliku ofertowego xPartner (zalecane przez xPartner),
    a gdy kopii brak / jest nieaktualna – z API (wszystkie strony)."""
    kat = KONTO.get("katalog")
    if kat:
        try:
            items = kat(size_txt)
            if items is not None:
                for it in items:
                    zapamietaj_cechy(it)
                return items
        except Exception:
            pass
    allp, page = [], 0
    while page < 30:
        count, items = api_call(cfg, productName=size_txt, resultsPerPage=100, page=page)
        allp += items
        page += 1
        if not items or len(allp) >= count:
            break
    return allp

def get_product(cfg, pid):
    _, items = api_call(cfg, productId=pid, showNotAvailable=True)
    return items[0] if items else None

# ---------------------------------------------------------------- logika
# Średnica z połówką (17.5, 19.5, 22.5 – ciężarowe) i „C” (opony dostawcze, inna nośność) są częścią rozmiaru:
# „265/70 R17.5” ≠ „265/70 R17”, „205/65 R16C” ≠ „205/65 R16”.
SIZE_RE = re.compile(r"(\d{3})\s*/\s*(\d{2})\s*Z?R\s*(\d{2})([.,]5(?![0-9A-Za-z]))?(C(?![A-Za-z]))?", re.I)

SIZE_LOOSE = re.compile(r"(?<!\d)(\d{3})\s*[/\\\-.x×, ]?\s*(\d{2})\s*(?:[/\\\-., ]|\s*Z?R\s*F?)?\s*(\d{2})([.,]5(?![0-9A-Za-z]))?(C(?![A-Za-z]))?(?!\d)", re.I)

def _rozmiar(w, p, r, pol, c):
    return "%s/%s R%s%s%s" % (w, p, r, ".5" if pol else "", "C" if c else "")

def find_sizes(txt):
    """Rozpoznaje rozmiar w dowolnym zapisie: 205/55 R16, 205/55 16, 205 55 16, 2055516, 205-55-16, 205/55/16, 205/55ZR16,
    także 265/70 R17.5 i 205/65 R16C (połówka i „C” zostają w rozmiarze)."""
    out = []
    for m in SIZE_LOOSE.finditer(txt or ""):
        w, p, r = (int(x) for x in m.groups()[:3])
        if 125 <= w <= 355 and w % 5 == 0 and 25 <= p <= 85 and p % 5 == 0 and 12 <= r <= 24:
            sz = _rozmiar(w, p, r, m.group(4), m.group(5))
            if sz not in out: out.append(sz)
    return out

def norm_size(s):
    m = SIZE_RE.search(s or "")
    if m: return _rozmiar(*m.groups())
    f = find_sizes(s)
    return f[0] if f else None

def season_of(p):
    s = (p["attrs"].get("Sezon", "") or "").upper()
    if "ZIM" in s: return "Zimowa"
    if "CAŁ" in s or "CAL" in s or "WIELO" in s or "ALL" in s: return "Całoroczna"
    if "LET" in s: return "Letnia"
    n = p["nazwa"]
    m = re.match(r"^\S+\s+([ZWL])\d{3}/", n)
    return {"Z": "Zimowa", "W": "Całoroczna", "L": "Letnia"}.get(m.group(1) if m else "", "?")

def producer_of(p):
    return (p["attrs"].get("Producent") or p["nazwa"].split(" ")[0]).upper()

KLASY = {"PREMIUM": "premium", "MIDDLE": "średnia", "BUDGET": "budżetowa"}

def klasa_of(p, cfg):
    k = (p["attrs"].get("Klasa") or "").upper()
    if k.startswith("PREM"): return "PREMIUM"
    if k in ("MIDDLE", "MEDIUM", "ŚREDNIA", "SREDNIA", "STANDARD", "QUALITY"): return "MIDDLE"
    if k in ("BUDGET", "ECONOMY", "EKONOMICZNA", "BUDŻETOWA", "BUDZETOWA", "ECO"): return "BUDGET"
    prod = bkey(producer_of(p))
    if prod in [bkey(x) for x in cfg["premium"]]: return "PREMIUM"
    if prod in [bkey(x) for x in cfg.get("srednie", [])]: return "MIDDLE"
    return "BUDGET"

def model_of(p):
    m = p["attrs"].get("Nazwa bieżnika")
    if m: return m.title()
    n = re.sub(r"\s+(DEMO|DOT\s?\d{4})\b", "", re.sub(r"^\S+\s+[ZWL]?\d{3}/\d{2}\s*Z?R\d{2}\s*", "", p["nazwa"]))
    return re.sub(r"\s+\d{2,3}[A-Z].*$", "", n).title()

def index_of(p):
    li = p["attrs"].get("Indeks nośności", ""); si = (p["attrs"].get("Indeks prędkości", "") or "").split("-")[0]
    xl = " XL" if re.search(r"\bXL\b", p["nazwa"]) else ""
    if li and si: return li + si + xl
    m = re.search(r"\b(\d{2,3}[A-Z])\b(\s+XL)?", p["nazwa"])
    return (m.group(1) + (" XL" if m.group(2) else "")) if m else ""

def dot_of(p):
    d = p["attrs"].get("Rok produkcji") or ""
    m = re.search(r"DOT\s?(\d{4})", d or p["nazwa"])
    return m.group(1) if m else ""

def is_standard(p):
    s = (p["attrs"].get("Struktura") or "STANDARD").upper()
    n = p["nazwa"].upper()
    return s == "STANDARD" and not re.search(r"\b(RFT|SSR|R/F|ROF|ZP|RUN ?FLAT|DSST|EMT)\b", n)

SEZ_ORDER = {"Zimowa": 0, "Całoroczna": 1, "Letnia": 2}
KL_ORDER = {"premium": 0, "średnia": 1, "budżetowa": 2}
def vkey(k):
    parts = k[0].split(" · ")
    return (SEZ_ORDER.get(parts[0], 9), KL_ORDER.get(parts[1] if len(parts) > 1 else "", 9), k[1])

def leaflet_url(pid, price):
    """Ulotka PDF generowana przez xPartner (wymaga zalogowania w przeglądarce)."""
    q = {"a": "b2b_products", "m": "getPDF", "pid": pid, "fp": 0, "fn": 0, "fb": 0, "fs": 0, "showc": 0, "price": "%.2f" % price}
    return "https://xpartner.net.pl/index.php?" + urllib.parse.urlencode(q)

def vlabel(variants, key):
    if key[0] == "wszystkie": return "Propozycja %d" % (key[1] + 1)
    multi = sum(1 for k in variants if k[0] == key[0]) > 1
    return key[0] + (" – propozycja %d" % (key[1] + 1) if multi else "")

def rabat_wymiany(req):
    """Rabat % na wymianę (0–100) i ręczne ceny wymiany za 1 koło {"R16|osobowy": 40}."""
    try: rw = max(0.0, min(100.0, float(str(req.get("rabat_wym") or 0).replace(",", "."))))
    except ValueError: rw = 0.0
    over = {}
    for k, v in (req.get("ceny_wym") or {}).items():
        try:
            if str(v).strip() not in ("",):
                over[str(k)] = max(0.0, float(str(v).replace(",", ".")))
        except ValueError:
            pass
    return rw, over


def cena_po_rabacie(c, rab):
    """Jak dla opon: po rabacie w górę do pełnych zł."""
    import math
    return float(math.ceil(round(c * (1 - rab / 100), 2) - 1e-9)) if rab else c


def doplata_progowa(cfg, zakup_brutto):
    """Kwota doliczana do ceny zakupu brutto wg progów (pierwszy próg, którego „do” obejmuje cenę; puste „do” = powyżej)."""
    progi = sorted((p for p in cfg.get("progi") or [] if p.get("do") not in (None, "")), key=lambda p: float(p["do"]))
    reszta = [p for p in cfg.get("progi") or [] if p.get("do") in (None, "")]
    for p in progi:
        if zakup_brutto <= float(p["do"]) + 0.004:
            return float(p.get("kwota") or 0)
    return float(reszta[0].get("kwota") or 0) if reszta else (float(progi[-1].get("kwota") or 0) if progi else 0.0)


def sell_price(cfg, netto):
    import math
    vat = 1 + cfg["vat_proc"] / 100
    if cfg.get("narzut_tryb") == "kwota":
        brutto = round(netto * vat, 2)
        cena = brutto + doplata_progowa(cfg, brutto)
    else:
        cena = netto * (1 + cfg["marza_proc"] / 100) * vat
    return float(math.ceil(round(cena, 2) - 1e-9))  # w górę do pełnych zł

def enrich(cfg, p):
    p = dict(p)
    p.update(sezon=season_of(p), producent=producer_of(p), klasa=klasa_of(p, cfg), model=model_of(p),
             indeks=index_of(p), dot=dot_of(p), standard=is_standard(p),
             cena_brutto=sell_price(cfg, p["netto"]),
             etykieta={k: p["attrs"].get(k, "") for k in ("Opory toczenia", "Przyczepność na mokrej nawierzchni", "Hałas", "Poziom hałasu")})
    nz = re.search(r"(\d{2})", p["attrs"].get("Poziom hałasu", "") or "")
    p.update(mokra=(p["attrs"].get("Przyczepność na mokrej nawierzchni") or "").strip()[:1].upper(),
             opory=(p["attrs"].get("Opory toczenia") or "").strip()[:1].upper(),
             halas=int(nz.group(1)) if nz else 0, homol=homol_of(p), demo=is_demo(p))
    mi = re.match(r"(\d{2,3})(?:/\d{2,3})?([A-Z]{1,2}\d?)", p["indeks"] or "")
    p.update(nosnosc=int(mi.group(1)) if mi else 0, predkosc=mi.group(2) if mi else "",
             rant=bool((p["attrs"].get("Rant ochronny") or "").strip()) or bool(re.search(r"\b(FR|MFS|FSL|RPB|MFS)\b", p["nazwa"].upper())))
    p["model_oferta"] = p["model"] + (" – DEMO (opona z demontażu)" if p["demo"] else "")
    return p

HOMOL = [("MO", r"\bMOE?\b|\bMO1\b|\bMO-S\b", "Mercedes (MO)"), ("AO", r"\bAOE?\b|\bRO[12]\b|\bA8A\b", "Audi (AO/RO)"), ("*", r"\*|\bBMW\b", "BMW (*)"),
         ("N", r"\bN[0-9]\b", "Porsche (N0–N9)"), ("VOL", r"\bVOL\b", "Volvo (VOL)"), ("T0", r"\bT[0O][0-9]?\b", "Tesla (T0)"),
         ("J", r"\bJLR\b|\bJ\b", "Jaguar (J)"), ("LR", r"\bLR\b", "Land Rover (LR)"), ("VW", r"\bVW\b", "VW"), ("FR", r"\b(FR|MFS|FP|RG)\b", "rant ochronny felgi")]

def is_demo(p):
    """Opona „DEMO” (z demontażu z nowego auta) – w xPartner oznaczona w nazwie albo w cechach."""
    if re.search(r"\bDEMO\b", p["nazwa"].upper()):
        return True
    return any("demont" in (k + " " + str(v)).lower() and str(v).strip().upper() not in ("", "NIE", "0", "FALSE")
               for k, v in p["attrs"].items())

def homol_of(p):
    src = " ".join([p["nazwa"].upper(), (p["attrs"].get("Homologacja") or "").upper()])
    src = SIZE_RE.sub(" ", src)
    return [k for k, rx, _ in HOMOL if re.search(rx, src)]

PLATE_RE = re.compile(r"(?<![A-Z0-9])([A-Z]{1,3})[ -]?([0-9][0-9A-Z]{2,5}|[A-Z]{0,2}[0-9][0-9A-Z]{1,4})(?![A-Z0-9])")
STOP = {"marka", "model", "rejestracja", "rozmiar", "wymaga", "nowych", "opon", "opony", "szt", "sztuk", "tak", "nie", "tylko",
        "wymiana", "wymianę", "wymiane", "auto", "samochód", "samochod", "pojazd", "i", "oraz", "x", "r", "zr", "nr", "rej"}

CRIT_RE = re.compile(r"^(demo|bez|suv|4x4|terenow\w*|dostawcz\w*|bus|van|czujnik\w*|tpms|przechow\w*|k[oó]ł|kola|koła|felg\w*|z|ze|wymian\w*|monta[żz]\w*|przek[łl]ad\w*|premium|prem|[śs]redni\w*|middle|medium|bud[żz]et\w*|budget|ekonom\w*|tani\w*|zim\w*|letn\w*|lato|lecie|summer\w*|winter\w*|ca[łl]orok|pory|roku|ca[łl]oroczn\w*|wielosezon\w*|runflat|run-?flat|rft|ssr|klas[aey]?|półk[aią]|polk[aią]|sezon\w*|opony|michelin|continental|goodyear|good-year|bridgestone|pirelli|nokian|dunlop|hankook|vredestein|yokohama|barum|dębica|debica|kleber|fulda|firestone|bfgoodrich|uniroyal|semperit|kumho|falken|toyo|nexen|sava|kormoran|matador)$", re.I)

def extras(t):
    """Typ auta, wymiana, TPMS, przechowalnia z dowolnego tekstu."""
    t = t.lower()
    typ = "suv" if re.search(r"\bsuv\b|4x4|4 ?x ?4|terenow", t) else "dostawczy" if re.search(r"dostawcz|\bbus\b|\bvan\b", t) else "osobowy"
    wym = bool(re.search(r"wymian|monta[żz]|przek[łl]ad", t)) and not re.search(r"bez (wymiany|monta[żz]u)", t)
    m = re.search(r"(\d)\s*(?:szt\.?\s*)?(?:czujnik\w*|tpms)|(?:czujnik\w*|tpms)\s*(?:x\s*)?(\d)\b", t)
    tp = int(m.group(1) or m.group(2)) if m else (4 if re.search(r"czujnik|tpms", t) else 0)
    pr = ""
    if re.search(r"przechow", t):
        pr = "kola" if re.search(r"k[oó][łl]|felg", t) else "opony"
    return {"typ": typ, "wymiana": wym, "tpms": min(tp, 8), "przech": pr}

def _cap(w):
    return w.upper() if (len(w) <= 3 and w.isalpha()) or any(c.isdigit() for c in w) else w.capitalize()

def parse_free_line(line):
    """'skoda octavia 2055516 dw5444lw 4 szt' -> pojazd. Rozmiar wymagany."""
    sizes = find_sizes(line)
    if not sizes: return None
    up = line.upper()
    rest = SIZE_LOOSE.sub(" ", up)
    q = re.search(r"(?<!\d)(\d{1,2})\s*(SZT|OPON|SZTUK)", rest)
    il = int(q.group(1)) if q else 4
    rest = re.sub(r"(?<!\d)\d{1,2}\s*(SZT|OPON|SZTUK)\.?", " ", rest)
    only_swap = bool(re.search(r"TYLKO\s+WYMIAN|\bNIE\b|BEZ OPON", up))
    if only_swap: il = 0
    reg = ""
    for m in PLATE_RE.finditer(rest):
        cand = m.group(1) + m.group(2)
        if any(c.isdigit() for c in cand) and 4 <= len(cand) <= 8 and not re.fullmatch(r"\d+", m.group(2)) or (len(m.group(1)) >= 2 and len(cand) >= 5):
            reg = cand; rest = rest[:m.start()] + " " + rest[m.end():]; break
    words = [w for w in re.split(r"[\s,;/|\t]+", rest) if w and w.lower() not in STOP and not re.fullmatch(r"[\d.,]+", w) and not CRIT_RE.match(w) and not brand_of_word(w)]
    ex = extras(line)
    return {"rej": reg, "pojazd": " ".join(_cap(w.lower()) for w in words), "rozmiar": sizes[0], "nowe": il > 0, "ilosc": il,
            "wymiana": ex["wymiana"] or only_swap, "typ": ex["typ"], "tpms": ex["tpms"], "przech": ex["przech"]}

def parse_request_text(txt):
    if not re.search(r"(^|\s)(TAK|NIE)(\s|$)", txt, re.M) or len([l for l in txt.splitlines() if l.strip()]) <= 1 or any(len(find_sizes(l)) and len(l.split()) >= 3 for l in txt.splitlines()):
        recs = [r for r in (parse_free_line(l) for l in re.split(r"[\n;]+", txt)) if r]
        if recs: return recs
    return parse_request_table(txt)

def parse_request_table(txt):
    """Wyciąga pojazdy z wklejonego zapytania (tabela z maila: Marka Model Rejestracja Rozmiar TAK/NIE)."""
    tokens = re.split(r"[\t\r\n|;]+|\s{2,}", txt)
    tokens = [t.strip() for t in tokens if t.strip()]
    recs, cur = [], []
    reg_re = re.compile(r"^[A-Z]{1,3}[0-9][0-9A-Z]{2,6}$")
    for t in tokens:
        cur.append(t)
        if t.upper() in ("TAK", "NIE"):
            joined = " ".join(cur)
            size = norm_size(joined)
            reg = next((x.replace(" ", "") for x in cur if reg_re.match(x.replace(" ", "").upper()) and not SIZE_RE.search(x)), "")
            if size:
                words = []
                for x in cur:
                    if x.replace(" ", "") == reg or SIZE_RE.search(x) or x.upper() in ("TAK", "NIE"): continue
                    if x.lower() in ("marka", "model", "rejestracja", "rozmiar", "wymaga nowych opon"): continue
                    words.append(x.title())
                recs.append({"rej": reg.upper(), "pojazd": " ".join(words[-2:]), "rozmiar": size, "nowe": t.upper() == "TAK", "ilosc": 4 if t.upper() == "TAK" else 0, "wymiana": True})
            cur = []
    if not recs:  # fallback: wiersz = pojazd
        for line in txt.splitlines():
            size = norm_size(line)
            if size:
                reg = next((x for x in line.split() if reg_re.match(x.upper()) and not SIZE_RE.search(x)), "")
                recs.append({"rej": reg.upper(), "pojazd": "", "rozmiar": size, "nowe": "NIE" not in line.upper(), "ilosc": 0 if "NIE" in line.upper() else 4, "wymiana": True})
    return recs

# marki opon: listy z ustawień (premium / średnie / budżet) + popularne + producenci widziani w wynikach
# marki opon z wyszukiwarki xPartner (listopad 2026) + producenci widziani w wynikach i z list w Ustawieniach
MARKI_STALE = [
    "BRIDGESTONE", "CONTINENTAL", "DUNLOP", "GOODYEAR", "METZELER", "MICHELIN", "NOKIAN", "PIRELLI", "PROMETEON",
    "TRELLEBORG", "VREDESTEIN", "YOKOHAMA", "BFGOODRICH", "TOYO", "ALLIANCE", "SOLIDEAL", "NEXEN", "MITAS", "MAXAM",
    "KUMHO", "HANKOOK", "GENERAL", "FULDA", "FIRESTONE", "FALKEN", "COOPER", "CAMSO", "UNIROYAL", "KLEBER", "SAILUN",
    "ROADX", "OPTIMO", "TRACMAX", "TRIANGLE", "FORTUNE", "WINDFORCE", "POWERTRAC", "DĘBICA", "BARUM", "GLOBGUM2",
    "KABAT", "KENDA", "LANVIGATOR", "MAXXIS", "PETLAS", "ROADHIKER", "STARMAXX", "TBBTIRES", "TRAXMAX", "TRAYAL",
    "TRAZANO", "VK TYRE", "APLUS", "ANTEO", "ATF", "CHIŃSKIE", "COMPASAL", "CST", "CULTOR", "DEESTONE", "DELI",
    "DYNAMAXX", "GISLAVED", "GITI", "GT RADIAL", "KORMORAN", "LEAO", "LING LONG", "MARCHER", "MATADOR", "MONTANA",
    "NANKANG", "NEUMASTER", "PMT", "RIKEN", "ROSAVA", "SAVA", "STARCO", "TAURUS", "TECHSHIELD", "TIGAR", "VEE RUBBER",
    "VIKING", "SEMPERIT", "LASSA", "LAUFENN", "HIFLY", "GRIPMAX", "ZEETEX", "ROTALLA", "IMPERIAL", "MARSHAL",
    "GOODRIDE", "WESTLAKE", "MINERVA", "DAVANTI", "ARIVO", "LINGLONG", "STRIAL", "ORIUM", "NORDEXX"]
MARKI = set()
_ALIAS = {"GOODYEAR": "GOODYEAR", "GOODYER": "GOODYEAR", "GY": "GOODYEAR", "DEBICA": "DĘBICA", "BFG": "BFGOODRICH",
          "CONTI": "CONTINENTAL", "BRIDGE": "BRIDGESTONE", "BS": "BRIDGESTONE", "MICH": "MICHELIN", "PIRA": "PIRELLI",
          "LINGLONG": "LINGLONG", "GTRADIAL": "GTRADIAL", "VK": "VKTYRE", "CHINSKIE": "CHIŃSKIE", "CHINSKA": "CHIŃSKIE"}


def ucz_marki(cfg=None, nazwy=()):
    for m in list(MARKI_STALE) + list((cfg or {}).get("premium", [])) + list((cfg or {}).get("srednie", [])) \
            + list((cfg or {}).get("budzet", [])) + list(nazwy):
        if m and len(bkey(m)) >= 2:
            MARKI.add(bkey(m))


def _odl(a, b, limit=2):
    """Odległość edycyjna (z zamianą sąsiednich liter), przerywana po przekroczeniu limitu."""
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    d = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(len(a) + 1):
        d[i][0] = i
    for j in range(len(b) + 1):
        d[0][j] = j
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            c = 0 if a[i - 1] == b[j - 1] else 1
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + c)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
    return d[-1][-1]


_NIE_MARKI = {"ZIMA", "ZIMOWE", "LATO", "LETNIE", "OPONY", "OPONA", "PREMIUM", "SREDNIA", "ŚREDNIA", "BUDZET", "BUDŻET",
              "WYMIANA", "DEMO", "RUNFLAT", "TYLKO", "PRZECHOWALNIA", "CZUJNIKI", "SZTUK", "OFERTA", "OFERTY", "TOYOTA",
              "OSOBOWY", "DOSTAWCZY", "KOMPLET", "FELGI", "FELGAMI",
              # marki i modele aut – nie mogą „podobieństwem” wpaść w marki opon
              "SKODA", "OCTAVIA", "SUPERB", "FABIA", "KAMIQ", "KAROQ", "KODIAQ", "SCALA", "RAPID", "ENYAQ", "VOLKSWAGEN",
              "PASSAT", "TIGUAN", "TOURAN", "GOLF", "POLO", "ARTEON", "TRANSPORTER", "CRAFTER", "CADDY", "AMAROK", "TAIGO",
              "TROC", "AUDI", "BMW", "MERCEDES", "SPRINTER", "VITO", "VIANO", "TOYOTA", "YARIS", "COROLLA", "AURIS", "AVENSIS",
              "RAV4", "CHR", "HILUX", "PROACE", "OPEL", "ASTRA", "CORSA", "INSIGNIA", "MOKKA", "VIVARO", "MOVANO", "ZAFIRA",
              "FORD", "FOCUS", "FIESTA", "MONDEO", "KUGA", "TRANSIT", "CUSTOM", "PUMA", "RANGER", "RENAULT", "CLIO", "MEGANE",
              "CAPTUR", "KADJAR", "TRAFIC", "MASTER", "KANGOO", "DACIA", "DUSTER", "SANDERO", "LOGAN", "JOGGER", "PEUGEOT",
              "PARTNER", "EXPERT", "BOXER", "CITROEN", "BERLINGO", "JUMPER", "JUMPY", "FIAT", "DUCATO", "DOBLO", "TIPO",
              "PANDA", "HYUNDAI", "TUCSON", "KONA", "I30", "SANTA", "KIA", "CEED", "SPORTAGE", "NIRO", "SORENTO", "PICANTO",
              "MAZDA", "HONDA", "CIVIC", "NISSAN", "QASHQAI", "JUKE", "XTRAIL", "NAVARA", "VOLVO", "SEAT", "LEON", "IBIZA",
              "ATECA", "ARONA", "CUPRA", "FORMENTOR", "SUZUKI", "VITARA", "SWIFT", "MITSUBISHI", "OUTLANDER", "TESLA",
              "LEXUS", "JEEP", "SUBARU", "PORSCHE", "LAND", "ROVER", "MINI", "IVECO", "DAILY", "MAN", "SCANIA"}


def brand_of_word(w):
    """Marka z wpisanego słowa: dokładnie, skrót (np. „conti”), początek nazwy (≥4 litery) albo literówka
    (1 błąd przy krótkich nazwach, 2 przy dłuższych – np. „silun” → SAILUN, „rodx” → ROADX)."""
    if not MARKI:
        ucz_marki()
    k = bkey(_ALIAS.get(bkey(w), w))
    if len(k) < 3 or k in _NIE_MARKI:
        return ""
    if k in MARKI:
        return k
    if len(k) >= 4:
        hits = sorted(m for m in MARKI if m.startswith(k))
        if len(hits) == 1:
            return hits[0]
        lim = 1 if len(k) <= 5 else 2
        best = sorted((_odl(k, m, lim), m) for m in MARKI if len(m) >= 4)
        best = [b for b in best if b[0] <= lim]
        if best and (len(best) == 1 or best[0][0] < best[1][0]):
            return best[0][1]
    return ""


def parse_quick(txt):
    """Szybkie polecenie, np. '205/55 r16 3 oferty premium średnia budżet zimowe 4 szt'."""
    t = txt.lower()
    sizes = find_sizes(txt)
    q = re.search(r"(?:^|\s)(\d{1,2})\s*(szt|opon|sztuk|x\b)", t) or re.search(r"\bx\s*(\d{1,2})\b", t)
    ilosc = int(q.group(1)) if q else 4
    sezony = []
    if re.search(r"(?<![a-ząćęłńóśźż])(zim|winter)", t): sezony.append("Zimowa")
    if re.search(r"(?<![a-ząćęłńóśźż])(ca[łl]oroczn|ca[łl]orok|wielosezon|all ?-?season|4 ?season|4 ?pory)", t): sezony.append("Całoroczna")
    if re.search(r"(?<![a-ząćęłńóśźż])(letn|lato|lecie|summer)", t): sezony.append("Letnia")
    klasy = []
    if re.search(r"premium|prem\b", t): klasy.append("PREMIUM")
    if re.search(r"[śs]redni|middle|medium", t): klasy.append("MIDDLE")
    if re.search(r"bud[żz]et|budget|ekonom|tani", t): klasy.append("BUDGET")
    marki = []
    slowa = [w for w in re.findall(r"[a-ząćęłńóśźż][a-ząćęłńóśźż0-9\-.]*", t) if not SIZE_LOOSE.search(w)]
    i = 0
    while i < len(slowa):   # najpierw dwa słowa razem („ling long”, „gt radial”, „vk tyre”)
        b2 = brand_of_word(slowa[i] + slowa[i + 1]) if i + 1 < len(slowa) else ""
        if b2 and bkey(slowa[i] + slowa[i + 1]) in MARKI:
            b, i = b2, i + 2
        else:
            b, i = brand_of_word(slowa[i]), i + 1
        if b and b not in marki:
            marki.append(b)
    ex = extras(t)
    wymiana = ex["wymiana"]
    runflat = bool(re.search(r"run ?-?flat|\brft\b|\bssr\b|\bzp\b|\brof\b", t))
    pojazdy = [{"rej": "", "pojazd": "", "rozmiar": s, "ilosc": ilosc, "nowe": True, "wymiana": wymiana, "typ": ex["typ"], "tpms": ex["tpms"], "przech": ex["przech"]} for s in sizes]
    if len(pojazdy) == 1:   # jedno auto: rejestracja i model jak w polu „Zapytanie klienta”
        try:
            fl = parse_free_line(txt) or {}
        except Exception:
            fl = {}
        if fl.get("rej"):
            pojazdy[0]["rej"] = fl["rej"]
        auto = [w for w in (fl.get("pojazd") or "").split()   # bez indeksów (91V), XL i „run flat”
                if not re.match(r"^(\d{2,3}[a-z]|xl|run|flat|runflat|rft)$", w, re.I)]
        if auto and any(re.match(r"^[a-ząćęłńóśźż-]{3,}$", w, re.I) for w in auto) and (fl.get("rej") or len(auto) >= 2):
            pojazdy[0]["pojazd"] = " ".join(auto)
    demo = "bez" if re.search(r"bez\s+demo", t) else "tylko" if re.search(r"\bdemo\b", t) else ""
    nosnosc, predkosc = indeks_z_tekstu(t)
    return {"demo": demo, "pojazdy": pojazdy, "sezony": sezony, "klasy": klasy, "runflat": runflat, "producenci": ", ".join(dict.fromkeys(marki)),
            "nosnosc": nosnosc, "predkosc": predkosc}


INDEKS_Q = re.compile(r"(?<![\d/.,])(\d{2,3})(?:/\d{2,3})?\s?([lmnpqrstuhvwyz])(?![a-ząćęłńóśźż0-9])")


def indeks_z_tekstu(t):
    """'91w' / '94 v' -> (91, 'W') – nośność i prędkość z szybkiego polecenia (rozmiar wcześniej wycięty)."""
    m = INDEKS_Q.search(SIZE_LOOSE.sub(" ", t.lower()))
    if not m or not 50 <= int(m.group(1)) <= 130:
        return 0, ""
    return int(m.group(1)), m.group(2).upper()

def do_search(cfg, req):
    sizes = sorted({norm_size(v["rozmiar"]) for v in req["pojazdy"] if v.get("nowe") and norm_size(v["rozmiar"])})
    sezony = req.get("sezony") or [""]
    prod_f = [bkey(x) for x in (req.get("producenci") or "").split(",") if x.strip()]
    klasy = req.get("klasy") or [req.get("klasa", "")]
    min_stan = int(req.get("min_stan", cfg["min_stan"]))
    need = {}
    for v in req["pojazdy"]:
        if v.get("nowe"):
            s = norm_size(v["rozmiar"]); need[s] = need.get(s, 0) + int(v.get("ilosc") or 4)
    with ThreadPoolExecutor(4) as ex:
        found = dict(zip(sizes, ex.map(lambda s: search_size(cfg, s), sizes)))
    res = {}
    for s in sizes:
        items = [enrich(cfg, p) for p in found[s] if norm_size(p["nazwa"]) == s and p["netto"] > 0]
        ucz_marki(nazwy=[p["producent"] for p in items])  # cena 0 = niedostępne do zamówienia
        res[s] = {}
        for sez in sezony:
          for klasa in klasy:
            lst = [p for p in items if not sez or p["sezon"] == sez]
            if req.get("tylko_runflat"): lst = [p for p in lst if not p["standard"]]
            if prod_f: lst = [p for p in lst if any(bkey(p["producent"]).startswith(x) for x in prod_f)]
            if klasa:
                lst = [p for p in lst if p["klasa"] == klasa]
            lst = [p for p in lst if p["ilosc"] >= need[s]]   # za mało sztuk na całą potrzebę – nie pokazujemy wcale
            for p in lst:
                p["ok_stan"] = p["ilosc"] >= max(min_stan, need[s])
            lst.sort(key=lambda p: (not p["ok_stan"], p["netto"]))
            grp = " · ".join(x for x in (sez, KLASY.get(klasa, klasa)) if x) or "wszystkie"
            res[s][grp] = lst
    info = KONTO.get("katalog_info")
    return {"wyniki": res, "potrzeba": need, "zrodlo": (info() if info else "") or "xPartner na żywo (API)"}

# ---------------------------------------------------------------- oferta
TYPY = {"osobowy": "osobowy", "suv": "SUV/4x4", "dostawczy": "dostawczy"}

def total(v):
    return v["opony"] + v["wymiana"] + v.get("uslugi", 0)

def build_offer(cfg, req):
    """req: pojazdy, wybor: {rozmiar: {sezon: [productId,...]}} – odświeża ceny/stany przez API."""
    ids = sorted({pid for s in req["wybor"].values() for l in s.values() for pid in l})
    with ThreadPoolExecutor(4) as ex:
        fresh = {pid: (enrich(cfg, p) if p else None) for pid, p in zip(ids, ex.map(lambda i: get_product(cfg, i), ids))}
    try: m_off = float(req.get("marza")) if req.get("marza") not in (None, "") else None
    except ValueError: m_off = None
    try: rab = max(0.0, min(90.0, float(req.get("rabat") or 0)))
    except ValueError: rab = 0.0
    over = {int(k): float(v) for k, v in (req.get("ceny") or {}).items() if str(v).strip() not in ("", "0")}
    c2 = dict(cfg, marza_proc=cfg["marza_proc"] if m_off is None else m_off)
    for pid, p in fresh.items():
        if not p: continue
        import math
        auto = sell_price(c2, p["netto"])
        if rab:
            auto = float(math.ceil(round(auto * (1 - rab / 100), 2) - 1e-9))
        p["cena_auto"] = auto
        p["cena_brutto"] = over.get(pid, auto)
        p["recznie"] = pid in over
    warnings = []
    rw, over_w = rabat_wymiany(req)
    kola = int(cfg["kola_na_auto"])
    rows, variants = [], {}
    sep = bool(req.get("osobno"))
    for vi, v in enumerate(req["pojazdy"]):
        v = {"rej": "", "pojazd": "", **v}
        s = norm_size(v["rozmiar"]) or v["rozmiar"]
        dia = (re.search(r"R(\d{2})", s) or [None, "16"])[1]
        typ = v.get("typ") or "osobowy"
        cen = cfg["wymiana_suv"] if typ == "suv" else cfg["wymiana_dost"] if typ == "dostawczy" else cfg["wymiana_kolo"]
        n_kol = int(v.get("ilosc") or 0) or kola   # wymiana tylu kół, ile opon; przy samej wymianie – komplet
        c0 = float(cen.get(dia, 0))
        kw = "R%s|%s" % (dia, typ)
        auto_w = cena_po_rabacie(c0, rw)
        c_w = over_w.get(kw, auto_w)
        v = dict(v, wym_tak=bool(v.get("wymiana")), wym_klucz=kw, wym_cennik=c0, wym_auto=auto_w, wym_szt=c_w, wym_recznie=kw in over_w)
        wym = c_w * n_kol if v.get("wymiana") else 0.0
        if v.get("wymiana") and not cen.get(dia):
            warnings.append("Brak ceny wymiany dla %s R%s (%s) – uzupełnij Ustawienia" % (v.get("rej") or s, dia, TYPY[typ]))
        n_tp = int(v.get("tpms") or 0)
        tp_kw = round(n_tp * float(cfg["tpms_cena"]), 2)
        tp_op = ("Czujniki TPMS %d szt. × %s" % (n_tp, pl(float(cfg["tpms_cena"])))) if n_tp else ""
        pr = v.get("przech") or ""
        pr_kw, pr_op = 0.0, ""
        if pr in ("opony", "kola"):
            big = int(dia) > 19
            pr_kw = float(cfg["przech_%s_%s" % (pr, "pow19" if big else "do19")])
            pr_op = "Przechowalnia %s (%s R19)" % ("opon" if pr == "opony" else "kół z felgami", "powyżej" if big else "do")
        v = dict(v, tpms_kw=tp_kw, tpms_op=tp_op, przech_kw=pr_kw, przech_op=pr_op, uslugi=tp_kw + pr_kw)
        if not v.get("nowe"):
            rows.append(dict(v, rozmiar=s, rodzaj="usługi" if not v.get("wymiana") else "tylko wymiana", wymiana=wym, opony=0, p=None, wariant=None))
            for key in variants: variants[key]["wymiana"] += wym
            continue
        for sez, lst in req["wybor"].get(s, {}).items():
            for k, pid in enumerate(lst):
                p = fresh.get(pid)
                if p and p["netto"] <= 0:
                    warnings.append("%s – brak ceny w xPartner (niedostępna do zamówienia), pominięto" % p["nazwa"]); continue
                if not p:
                    warnings.append("Produkt %s niedostępny w API" % pid); continue
                q = int(v.get("ilosc") or 4)
                if sep:
                    vl = " ".join(x for x in (v.get("rej"), v.get("pojazd")) if x) or s
                    if sum(1 for w in req["pojazdy"] if (" ".join(x for x in (w.get("rej"), w.get("pojazd")) if x) or norm_size(w["rozmiar"])) == vl) > 1:
                        vl += " (%d)" % (vi + 1)
                    key = (vl + ("" if sez == "wszystkie" else " · " + sez), k)
                else:
                    key = (sez, k)
                variants.setdefault(key, {"opony": 0.0, "wymiana": 0.0, "modele": set()})
                rows.append(dict(v, rozmiar=s, rodzaj=p["sezon"], p=p, ilosc=q, opony=round(p["cena_brutto"] * q, 2), wymiana=wym, wariant=key))
    # wymiana: każde auto liczone raz na wariant
    for key, var in variants.items():
        var["opony"] = sum(r["opony"] for r in rows if r["wariant"] == key)
        var["wymiana"] = sum(r["wymiana"] for r in rows if r["wariant"] == key) + sum(r["wymiana"] for r in rows if r["p"] is None)
        for f in ("tpms_kw", "przech_kw"):
            var[f] = sum(r[f] for r in rows if r["wariant"] == key) + sum(r[f] for r in rows if r["p"] is None)
        var["uslugi"] = var["tpms_kw"] + var["przech_kw"]
        var["modele"] = sorted({"%s %s" % (r["p"]["producent"].title(), r["p"]["model"]) for r in rows if r["wariant"] == key})
    if not variants and rows:
        variants[("Usługi", 0)] = {"opony": 0.0, "wymiana": sum(r["wymiana"] for r in rows), "tpms_kw": sum(r["tpms_kw"] for r in rows), "przech_kw": sum(r["przech_kw"] for r in rows), "uslugi": sum(r["uslugi"] for r in rows), "modele": []}
    # stany vs potrzeba
    need = {}
    for r in rows:
        if r["p"]: need[r["p"]["id"]] = need.get(r["p"]["id"], 0) + r["ilosc"]
    for pid, n in need.items():
        p = fresh[pid]
        if p and p["ilosc"] < n:
            warnings.append("%s – na stanie %d szt., potrzeba %d" % (p["nazwa"], p["ilosc"], n))
    return rows, variants, warnings

def write_xlsx(cfg, req, rows, variants):
    from openpyxl import Workbook
    from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
    wb = Workbook(); ws = wb.active; ws.title = "Oferta"
    _ws_append = ws.append
    def _bez_formul(row):   # tekst wpisany przez użytkownika albo z xPartner nie może stać się formułą Excela
        return [(" " + v) if isinstance(v, str) and v[:1] in ("=", "+", "-", "@") and not re.match(r"^=[A-Z]+\d+[*+]", v) else v for v in row]
    ws.append = lambda row: _ws_append(_bez_formul(row))
    hdr = ["Rejestracja", "Pojazd", "Rozmiar", "Rodzaj", "Producent", "Model opony", "Indeks xPartner", "Nośność/prędkość", "Cena brutto / szt.", "Ilość", "Opony razem", "Wymiana kół", "Czujniki TPMS", "Przechowalnia", "RAZEM brutto", "DOT", "Stan (szt.)", "Usługi – opis"]
    kl = (req.get("klient") or "").strip()
    ws.append(["OFERTA – opony i usługi" + (" dla: " + kl if kl else "")])
    ws["A1"].font = Font(b=True, size=14)
    ws.append(["Data: %s · Latex Serwis – oddział Wrocław" % datetime.datetime.now().strftime("%d.%m.%Y")])
    ws["A2"].font = Font(size=10, color="FF595959")
    ws.append([])
    ws.append(hdr)
    HR = ws.max_row
    money = '#,##0.00\\ "zł"'
    thin = Side(style="thin", color="FFBFBFBF"); B = Border(thin, thin, thin, thin)
    palette = ["FFC6EFCE", "FFFFCC99", "FFFFFFFF", "FF9BDCF5", "FFFFFF00", "FFE4DFEC", "FFFCE4D6", "FFDDEBF7"]
    regs = []
    for r in rows:
        if r["rej"] not in regs: regs.append(r["rej"])
    for r in rows:
        i = ws.max_row + 1; p = r["p"]
        wh = r["wymiana"]
        if p:
            ws.append([r["rej"], (r["pojazd"] + (" (%s)" % TYPY[r.get("typ")] if r.get("typ") in ("suv", "dostawczy") else "")).strip(), r["rozmiar"], r["rodzaj"], p["producent"].title(), p["model_oferta"], p["id"], p["indeks"], p["cena_brutto"], r["ilosc"], "=I%d*J%d" % (i, i), wh, r["tpms_kw"], r["przech_kw"], "=K%d+L%d+M%d+N%d" % (i, i, i, i), p["dot"], p["ilosc"], "; ".join(x for x in (r["tpms_op"], r["przech_op"]) if x)])
        else:
            ws.append([r["rej"], r["pojazd"], r["rozmiar"], r["rodzaj"], None, None, None, None, None, None, 0, wh, r["tpms_kw"], r["przech_kw"], "=K%d+L%d+M%d+N%d" % (i, i, i, i), None, None, "; ".join(x for x in (r["tpms_op"], r["przech_op"]) if x)])
        col = palette[regs.index(r["rej"]) % len(palette)]
        for c in ws[i]:
            c.fill = PatternFill("solid", fgColor=col); c.border = B
            if c.column in (9, 11, 12, 13, 14, 15): c.number_format = money
    for c in ws[HR]:
        c.font = Font(b=True, color="FFFFFFFF"); c.fill = PatternFill("solid", fgColor="FF305496")
        c.alignment = Alignment(wrap_text=True, horizontal="center", vertical="center"); c.border = B
    ws.row_dimensions[HR].height = 32
    r0 = ws.max_row + 2
    ws.cell(r0, 1, "PODSUMOWANIE WARIANTÓW (opony + wymiana + usługi)").font = Font(b=True, size=12)
    for (sez, k), var in sorted(variants.items(), key=lambda kv: vkey(kv[0])):
        r0 += 1
        ws.cell(r0, 1, "Wariant %s – %s" % (vlabel(variants, (sez, k)).upper(), ", ".join(var["modele"]))).font = Font(b=True)
        for col, val in ((11, var["opony"]), (12, var["wymiana"]), (13, var["tpms_kw"]), (14, var["przech_kw"]), (15, total(var))):
            c = ws.cell(r0, col, round(val, 2)); c.number_format = money; c.border = B
            c.fill = PatternFill("solid", fgColor="FFD9E1F2")
        ws.cell(r0, 15).font = Font(b=True)
    r0 += 2
    notes = ["Ceny brutto (VAT %g%%). Wymiana obejmuje demontaż, montaż i wyważenie (liczona za każde wymieniane koło)." % cfg["vat_proc"],
             "Ceny i stany pobrane z xPartner: %s." % datetime.datetime.now().strftime("%d.%m.%Y %H:%M"),
             "Gwarancja producenta na wady fabryczne, standardowo do 5 lat od daty produkcji; nie obejmuje uszkodzeń mechanicznych, jazdy na złym ciśnieniu i złej geometrii.",
             "Ceny ważne %d dni, z zastrzeżeniem dostępności." % cfg["waznosc_dni"]]
    for t in notes:
        ws.cell(r0, 1, t).font = Font(i=True, size=9, color="FF595959"); r0 += 1
    for col, w in zip("ABCDEFGHIJKLMNOPQR", [11, 18, 12, 13, 13, 30, 10, 10, 13, 6, 14, 14, 13, 13, 15, 7, 9, 40]):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "A%d" % (HR + 1)
    os.makedirs(OUT_DIR, exist_ok=True)
    klient = re.sub(r"[^\w\- ]", "", req.get("klient") or "klient").strip().replace(" ", "_") or "klient"
    oid = safe_oid(req.get("oid"))
    name = "Oferta_%s_%s.xlsx" % (klient, oid)
    path = os.path.join(OUT_DIR, name)
    old = (load_hist(oid) or {}).get("plik")
    if old and old != path and os.path.exists(old):
        try: os.remove(old)   # zmieniona nazwa klienta – usuń poprzednią wersję tej samej oferty
        except OSError: pass
    wb.save(path)
    return path

def safe_oid(o):
    o = re.sub(r"[^0-9_]", "", str(o or ""))
    return o or datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

def load_hist(oid):
    try:
        return HIST.get(safe_oid(oid)) if HIST else None
    except Exception:
        return None

def snap_ofert(rows):
    """Ceny i stany wybranych opon w chwili zapisu – do porównania przy ponownym otwarciu z historii."""
    out, byly = [], set()
    for r in rows:
        p = r.get("p")
        if p and p["id"] not in byly:
            byly.add(p["id"])
            out.append({"id": p["id"], "nazwa": p.get("nazwa", ""), "cena": p.get("cena_brutto", 0), "ilosc": int(p.get("ilosc") or 0)})
    return out


def zmiany_ofert(snap, rows):
    """Co się zmieniło od zapisu oferty: cena, stan, brak opony (lista dla żółtej ramki w Panelu)."""
    teraz, potrzeba = {}, {}
    for r in rows:
        p = r.get("p")
        if p:
            teraz[p["id"]] = p
            potrzeba[p["id"]] = potrzeba.get(p["id"], 0) + int(r.get("ilosc") or 0)
    out = []
    for s in snap or []:
        p = teraz.get(s.get("id"))
        if not p:
            out.append({"nazwa": s.get("nazwa", ""), "co": "niedostępna w xPartner lub nie w wynikach"})
            continue
        if abs(float(p.get("cena_brutto") or 0) - float(s.get("cena") or 0)) >= 0.5:
            out.append({"nazwa": s.get("nazwa", ""), "co": "cena %s → %s" % (pl(float(s.get("cena") or 0)), pl(float(p.get("cena_brutto") or 0))),
                        "w_gore": float(p.get("cena_brutto") or 0) > float(s.get("cena") or 0)})
        il = int(p.get("ilosc") or 0)
        if il < potrzeba.get(p["id"], 0):
            out.append({"nazwa": s.get("nazwa", ""), "co": "stan %d szt. (było %d) – za mało do oferty" % (il, int(s.get("ilosc") or 0)), "w_gore": True})
    return out


def save_hist(req, summ, path, rows=None):
    if not HIST:
        return
    oid = safe_oid(req.get("oid"))
    rec = {"osobno": req.get("osobno"), "marza": req.get("marza"), "rabat": req.get("rabat"), "ceny": req.get("ceny") or {},
           "rabat_wym": req.get("rabat_wym"), "ceny_wym": req.get("ceny_wym") or {},
           "oid": oid, "data": datetime.datetime.now().strftime("%d.%m.%Y %H:%M"), "klient": req.get("klient", ""),
           "pojazdy": req.get("pojazdy", []), "wybor": req.get("wybor", {}), "sel": req.get("sel", []),
           "warianty": summ, "plik": path, "oddzial": req.get("oddzial") or "", "snap": snap_ofert(rows or [])}
    hay = (rec["klient"] + " " + " ".join(v.get("rej", "") + " " + v.get("pojazd", "") + " " + v.get("rozmiar", "") for v in rec["pojazdy"])
           + " " + " ".join(m for w in summ for m in w.get("modele", []))).lower()
    HIST.save(oid, rec["klient"], rec, hay)

def list_hist(q=""):
    out = []
    try:
        recs = HIST.list(q) if HIST else []
    except Exception:
        recs = []
    for row in recs:
        r = row.get("dane") or {}
        if not r.get("oid"):
            continue
        out.append({"id": row.get("id"), "kto": row.get("kto") or row.get("owner") or "", "owner": row.get("owner") or "",
                    "oid": r["oid"], "data": r.get("data"), "klient": r.get("klient", ""),
                    "pojazdy": ", ".join(" ".join(x for x in (v.get("rej"), v.get("pojazd")) if x) or v.get("rozmiar", "") for v in r.get("pojazdy", [])),
                    "warianty": [{"wariant": w["wariant"], "modele": ", ".join(w["modele"]), "razem": w["razem"]} for w in r.get("warianty", [])],
                    "razem": max([w.get("razem", 0) for w in r.get("warianty", [])] or [0]),
                    "plik_ok": os.path.exists(r.get("plik") or ""),
                    "status": row.get("status") or "nowa", "status_at": row.get("status_at") or "", "link": bool(row.get("link_at")),
                    "otwarta": row.get("link_otwarta") or "", "odp": row.get("klient_odp") or None,
                    "oddzwon": do_oddzwonienia(row.get("status"), row.get("status_at"))})
    return out


STATUSY_OFERT = {"nowa": "Nowa", "wyslana": "Wysłana", "przyjeta": "Przyjęta", "odrzucona": "Odrzucona", "zamowiona": "Zamówiona"}
ODDZWON_DNI = 2
STRONA_KLIENTA = "https://djjuniord-boop.github.io/IntegraCRM/"   # strona z ofertą dla klienta (GitHub Pages, jak SERWIS QR)


def do_oddzwonienia(status, status_at, teraz=None):
    """Wysłana, a klient nie odpowiedział od 2 dni -> przypomnij, żeby zadzwonić."""
    if status != "wyslana" or not status_at:
        return False
    try:
        t = datetime.datetime.fromisoformat(str(status_at).replace("Z", "+00:00"))
    except ValueError:
        return False
    teraz = teraz or datetime.datetime.now(datetime.timezone.utc)
    return (teraz - t).total_seconds() >= ODDZWON_DNI * 86400


def link_dane(cfg, req, rows, oddzial, kto=""):
    """Migawka dla strony klienta: gotowe strony PDF każdego modelu (bez cen zakupu) + skrót do kart wyboru."""
    modele, byly = [], set()
    for r in rows:
        p = r.get("p")
        if not p or p["id"] in byly:
            continue
        byly.add(p["id"])
        d = pdf_dane(cfg, req, rows, p["id"], oddzial, kto, STRONA_KLIENTA + "logo.png")
        modele.append({"id": p["id"], "tytul": d["tytul"], "tag": d["tag"], "cena_szt": d["cena_szt"], "brutto": d["brutto"],
                       "mokra": p.get("mokra") or "", "opory": p.get("opory") or "", "halas": p.get("halas") or "",
                       "html": wypelnij(wzor_pdf(), d)})
    if not modele:
        raise ValueError("W ofercie nie ma opon – wybierz opony i przelicz ofertę.")
    d0 = pdf_dane(cfg, req, rows, modele[0]["id"], oddzial, kto, "")
    return {"nr": d0["nr"], "klient": d0["klient"], "wazna": d0["wazna"], "o_nazwa": d0["o_nazwa"], "o_tel": d0["o_tel"],
            "o_kom": [x["t"] for x in d0["o_kom"]], "kto": kto, "modele": modele}

def pl(x):
    s = "{:,.2f}".format(x).replace(",", " ").replace(".", ",")
    return s + " zł"

def email_text(cfg, req, rows, variants):
    kl = (req.get("klient") or "").strip()
    L = ["Dzień dobry,", "", "dziękujemy za zapytanie. W załączeniu przesyłamy ofertę na zakup i wymianę opon" + (" dla %s" % kl if kl else "") + ".", ""]
    per_car = any(r.get("rej") or r.get("pojazd") for r in rows if r["p"])
    by_var = {}
    for r in rows:
        if r["p"]: by_var.setdefault(r["wariant"], []).append(r)
    for key in sorted(variants, key=vkey):
        sez, k = key; var = variants[key]
        L.append("WARIANT: " + vlabel(variants, key).upper())
        if per_car:
            for r in by_var.get(key, []):
                p = r["p"]; kto = " ".join(x for x in (r.get("rej"), r.get("pojazd")) if x) or r["rozmiar"]
                L.append("• %s: %s %s %s %s – %s brutto/szt. × %d = %s" % (kto, p["producent"].title(), p["model_oferta"], r["rozmiar"], p["indeks"], pl(p["cena_brutto"]), r["ilosc"], pl(r["opony"])))
        else:
            seen = {}
            for r in by_var.get(key, []):
                p = r["p"]; kk = (p["id"])
                seen.setdefault(kk, [p, r["rozmiar"], 0]); seen[kk][2] += r["ilosc"]
            for p, s, q in seen.values():
                L.append("• %s %s %s %s – %s brutto/szt. × %d = %s" % (p["producent"].title(), p["model_oferta"], s, p["indeks"], pl(p["cena_brutto"]), q, pl(p["cena_brutto"] * q)))
        parts = []
        if var["opony"]: parts.append("Opony: " + pl(var["opony"]))
        if var["wymiana"]: parts.append("Wymiana: " + pl(var["wymiana"]))
        if var["tpms_kw"]: parts.append("Czujniki TPMS: " + pl(var["tpms_kw"]))
        if var["przech_kw"]: parts.append("Przechowalnia: " + pl(var["przech_kw"]))
        L.append(" | ".join(parts + ["RAZEM: %s brutto" % pl(total(var))]))
        L.append("")
    us = [r for r in rows if r["uslugi"]]
    if us:
        L.append("USŁUGI DODATKOWE")
        seen = set()
        for r in us:
            k = (r["rej"], r["rozmiar"])
            if k in seen: continue
            seen.add(k)
            kto = " ".join(x for x in (r["pojazd"], r["rej"]) if x) or r["rozmiar"]
            if r["tpms_kw"]: L.append("• %s – %s = %s" % (kto, r["tpms_op"], pl(r["tpms_kw"])))
            if r["przech_kw"]: L.append("• %s – %s = %s" % (kto, r["przech_op"], pl(r["przech_kw"])))
        L.append("")
    L += ["GWARANCJA",
          "• Gwarancja producenta na wady fabryczne (materiałowe i produkcyjne) – standardowo do 5 lat od daty produkcji.",
          "• Nie obejmuje uszkodzeń mechanicznych (przebicia, przecięcia, uderzenia), jazdy na niewłaściwym ciśnieniu, złej geometrii ani naturalnego zużycia.",
          "• Reklamację zgłaszają Państwo w naszym serwisie z dowodem zakupu; oponę przekazujemy do oceny producenta.", "",
          "Ceny ważne %d dni, z zastrzeżeniem dostępności." % cfg["waznosc_dni"], "",
          "Z poważaniem,", cfg["podpis"]]
    return "\n".join(L)

# ---------------------------------------------------------------- HTTP

# ---------------------------------------------------------------- szablon Excel z pojazdami
SZABLON_KOL = ["Rejestracja", "Marka", "Model", "Rozmiar", "Ilość opon", "Typ auta", "Wymiana", "Czujniki TPMS", "Przechowalnia"]


def szablon_xlsx():
    """Pusty szablon zapytania (lista pojazdów) z listami wyboru i przykładem. Zwraca ścieżkę pliku."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation
    wb = Workbook()
    ws = wb.active
    ws.title = "Pojazdy"
    ws.append(SZABLON_KOL)
    ws.append(["DW5444LW", "Skoda", "Octavia", "205/55 R16", 4, "osobowy", "TAK", "NIE", "NIE"])
    for c in ws[1]:
        c.font = Font(b=True, color="FFFFFFFF")
        c.fill = PatternFill("solid", fgColor="FFE30613")
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for c in ws[2]:
        c.font = Font(i=True, color="FF7A7A7A")
    for col, w in zip("ABCDEFGHI", [14, 14, 16, 14, 11, 13, 10, 13, 16]):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "A2"
    for rng, lst in (("F2:F500", '"osobowy,SUV,dostawczy"'), ("G2:G500", '"TAK,NIE"'),
                     ("H2:H500", '"TAK,NIE"'), ("I2:I500", '"TAK,NIE"')):
        dv = DataValidation(type="list", formula1=lst, allow_blank=True)
        ws.add_data_validation(dv)
        dv.add(rng)
    dv = DataValidation(type="whole", operator="between", formula1="0", formula2="20", allow_blank=True)
    ws.add_data_validation(dv)
    dv.add("E2:E500")
    inf = wb.create_sheet("Instrukcja")
    for line in ("Jak wypełnić:",
                 "• Jeden pojazd = jeden wiersz w arkuszu „Pojazdy”. Wiersz 2 to przykład – nadpisz go albo usuń.",
                 "• Rozmiar w dowolnym zapisie: 205/55 R16, 205/55 16 albo 2055516. To jedyna wymagana kolumna.",
                 "• Ilość opon: 0 = auto tylko na wymianę (bez nowych opon). Puste = 4.",
                 "• Typ auta (osobowy / SUV / dostawczy) oraz Wymiana, Czujniki TPMS, Przechowalnia (TAK / NIE) – wybierz z listy.",
                 "• Czujniki TPMS = TAK: czujnik do każdej nowej opony (przy samej wymianie – 4). Przechowalnia = TAK: przechowanie opon.",
                 "• Zapisz plik i w programie kliknij „📤 Wczytaj z Excela”."):
        inf.append([line])
    inf.column_dimensions["A"].width = 100
    inf["A1"].font = Font(b=True, size=13)
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, "Szablon_zapytania_opony.xlsx")
    try:
        wb.save(path)
    except PermissionError:   # plik otwarty w Excelu
        path = os.path.join(OUT_DIR, "Szablon_zapytania_opony_%s.xlsx" % datetime.datetime.now().strftime("%H%M%S"))
        wb.save(path)
    return path


def _norm_head(h):
    return re.sub(r"[^a-ząćęłńóśźż]", "", str(h or "").lower())


def czytaj_xlsx(data: bytes):
    """Pojazdy z pliku Excel: najpierw po nagłówkach (szablon albo podobna tabela), inaczej każdy wiersz jak tekst."""
    import io
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    ws = wb["Pojazdy"] if "Pojazdy" in wb.sheetnames else wb.worksheets[0]
    rows = [["" if v is None else str(v).strip() for v in r] for r in ws.iter_rows(values_only=True)]
    rows = [r for r in rows if any(r)]
    if not rows:
        return []
    alias = {"rej": ("rejestracja", "nrrej", "nrrejestracyjny", "numerrejestracyjny", "tablica", "rej"),
             "marka": ("marka", "producentauta"), "model": ("model", "pojazd", "samochód", "samochod", "auto"),
             "rozmiar": ("rozmiar", "rozmiaropon", "rozmiaropony", "opony", "opona"),
             "ilosc": ("iloscopon", "ilośćopon", "ilosc", "ilość", "szt", "sztuk"),
             "typ": ("typauta", "typ", "rodzajauta"), "wym": ("wymiana", "montaż", "montaz"),
             "tpms": ("czujnikitpms", "tpms", "czujniki"), "przech": ("przechowalnia", "depozyt"),
             "tak": ("wymaganowychopon", "noweopony", "nowe")}
    head = [_norm_head(h) for h in rows[0]]
    col = {}
    for key, names in alias.items():
        for i, h in enumerate(head):
            if h in names and i not in col.values():
                col[key] = i
                break
    out = []
    if "rozmiar" in col:
        for r in rows[1:]:
            g = lambda k: r[col[k]] if k in col and col[k] < len(r) else ""
            size = norm_size(g("rozmiar"))
            if not size:
                continue
            il_txt = g("ilosc")
            try:
                il = int(float(il_txt.replace(",", "."))) if il_txt != "" else 4
            except ValueError:
                il = 4
            if g("tak").upper() == "NIE":
                il = 0
            typ = g("typ").lower()
            typ = "suv" if ("suv" in typ or "4x4" in typ) else "dostawczy" if "dostaw" in typ else "osobowy"
            pr = g("przech").lower()
            pr = ("kola" if pr.startswith(("koł", "kol")) else "opony" if pr.startswith(("opon", "tak", "t", "1", "x"))
                  and not pr.startswith("tr") else "")
            tv = g("tpms").strip().upper()
            if tv in ("TAK", "T", "X", "PRAWDA", "TRUE"):
                tp = il if il > 0 else 4
            else:
                try:
                    tp = max(0, min(8, int(float(tv.replace(",", ".") or 0))))
                except ValueError:
                    tp = 0
            wym = g("wym").upper() in ("TAK", "T", "1", "X", "PRAWDA", "TRUE") or (il == 0 and g("tak").upper() == "NIE")
            pojazd = " ".join(x.title() if not (len(x) <= 3 and x.isalpha()) else x.upper() for x in (g("marka"), g("model")) if x)
            out.append({"rej": re.sub(r"\s+", "", g("rej")).upper(), "pojazd": pojazd, "rozmiar": size, "ilosc": il,
                        "nowe": il > 0, "wymiana": wym, "typ": typ, "tpms": tp, "przech": pr})
        return out
    return parse_request_text("\n".join(" ".join(r) for r in rows))


# ---------------------------------------------------------------- obsługa poleceń strony (window.pywebview.api.call)
class Odpowiedz(Exception):
    def __init__(self, code, body):
        super().__init__(str(body))
        self.code, self.body = code, body


def _in_out_dir(p):
    return bool(p) and os.path.dirname(os.path.abspath(p)) == os.path.abspath(OUT_DIR)


# ------------------------------------------------------------ PDF oferty (jeden model opony)
# Wzór pdf_wzor.html jest wspólny z aplikacją Android (mobile/www/pdf_wzor.js – kopia, test zgodności pilnuje).
PDF_WZOR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pdf_wzor.html")
OSTATNIA = {}   # ostatnio wyliczona oferta (dla /api/pdf): req, wiersze
EU_KOLORY = [("A", "#00A651", "#fff"), ("B", "#4CB848", "#fff"), ("C", "#BFD730", "#111"), ("D", "#FFF200", "#111"), ("E", "#F7941D", "#fff")]
KLASA_PDF = {"PREMIUM": "PREMIUM", "MIDDLE": "ŚREDNIA", "BUDGET": "BUDŻET"}
EPREL_IMG = "https://eprel.ec.europa.eu/api/products/tyres/%s/labels?format=PNG"   # oficjalna etykieta UE z kodem QR
ODDZIAL_POLA = ("nazwa", "adres", "tel", "www", "email")

def _esc(v):
    return (str(v).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#39;"))

def _szukaj(stos, k):
    for c in reversed(stos):
        if isinstance(c, dict) and k in c:
            return c[k]
    return None

_TAG = re.compile(r"\{\{(\{?)([#^/>]?)\s*([\w.]+)\s*\}?\}\}")

def wypelnij(tpl, ctx, stos=None):
    """Wypełnia wzór: {{x}} (tekst zabezpieczony), {{{x}}}, {{#x}}…{{/x}} (gdy jest / każdy element listy), {{^x}}…{{/x}}."""
    stos = (stos or []) + [ctx]
    out, i = [], 0
    while True:
        m = _TAG.search(tpl, i)
        if not m:
            out.append(tpl[i:]); break
        out.append(tpl[i:m.start()])
        raw, typ, k = m.group(1), m.group(2), m.group(3)
        if typ in ("#", "^"):
            # znajdź pasujące zamknięcie (z zagnieżdżeniem tej samej nazwy)
            glab, j, koniec_wn = 1, m.end(), m.end()
            zn = re.compile(r"\{\{([#^/])\s*" + re.escape(k) + r"\s*\}\}")
            while glab:
                n = zn.search(tpl, j)
                if not n:
                    raise ValueError("wzór: brak {{/%s}}" % k)
                glab += -1 if n.group(1) == "/" else 1
                koniec_wn, j = n.start(), n.end()
            wn, v = tpl[m.end():koniec_wn], _szukaj(stos, k)
            if typ == "^":
                if not v:
                    out.append(wypelnij(wn, {}, stos))
            elif isinstance(v, list):
                out.extend(wypelnij(wn, e if isinstance(e, dict) else {".": e}, stos) for e in v)
            elif v:
                out.append(wypelnij(wn, v if isinstance(v, dict) else {}, stos))
            i = j
            continue
        v = _szukaj(stos, k)
        out.append("" if v is None or v is False else (str(v) if raw else _esc(v)))
        i = m.end()
    return "".join(out)

def wzor_pdf():
    """Wzór + fragmenty z dołu pliku (<!--nazwa-->…) wstawione w miejsca {{>nazwa}}."""
    with open(PDF_WZOR, encoding="utf-8") as f:
        czesci = re.split(r"<!--(\w+)-->", f.read())
    t, frag = czesci[0], {czesci[i]: czesci[i + 1].strip() for i in range(1, len(czesci) - 1, 2)}
    for _ in range(3):
        for k, v in frag.items():
            t = t.replace("{{>%s}}" % k, v)
    return t

PDF_POROWNANIE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pdf_porownanie.html")
KLASY_EU = "ABCDE"


def _liczba(s):
    """'1 780,00 zł' -> 1780.0 (kwoty z pdf_dane)."""
    try:
        return float(re.sub(r"[^\d,]", "", str(s)).replace(",", "."))
    except ValueError:
        return 0.0


def porownanie_dane(cfg, req, rows, pids, oddzial, kto="", logo=""):
    """2–3 modele obok siebie: od najtańszego; plusy liczone względem najtańszego z etykiety UE (orientacyjnie)."""
    pids = list(dict.fromkeys(int(x) for x in pids))
    if not 2 <= len(pids) <= 3:
        raise ValueError("Porównanie obejmuje 2 lub 3 modele opon – zmień wybór.")
    D = sorted((pdf_dane(cfg, req, rows, pid, oddzial, kto, logo) for pid in pids), key=lambda d: _liczba(d["brutto"]))
    P = {r["p"]["id"]: r["p"] for r in rows if r.get("p")}
    poziomy = ["EKONOMICZNA", "POLECANA", "PREMIUM"] if len(D) == 3 else ["EKONOMICZNA", "PREMIUM"]
    baza = P.get(int(D[0]["xp_id"]), {})
    kol = []
    for i, d in enumerate(D):
        p = P.get(int(d["xp_id"]), {})
        plusy = []
        if i:
            km = KLASY_EU.find(baza.get("mokra") or "?") - KLASY_EU.find(p.get("mokra") or "?")
            if p.get("mokra") and baza.get("mokra") and km > 0:
                plusy.append("hamowanie na mokrym o %d kl. lepsze – do ok. %s m krócej z 80 km/h" % (km, ("%g" % (4.5 * km)).replace(".", ",")))
            ko = KLASY_EU.find(baza.get("opory") or "?") - KLASY_EU.find(p.get("opory") or "?")
            if p.get("opory") and baza.get("opory") and ko > 0:
                plusy.append("opory toczenia o %d kl. niższe – ok. %d l paliwa mniej na 40 000 km" % (ko, 37 * ko))
            if p.get("halas") and baza.get("halas") and int(baza["halas"]) - int(p["halas"]) >= 2:
                plusy.append("ciszej o %d dB" % (int(baza["halas"]) - int(p["halas"])))
        kol.append({"poziom": poziomy[i], "best": (i == 1) if len(D) == 3 else (i == 1), "tytul": d["tytul"],
                    "sezon": d["tag"].replace("OPONA ", "", 1), "indeks": d["indeks"], "dot": d["dot"], "snieg": d["snieg"],
                    "mokra": p.get("mokra") or "", "opory": p.get("opory") or "", "halas": d["halas"],
                    "plusy": [{"t": t} for t in plusy], "cena_szt": d["cena_szt"], "brutto": d["brutto"], "netto": d["netto"]})
    d0 = D[0]
    uslugi = [x["nazwa"] for x in d0["pozycje"] if not x["nazwa"].startswith("Opona")]
    return dict({k: d0[k] for k in ("logo", "nr", "data", "wazna", "o_nazwa", "o_adres", "o_tel", "o_www", "o_kom", "klient", "pojazd",
                                     "kto", "rozmiar", "vat_proc", "rabaty")},
                kolumny=kol, uslugi=", ".join(uslugi) if uslugi else "same opony (bez usług)")


def porownanie_html(cfg, req, rows, pids, oddzial, kto="", logo=""):
    with open(PDF_POROWNANIE, encoding="utf-8") as f:
        return wypelnij(f.read(), porownanie_dane(cfg, req, rows, pids, oddzial, kto, logo))


def _skala(lit):
    return [{"l": l, "kolor": k, "tekst": t, "szer": 34 + 9 * i, "on": l == lit} for i, (l, k, t) in enumerate(EU_KOLORY)]

def _data_oid(oid, dni=0):
    try:
        d = datetime.date(int(oid[0:4]), int(oid[4:6]), int(oid[6:8]))
    except (ValueError, TypeError):
        d = datetime.date.today()
    return (d + datetime.timedelta(days=dni)).strftime("%d.%m.%Y")

def pdf_dane(cfg, req, rows, pid, oddzial, kto="", logo=""):
    """Dane PDF dla jednego modelu opony: pojazdy z tą oponą, każda usługa osobno, rabat, netto/VAT/brutto."""
    R = [r for r in rows if r.get("p") and r["p"]["id"] == pid]
    if not R:
        raise ValueError("Tej opony nie ma w ofercie – wygeneruj ofertę ponownie.")
    if not oddzial or not all((oddzial.get(k) or "").strip() for k in ("nazwa", "adres", "tel")):
        raise ValueError("Brak danych oddziału (nazwa, adres, telefon) – administrator uzupełnia je w Panelu: Ustawienia → Oddziały.")
    p = R[0]["p"]
    vat = float(cfg.get("vat_proc") or 23)
    try: rab = max(0.0, min(90.0, float(req.get("rabat") or 0)))
    except ValueError: rab = 0.0
    przed_szt = p["cena_brutto"] if (p.get("recznie") or not rab) else sell_price(cfg, p["netto"])
    il = sum(int(r.get("ilosc") or 0) for r in R)
    poz = [{"nazwa": "Opona " + p["nazwa"], "q": il, "j": "szt.", "c": przed_szt, "po": p["cena_brutto"],
            "r": rab if przed_szt > p["cena_brutto"] else 0}]
    kola = int(cfg["kola_na_auto"])
    rw, _ = rabat_wymiany(req)
    wym, rabat_wym_kw = {}, 0.0
    for r in R:
        if r.get("wym_tak", r.get("wymiana")):
            n = int(r.get("ilosc") or 0) or kola
            dia = (re.search(r"R(\d{2})", r.get("rozmiar") or "") or [None, ""])[1]
            typ = r.get("typ") or "osobowy"
            szt = r.get("wym_szt", round(r["wymiana"] / n, 2))
            c = r.get("wym_cennik", szt) if (rw and not r.get("wym_recznie")) else szt
            rabat_wym_kw += (c - szt) * n
            key = (dia, typ, round(c, 2), round(szt, 2))
            wym[key] = wym.get(key, 0) + n
    for (dia, typ, c, szt), n in wym.items():
        poz.append({"nazwa": "Wymiana opon – demontaż, montaż, wyważenie (R%s%s)" % (dia, "" if typ == "osobowy" else ", " + TYPY.get(typ, typ)),
                    "q": n, "j": "szt.", "c": c, "po": szt, "r": rw if c > szt else 0})
    n_tp = sum(int(r.get("tpms") or 0) for r in R)
    if n_tp:
        poz.append({"nazwa": "Czujnik ciśnienia TPMS (z montażem)", "q": n_tp, "j": "szt.", "c": float(cfg["tpms_cena"])})
    dep = {}
    for r in R:
        if r.get("przech_kw"):
            key = (r["przech_op"], r["przech_kw"])
            dep[key] = dep.get(key, 0) + 1
    for (op, c), n in dep.items():
        poz.append({"nazwa": "Depozyt – " + op[:1].lower() + op[1:] + ", 1 sezon", "q": n, "j": "kpl.", "c": float(c)})
    przed = round(sum(x["q"] * x["c"] for x in poz), 2)
    rabat_kw = round((przed_szt - p["cena_brutto"]) * il, 2)
    rabat_wym_kw = round(rabat_wym_kw, 2)
    brutto = round(przed - rabat_kw - rabat_wym_kw, 2)
    netto = round(brutto / (1 + vat / 100), 2)
    oid = str(req.get("oid") or "")
    poj = []
    for r in R:
        t = " · ".join(x for x in ((r.get("pojazd") or "").strip(), (r.get("rej") or "").strip().upper()) if x)
        if t and t not in poj:
            poj.append(t)
    sez = (p.get("sezon") or "").upper()
    cechy = dict(CECHY.get(pid) or {}, **{k: v for k, v in (p.get("attrs") or {}).items() if v})
    hk = (cechy.get("Hałas") or "").strip()[:1].upper()
    eprel = re.sub(r"\D", "", cechy.get("Kod EPREL") or "")[:12]
    eu = bool(p.get("mokra") or p.get("opory") or p.get("halas"))
    vp = ("%g" % vat).replace(".", ",")
    return {
        "logo": logo, "nr": "OF/%s/%s/%s-%s" % (oid[0:4], oid[4:6], oid[6:8], oid[9:13]) if len(oid) >= 13 else "OF/" + oid,
        "data": _data_oid(oid), "wazna": _data_oid(oid, int(cfg.get("waznosc_dni") or 7)),
        "o_nazwa": oddzial.get("nazwa", ""), "o_adres": oddzial.get("adres", ""), "o_tel": oddzial.get("tel", ""),
        "o_www": oddzial.get("www", ""), "o_email": oddzial.get("email", ""),
        "o_kom": [{"t": t.strip()} for t in re.split(r"[,;]", oddzial.get("kom", "") or "") if t.strip()],
        "xp_id": str(p.get("id") or ""),
        "klient": (req.get("klient") or "").strip(), "pojazd": ", ".join(poj), "kto": kto,
        "tag": "OPONA " + sez + (" · " + KLASA_PDF[p["klasa"]] if p.get("klasa") in KLASA_PDF else "") + (" · DEMO" if p.get("demo") else ""),
        "tytul": p["nazwa"], "producent": p.get("producent", ""), "model": p.get("model", ""), "rozmiar": R[0].get("rozmiar", ""),
        "indeks": p.get("indeks", ""), "dot": p.get("dot", ""), "foto": p.get("foto", ""), "ean": p.get("ean", ""),
        "eu": eu or bool(eprel), "ma_opory": bool(p.get("opory")), "ma_mokra": bool(p.get("mokra")),
        "skala_opory": _skala(p.get("opory")), "skala_mokra": _skala(p.get("mokra")),
        "halas": p.get("halas") or "", "halas_klasa": hk if hk in ("A", "B", "C") else "",
        "snieg": bool((cechy.get("Przyczepność na śniegu") or "").strip()), "lod": bool((cechy.get("Przyczepność na lodzie") or "").strip()),
        "eprel": eprel, "eprel_img": EPREL_IMG % eprel if eprel else "",
        "cena_szt": pl(p["cena_brutto"]), "cena_szt_netto": pl(round(p["cena_brutto"] / (1 + vat / 100), 2)),
        "pozycje": [{"nazwa": x["nazwa"], "ilosc": "%d %s" % (x["q"], x["j"]), "cena": pl(x["c"]),
                     "rab": ("−" + ("%g" % x["r"]).replace(".", ",") + "%") if x.get("r") else "",
                     "cena_po": pl(x.get("po", x["c"])), "wartosc": pl(round(x["q"] * x.get("po", x["c"]), 2))} for x in poz],
        "oszczednosc": pl(round(rabat_kw + rabat_wym_kw, 2)), "cena_szt_przed": pl(przed_szt) if przed_szt > p["cena_brutto"] else "",
        "rabat": (("%g" % rab).replace(".", ",") + "%") if rabat_kw > 0 else "", "przed": pl(przed), "rabat_kw": pl(rabat_kw),
        "rabat_wym": (("%g" % rw).replace(".", ",") + "%") if rabat_wym_kw > 0 else "", "rabat_wym_kw": pl(rabat_wym_kw),
        "rabaty": rabat_kw > 0 or rabat_wym_kw > 0,
        "netto": pl(netto), "vat": pl(round(brutto - netto, 2)), "vat_proc": vp, "brutto": pl(brutto),
    }

def pdf_html(cfg, req, rows, pid, oddzial, kto="", logo=""):
    return wypelnij(wzor_pdf(), pdf_dane(cfg, req, rows, pid, oddzial, kto, logo))

def polacz_strony(strony):
    """Kilka PDF-ów (pełne strony HTML z tego samego wzoru) -> jeden dokument, każda opona na osobnej stronie A4."""
    if len(strony) == 1:
        return strony[0]
    glowa = strony[0].split("<body>", 1)[0]
    srodki = [h.split("<body>", 1)[1].rsplit("</body>", 1)[0] for h in strony]
    styl = "<style>.page{break-after:page}.page:last-of-type{break-after:auto}</style>"
    return glowa.replace("</head>", styl + "</head>", 1) + "<body>" + "".join(srodki) + "</body></html>"

def oddzial_oferty(req):
    """Oddział do PDF: tylko z przypisanych do konta (KONTO['oddzialy']); przy kilku – wybrany w ofercie."""
    moje = KONTO.get("oddzialy") or []
    dane = KONTO.get("oddzialy_dane") or {}
    if not moje:
        raise ValueError("Twoje konto nie ma przypisanego oddziału – poproś administratora (UŻYTKOWNICY → konto → oddziały).")
    o = req.get("oddzial") if req.get("oddzial") in moje else moje[0]
    return o, dict(dane.get(o) or {}, nazwa=(dane.get(o) or {}).get("nazwa") or o)


def opis_pol(items):
    """Do testu połączenia: co xPartner podaje przy produkcie (zdjęcie, EAN, etykieta UE)."""
    if not items:
        return ""
    p = items[0]
    et = [k for k in ("Opory toczenia", "Przyczepność na mokrej nawierzchni", "Poziom hałasu", "Hałas") if p["attrs"].get(k)]
    return ("\nZdjęcie opony: %s · EAN: %s · etykieta UE: %s\nPola produktu: %s\nCechy: %s" % (
        "TAK" if p.get("foto") else "brak", "TAK" if p.get("ean") else "brak", ", ".join(et) or "brak",
        ", ".join(p.get("pola") or []), ", ".join(sorted(p["attrs"]))))

def moze_zamawiac():
    return bool(KONTO.get("admin") or KONTO.get("zamawianie"))


ZAMAWIAM = threading.Lock()   # jedno zamówienie naraz – drugi klik nie wyśle drugiego zamówienia


def koszyk_route(route, body, cfg):
    from oferty import koszyk as K
    if not moze_zamawiac():
        return 403, {"error": "Brak uprawnienia „Zamawianie w xPartner” – poproś administratora (UŻYTKOWNICY → Moduły)."}
    try:
        if route == "/api/koszyk/adresy":
            return 200, {"adresy": K.adresy(cfg, KONTO.get("oddzialy_konta") or KONTO.get("oddzialy") or [])}
        if route == "/api/koszyk/odswiez":
            return 200, {"pozycje": K.odswiez(cfg, body.get("pozycje") or [], get_product), "czas": time.strftime("%H:%M")}
        if route == "/api/koszyk/zamow":
            if not ZAMAWIAM.acquire(blocking=False):
                return 409, {"error": "Zamówienie jest właśnie wysyłane – poczekaj na wynik."}
            try:
                xml_txt = K.order_xml(body)
                spr = [p for p in K.odswiez(cfg, body.get("pozycje") or [], get_product) if not p["ok"]]
                if spr:   # zalecenie xPartner: stany sprawdzone tuż przed zamówieniem
                    return 409, {"error": "Zmieniły się stany w xPartner – popraw koszyk.", "pozycje_zle": spr}
                zam, uwagi = K.czytaj_wynik(K.wyslij(cfg, xml_txt))
            finally:
                ZAMAWIAM.release()
            nr = ", ".join(z["nr"] for z in zam)
            if KONTO.get("dziennik"):
                KONTO["dziennik"]("zamówienie", nr, {"numer": body.get("numer") or "", "pozycje": body.get("pozycje"),
                                                     "dostawa": body.get("adres_opis") or "", "kto": KONTO.get("kto") or ""})
            return 200, {"zamowienia": zam, "uwagi": uwagi}
    except K.Blad as e:
        return 400, {"error": str(e)}
    except Exception as e:   # błąd xPartner (zamowienia.Blad) – bez treści innych błędów (adres z loginem)
        return 502, {"error": str(e) if e.__class__.__name__ == "Blad" else "Brak odpowiedzi xPartner (%s)" % e.__class__.__name__}
    return 404, {"error": "Nieznane polecenie"}


def handle(path, body=None, open_path=None):
    """Polecenie strony -> (kod, odpowiedź). open_path(ścieżka) otwiera plik/folder w Windows."""
    u = urllib.parse.urlparse(path)
    qs = urllib.parse.parse_qs(u.query)
    route = u.path
    cfg = load_cfg()
    ucz_marki(cfg)
    try:
        if route.startswith("/api/koszyk/"):
            return koszyk_route(route, body or {}, cfg)
        if body is None:
            if route == "/api/cfg":
                c = dict(cfg)
                c["login"] = "tak" if cfg.get("login") else ""
                c["marki_xp"] = MARKI_STALE
                c["password"] = ""
                c["oddzialy"], c["oddzialy_dane"], c["admin"] = KONTO.get("oddzialy") or [], KONTO.get("oddzialy_dane") or {}, bool(KONTO.get("admin"))
                c["zamowienia"] = bool(KONTO.get("admin") or KONTO.get("zamowienia"))
                c["zamawianie"] = moze_zamawiac()
                return 200, c
            if route in ("/api/zamowienia", "/api/zamkniete", "/api/faktury", "/api/faktura"):
                if not (KONTO.get("admin") or KONTO.get("zamowienia")):
                    return 403, {"error": "Brak dostępu do zamówień – poproś administratora (UŻYTKOWNICY → moduł Zamówienia)."}
                from oferty import zamowienia
                return zamowienia.handle(route, {k: v[0] for k, v in qs.items()}, cfg, bool(KONTO.get("admin")), KONTO.get("oddzialy") or [])
            if route == "/api/history":
                if qs.get("id"):
                    r = HIST.get_id(qs["id"][0]) if HIST else None
                    return (200, r) if r else (404, {"error": "Brak oferty"})
                return 200, {"lista": list_hist(qs.get("q", [""])[0]), "admin": bool(getattr(HIST, "admin", False)),
                             "me": (getattr(HIST, "me", "") or "").lower()}
            if route == "/api/openfile":
                r = (HIST.get_id((qs.get("id") or [""])[0]) if HIST else None) or {}
                p = r.get("plik") or ""
                if _in_out_dir(p) and os.path.exists(p) and open_path:
                    open_path(p)
                    return 200, {"ok": True}
                return 404, {"error": "Plik nie istnieje na tym komputerze"}
            if route == "/api/open":
                os.makedirs(OUT_DIR, exist_ok=True)
                if open_path:
                    open_path(OUT_DIR)
                return 200, {"ok": True}
            return 404, {"error": "404"}
        if route == "/api/cfg":
            for k in DEFAULT_CFG:
                if k in body:
                    cfg[k] = body[k]
            save_cfg(cfg)
            return 200, {"ok": True}
        if route == "/api/test":
            count, items = api_call(cfg, productName="205/55 R16", resultsPerPage=1)
            return 200, {"ok": True, "msg": "Połączono z xPartner. Przykładowe zapytanie zwróciło %d produktów." % count + opis_pol(items)}
        if route == "/api/pdf":
            if not OSTATNIA.get("rows"):
                return 400, {"error": "Najpierw wygeneruj ofertę."}
            # id – jedna opona; ids – kilka opon w jednym pliku (strona na oponę)
            ids = [int(x) for x in (body.get("ids") or [body.get("id") or 0])][:30]
            for pid in ids:
                if pid not in CECHY and KONTO.get("katalog_cechy"):
                    try:
                        zapamietaj_cechy({"id": pid, "attrs": KONTO["katalog_cechy"](pid) or {}})
                    except Exception:
                        pass
            o, dane = oddzial_oferty({"oddzial": body.get("oddzial") or OSTATNIA["req"].get("oddzial")})
            if body.get("porownanie"):
                return 200, {"html": porownanie_html(cfg, OSTATNIA["req"], OSTATNIA["rows"], ids, dane, KONTO.get("kto") or "", body.get("logo") or ""),
                             "oddzial": o, "stron": 1}
            strony = [pdf_html(cfg, OSTATNIA["req"], OSTATNIA["rows"], pid, dane, KONTO.get("kto") or "", body.get("logo") or "") for pid in ids]
            return 200, {"html": polacz_strony(strony), "oddzial": o, "stron": len(strony)}
        if route == "/api/link":
            if not (HIST and hasattr(HIST, "link")):
                return 500, {"error": "Link wymaga zapisu w historii (zaloguj się ponownie)."}
            if not OSTATNIA.get("rows"):
                return 400, {"error": "Najpierw przelicz ofertę."}
            o, dane = oddzial_oferty({"oddzial": body.get("oddzial") or OSTATNIA["req"].get("oddzial")})
            oid = safe_oid(OSTATNIA["req"].get("oid"))
            try:
                ld = link_dane(cfg, OSTATNIA["req"], OSTATNIA["rows"], dane, KONTO.get("kto") or "")
                tok = HIST.link(oid, ld)
            except Exception as e:
                msg = str(e)
                if "oferty_link" in msg or "404" in msg or "PGRST202" in msg:
                    msg = "Baza nie ma jeszcze funkcji linków – administrator musi wkleić plik SQL (supabase/oferty_status_link_2026-11-08.sql)."
                return 500, {"error": msg}
            url = STRONA_KLIENTA + "oferta.html#" + str(tok)
            tel = o and (dane or {}).get("tel") or ""
            sms = "Dzień dobry, oferta na opony od Latex Serwis: %s (ważna do %s). Wybierz model i kliknij „Akceptuję” – oddzwonimy.%s" % (
                url, ld["wazna"], (" Tel. " + tel) if tel else "")
            return 200, {"url": url, "sms": sms, "wazna": ld["wazna"]}
        if route == "/api/status":
            st = body.get("status")
            if st not in STATUSY_OFERT or not HIST or not hasattr(HIST, "status"):
                return 400, {"error": "Zły status"}
            try:
                HIST.status(safe_oid(body.get("oid")), st)
            except Exception:
                return 500, {"error": "Nie udało się zmienić statusu – administrator musi wkleić plik SQL (supabase/oferty_status_link_2026-11-08.sql)."}
            return 200, {"ok": True}
        if route == "/api/quick":
            return 200, parse_quick(body.get("text", ""))
        if route == "/api/szablon":
            path_s = szablon_xlsx()
            if open_path:
                open_path(path_s)
            return 200, {"plik": path_s}
        if route == "/api/xlsx":
            import base64
            try:
                poj = czytaj_xlsx(base64.b64decode(body.get("b64", "")))
            except Exception:
                return 400, {"error": "Nie udało się odczytać pliku – zapisz go w Excelu jako .xlsx (np. z szablonu)."}
            if not poj:
                return 400, {"error": "W pliku nie znalazłem żadnego rozmiaru opony (np. 205/55 R16). Użyj szablonu."}
            return 200, {"pojazdy": poj}
        if route == "/api/parse":
            txt = body.get("text", "")
            q = parse_quick(txt)
            return 200, {"pojazdy": parse_request_text(txt), "kryteria": {k: q[k] for k in ("sezony", "klasy", "producenci", "runflat")}}
        if route == "/api/search":
            return 200, do_search(cfg, body)
        if route == "/api/offer":
            rows, variants, warns = build_offer(cfg, body)
            OSTATNIA.clear(); OSTATNIA.update(req=body, rows=rows)
            if not rows:
                return 400, {"error": "Brak wybranych opon."}
            path_x = ""   # arkusz Excel z ofertą – wyłączony (decyzja właściciela 2026-11-09); oferta = PDF + historia w bazie
            summ = [{"wariant": vlabel(variants, (s, k)), "modele": v["modele"], "opony": round(v["opony"], 2),
                     "wymiana": round(v["wymiana"], 2), "tpms": round(v["tpms_kw"], 2), "przech": round(v["przech_kw"], 2),
                     "razem": round(total(v), 2)} for (s, k), v in sorted(variants.items(), key=lambda kv: vkey(kv[0]))]
            ul, seen = [], set()
            for r in rows:
                p = r["p"]
                if p and p["id"] not in seen:
                    seen.add(p["id"])
                    ul.append({"id": p["id"], "nazwa": p["nazwa"], "cena": p["cena_brutto"], "auto": p["cena_auto"],
                               "recznie": p["recznie"], "zakup": p["brutto_zak"], "url": leaflet_url(p["id"], p["cena_brutto"])})
            try:
                save_hist(body, summ, path_x, rows)
            except Exception as e:
                warns.append("Nie zapisano oferty w historii: %s" % e)
            wc = {}
            for r in rows:
                if r.get("wym_tak") and r.get("wym_klucz") and r["wym_klucz"] not in wc:
                    d, t = r["wym_klucz"].split("|")
                    wc[r["wym_klucz"]] = {"klucz": r["wym_klucz"], "opis": "Wymiana %s%s" % (d, "" if t == "osobowy" else " " + TYPY.get(t, t)),
                                          "cennik": r["wym_cennik"], "auto": r["wym_auto"], "cena": r["wym_szt"], "recznie": r["wym_recznie"]}
            return 200, {"ulotki": ul, "wymiany": list(wc.values()), "zmiany": zmiany_ofert(body.get("porownaj"), rows) if body.get("porownaj") else [],
                         "plik": path_x, "oddzialy": KONTO.get("oddzialy") or [], "email": email_text(cfg, body, rows, variants), "warianty": summ, "uwagi": warns}
    except ApiError as e:
        return 502, {"error": str(e)}
    except Exception as e:
        return 500, {"error": "%s: %s" % (e.__class__.__name__, e)}
    return 404, {"error": "404"}
