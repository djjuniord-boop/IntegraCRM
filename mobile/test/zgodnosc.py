"""Porównanie silnika Panelu (Python) z silnikiem aplikacji (JS): te same wejścia -> te same wyniki.
Uruchom: python3 mobile/test/zgodnosc.py   (wymaga node)"""
import json, subprocess, sys, os, copy
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app")); sys.path.insert(0, str(ROOT / "tests"))
import test_oferty as T
from oferty import silnik as S
import asyncio

T._setup()
DB = T.DB
TEKSTY = ["2055516 zimowe premium", "205/55 16 sailun", "silun 2055516 x2", "rodx 1956515 bez demo", "2155517 conti runflat",
          "skoda octavia 2055516 dw5444lw z wymianą 4 czujniki przechowalnia kół srednia", "bmw x5 suv 275/40 20 dw12345 wymiana przechowalnia opon",
          "transit dostawczy 2156516 tylko wymiana", "vw passat 2055516 dw5444lw silun", "2055516 ling long 8 szt", "2254517 premium budzet całoroczne demo",
          "SKODA\tOCTAVIA\tDX1522H\t205/60 R16\tTAK\nSKODA\tOCTAVIA\tDX3985C\t205/60 R16\tNIE",
          "superb 215/55 17 DX1209H 4 szt\nDX3985C octavia 205/60 16 tylko wymiana"]
SLOWA = ["silun", "rodx", "conti", "brigestone", "hankuk", "michlein", "goodyar", "debica", "vredstein", "passat", "tiguan", "octavia", "bfg", "toyo", "zimowe"]
S.ucz_marki(S.load_cfg())
py = {"quick": [S.parse_quick(t) for t in TEKSTY], "parse": [S.parse_request_text(t) for t in TEKSTY],
      "marki": [S.brand_of_word(w) for w in SLOWA], "sizes": [S.find_sizes(t) for t in TEKSTY]}
cfg = S.load_cfg()
py["enrich"] = [{k: v for k, v in S.enrich(cfg, p).items() if k in ("sezon", "producent", "klasa", "model", "indeks", "dot", "standard", "cena_brutto", "mokra", "halas", "homol", "demo", "model_oferta")} for p in DB]
cfg2 = dict(cfg, narzut_tryb="kwota")
py["ceny"] = [[S.sell_price(cfg, n), S.sell_price(cfg2, n)] for n in (100, 236.44, 300, 325.2, 344.10, 500, 731.0, 800)]
reqs = [{"pojazdy": [{"rozmiar": "205/55 R16", "ilosc": 4, "nowe": True}], "sezony": [], "klasy": []},
        {"pojazdy": [{"rozmiar": "205/55 R16", "ilosc": 4, "nowe": True}], "sezony": ["Zimowa"], "klasy": ["PREMIUM", "BUDGET"], "producenci": ""}]
py["search"] = [{s: {g: [p["id"] for p in l] for g, l in d.items()} for s, d in S.do_search(cfg, r)["wyniki"].items()} for r in reqs]
offers = [{"oid": "1", "klient": "Firma", "rabat": "10", "pojazdy": [{"rej": "DW1", "pojazd": "Skoda", "rozmiar": "205/55 R16", "ilosc": 2, "nowe": True, "wymiana": True, "tpms": 4, "przech": "opony", "typ": "osobowy"},
            {"rej": "DX9", "pojazd": "", "rozmiar": "205/55 R16", "ilosc": 0, "nowe": False, "wymiana": True, "tpms": 0, "przech": "kola", "typ": "suv"}], "wybor": {"205/55 R16": {"wszystkie": [1, 2]}}},
          {"oid": "2", "osobno": True, "ceny": {"1": 500}, "pojazdy": [{"rozmiar": "205/55 R16", "ilosc": 4, "nowe": True}, {"rozmiar": "235/55 R18", "ilosc": 4, "nowe": True}],
           "wybor": {"205/55 R16": {"wszystkie": [1]}, "235/55 R18": {"wszystkie": [5]}}}]
py["offer"] = []
for o in offers:
    c, r = S.handle("/api/offer", copy.deepcopy(o))
    py["offer"].append({"warianty": r["warianty"], "email": r["email"], "uwagi": r["uwagi"], "ulotki": [(u["id"], u["cena"]) for u in r["ulotki"]]})
inp = {"TEKSTY": TEKSTY, "SLOWA": SLOWA, "DB": DB, "reqs": reqs, "offers": offers}
js = subprocess.run(["node", str(Path(__file__).with_name("zgodnosc_js.cjs"))], input=json.dumps(inp), capture_output=True, text=True)
if js.returncode:
    print(js.stderr); sys.exit(2)
jo = json.loads(js.stdout)
bad = 0
def norm(x):  # JSON (krotki -> listy)
    return json.loads(json.dumps(x))
for k in py:
    a, b = norm(py[k]), jo[k]
    if a != b:
        for i, (x, y) in enumerate(zip(a, b)):
            if x != y:
                bad += 1
                print("RÓŻNICA", k, i, "\n PY:", json.dumps(x, ensure_ascii=False)[:600], "\n JS:", json.dumps(y, ensure_ascii=False)[:600])
        if len(a) != len(b):
            bad += 1; print("RÓŻNA DŁUGOŚĆ", k)
print("porównano:", {k: len(v) for k, v in py.items()}); print("przykład oferty:", py["offer"][0]["warianty"]); print("zgodność:", "OK" if not bad else f"{bad} różnic")
sys.exit(1 if bad else 0)
