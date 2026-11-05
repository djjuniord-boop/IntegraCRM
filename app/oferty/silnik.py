"""OFERTY OPON – silnik: wyszukiwanie opon w xPartner (XML API, productsList), oferta (XLSX, e-mail, ulotki).

Bez okna i bez bazy: dane konta (login API, ustawienia) i historię dostarcza okno.py przez KONTO i HIST.
Tylko biblioteka standardowa + openpyxl (dołączone do IntegraCRM.exe).
"""
import datetime
import json
import os
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

VERSION = "panel"
OUT_DIR = os.path.join(os.path.expanduser("~"), "Documents", "Oferty opon")
API_URL = "https://xpartner.net.pl/index.php"

# uzupełnia okno.py po zalogowaniu: {"login": ..., "password": ..., "ustawienia": {...}, "zapisz": funkcja(dict)}
KONTO = {"login": "", "password": "", "ustawienia": {}, "zapisz": None}
# historia ofert (baza): obiekt z metodami get(oid) -> dict|None, save(oid, klient, dane, szukaj), list(q) -> [dict]
HIST = None

DEFAULT_CFG = {
    "marza_proc": 5.0, "vat_proc": 23.0,
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
            "kod": _txt(p, "manufacturerCode"), "ean": _txt(p, "ean"),
            "nazwa": _txt(p, "name"),
            "ilosc": int(_txt(p, "quantity") or 0),
            "netto": num("netDiscountPrice"), "brutto_zak": num("grossDiscountPrice"),
            "netto_kat": num("netListPrice"),
            "attrs": attrs, "magazyny": stock,
        })
    return count, out

