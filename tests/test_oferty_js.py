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
           "/api/koszyk/odswiez": {"pozycje": [], "czas": "10:00"}, "/api/zamowienia": {"zamowienia": [], "oddzialy": [], "czas": "10:00"}, "/api/tpms": {"lista": [{"id": 1, "nazwa": "TPMS CZUJNIK KIA", "producent": "CUB", "rodzaj": "zam", "demo": False, "marki": ["KIA"], "zawor": "", "stan": 5, "magazyny": {"Opole": 5}, "netto": 90, "brutto_zak": 110.7, "netto_kat": 90, "grupa": 1}], "q": {"ilosc": 4, "marki": ["KIA"], "slowa": []}, "rodzaje": {"zam": "zamiennik"}, "zrodlo": ""}}
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
                       "zapTog()", "zapTog()", "widok('t')", "tSzukaj()", "tRender()", "kDodaj(1,4,'TPMS CZUJNIK KIA')", "widok('o')"):
                try:
                    pg.evaluate(js)
                except Exception as e:
                    bledy.append("%s: %s" % (js, e))
                pg.wait_for_timeout(250)
            b.close()
    finally:
        p.unlink()
    assert not bledy, bledy


def test_niepelny_rozmiar_w_oknie():
    """Szybkie polecenie „zima r16” na prawdziwym silniku: pasek rozmiarów filtruje, oferta z opon dwóch rozmiarów
    trafia do silnika jako osobne pozycje z prawdziwymi rozmiarami (bez gwiazdek)."""
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        print("  (pominięty – brak Playwright)")
        return
    sys.path.insert(0, str(ROOT / "tests"))
    import test_oferty as T
    from oferty import silnik as S
    T._setup()
    db = T.DB + [T._p(7, "DĘBICA Z195/65 R16 FRIGO 2 92H", 40, 200.0, "DĘBICA", "FRIGO 2", "ZIMOWA", "BUDGET")]

    class Kat:
        def __call__(self, s):
            return None

        def wzorzec(self, wz, marki, sezony):
            return [dict(p) for p in db]
    stare = dict(S.KONTO)
    S.KONTO.update(katalog=Kat(), katalog_info=lambda: "z pliku", oddzialy=["Latex Wrocław"], oddzialy_dane=T.ODDZ, kto="T")
    oferty = []

    def handle(path, body):
        if path == "/api/offer":
            oferty.append(body)
        c, r = S.handle(path, body)
        return [c, r]
    html = (ROOT / "app/oferty/index.html").read_text(encoding="utf-8").replace(
        "<head>", "<head><script>window.alert=window.confirm=()=>true;window.pywebview={api:{call:async(p,b)=>{const r=await window.pyCall(p,b||null);"
        "return{code:r[0],body:r[1]}}}};</script>", 1)
    p = ROOT / "app/oferty/_test_js2.html"
    p.write_text(html, encoding="utf-8")
    bledy = []
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(args=["--no-sandbox"])
            pg = b.new_page()
            pg.expose_function("pyCall", handle)
            pg.on("pageerror", lambda e: bledy.append(str(e)))
            pg.goto(p.as_uri())
            pg.wait_for_timeout(800)
            pg.fill("#quick", "zima r16")
            pg.evaluate("quick()")
            pg.wait_for_timeout(1200)
            chips = pg.evaluate("[...document.querySelectorAll('#res .rozf button')].map(b=>b.textContent.trim())")
            assert len(chips) == 2 and any(c.startswith("205/55 R16") for c in chips), chips
            assert "R16 – wszystkie rozmiary" in pg.inner_text("#res")
            pg.evaluate("document.querySelector('#res .rozf button').click()")   # filtr: jeden rozmiar
            pg.wait_for_timeout(200)
            widoczne = pg.evaluate("new Set([...document.querySelectorAll('#res tr td:nth-child(3) b')].map(x=>x.textContent)).size")
            assert widoczne == 1, widoczne
            pg.evaluate("document.querySelector('#res .rozf button.on').click()")   # zdjęcie filtra
            pg.wait_for_timeout(200)
            pg.evaluate("""(()=>{const ks=[...document.querySelectorAll('#res .pick')];const roz=new Set();for(const k of ks){
                const r=k.closest('tr').children[2].textContent;if(!roz.has(r)){roz.add(r);k.click()}}})()""")
            pg.evaluate("offer()")
            pg.wait_for_timeout(1500)
            oferta_byla = pg.evaluate("$('#outCard').style.display!=='none'")
            stary_oid = pg.evaluate("OID")
            pg.fill("#quick", "zima r16")   # nowe szybkie polecenie czyści poprzednią ofertę (2026-11-18)
            pg.evaluate("quick()")
            pg.wait_for_timeout(1200)
            po = pg.evaluate("[$('#outCard').style.display, SEL.size, OID, $('#quick').value]")
            b.close()
    finally:
        p.unlink()
        S.KONTO.clear(); S.KONTO.update(stare)
    assert not bledy, bledy
    assert oferty, "brak wywołania oferty"
    assert oferta_byla and po[:2] == ["none", 0] and po[2] != stary_oid and po[3] == "zima r16", po
    o = oferty[-1]
    assert sorted(v["rozmiar"] for v in o["pojazdy"]) == ["195/65 R16", "205/55 R16"], o["pojazdy"]
    assert sorted(o["wybor"]) == ["195/65 R16", "205/55 R16"] and all("*" not in k for k in o["sel"]), o




