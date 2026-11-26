"""DEPOZYT: szukaj.py (Panel) i depozyt.js (telefon) szukają tak samo. Zmyślone dane, bez prawdziwych numerów.
Uruchom: python3 mobile/test/zgodnosc_depozyt.py   (wymaga node)"""
import json, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app"))
from depozyt import szukaj as S

POZ = [
    {"id": 1, "nr": "XX1234A", "lok": "K12.3", "marka": "Testowa", "marka2": "Kombi", "uwagi": "", "komentarz": "", "rodzaj": ""},
    {"id": 2, "nr": "XX12340", "lok": "K1.1", "marka": "Inna", "uwagi": "chyba XY8L367?", "komentarz": "felgi alu", "rodzaj": "LATO"},
    {"id": 3, "nr": "QQ 5O2B", "lok": "M8/10", "marka": "Próbna", "uwagi": "", "komentarz": "Żółta naklejka", "rodzaj": "ZIMA?"},
    {"id": 4, "nr": "ZZ-77GT1", "lok": "KPOK", "marka": "Ćwiczebna", "marka2": "", "uwagi": "ZZ77GTI", "komentarz": "", "rodzaj": ""},
    {"id": 5, "nr": "", "lok": "MAGOPIS", "marka": "BEZ NUMERU", "uwagi": None, "komentarz": None, "rodzaj": None},
    {"id": 6, "nr": "AB0001C", "lok": "K2", "marka": "Fikcyjna", "uwagi": "x", "komentarz": "", "rodzaj": ""},
    {"id": 7, "nr": "XX1243A", "lok": "K3", "marka": "Testowa", "uwagi": "", "komentarz": "", "rodzaj": ""},
]
Q = ["XX1234A", "xx 1234a", "1234", "XXI234A", "XX1243A", "XX1235A", "XX12", "XY8L367", "XY8L36", "QQ502B", "Q5O2", "ZZ77GT1", "ZZ77GTI", "K12", "kpok",
     "felgi", "żółta", "ćwiczebna", "lato", "AB000IC", "AB0O01C", "ABOOO1C", "", "  ", "X", "zz-77", "99999", "XX1234AB", "XX234A"]
PARY = [["XX1234A", "XX1243A", 2], ["ABC", "ABCD", 1], ["KOT", "KOTEK", 1], ["", "AB", 2], ["Ż0Ł", "ZOL", 3]]
py = {"wyniki": [[[p["id"], pkt, fz] for p, pkt, fz in S.szukaj(POZ, q)] for q in Q],
      "kanon": [S.kanon(q) for q in Q], "norm": [S.norm(q) for q in Q],
      "lev": [S.lev(a, b, l) for a, b, l in PARY], "frag": [S._lev_fragment(a, b, l) for a, b, l in PARY],
      "numery": [S.numery(p) for p in POZ]}
js = subprocess.run(["node", "-e", """
const D=require(process.argv[1]);const I=JSON.parse(require('fs').readFileSync(0,'utf8'));
console.log(JSON.stringify({wyniki:I.Q.map(q=>D.szukaj(I.POZ,q).map(([p,a,b])=>[p.id,a,b])),kanon:I.Q.map(D.kanon),norm:I.Q.map(D.norm),
 lev:I.PARY.map(([a,b,l])=>D.lev(a,b,l)),frag:I.PARY.map(([a,b,l])=>D._lev_fragment(a,b,l)),numery:I.POZ.map(D.numery)}))""",
                     str(ROOT / "mobile/www/depozyt.js")], input=json.dumps({"POZ": POZ, "Q": Q, "PARY": PARY}), capture_output=True, text=True)
if js.returncode:
    print(js.stderr); sys.exit(2)
jo = json.loads(js.stdout)
bad = 0
for k, a in py.items():
    a = json.loads(json.dumps(a))
    for i, (x, y) in enumerate(zip(a, jo[k])):
        if x != y:
            bad += 1; print("RÓŻNICA", k, i, repr(Q[i]) if k in ("wyniki", "kanon", "norm") else "", "\n PY:", x, "\n JS:", y)
    if len(a) != len(jo[k]):
        bad += 1; print("RÓŻNA DŁUGOŚĆ", k)
assert any(fz for w in py["wyniki"] for _, _, fz in w) and any(not fz for w in py["wyniki"] for _, _, fz in w), "test bez literówek"
print("porównano zapytań:", len(Q), "· trafień:", sum(len(w) for w in py["wyniki"]))
print("zgodność depozytu:", "OK" if not bad else f"{bad} różnic")
sys.exit(1 if bad else 0)