def api_call(cfg, **params):
    if not cfg.get("login") or not cfg.get("password"):
        raise ApiError("Twoje konto nie ma jeszcze loginu API xPartner – poproś administratora o wpisanie go "
                       "(UŻYTKOWNICY → konto → xPartner).")
    q = {"a": "b2b_xmlApi", "login": cfg["login"], "pass": cfg["password"], "m": "productsList"}
    q.update({k: ("true" if v is True else "false" if v is False else v) for k, v in params.items()})
    url = API_URL + "?" + urllib.parse.urlencode(q)
    req = urllib.request.Request(url, headers={"User-Agent": "PanelLatexSerwis-Oferty"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
    except Exception as e:
        raise ApiError("Brak połączenia z xPartner: %s" % e.__class__.__name__)
    try:
        return parse_products(data)
    except ET.ParseError:
        raise ApiError("Nieprawidłowa odpowiedź API (nie XML) – sprawdź login/hasło.")

def search_size(cfg, size_txt):
    """Pobiera wszystkie produkty o danym rozmiarze (wszystkie strony)."""
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
SIZE_RE = re.compile(r"(\d{3})\s*/\s*(\d{2})\s*Z?R\s*(\d{2})", re.I)

SIZE_LOOSE = re.compile(r"(?<!\d)(\d{3})\s*[/\\\-.x×, ]?\s*(\d{2})\s*(?:[/\\\-., ]|\s*Z?R\s*F?)?\s*(\d{2})(?:[.,]5)?(?!\d)", re.I)

def find_sizes(txt):
    """Rozpoznaje rozmiar w dowolnym zapisie: 205/55 R16, 205/55 16, 205 55 16, 2055516, 205-55-16, 205/55/16, 205/55ZR16."""
    out = []
    for m in SIZE_LOOSE.finditer(txt or ""):
        w, p, r = (int(x) for x in m.groups())
        if 125 <= w <= 355 and w % 5 == 0 and 25 <= p <= 85 and p % 5 == 0 and 12 <= r <= 24:
            sz = "%d/%d R%d" % (w, p, r)
            if sz not in out: out.append(sz)
    return out

def norm_size(s):
    m = SIZE_RE.search(s or "")
    if m: return "%s/%s R%s" % m.groups()
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
    n = re.sub(r"^\S+\s+[ZWL]?\d{3}/\d{2}\s*Z?R\d{2}\s*", "", p["nazwa"])
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

def sell_price(cfg, netto):
    import math
    return float(math.ceil(round(netto * (1 + cfg["marza_proc"] / 100) * (1 + cfg["vat_proc"] / 100), 2) - 1e-9))  # w górę do pełnych zł

def enrich(cfg, p):
    p = dict(p)
    p.update(sezon=season_of(p), producent=producer_of(p), klasa=klasa_of(p, cfg), model=model_of(p),
             indeks=index_of(p), dot=dot_of(p), standard=is_standard(p),
             cena_brutto=sell_price(cfg, p["netto"]),
             etykieta={k: p["attrs"].get(k, "") for k in ("Opory toczenia", "Przyczepność na mokrej nawierzchni", "Hałas", "Poziom hałasu")})
    nz = re.search(r"(\d{2})", p["attrs"].get("Poziom hałasu", "") or "")
    p.update(mokra=(p["attrs"].get("Przyczepność na mokrej nawierzchni") or "").strip()[:1].upper(),
             opory=(p["attrs"].get("Opory toczenia") or "").strip()[:1].upper(),
             halas=int(nz.group(1)) if nz else 0, homol=homol_of(p))
    return p

HOMOL = [("MO", r"\bMOE?\b|\bMO1\b|\bMO-S\b", "Mercedes (MO)"), ("AO", r"\bAOE?\b|\bRO[12]\b|\bA8A\b", "Audi (AO/RO)"), ("*", r"\*|\bBMW\b", "BMW (*)"),
         ("N", r"\bN[0-9]\b", "Porsche (N0–N9)"), ("VOL", r"\bVOL\b", "Volvo (VOL)"), ("T0", r"\bT[0O][0-9]?\b", "Tesla (T0)"),
         ("J", r"\bJLR\b|\bJ\b", "Jaguar (J)"), ("LR", r"\bLR\b", "Land Rover (LR)"), ("VW", r"\bVW\b", "VW"), ("FR", r"\b(FR|MFS|FP|RG)\b", "rant ochronny felgi")]

def homol_of(p):
    src = " ".join([p["nazwa"].upper(), (p["attrs"].get("Homologacja") or "").upper()])
    src = SIZE_RE.sub(" ", src)
    return [k for k, rx, _ in HOMOL if re.search(rx, src)]

PLATE_RE = re.compile(r"(?<![A-Z0-9])([A-Z]{1,3})[ -]?([0-9][0-9A-Z]{2,5}|[A-Z]{0,2}[0-9][0-9A-Z]{1,4})(?![A-Z0-9])")
STOP = {"marka", "model", "rejestracja", "rozmiar", "wymaga", "nowych", "opon", "opony", "szt", "sztuk", "tak", "nie", "tylko",
        "wymiana", "wymianę", "wymiane", "auto", "samochód", "samochod", "pojazd", "i", "oraz", "x", "r", "zr", "nr", "rej"}

CRIT_RE = re.compile(r"^(suv|4x4|terenow\w*|dostawcz\w*|bus|van|czujnik\w*|tpms|przechow\w*|k[oó]ł|kola|koła|felg\w*|z|ze|wymian\w*|monta[żz]\w*|przek[łl]ad\w*|premium|prem|[śs]redni\w*|middle|medium|bud[żz]et\w*|budget|ekonom\w*|tani\w*|zim\w*|letn\w*|lato|ca[łl]oroczn\w*|wielosezon\w*|runflat|run-?flat|rft|ssr|klas[aey]?|półk[aią]|polk[aią]|sezon\w*|opony|michelin|continental|goodyear|good-year|bridgestone|pirelli|nokian|dunlop|hankook|vredestein|yokohama|barum|dębica|debica|kleber|fulda|firestone|bfgoodrich|uniroyal|semperit|kumho|falken|toyo|nexen|sava|kormoran|matador)$", re.I)

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
    words = [w for w in re.split(r"[\s,;/|\t]+", rest) if w and w.lower() not in STOP and not re.fullmatch(r"[\d.,]+", w) and not CRIT_RE.match(w)]
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

def parse_quick(txt):
    """Szybkie polecenie, np. '205/55 r16 3 oferty premium średnia budżet zimowe 4 szt'."""
    t = txt.lower()
    sizes = find_sizes(txt)
    q = re.search(r"(?:^|\s)(\d{1,2})\s*(szt|opon|sztuk|x\b)", t) or re.search(r"\bx\s*(\d{1,2})\b", t)
    ilosc = int(q.group(1)) if q else 4
    sezony = []
    if re.search(r"zim", t): sezony.append("Zimowa")
    if re.search(r"ca[łl]oroczn|wielosezon|all ?season|4 ?season", t): sezony.append("Całoroczna")
    if re.search(r"letn|lato", t): sezony.append("Letnia")
    klasy = []
    if re.search(r"premium|prem\b", t): klasy.append("PREMIUM")
    if re.search(r"[śs]redni|middle|medium", t): klasy.append("MIDDLE")
    if re.search(r"bud[żz]et|budget|ekonom|tani", t): klasy.append("BUDGET")
    marki = [b for b in ["michelin", "continental", "goodyear", "good-year", "bridgestone", "pirelli", "nokian", "dunlop", "hankook", "vredestein", "yokohama",
                         "barum", "dębica", "debica", "kleber", "fulda", "firestone", "bfgoodrich", "uniroyal", "semperit", "kumho", "falken", "toyo", "nexen", "sava", "kormoran", "matador"] if b in t]
    marki = ["GOODYEAR" if m in ("goodyear", "good-year") else m.upper() for m in marki]
    ex = extras(t)
    wymiana = ex["wymiana"]
    runflat = bool(re.search(r"run ?-?flat|\brft\b|\bssr\b|\bzp\b|\brof\b", t))
    pojazdy = [{"rej": "", "pojazd": "", "rozmiar": s, "ilosc": ilosc, "nowe": True, "wymiana": wymiana, "typ": ex["typ"], "tpms": ex["tpms"], "przech": ex["przech"]} for s in sizes]
    return {"pojazdy": pojazdy, "sezony": sezony, "klasy": klasy, "runflat": runflat, "producenci": ", ".join(dict.fromkeys(marki))}

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
        items = [enrich(cfg, p) for p in found[s] if norm_size(p["nazwa"]) == s and p["netto"] > 0]  # cena 0 = niedostępne do zamówienia
        res[s] = {}
        for sez in sezony:
          for klasa in klasy:
            lst = [p for p in items if not sez or p["sezon"] == sez]
            if req.get("tylko_runflat"): lst = [p for p in lst if not p["standard"]]
            if prod_f: lst = [p for p in lst if bkey(p["producent"]) in prod_f]
            if klasa:
                lst = [p for p in lst if p["klasa"] == klasa]
            for p in lst:
                p["ok_stan"] = p["ilosc"] >= max(min_stan, need[s])
            lst.sort(key=lambda p: (not p["ok_stan"], p["netto"]))
            grp = " · ".join(x for x in (sez, KLASY.get(klasa, klasa)) if x) or "wszystkie"
            res[s][grp] = lst
    return {"wyniki": res, "potrzeba": need}

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
        auto = sell_price(c2, p["netto"] * (1 - rab / 100))
        p["cena_auto"] = auto
        p["cena_brutto"] = over.get(pid, auto)
        p["recznie"] = pid in over
    warnings = []
    kola = int(cfg["kola_na_auto"])
    rows, variants = [], {}
    sep = bool(req.get("osobno"))
    for vi, v in enumerate(req["pojazdy"]):
        s = norm_size(v["rozmiar"]) or v["rozmiar"]
        dia = (re.search(r"R(\d{2})", s) or [None, "16"])[1]
        typ = v.get("typ") or "osobowy"
        cen = cfg["wymiana_suv"] if typ == "suv" else cfg["wymiana_dost"] if typ == "dostawczy" else cfg["wymiana_kolo"]
        n_kol = int(v.get("ilosc") or 0) or kola   # wymiana tylu kół, ile opon; przy samej wymianie – komplet
        wym = float(cen.get(dia, 0)) * n_kol if v.get("wymiana") else 0.0
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
    hdr = ["Rejestracja", "Pojazd", "Rozmiar", "Rodzaj", "Producent", "Model opony", "Indeks", "Cena brutto / szt.", "Ilość", "Opony razem", "Wymiana kół", "Czujniki TPMS", "Przechowalnia", "RAZEM brutto", "DOT", "Stan (szt.)", "Usługi – opis"]
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
            ws.append([r["rej"], (r["pojazd"] + (" (%s)" % TYPY[r.get("typ")] if r.get("typ") in ("suv", "dostawczy") else "")).strip(), r["rozmiar"], r["rodzaj"], p["producent"].title(), p["model"], p["indeks"], p["cena_brutto"], r["ilosc"], "=H%d*I%d" % (i, i), wh, r["tpms_kw"], r["przech_kw"], "=J%d+K%d+L%d+M%d" % (i, i, i, i), p["dot"], p["ilosc"], "; ".join(x for x in (r["tpms_op"], r["przech_op"]) if x)])
        else:
            ws.append([r["rej"], r["pojazd"], r["rozmiar"], r["rodzaj"], None, None, None, None, None, 0, wh, r["tpms_kw"], r["przech_kw"], "=J%d+K%d+L%d+M%d" % (i, i, i, i), None, None, "; ".join(x for x in (r["tpms_op"], r["przech_op"]) if x)])
        col = palette[regs.index(r["rej"]) % len(palette)]
        for c in ws[i]:
            c.fill = PatternFill("solid", fgColor=col); c.border = B
            if c.column in (8, 10, 11, 12, 13, 14): c.number_format = money
    for c in ws[HR]:
        c.font = Font(b=True, color="FFFFFFFF"); c.fill = PatternFill("solid", fgColor="FF305496")
        c.alignment = Alignment(wrap_text=True, horizontal="center", vertical="center"); c.border = B
    ws.row_dimensions[HR].height = 32
    r0 = ws.max_row + 2
    ws.cell(r0, 1, "PODSUMOWANIE WARIANTÓW (opony + wymiana + usługi)").font = Font(b=True, size=12)
    for (sez, k), var in sorted(variants.items(), key=lambda kv: vkey(kv[0])):
        r0 += 1
        ws.cell(r0, 1, "Wariant %s – %s" % (vlabel(variants, (sez, k)).upper(), ", ".join(var["modele"]))).font = Font(b=True)
        for col, val in ((10, var["opony"]), (11, var["wymiana"]), (12, var["tpms_kw"]), (13, var["przech_kw"]), (14, total(var))):
            c = ws.cell(r0, col, round(val, 2)); c.number_format = money; c.border = B
            c.fill = PatternFill("solid", fgColor="FFD9E1F2")
        ws.cell(r0, 14).font = Font(b=True)
    r0 += 2
    notes = ["Ceny brutto (VAT %g%%). Wymiana obejmuje demontaż, montaż i wyważenie (liczona za każde wymieniane koło)." % cfg["vat_proc"],
             "Ceny i stany pobrane z xPartner: %s." % datetime.datetime.now().strftime("%d.%m.%Y %H:%M"),
             "Gwarancja producenta na wady fabryczne, standardowo do 5 lat od daty produkcji; nie obejmuje uszkodzeń mechanicznych, jazdy na złym ciśnieniu i złej geometrii.",
             "Ceny ważne %d dni, z zastrzeżeniem dostępności." % cfg["waznosc_dni"]]
    for t in notes:
        ws.cell(r0, 1, t).font = Font(i=True, size=9, color="FF595959"); r0 += 1
    for col, w in zip("ABCDEFGHIJKLMNOPQ", [11, 18, 12, 13, 13, 26, 10, 13, 6, 14, 14, 13, 13, 15, 7, 9, 40]):
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

def save_hist(req, summ, path):
    if not HIST:
        return
    oid = safe_oid(req.get("oid"))
    rec = {"osobno": req.get("osobno"), "marza": req.get("marza"), "rabat": req.get("rabat"), "ceny": req.get("ceny") or {},
           "oid": oid, "data": datetime.datetime.now().strftime("%d.%m.%Y %H:%M"), "klient": req.get("klient", ""),
           "pojazdy": req.get("pojazdy", []), "wybor": req.get("wybor", {}), "sel": req.get("sel", []),
           "warianty": summ, "plik": path}
    hay = (rec["klient"] + " " + " ".join(v.get("rej", "") + " " + v.get("pojazd", "") + " " + v.get("rozmiar", "") for v in rec["pojazdy"])
           + " " + " ".join(m for w in summ for m in w.get("modele", []))).lower()
    HIST.save(oid, rec["klient"], rec, hay)

def list_hist(q=""):
    out = []
    try:
        recs = HIST.list(q) if HIST else []
    except Exception:
        recs = []
    for r in recs:
        out.append({"oid": r["oid"], "data": r.get("data"), "klient": r.get("klient", ""),
                    "pojazdy": ", ".join(" ".join(x for x in (v.get("rej"), v.get("pojazd")) if x) or v.get("rozmiar", "") for v in r.get("pojazdy", [])),
                    "warianty": [{"wariant": w["wariant"], "modele": ", ".join(w["modele"]), "razem": w["razem"]} for w in r.get("warianty", [])],
                    "plik_ok": os.path.exists(r.get("plik") or "")})
    return out

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
                L.append("• %s: %s %s %s %s – %s brutto/szt. × %d = %s" % (kto, p["producent"].title(), p["model"], r["rozmiar"], p["indeks"], pl(p["cena_brutto"]), r["ilosc"], pl(r["opony"])))
        else:
            seen = {}
            for r in by_var.get(key, []):
                p = r["p"]; kk = (p["id"])
                seen.setdefault(kk, [p, r["rozmiar"], 0]); seen[kk][2] += r["ilosc"]
            for p, s, q in seen.values():
                L.append("• %s %s %s %s – %s brutto/szt. × %d = %s" % (p["producent"].title(), p["model"], s, p["indeks"], pl(p["cena_brutto"]), q, pl(p["cena_brutto"] * q)))
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

# ---------------------------------------------------------------- obsługa poleceń strony (window.pywebview.api.call)
class Odpowiedz(Exception):
    def __init__(self, code, body):
        super().__init__(str(body))
        self.code, self.body = code, body


def _in_out_dir(p):
    return bool(p) and os.path.dirname(os.path.abspath(p)) == os.path.abspath(OUT_DIR)


def handle(path, body=None, open_path=None):
    """Polecenie strony -> (kod, odpowiedź). open_path(ścieżka) otwiera plik/folder w Windows."""
    u = urllib.parse.urlparse(path)
    qs = urllib.parse.parse_qs(u.query)
    route = u.path
    cfg = load_cfg()
    try:
        if body is None:
            if route == "/api/cfg":
                c = dict(cfg)
                c["login"] = "tak" if cfg.get("login") else ""
                c["password"] = ""
                return 200, c
            if route == "/api/history":
                if qs.get("oid"):
                    r = load_hist(qs["oid"][0])
                    return (200, r) if r else (404, {"error": "Brak oferty"})
                return 200, {"lista": list_hist(qs.get("q", [""])[0])}
            if route == "/api/openfile":
                r = load_hist((qs.get("oid") or [""])[0]) or {}
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
            count, _ = api_call(cfg, productName="205/55 R16", resultsPerPage=1)
            return 200, {"ok": True, "msg": "Połączono z xPartner. Przykładowe zapytanie zwróciło %d produktów." % count}
        if route == "/api/quick":
            return 200, parse_quick(body.get("text", ""))
        if route == "/api/parse":
            txt = body.get("text", "")
            q = parse_quick(txt)
            return 200, {"pojazdy": parse_request_text(txt), "kryteria": {k: q[k] for k in ("sezony", "klasy", "producenci", "runflat")}}
        if route == "/api/search":
            return 200, do_search(cfg, body)
        if route == "/api/offer":
            rows, variants, warns = build_offer(cfg, body)
            if not rows:
                return 400, {"error": "Brak wybranych opon."}
            path_x = write_xlsx(cfg, body, rows, variants)
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
                save_hist(body, summ, path_x)
            except Exception as e:
                warns.append("Nie zapisano oferty w historii: %s" % e)
            return 200, {"ulotki": ul, "plik": path_x, "email": email_text(cfg, body, rows, variants), "warianty": summ, "uwagi": warns}
    except ApiError as e:
        return 502, {"error": str(e)}
    except Exception as e:
        return 500, {"error": "%s: %s" % (e.__class__.__name__, e)}
    return 404, {"error": "404"}
