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
           "/api/koszyk/odswiez": {"pozycje": [], "czas": "10:00"}, "/api/zamowienia": {"zamowienia": [], "oddzialy": [], "czas": "10:00"}, "/api/tpms": {"lista": [{"id": 1, "nazwa": "TPMS CZUJNIK KIA", "producent": "CUB", "rodzaj": "zam", "demo": False, "marki": ["KIA"], "zawor": "", "stan": 5, "magazyny": {"Opole": 5}, "netto": 90, "brutto_zak": 110.7, "netto_kat": 90, "grupa": 1}], "q": {"ilosc": 4, "marki": ["KIA"], "slowa": []}, "rodzaje": {"zam": "zamiennik"}, "zrodlo": ""},
           "/api/ws_raport": {"dzis": 250, "limit": 300, "osoby": [{"email": "a@b.pl", "imie": "<b>Jan</b>", "n": 250}], "dni": [{"dzien": "2026-11-27", "n": 250}]},
           "/api/ws_limit": {"dzis": 250, "limit": 5000, "osoby": [], "dni": []},
           "/api/felgi_oferta": {"propozycje": [{"nr": 1, "pozycje": [{"k": "felga", "nazwa": "Felga X", "opis": "alu", "q": 4, "c": 523, "w": 2092}], "razem": 2092, "blad": ""},
                                                {"nr": 2, "pozycje": [{"k": "felga", "nazwa": "Felga Y", "q": 4, "c": 400, "w": 1600}], "razem": 1600, "blad": 'Felga 2 ma 17", opony są R18 – nie pasują.'},
                                                {"nr": 3, "pozycje": [{"k": "felga", "nazwa": "Felga Z", "q": 4, "c": 400, "w": 1600}], "razem": 1600, "blad": "", "ostrz": "Felga 3 ma 16\""}],
                                 "edycja": [{"id": 231798, "k": "felga", "nr": 1, "nazwa": "Felga X", "zakup": 462, "auto": 523, "cena": 523, "recznie": False}],
                                 "wymiany": [{"klucz": "R17|osobowy", "opis": "Montaż R17", "cennik": 50, "auto": 50, "cena": 50, "recznie": False}], "uwagi": []},
           "/api/felgi_pdf": {"plik": "x.pdf"},
           "/api/felgi_zdjecia": {"zdjecia": {"231798": ["https://xpartner.net.pl/descriptionFiles/images/1/abc.jpg"]}},
           "/api/felgi": {"lista": [{"id": 231798, "nazwa": "DIEWE NEVE 7X17 5X112 ET46/57.1", "szer": "7", "sred": "17", "pcd": "5x112", "et": "46",
                                     "otwor": "57.1", "rodzaj": "aluminiowa", "producent": "DIEWE", "model": "NEVE", "kod": "N", "demo": False,
                                     "stan": 4, "brutto_zak": 462.14, "cena": 523, "foto": "", "marki": []}], "q": {"ilosc": 4}, "marza": 13, "zrodlo": ""}}
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
            for js in ("openCfg()", "saveCfg()", "openCfg()", "cTab(document.querySelector('.ctabs button[data-t=fe]'))",
                       "document.querySelector('input[name=ftryb][value=kwota]').checked=true;drawFProgi()", "FPROGI.push({do:null,kwota:50});drawFProgi()",
                       "document.querySelector('input[name=ntryb][value=kwota]').checked=true;drawProgi()",
                       "cTab(document.querySelector('.ctabs button[data-t=pdf]'))", "cTab(document.querySelector('.ctabs button[data-t=ko]'))",
                       "cTab(document.querySelector('.ctabs button[data-t=og]'))", "wsRaport(5000)", "saveCfg()", "dlg.close()", "openHist()", "hdlg.close()", "openKosz()", "kdlg.close()", "openZam()",
                       "zapTog()", "zapTog()", "widok('t')", "tSzukaj()", "tRender()", "kDodaj(1,4,'TPMS CZUJNIK KIA')",
                       "widok('f')", "fSzukaj()", "fRender()", "fWybierz(231798)", "fLicz()", "fUst('mon',true)", "fUst('rf','10')", "fSetC(231798,'600')", "fSetW('R17|osobowy','40')",
                       "fWybierzCzujniki()", "tSzukaj()", "fDodajCzujnik(1)", "fWybierzOpony()", "fKompletKoniec()", "fZdjecia(true)",
                       "fPdf(document.querySelector('#fUl .ulk:not([disabled])'),0)", "fPdf(document.createElement('button'),-1)", "fZapiszUw()",
                       "fZHist({felgi_dane:[{id:5,nazwa:'GMP',sred:'18'}],ilosc:4,rabat:{f:'5'},typ_oferty:'felgi'},{oid:'x',owner:''})", "fUsun(5)", "fWybierz(231798)", "fWyczysc()", "widok('o')"):
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


