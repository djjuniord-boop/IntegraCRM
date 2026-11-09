"""OFERTY OPON – zrzuty ekranu w prawdziwym Edge na Windows (GitHub Actions; lokalnie: Chromium/Edge z OFERTY_PRZEGLADARKA).

Robi zrzuty tego, czego zwykły test okna nie pokazuje (strona Panelu działa w WebView2 = Edge):
  oferty_zamowienia.png  – okno „Zamówienia xPartner” z przykładowymi danymi
  oferty_historia.png    – historia ofert ze statusami, przypomnieniem i odpowiedzią klienta
  oferty_porownanie.png  – PDF „Porównanie” (2 modele) wygenerowany z prawdziwego wzoru
  oferta_klient.png      – strona oferty dla klienta (telefon 390 px)
Dane zmyślone (tests/test_oferty, tests/test_zamowienia). Uruchom: python tests/ui_oferty_win.py <folder_na_zrzuty>
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app")); sys.path.insert(0, str(ROOT / "tests"))
import test_oferty as T          # noqa: E402
import test_zamowienia as TZ     # noqa: E402
from oferty import okno, silnik as S, zamowienia as Z   # noqa: E402

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "shots").resolve()
OUT.mkdir(parents=True, exist_ok=True)
TMP = Path(tempfile.mkdtemp(prefix="oferty_ui_"))
EDGE = okno._przegladarka()
if not EDGE:
    sys.exit("Brak Edge/Chrome – zrzuty pominięte")


def zrzut(html_path, png, w=1300, h=900, czekaj=2500):
    out = OUT / png
    subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--no-first-run", "--hide-scrollbars", "--allow-file-access-from-files",
                    "--window-size=%d,%d" % (w, h), "--virtual-time-budget=%d" % czekaj,
                    "--screenshot=" + str(out), html_path.as_uri()], timeout=90, check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ok = out.exists() and out.stat().st_size > 5000
    print(("OK   " if ok else "BRAK ") + png)
    return ok


def panel_z(skrypt, nazwa):
    """Strona Panelu (index.html) z podmienionym API (bez xPartner i bazy) i skryptem otwierającym okno."""
    html = (ROOT / "app/oferty/index.html").read_text(encoding="utf-8")
    html = html.replace("<head>", "<head><script>window.alert=window.confirm=window.prompt=()=>true;</script>", 1)   # okna dialogowe blokują tryb bez ekranu
    html = html.replace("</body>", "<script>\n" + skrypt + "\n</script></body>")
    p = ROOT / "app/oferty" / ("_test_" + nazwa + ".html")   # obok oryginału – działają ścieżki względne
    p.write_text(html, encoding="utf-8")
    return p


wyniki = []
try:
    zam = {"zamowienia": Z.czytaj_zamowienia(Z.parsuj(TZ.XML_ZAM)), "czas": "10:00", "oddzialy": ["Latex Wrocław"], "ukryte": 0}
    p = panel_z("window.pywebview={api:{call:async(p)=>({code:200,body:p.startsWith('/api/zamowienia')?%s:{}})}};"
                "setTimeout(()=>{CFG=Object.assign(window.CFG||{},{zamowienia:true,admin:false});openZam()},300);" % json.dumps(zam), "zam")
    wyniki.append(zrzut(p, "oferty_zamowienia.png"))

    hist = [{"id": 1, "kto": "Jan Test", "owner": "jan@test.pl", "oid": "20261106_100000", "data": "06.11.2026 10:00", "klient": "Firma Test",
             "pojazdy": "Octavia DW1", "warianty": [{"wariant": "P1", "modele": "Nokian Snowproof 1", "razem": 1668}], "razem": 1668, "plik_ok": False,
             "status": "wyslana", "status_at": "2026-11-05T10:00:00Z", "link": True, "otwarta": "2026-11-06", "odp": None, "oddzwon": True},
            {"id": 2, "kto": "Jan Test", "owner": "jan@test.pl", "oid": "20261107_100000", "data": "07.11.2026 10:00", "klient": "Klient B",
             "pojazdy": "Golf", "warianty": [{"wariant": "P1", "modele": "Barum Polaris 6", "razem": 900}], "razem": 900, "plik_ok": False,
             "status": "przyjeta", "status_at": "2026-11-07T10:00:00Z", "link": True, "otwarta": "x",
             "odp": {"wybor": "BARUM POLARIS 6", "tel": "600 100 200", "uwagi": "po 16"}, "oddzwon": False}]
    p = panel_z("window.pywebview={api:{call:async(p)=>({code:200,body:p.startsWith('/api/history')?{lista:%s,admin:false,me:'jan@test.pl'}:{}})}};"
                "setTimeout(openHist,300);" % json.dumps(hist), "hist")
    wyniki.append(zrzut(p, "oferty_historia.png"))

    T._pdf(["Latex Wrocław"], {"id": 1}, {"wybor": {"205/55 R16": {"wszystkie": [1, 2]}}})
    code, r = S.handle("/api/pdf", {"ids": [1, 2], "porownanie": 1, "logo": (ROOT / "app/assets/logo.png").as_uri()})
    assert code == 200, r
    p = TMP / "porownanie.html"; p.write_text(r["html"], encoding="utf-8")
    wyniki.append(zrzut(p, "oferty_porownanie.png", 794, 1123))

    d = S.link_dane(S.load_cfg(), S.OSTATNIA["req"], S.OSTATNIA["rows"], T.ODDZ["Latex Wrocław"], "Jan Test")
    k = (ROOT / "app/oferty/klient.html").read_text(encoding="utf-8").replace(
        '<script src="config.js"></script>',
        "<script>window.SERWIS_CFG={url:'x',key:'x'};location.hash='11111111-2222-3333-4444-555555555555';"
        "window.fetch=async()=>({ok:true,json:async()=>(%s)});</script>" % json.dumps({"dane": d, "odp": None}))
    p = TMP / "klient.html"; p.write_text(k, encoding="utf-8")
    import shutil
    shutil.copy2(ROOT / "app/assets/logo.png", TMP / "logo.png")
    wyniki.append(zrzut(p, "oferta_klient.png", 390, 1400))
finally:
    for f in (ROOT / "app/oferty").glob("_test_*.html"):
        f.unlink()
print("Zrzuty OFERTY OPON: %d/%d" % (sum(wyniki), len(wyniki)))
sys.exit(0 if all(wyniki) else 1)
