"""WYNIKI: dane.py (Panel) i wyniki.js (telefon) liczą to samo. Uruchom: python3 mobile/test/zgodnosc_wyniki.py"""
import json, subprocess, sys, datetime
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app"))
from wyniki import dane as D
H = ["2026-11-01", "2026-11-11"]
ROWS = [  # bieżący (aktualizacja dziś / wczoraj), bez celu, bez wykonania, zamknięte, ręczne, przyszły
    {"year": 2026, "month": 11, "label": "Listopad 2026", "target": 300000, "done": 61234.5, "holidays": H, "updated_at": "2026-11-05T15:20:00+00:00"},
    {"year": 2026, "month": 10, "label": "Październik 2026", "target": 280000, "done": 291000, "holidays": [], "updated_at": "2026-10-31T10:00:00+00:00"},
    {"year": 2026, "month": 9, "target": None, "done": 150000, "holidays": []},
    {"year": 2026, "month": 8, "target": 250000, "done": None, "holidays": []},
    {"year": 2026, "month": 7, "target": 240000, "done": 200000, "holidays": [], "manual": True},
    {"year": 2026, "month": 12, "target": 310000, "done": None, "holidays": ["2026-12-25", "2026-12-26"]},
]
RUNS = [{"run_at": "2026-11-02T08:00:00+00:00", "done": 10000}, {"run_at": "2026-11-03T09:00:00+00:00", "done": 25000},
        {"run_at": "2026-11-03T17:00:00+00:00", "done": 31000}, {"run_at": "2026-10-30T09:00:00+00:00", "done": 280000},
        {"run_at": "2026-11-04T09:00:00+00:00", "done": None}]
DNI = ["2026-11-05", "2026-11-30", "2026-12-01", "2026-11-02"]
py = []
for t in DNI:
    td = datetime.date.fromisoformat(t)
    rows = [dict(r, updated_at=r.get("updated_at")) for r in ROWS]
    sel = D.wybierz_miesiac(rows, td)
    py.append({"pods": [D.podsumowanie(r, td) for r in rows], "wybor": sel and [sel["year"], sel["month"]],
               "poprz": [[r["year"], r["month"]] for r in D.poprzednie(rows, sel)],
               "pkt": [list(p) for p in D.punkty_wykresu(ROWS[0], RUNS, td)],
               "dni": D.dni_sprzedazowe(2026, 11, H).__len__()})
js = subprocess.run(["node", "-e", """
const W=require(process.argv[1]);const I=JSON.parse(require('fs').readFileSync(0,'utf8'));
console.log(JSON.stringify(I.DNI.map(t=>{const sel=W.wybierz_miesiac(I.ROWS,t);return{pods:I.ROWS.map(r=>W.podsumowanie(r,t)),wybor:sel&&[sel.year,sel.month],
 poprz:W.poprzednie(I.ROWS,sel).map(r=>[r.year,r.month]),pkt:W.punkty_wykresu(I.ROWS[0],I.RUNS,t),dni:W.dni_sprzedazowe(2026,11,["2026-11-01","2026-11-11"]).length}})))""",
                     str(ROOT / "mobile/www/wyniki.js")], input=json.dumps({"ROWS": ROWS, "RUNS": RUNS, "DNI": DNI}), capture_output=True, text=True, env={"TZ": "Europe/Warsaw", "PATH": "/usr/bin:/usr/local/bin:/bin"})
if js.returncode: print(js.stderr); sys.exit(2)
jo = json.loads(js.stdout)
def norm(x):
    if isinstance(x, float): return round(x, 6)
    if isinstance(x, dict): return {k: norm(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)): return [norm(v) for v in x]
    return x
bad = 0
for i, (a, b) in enumerate(zip(norm(json.loads(json.dumps(py))), norm(jo))):
    for k in a:
        if a[k] != b[k]:
            bad += 1; print("RÓŻNICA", DNI[i], k, "\n PY:", json.dumps(a[k], ensure_ascii=False)[:700], "\n JS:", json.dumps(b[k], ensure_ascii=False)[:700])
print("przykład:", {k: py[0]["pods"][0][k] for k in ("pct", "tempo", "prognoza", "potrzeba_dziennie", "dni_minelo")})
print("zgodność WYNIKI:", "OK" if not bad else f"{bad} różnic"); sys.exit(1 if bad else 0)