def test_faktura_bez_subkonta_widoczna_przy_filtrze_oddzialu():
    """2026-11-20: faktury bez przypisanego oddziału (tylko z faktury / bez zamówienia) nie trafiają pod wybrany
    oddział (xPartner nie oddaje kodu odbiorcy przez API) – widać je dopiero pod „wszystkie subkonta”."""
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        print("  (pominięty – brak Playwright)")
        return
    def zam(nr, nr_erp, kto, faktura, netto, zfakt=False, bez=False, status=6, txt="Zrealizowane", mag=""):
        z = {"nr": nr, "nr_erp": nr_erp, "nr_zew": "", "status": status, "status_txt": txt, "data": "2026-11-20",
             "kto": kto, "zamowil": "", "magazyn": mag, "odbiorca": "", "dostawa": {}, "komentarz": "",
             "pozycje": [], "faktury": [faktura], "netto": netto, "szt": 4, "do_wydania": 0}
        if zfakt:
            z["z_faktury"] = True
        if bez:
            z["bez_zamowienia"] = True
        return z
    z_wroc = zam("25354046400", "000740000/26", "Detal Wrocław", "CH0460000/26", 100)          # potwierdzony Wrocław
    z_tylko = zam("", "000747670/26", "", "CH0469205/26", 1778.68, zfakt=True, status=0, txt="tylko z faktury")
    z_bez = zam("", "", "", "CH0470167/26", 999, zfakt=True, bez=True, status=0, txt="faktura bez zamówienia", mag="Opole")
    odp = {"/api/cfg": {"zamawianie": True, "oferty": True, "admin": True, "oddzialy": [], "oddzialy_dane": {}, "premium": [], "progi": []},
           "/api/zamkniete": {"zamowienia": [z_wroc, z_tylko, z_bez], "faktur": 3, "od": "2026-11-18", "do": "2026-11-20", "czas": "12:00"},
           "/api/zamowienia": {"zamowienia": [], "czas": "12:00"}}
    mock = ("window.alert=window.confirm=window.prompt=()=>true;const ODP=%s;window.pywebview={api:{call:async(p,b)=>"
            "({code:200,body:ODP[Object.keys(ODP).find(k=>p.startsWith(k))]||{}})}};" % json.dumps(odp))
    html = (ROOT / "app/oferty/index.html").read_text(encoding="utf-8").replace("<head>", "<head><script>" + mock + "</script>", 1)
    p = ROOT / "app/oferty/_test_js4.html"
    p.write_text(html, encoding="utf-8")
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(args=["--no-sandbox"])
            pg = b.new_page()
            pg.goto(p.as_uri())
            pg.wait_for_timeout(400)
            pg.evaluate("openZam()")
            pg.wait_for_timeout(200)
            pg.evaluate("zTab(document.querySelector('.zt[data-t=h]'))")
            pg.wait_for_timeout(500)
            def tekst():
                return " || ".join(pg.eval_on_selector_all("#zL .zk .h", "els=>els.map(e=>e.textContent)"))
            pg.select_option("#zkto", label="Detal Wrocław")
            pg.wait_for_timeout(150)
            t = tekst()
            assert "000740000/26" in t, t                                       # potwierdzony Wrocław widoczny
            assert "000747670/26" not in t, ("faktura bez oddzialu nie pod Wroclawiem", t)
            assert "CH0470167/26" not in t, ("faktura bez zamowienia (Opole) nie pod Wroclawiem", t)
            pg.select_option("#zkto", value="")   # wszystkie subkonta
            pg.wait_for_timeout(150)
            t2 = tekst()
            assert "000747670/26" in t2 and "CH0470167/26" in t2, ("nieprzypisane faktury widoczne pod wszystkie subkonta", t2)
            b.close()
    finally:
        p.unlink()


