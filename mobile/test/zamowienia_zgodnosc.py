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
pass

# historia zamówień (faktury -> getOrder): te same dane wejściowe w Pythonie i JS
ODP = {"getInvoices|": T.XML_FAKTURY.decode(),
       "getInvoice|FV0000001/26": T.XML_FAKTURA.decode().replace("XP/1/2026", "12345678901").replace("FV0000002/26", "FV0000001/26"),
       "getInvoice|FV0000002/26": T.XML_FAKTURA.decode().replace("XP/1/2026", "000000001/26"),
       "getOrder|12345678901": T.XML_ZAM.decode().replace("<orders>", "").replace("</orders>", "").split("<order><orderXp>XP/2")[0].replace("</response>", "") + "</response>",
       "getOrder|000000001/26": T.XML_BLAD.decode()}
def _api(cfg, m, **p):
    return Z.parsuj(ODP[m + "|" + (p.get("invoiceNumber") or p.get("orderXp") or p.get("orderErp") or "")].encode())
Z.api_xml, Z._PAMIEC = _api, {}
py_h = Z.zamkniete({"login": "t"}, "2026-10-01", "2026-10-31")
with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox"]); pg = b.new_page(); pg.add_script_tag(content=src)
    js_h = pg.evaluate("""async (o) => { const Z = window.Zamowienia; Z.api_xml = async (c, m, p) => Z.parsuj(o[m + "|" + ((p && (p.invoiceNumber || p.orderXp || p.orderErp)) || "")]);
      return await Z.zamkniete({ login: "t" }, "2026-10-01", "2026-10-31"); }""", ODP)
    b.close()
ok_h = json.loads(json.dumps(py_h)) == js_h and len(py_h["zamowienia"]) == 1 and py_h["bledy"] == 1
print("Historia zamówień – zgodność Python/JS:", "OK" if ok_h else "BŁĄD\n PY %s\n JS %s" % (py_h, js_h))
sys.exit(0 if ok_h and not bad else 1)
