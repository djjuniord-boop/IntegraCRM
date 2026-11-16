"""OFERTY OPON – strona Panelu (index.html) w przeglądarce bez okna: otwiera każde okno (ustawienia, historia, koszyk,
zamówienia) i sprawdza, że nie ma błędów JavaScript. Wymaga Playwright + Chromium (Linux: zainstalowane; brak = pominięty)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))


def test_okna_ofert_bez_bledow_js():
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        print("  (pominięty – brak Playwright)")
        return
    cfg = {"zamowienia": True, "zamawianie": True, "admin": True, "premium": [], "progi": [], "marza_proc": 10, "vat_proc": 23,
           "min_stan": 0, "kola_na_auto": 4, "waznosc_dni": 7, "narzut_tryb": "procent", "oddzialy": ["Latex Wrocław"],
           "oddzialy_dane": {"Latex Wrocław": {"nazwa": "Latex", "adres": "x", "tel": "1"}}, "ceny_oddzial": "Latex Wrocław",
           "ceny_edycja": False}
    odp = {"/api/cfg": cfg, "/api/history": {"lista": [], "admin": True, "me": "a@b.pl"}, "/api/koszyk/adresy": {"adresy": []},
           "/api/koszyk/odswiez": {"pozycje": [], "czas": "10:00"}, "/api/zamowienia": {"zamowienia": [], "oddzialy": [], "czas": "10:00"}}
    mock = ("window.alert=window.confirm=window.prompt=()=>true;const ODP=%s;window.pywebview={api:{call:async(p,b)=>"
            "({code:200,body:ODP[Object.keys(ODP).find(k=>p.startsWith(k))]||{}})}};" % json.dumps(odp))
    html = (ROOT / "app/oferty/index.html").read_text(encoding="utf-8").replace("<head>", "<head><script>" + mock + "</script>", 1)
    p = ROOT / "app/oferty/_test_js.html"
    p.write_text(html, encoding="utf-8")
    bledy = []
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(args=["--no-sandbox"])
            pg = b.new_page()
            pg.on("pageerror", lambda e: bledy.append(str(e)))
            pg.goto(p.as_uri())
            pg.wait_for_timeout(600)
            for js in ("openCfg()", "saveCfg()", "openCfg()", "dlg.close()", "openHist()", "hdlg.close()", "openKosz()", "kdlg.close()", "openZam()",
                       "zapTog()", "zapTog()"):
                try:
                    pg.evaluate(js)
                except Exception as e:
                    bledy.append("%s: %s" % (js, e))
                pg.wait_for_timeout(250)
            b.close()
    finally:
        p.unlink()
    assert not bledy, bledy


if __name__ == "__main__":
    test_okna_ofert_bez_bledow_js()
    print("Okna Ofert bez błędów JS")