def test_bydgoszcz_48h_w_koszyku_i_zamowieniach():
    """2026-11-21: koszyk prognozuje dostawę z Bydgoszczy (pewne/może), potwierdzenie i otwarte zamówienia pokazują 48 h."""
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        print("  (pominięty – brak Playwright)")
        return
    otw = {"nr": "25354046500", "nr_erp": "000750000/26", "nr_zew": "", "status": 3, "status_txt": "W realizacji", "data": "2026-11-21",
           "kto": "Detal Wrocław", "zamowil": "", "magazyn": "Bydgoszcz", "odbiorca": "", "dostawa": {}, "komentarz": "",
           "pozycje": [], "faktury": [], "netto": 100, "szt": 4, "do_wydania": 4}
    odp = {"/api/cfg": {"zamawianie": True, "oferty": True, "admin": True, "oddzialy": [], "oddzialy_dane": {}, "premium": [], "progi": []},
           "/api/zamowienia": {"zamowienia": [otw], "czas": "08:00"}}
    mock = ("window.alert=window.confirm=window.prompt=()=>true;const ODP=%s;window.pywebview={api:{call:async(p,b)=>"
            "({code:200,body:ODP[Object.keys(ODP).find(k=>p.startsWith(k))]||{}})}};" % json.dumps(odp))
    html = (ROOT / "app/oferty/index.html").read_text(encoding="utf-8").replace("<head>", "<head><script>" + mock + "</script>", 1)
    p = ROOT / "app/oferty/_test_js5.html"
    p.write_text(html, encoding="utf-8")
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(args=["--no-sandbox"])
            pg = b.new_page()
            pg.goto(p.as_uri())
            pg.wait_for_timeout(400)
            w = pg.evaluate("""()=>[JSON.stringify(kDal({'Bydgoszcz':12},4)),JSON.stringify(kDal({'Bydgoszcz':50,'Czechowice-Dziedzice':50},4)),
               JSON.stringify(kDal({'Opole':50},4)),JSON.stringify(kDal({'Bydgoszcz':50,'Opole':2},4))]""")
            assert '"pewne":true' in w[0] and '"pewne":false' in w[1] and w[2] == "null" and '"pewne":true' in w[3], w
            # 50 = „50+”: przy 60 szt. nie wiemy, czy Czechowice wystarczą – tylko „może”; 49 to dokładna liczba
            w2 = pg.evaluate("""()=>[kDal({'Czechowice-Dziedzice':50,'Bydgoszcz':50},60).pewne,kDal({'Czechowice-Dziedzice':49,'Bydgoszcz':50},60).pewne,
               (CFG.bydgoszcz_dostawa='2 dni robocze',kDal({'Bydgoszcz':5},4).czas+'|'+dal48('Bydgoszcz'))]""")
            assert w2[0] is False and w2[1] is True and w2[2] == "2 dni robocze|2 dni robocze", w2
            pg.evaluate("delete CFG.bydgoszcz_dostawa")
            pg.evaluate("""()=>{KOSZ=[{id:1,nazwa:'A',ilosc:4},{id:2,nazwa:'B',ilosc:4},{id:3,nazwa:'C',ilosc:4}];
               const d=(id,m)=>({id,ok:true,nazwa:'Opona '+id,netto:100,brutto:123,netto_kat:100,stan:50,magazyny:m});
               KDANE={1:d(1,{'Bydgoszcz':12}),2:d(2,{'Bydgoszcz':50,'Czechowice-Dziedzice':50}),3:d(3,{'Opole':50})};kDraw()}""")
            kl = pg.inner_text("#kL")
            assert "1 pozycja (4 szt.) pojedzie co najmniej częściowo z magazynu Bydgoszcz" in kl and "może pójść z Bydgoszczy" in kl, kl
            assert pg.eval_on_selector_all("#kL tr.k48", "e=>e.length") == 1
            assert pg.eval_on_selector_all("#kL .bdg48", "e=>e.length") == 2   # znaczki w wierszach 1 (pewne) i 2 (może)
            pg.evaluate("openZam()")
            pg.wait_for_timeout(500)
            zl = pg.inner_text("#zL")
            assert "ok. 48 h" in zl, zl
            b.close()
    finally:
        p.unlink()


