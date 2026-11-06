"""Zamówienia: aplikacja (zamowienia.js, w przeglądarce) liczy to samo co Panel (zamowienia.py). Uruchom: python3 mobile/test/zamowienia_zgodnosc.py"""
import json, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app")); sys.path.insert(0, str(ROOT / "tests"))
from oferty import zamowienia as Z
import test_zamowienia as T

py = {"zam": Z.czytaj_zamowienia(Z.parsuj(T.XML_ZAM)), "fak": Z.czytaj_faktury(Z.parsuj(T.XML_FAKTURY)),
      "fa": Z.czytaj_fakture(Z.parsuj(T.XML_FAKTURA)), "okres": [list(Z.okres("", "", __import__("datetime").date(2026, 11, 6))),
      list(Z.okres("2025-01-01", "2026-03-01"))]}
src = (ROOT / "mobile/www/zamowienia.js").read_text(encoding="utf-8")
with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox"]); pg = b.new_page(); pg.add_script_tag(content=src)
    js = pg.evaluate("""(x) => { const Z = window.Zamowienia; return { zam: Z.czytaj_zamowienia(Z.parsuj(x.z)), fak: Z.czytaj_faktury(Z.parsuj(x.f)),
      fa: Z.czytaj_fakture(Z.parsuj(x.fa)), okres: [Z.okres("", "", "2026-11-06"), Z.okres("2025-01-01", "2026-03-01")] }; }""",
                     {"z": T.XML_ZAM.decode(), "f": T.XML_FAKTURY.decode(), "fa": T.XML_FAKTURA.decode()})
    b.close()
bad = [k for k in py if json.loads(json.dumps(py[k])) != js[k]]
import difflib
for k in bad: print("\n".join(list(difflib.unified_diff(json.dumps(py[k],indent=0,ensure_ascii=False).splitlines(), json.dumps(js[k],indent=0,ensure_ascii=False).splitlines(), lineterm=""))[:30]))
for k in bad:
    print("RÓŻNICA", k, "\n PY", json.dumps(py[k], ensure_ascii=False)[:600], "\n JS", json.dumps(js[k], ensure_ascii=False)[:600])
print("Zamówienia – zgodność Python/JS:", "OK" if not bad else "BŁĄD")
sys.exit(1 if bad else 0)