def test_szukanie_zamowienia_po_fakturze():
    """2026-11-18: w „Zrealizowanych” wyszukiwarka znajduje zamówienie po numerze faktury i numerze obcym."""
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        print("  (pominięty – brak Playwright)")
        return
    z = {"nr": "25354046318", "nr_erp": "000734816/26", "nr_zew": "zamowienie jakubczyk", "status": 6, "status_txt": "Zrealizowane",
         "data": "2026-11-17", "kto": "Detal Wrocław", "zamowil": "", "magazyn": "Ruda Śląska", "odbiorca": "", "dostawa": {},
         "komentarz": "", "pozycje": [], "faktury": ["CH0461690/26"], "netto": 1108.8, "szt": 4, "do_wydania": 0}
    odp = {"/api/cfg": {"zamowienia": True, "admin": True, "oddzialy": [], "oddzialy_dane": {}, "premium": [], "progi": []},
           "/api/zamkniete": {"zamowienia": [z], "faktur": 1, "od": "2026-11-16", "do": "2026-11-18", "czas": "10:00"},
           "/api/zamowienia": {"zamowienia": [], "czas": "10:00"}}
    mock = ("window.alert=window.confirm=window.prompt=()=>true;const ODP=%s;window.pywebview={api:{call:async(p,b)=>"
            "({code:200,body:ODP[Object.keys(ODP).find(k=>p.startsWith(k))]||{}})}};" % json.dumps(odp))
    html = (ROOT / "app/oferty/index.html").read_text(encoding="utf-8").replace("<head>", "<head><script>" + mock + "</script>", 1)
    p = ROOT / "app/oferty/_test_js2.html"
    p.write_text(html, encoding="utf-8")
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(args=["--no-sandbox"])
            pg = b.new_page()
            pg.goto(p.as_uri())
            pg.wait_for_timeout(500)
            pg.evaluate("openZam()")
            pg.wait_for_timeout(300)
            pg.evaluate("zTab(document.querySelector('.zt[data-t=h]'))")
            pg.wait_for_timeout(500)
            wyn = {}
            for q in ("CH0461690/26", "ch0461690", "jakubczyk", "000734816"):
                pg.evaluate("q=>{$('#zq').value=q;zDraw()}", q)
                wyn[q] = pg.evaluate("document.querySelectorAll('#zL .zk').length")
            b.close()
    finally:
        p.unlink()
    assert all(v == 1 for v in wyn.values()), wyn


def test_pamiec_pol_numery_uwagi():
    """2026-11-20: pola „Numery i uwagi” podpowiadają z historii i zapamiętują po udanym zamówieniu (localStorage)."""
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        print("  (pominięty – brak Playwright)")
        return
    odp = {"/api/cfg": {"zamawianie": True, "oferty": True, "admin": True, "oddzialy": [], "oddzialy_dane": {}, "premium": [], "progi": []},
           "/api/koszyk/adresy": {"adresy": []}, "/api/koszyk/odswiez": {"pozycje": [], "czas": "10:00"}}
    mock = ("window.alert=window.confirm=window.prompt=()=>true;const ODP=%s;window.pywebview={api:{call:async(p,b)=>"
            "({code:200,body:ODP[Object.keys(ODP).find(k=>p.startsWith(k))]||{}})}};" % json.dumps(odp))
    html = (ROOT / "app/oferty/index.html").read_text(encoding="utf-8").replace("<head>", "<head><script>" + mock + "</script>", 1)
    p = ROOT / "app/oferty/_test_js3.html"
    p.write_text(html, encoding="utf-8")
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(args=["--no-sandbox"])
            pg = b.new_page()
            pg.goto(p.as_uri())
            pg.wait_for_timeout(400)
            pg.evaluate("openKosz()")
            pg.wait_for_timeout(200)
            # historia w pamięci -> podpowiedź po wpisaniu fragmentu
            pg.evaluate("localStorage.setItem('oferty_pola_hist',JSON.stringify({opis:['DW 912AC','DW 7KT55'],nr:[],uw:[]}))")
            pg.fill("#kOpis", "912")
            pg.wait_for_timeout(150)
            podp = pg.eval_on_selector_all("#kNumUw .khac.on .it .t", "els=>els.map(e=>e.textContent)")
            assert podp == ["DW 912AC"], podp
            # klik w podpowiedź wypełnia pole
            pg.eval_on_selector("#kNumUw .khac.on .it .t", "e=>e.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}))")
            assert pg.input_value("#kOpis") == "DW 912AC"
            # zapamiętywanie: dedup (bez względu na wielkość liter), najnowsze na górze, limit 20
            wynik = pg.evaluate("""()=>{localStorage.removeItem('oferty_pola_hist');
              for(let i=0;i<25;i++)khRemember('nr','NR'+i);
              khRemember('nr','nr3');            // duplikat (inna wielkość liter) -> na górę, bez powtórki
              const a=khLoad().nr;return [a.length,a[0],a.filter(x=>x.toUpperCase()==='NR3').length]}""")
            assert wynik == [20, "nr3", 1], wynik
            b.close()
    finally:
        p.unlink()


if __name__ == "__main__":
    test_okna_ofert_bez_bledow_js()
    test_niepelny_rozmiar_w_oknie()
    test_szukanie_zamowienia_po_fakturze()
    test_pamiec_pol_numery_uwagi()
    print("Okna Ofert bez błędów JS")