def test_historia_felg_bez_xss_i_whatsapp_bez_starego_pdf():
    """Recenzja 1.2.21: wpis felg w Historii z podrobionymi danymi nie wykonuje skryptu; zmiana oferty kasuje PDF do WhatsApp."""
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        print("  (pominięty – brak Playwright)")
        return
    zly = '<img src=x onerror="window.__XSS=1">'
    rec = {"typ_oferty": "felgi", "felgi_dane": [{"id": zly, "nazwa": zly, "stan": zly, "kod": zly}, {"id": 7, "nazwa": "OK", "stan": 4}],
           "opona": {"id": zly, "nazwa": zly}, "czujnik": {"id": 3, "nazwa": zly, "kod": zly}, "ilosc": 4, "rabat": {"f": zly}, "klient": zly}
    odp = {"/api/cfg": {"oddzialy": ["Latex Wrocław"], "zamawianie": True, "admin": False, "felgi_max": 3},
           "/api/history?id": rec, "/api/history": {"lista": [{"id": 5, "oid": "x", "owner": "", "typ": "felgi", "warianty": [], "kto": "a", "klient": zly, "pojazdy": ""}], "admin": False, "me": ""},
           "/api/felgi_oferta": {"propozycje": [{"nr": 1, "pozycje": [{"k": "felga", "nazwa": zly, "q": 4, "c": 1, "w": 4}], "razem": 4, "blad": ""}],
                                 "edycja": [{"id": zly, "k": "felga", "nr": 1, "nazwa": zly, "zakup": 1, "auto": 1, "cena": 1, "recznie": True}], "wymiany": [], "uwagi": []}}
    mock = ("window.alert=window.confirm=window.prompt=()=>true;const ODP=%s;window.pywebview={api:{call:async(p,b)=>"
            "({code:200,body:ODP[Object.keys(ODP).find(k=>p.startsWith(k))]||{}})}};" % json.dumps(odp))
    html = (ROOT / "app/oferty/index.html").read_text(encoding="utf-8").replace("<head>", "<head><script>" + mock + "</script>", 1)
    p = ROOT / "app/oferty/_test_js2.html"
    p.write_text(html, encoding="utf-8")
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(args=["--no-sandbox"])
            pg = b.new_page()
            bledy = []
            pg.on("pageerror", lambda e: bledy.append(str(e)))
            pg.goto(p.as_uri())
            pg.wait_for_timeout(500)
            pg.evaluate("openHist()")
            pg.wait_for_timeout(300)
            pg.evaluate("restoreHist(5)")
            pg.wait_for_timeout(800)
            assert pg.evaluate("window.__XSS") is None, "XSS z Historii ofert felg"
            assert pg.evaluate("FWS.length") == 1 and pg.evaluate("FOP") is None
            pg.evaluate("FPDF='stary.pdf';fUst('il','3')")
            pg.wait_for_timeout(600)
            assert pg.evaluate("FPDF") == ""
            pg.evaluate("FPDF='stary.pdf';FOP=null;fWybrane();fLicz()")
            pg.wait_for_timeout(400)
            assert pg.evaluate("FPDF") == "" and pg.evaluate("window.__XSS") is None
            b.close()
    finally:
        p.unlink()
    assert not bledy, bledy


def test_dobor_po_aucie_w_oknie():
    """2026-11-27: okno „Dobierz po aucie” (felgi i opony) – listy, rozmiary, szukanie felg z oceną, opony do szybkiego polecenia."""
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        print("  (pominięty – brak Playwright)")
        return
    zly = '<img src=x onerror="window.__XSS=1">'
    auto = {"nazwa": "VW Golf " + zly, "pcd": "5x112", "cb": 57.1, "gwint": "M14 x 1.5", "mocowanie": "Lug bolts", "moment": "140 Nm", "lata": "2019–2024",
            "kola": [{"oe": True, "przod": {"sred": 17.0, "szer": 7.5, "et": 51.0, "felga": "7.5Jx17 ET51", "opona": "225/45ZR17", "opona_txt": "225/45ZR17 91W", "cisn": 2.4},
                      "tyl": None, "zima": False, "rf": False, "xl": False, "stal": False}], "kola_opony": ["225/45 R17"]}
    mock = ("window.alert=window.confirm=window.prompt=()=>true;const AUTO=%s;window.pywebview={api:{call:async(p,b)=>{"
            "if(p.startsWith('/api/cfg'))return{code:200,body:{oddzialy:['Latex Wrocław'],felgi_max:3,mod_ceny:false}};"
            "if(p.startsWith('/api/auto')){const m=b.m;return{code:200,body:m==='by_model'?{auto:AUTO}:{lista:[{slug:'x1',name:m+' '+'%s'}]}}}"
            "if(p.startsWith('/api/felgi'))return{code:200,body:{lista:[{id:2,nazwa:'FELGA',sred:'17',szer:'7.5',pcd:'5x112',et:'51',otwor:'57.1',stan:8,cena:500,brutto_zak:400,ocena:'ok',ocena_txt:'pasuje fabrycznie',kod:'',producent:'X',model:''},"
            "{id:3,nazwa:'FELGA2',sred:'17',pcd:'5x108',stan:8,cena:400,brutto_zak:300,ocena:'nie',ocena_txt:'inny rozstaw',kod:'',producent:'X',model:''}],q:{ilosc:4},wzor:'w'}};"
            "if(p.startsWith('/api/quick'))return{code:200,body:{pojazdy:[{rozmiar:'225/45 R17',ilosc:4}],sezony:[],klasy:[],producenci:[]}};"
            "return{code:200,body:{}}}}};" % (json.dumps(auto), zly.replace("'", "\\'")))
    html = (ROOT / "app/oferty/index.html").read_text(encoding="utf-8").replace("<head>", "<head><script>" + mock + "</script>", 1)
    p = ROOT / "app/oferty/_test_js3.html"
    p.write_text(html, encoding="utf-8")
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(args=["--no-sandbox"])
            pg = b.new_page()
            bledy = []
            pg.on("pageerror", lambda e: bledy.append(str(e)))
            pg.goto(p.as_uri())
            pg.wait_for_timeout(500)
            for js in ("widok('f')", "aOtworz('f')", "$('#a_make').value='x1';aZmiana('make')", "$('#a_model').value='x1';aZmiana('model')",
                       "$('#a_year').value='x1';aZmiana('year')", "$('#a_mod').value='x1';aZmiana('mod')"):
                pg.evaluate(js)
                pg.wait_for_timeout(250)
            assert "225/45ZR17 91W" in pg.inner_text("#aWyn") and "140 Nm" in pg.inner_text("#aWyn")
            pg.evaluate("aFelgi(0)")
            pg.wait_for_timeout(500)
            assert pg.evaluate("$('#fq').value").startswith("5x112 R17")
            assert pg.evaluate("document.querySelectorAll('#fRes .fw').length") == 1   # niepasująca ukryta
            assert "pasuje fabrycznie" in pg.inner_text("#fRes")
            pg.evaluate("ATYLKO=false;fRender(true)")
            assert pg.evaluate("document.querySelectorAll('#fRes .fw').length") == 2
            pg.evaluate("fWybierz(2)")
            pg.wait_for_timeout(400)
            assert "Dobrane do" in pg.inner_text("#fOfAuto") and pg.evaluate("fCialo().auto_pdf") == 1
            assert pg.evaluate("document.body.classList.contains('bezCen')")   # bez uprawnienia do cen – pola cen ukryte
            assert pg.evaluate("[...document.querySelectorAll('#fEdit .cenaEd')].every(e=>getComputedStyle(e).display==='none')")
            pg.evaluate("aOtworz('o')")
            pg.wait_for_timeout(300)
            pg.evaluate("aWczytaj(0)")
            pg.wait_for_timeout(400)
            pg.evaluate("aOpony(0)")
            pg.wait_for_timeout(600)
            assert pg.evaluate("$('#quick').value").startswith("225/45 R17")
            assert pg.evaluate("window.__XSS") is None
            b.close()
    finally:
        p.unlink()
    assert not bledy, bledy


JPG8 = "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAAIAAgDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDi6KKK+ZP3E//Z"   # prawdziwy JPEG 8x8


def test_zdjecia_felg_z_bazy_w_oknie():
    """2026-11-27: zdjęcia felg z bazy (data:image/jpeg), „zdjęcie wkrótce” dla niesprawdzonych, bez okna logowania;
    administrator widzi stan zdjęć w Ustawieniach → Felgi."""
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        print("  (pominięty – brak Playwright)")
        return
    jpg = JPG8
    f = lambda i: {"id": i, "nazwa": "FELGA %d" % i, "sred": "17", "szer": "7", "pcd": "5x112", "et": "45", "otwor": "57.1", "stan": 8,
                   "cena": 500, "brutto_zak": 400, "kod": "", "producent": "X", "model": "", "foto": "", "marki": []}
    odp = {"/api/cfg": {"oddzialy": ["Latex Wrocław"], "felgi_max": 3, "admin": True},
           "/api/felgi_zdjecia_pelne": {"zdjecia": {"1": [jpg, jpg]}},
           "/api/felgi_zdjecia": {"zdjecia": {"1": jpg, "3": ""}, "wkrotce": [2]},
           "/api/felgi_foto_stan": {"w_bazie": 1200, "sprawdzone": 1500, "trwa": True, "zrobione": 40, "wszystkie": 300, "start": True},
           "/api/felgi": {"lista": [f(1), f(2), f(3)], "q": {"ilosc": 4}, "zrodlo": ""}}
    mock = ("window.alert=window.confirm=window.prompt=()=>true;const ODP=%s;window.pywebview={api:{call:async(p,b)=>"
            "({code:200,body:ODP[Object.keys(ODP).sort((a,b)=>b.length-a.length).find(k=>p.startsWith(k))]||{}})}};" % json.dumps(odp))
    html = (ROOT / "app/oferty/index.html").read_text(encoding="utf-8").replace("<head>", "<head><script>" + mock + "</script>", 1)
    p = ROOT / "app/oferty/_test_js4.html"
    p.write_text(html, encoding="utf-8")
    bledy = []
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(args=["--no-sandbox"])
            pg = b.new_page()
            pg.on("pageerror", lambda e: bledy.append(str(e)))
            pg.goto(p.as_uri())
            pg.wait_for_timeout(500)
            pg.evaluate("widok('f')")
            pg.fill("#fq", "R17")
            pg.evaluate("fSzukaj()")
            pg.wait_for_timeout(900)
            assert pg.evaluate("document.querySelectorAll('#fRes img.ph').length") == 1
            assert pg.evaluate("document.querySelector('#fRes img.ph').src").startswith("data:image/jpeg")
            assert "zdjęcie wkrótce" in pg.inner_text("#fRes") and pg.inner_text("#fRes").count("zdjęcie wkrótce") == 1
            assert "zaloguj" not in pg.inner_text("#fMsg").lower() and "brak zdjęcia w xPartner" in pg.inner_text("#fRes")
            assert pg.evaluate("Object.keys(fCialo().fotos).length") == 0   # przeliczenie oferty bez zdjęć
            pg.evaluate("fWybierz(1)")
            pg.wait_for_timeout(300)
            pg.evaluate("fPelne()")
            pg.wait_for_timeout(300)
            assert pg.evaluate("fCialo(1).fotos[1].length") == 2   # do PDF pełne zdjęcia z bazy
            # 2026-11-27: zmiana oferty po zrobieniu PDF = nowa oferta (nowy numer), poprzednia zostaje w Historii
            o1 = pg.evaluate("fPoPdf();FOID")
            pg.evaluate("fLicz()")
            pg.wait_for_timeout(200)
            assert pg.evaluate("FOID") == o1   # bez zmian – ta sama oferta
            pg.evaluate("FIL=2;fLicz()")
            pg.wait_for_timeout(200)
            assert pg.evaluate("FOID") != o1 and not pg.evaluate("FZAP") and "NOWA oferta" in pg.evaluate("FNOWA_INFO")
            pg.evaluate("openCfg()")
            pg.wait_for_timeout(500)
            t = pg.inner_text("#fotoBox")
            assert "1200" in t.replace("\xa0", "").replace(" ", "") and "40" in t and "300" in t
            b.close()
    finally:
        p.unlink()
    assert not bledy, bledy


def test_zdjecia_felg_po_kilku_wyszukiwaniach():
    """Recenzja 1.2.29: po kilku wyszukiwaniach (setki felg) zdjęcia widocznych felg nie znikają z pamięci okna."""
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        print("  (pominięty – brak Playwright)")
        return
    jpg = JPG8
    mock = ("window.alert=window.confirm=window.prompt=()=>true;const J='%s';const f=i=>({id:i,nazwa:'FELGA '+i,sred:'17',szer:'7',pcd:'5x112',et:'45',otwor:'57.1',stan:8,cena:500,brutto_zak:400,kod:'',producent:'X',model:'',foto:'',marki:[]});"
            "window.pywebview={api:{call:async(p,b)=>{if(p.startsWith('/api/cfg'))return{code:200,body:{oddzialy:['Latex Wrocław'],felgi_max:3,felgi_na_stronie:200}};"
            "if(p.startsWith('/api/felgi_zdjecia'))return{code:200,body:{zdjecia:Object.fromEntries(b.ids.map(i=>[i,J])),wkrotce:[]}};"
            "if(p.startsWith('/api/felgi')){const [a,n]=b.q.split(' ').map(Number);return{code:200,body:{lista:Array.from({length:n},(_,k)=>f(a+k)),q:{ilosc:4},zrodlo:''}}}"
            "return{code:200,body:{}}}}};" % jpg)
    html = (ROOT / "app/oferty/index.html").read_text(encoding="utf-8").replace("<head>", "<head><script>" + mock + "</script>", 1)
    p = ROOT / "app/oferty/_test_js5.html"
    p.write_text(html, encoding="utf-8")
    bledy = []
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(args=["--no-sandbox"])
            pg = b.new_page()
            pg.on("pageerror", lambda e: bledy.append(str(e)))
            pg.goto(p.as_uri())
            pg.wait_for_timeout(400)
            pg.evaluate("widok('f');FPOK=200")
            for q, n in (("100000 200", 200), ("200000 200", 200), ("10 60", 60), ("5000 200", 200), ("300000 200", 200), ("10 60", 60)):
                pg.fill("#fq", q)
                pg.evaluate("fSzukaj()")
                pg.wait_for_function("!FZDJ_TRWA&&FL.length===%d&&document.querySelectorAll('#fRes .fw').length>0&&document.querySelectorAll('#fRes img.ph').length===document.querySelectorAll('#fRes .fw').length" % n, timeout=20000)
            assert pg.evaluate("FZDJ.size") <= 600
            b.close()
    finally:
        p.unlink()
    assert not bledy, bledy


if __name__ == "__main__":
    test_okna_ofert_bez_bledow_js()
    test_niepelny_rozmiar_w_oknie()
    test_szukanie_zamowienia_po_fakturze()
    test_pamiec_pol_numery_uwagi()
    test_faktura_bez_subkonta_widoczna_przy_filtrze_oddzialu()
    test_bydgoszcz_48h_w_koszyku_i_zamowieniach()
    test_historia_felg_bez_xss_i_whatsapp_bez_starego_pdf()
    test_dobor_po_aucie_w_oknie()
    test_zdjecia_felg_z_bazy_w_oknie()
    test_zdjecia_felg_po_kilku_wyszukiwaniach()
    print("Okna Ofert bez błędów JS")

