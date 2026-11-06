"""Testy modułu OFERTY OPON (silnik): rozpoznawanie zapytań, wyszukiwanie, oferta, historia – bez okna i bez xPartner."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))
from oferty import silnik as S  # noqa: E402


def _p(pid, name, qty, net, prod, model, sez, klasa, li="91", si="H", ext=None):
    attrs = {"Asortyment": "OPONY", "Struktura": "STANDARD", "Producent": prod, "Nazwa bieżnika": model,
             "Indeks nośności": li, "Indeks prędkości": si + "-210KMH", "Klasa": klasa, "Sezon": sez,
             "Rok produkcji": "DOT2026", **(ext or {})}
    return {"id": pid, "kod": "", "ean": "", "nazwa": name, "ilosc": qty, "netto": net, "brutto_zak": round(net * 1.23, 2),
            "netto_kat": net, "attrs": attrs, "magazyny": {}}


DB = [_p(5, "CONTINENTAL L235/55 R18 ECOCONTACT 6 104V XL DOT2025 DEMO", 4, 300.0, "CONTINENTAL", "", "LETNIA", "PREMIUM"),
      _p(1, "BRIDGESTONE Z205/55 R16 BLIZZAK 6 91H", 80, 344.10, "BRIDGESTONE", "BLIZZAK 6", "ZIMOWA", "PREMIUM",
         ext={"Przyczepność na mokrej nawierzchni": "B", "Poziom hałasu": "70 dB"}),
      _p(2, "BARUM Z205/55 R16 POLARIS 6 91H", 99, 236.44, "BARUM", "POLARIS 6", "ZIMOWA", "BUDGET"),
      _p(3, "NOKIAN W205/55 R16 SEASONPROOF 2 94V XL", 60, 0.0, "NOKIAN", "SEASONPROOF 2", "CAŁOROCZNA", "PREMIUM"),
      _p(4, "PIRELLI W215/55 R17 POWERGY 2 ALL SEASON 98W XL", 60, 445.29, "PIRELLI", "POWERGY 2 ALL SEASON", "CAŁOROCZNA", "PREMIUM")]


def _fake(cfg, **q):
    if "productId" in q:
        it = [p for p in DB if p["id"] == int(q["productId"])]
    else:
        it = [p for p in DB if q.get("productName", "") in p["nazwa"]] if not q.get("page") else []
    return len(it), [dict(p) for p in it]


class _Hist:
    def __init__(self):
        self.d = {}

    def get(self, oid):
        return self.d.get(oid)

    def save(self, oid, klient, dane, szukaj):
        self.d[oid] = dane

    def get_id(self, rid):
        return list(self.d.values())[int(rid) - 1]

    def list(self, q=""):
        return [{"id": i + 1, "owner": "a@b.pl", "kto": "Jan", "dane": d} for i, d in enumerate(self.d.values())]


def _setup():
    S.api_call = _fake
    S.KONTO.update(login="x", password="y", ustawienia={}, zapisz=lambda d: None)
    S.HIST = _Hist()
    S.OUT_DIR = tempfile.mkdtemp()


def test_rozmiary_w_dowolnym_zapisie():
    for t in ("205/55 16", "2055516", "205 55 16", "205/55R16", "205-55-16"):
        assert S.find_sizes(t) == ["205/55 R16"], t
    assert S.find_sizes("2254517 premium 2 szt") == ["225/45 R17"]


def test_zapytanie_tekstem():
    r = S.parse_request_text("skoda octavia 2055516 dw5444lw z wymianą 4 czujniki przechowalnia kół srednia")[0]
    assert (r["rej"], r["pojazd"], r["rozmiar"], r["wymiana"], r["tpms"], r["przech"]) == \
        ("DW5444LW", "Skoda Octavia", "205/55 R16", True, 4, "kola")
    q = S.parse_quick("2055516 zimowe premium michelin runflat")
    assert q["sezony"] == ["Zimowa"] and q["klasy"] == ["PREMIUM"] and q["producenci"] == "MICHELIN" and q["runflat"]


def test_wyszukiwanie_pomija_cene_zero():
    _setup()
    r = S.do_search(S.load_cfg(), {"pojazdy": [{"rozmiar": "205/55 R16", "ilosc": 4, "nowe": True}], "sezony": [], "klasy": []})
    ids = [p["id"] for p in r["wyniki"]["205/55 R16"]["wszystkie"]]
    assert 3 not in ids and set(ids) == {1, 2}


def test_oferta_ceny_wymiana_uslugi_historia():
    _setup()
    req = {"oid": "20261105_120000", "klient": "Test", "pojazdy": [
        {"rej": "DW1", "pojazd": "Skoda", "rozmiar": "205/55 R16", "ilosc": 2, "nowe": True, "wymiana": True,
         "tpms": 4, "przech": "opony", "typ": "osobowy"}], "wybor": {"205/55 R16": {"wszystkie": [1]}}, "rabat": "10"}
    code, res = S.handle("/api/offer", req)
    assert code == 200, res
    w = res["warianty"][0]
    # 344,10 × 1,05 × 1,23 = 444,41 → 445 zł; rabat 10% → 400,50 → 401 zł; 2 szt.; wymiana 2 × 44; TPMS 4 × 150; przechowalnia 120
    assert (w["opony"], w["wymiana"], w["tpms"], w["przech"]) == (802.0, 88.0, 600.0, 120.0)
    assert os.path.exists(res["plik"]) and "Test" in res["email"]
    assert S.HIST.get("20261105_120000")["klient"] == "Test"
    code, lst = S.handle("/api/history?q=")
    assert code == 200 and lst["lista"][0]["klient"] == "Test" and lst["lista"][0]["kto"] == "Jan"
    code, one = S.handle("/api/history?id=1")
    assert code == 200 and one["oid"] == "20261105_120000"


def test_brak_loginu_xpartner():
    S.KONTO.update(login="", password="")
    import importlib
    importlib.reload(S)
    code, res = S.handle("/api/search", {"pojazdy": [{"rozmiar": "205/55 R16", "ilosc": 4, "nowe": True}]})
    assert code == 502 and "administratora" in res["error"]


def test_szablon_excel_i_wczytanie():
    _setup()
    from openpyxl import load_workbook
    path = S.szablon_xlsx()
    wb = load_workbook(path)
    ws = wb["Pojazdy"]
    ws.append(["DX1209H", "Skoda", "Superb", "2155517", 2, "SUV", "TAK", "TAK", "TAK"])
    ws.append(["DX3985C", "Skoda", "Octavia", "205/60 16", 0, "osobowy", "TAK", "TAK", "NIE"])
    wb.save(path)
    poj = S.czytaj_xlsx(open(path, "rb").read())
    assert len(poj) == 3
    assert poj[1] == {"rej": "DX1209H", "pojazd": "Skoda Superb", "rozmiar": "215/55 R17", "ilosc": 2, "nowe": True,
                      "wymiana": True, "typ": "suv", "tpms": 2, "przech": "opony"}
    assert poj[2]["ilosc"] == 0 and poj[2]["przech"] == "" and poj[2]["wymiana"] and poj[2]["tpms"] == 4
    assert poj[0]["tpms"] == 0 and poj[0]["przech"] == ""


def test_inna_tabela_excel():
    from openpyxl import Workbook
    import io
    wb = Workbook()
    ws = wb.active
    for r in (["Marka", "Model", "Rejestracja", "Rozmiar", "Wymaga nowych opon"],
              ["SKODA", "OCTAVIA", "DX1522H", "205/60 R16", "TAK"], ["SKODA", "OCTAVIA", "DX3985C", "205/60 R16", "NIE"]):
        ws.append(r)
    b = io.BytesIO()
    wb.save(b)
    poj = S.czytaj_xlsx(b.getvalue())
    assert [(p["rej"], p["ilosc"]) for p in poj] == [("DX1522H", 4), ("DX3985C", 0)]


def test_demo_i_indeks_xpartner():
    _setup()
    p = S.enrich(S.load_cfg(), DB[0])
    assert p["demo"] and p["model_oferta"].endswith("DEMO (opona z demontażu)")
    q = S.parse_quick("2355518 demo")
    assert q["demo"] == "tylko" and S.parse_quick("2355518 bez demo")["demo"] == "bez"
    req = {"oid": "1", "pojazdy": [{"rozmiar": "235/55 R18", "ilosc": 4, "nowe": True}], "wybor": {"235/55 R18": {"wszystkie": [5]}}}
    code, res = S.handle("/api/offer", req)
    assert code == 200 and "DEMO" in res["email"]
    from openpyxl import load_workbook
    ws = load_workbook(res["plik"]).active
    assert ws.cell(4, 7).value == "Indeks xPartner" and ws.cell(5, 7).value == 5 and ws.cell(5, 11).value == "=I5*J5"


def test_marka_z_listy_i_wyszukiwanie_po_marce():
    _setup()
    S.ucz_marki(S.load_cfg())
    assert S.parse_quick("2055516 sailun")["producenci"] == "SAILUN"
    for w, sez in [("w lecie", ["Letnia"]), ("4 pory roku", ["Całoroczna"]), ("całorok", ["Całoroczna"]), ("summer", ["Letnia"]),
                   ("winter", ["Zimowa"]), ("zimówki", ["Zimowa"]), ("wielosezonowe", ["Całoroczna"]), ("platon", []), ("stulecie", [])]:
        assert S.parse_quick("2055516 " + w)["sezony"] == sez, w
    assert S.parse_quick("2055516 conti zimowe")["producenci"] == "CONTINENTAL"
    assert S.parse_quick("2055516 good-year")["producenci"] == "GOODYEAR"
    r = S.do_search(S.load_cfg(), {"pojazdy": [{"rozmiar": "205/55 R16", "ilosc": 4, "nowe": True}], "producenci": "BARUM"})
    assert [p["producent"] for g in r["wyniki"]["205/55 R16"].values() for p in g] == ["BARUM"]
    v = S.parse_request_text("skoda octavia 2055516 dw5444lw sailun")[0]
    assert v["pojazd"] == "Skoda Octavia"


def test_literowki_i_skroty_marek():
    S.ucz_marki()
    for w, m in (("silun", "SAILUN"), ("rodx", "ROADX"), ("conti", "CONTINENTAL"), ("brigestone", "BRIDGESTONE"),
                 ("hankuk", "HANKOOK"), ("michlein", "MICHELIN"), ("goodyar", "GOODYEAR"), ("debica", "DĘBICA"),
                 ("vredstein", "VREDESTEIN"), ("winforce", "WINDFORCE"), ("bfg", "BFGOODRICH")):
        assert S.brand_of_word(w) == m, w
    for w in ("passat", "tiguan", "octavia", "skoda", "toyota", "zimowe", "transit", "ducato"):
        assert S.brand_of_word(w) == "", w
    assert S.parse_quick("2055516 ling long")["producenci"] == "LINGLONG"
    v = S.parse_request_text("vw passat 2055516 dw5444lw silun")[0]
    assert v["pojazd"] == "VW Passat"


def test_doplata_kwotowa_wg_progow():
    _setup()
    S.KONTO["ustawienia"] = {"narzut_tryb": "kwota"}
    cfg = S.load_cfg()
    # zakup netto -> brutto: 300 -> 369 (+50), 500 -> 615 (+70), 800 -> 984 (+90); 325,20 -> 399,996 ≈ 400 (+50)
    assert [S.sell_price(cfg, n) for n in (300, 500, 800, 325.2)] == [419.0, 685.0, 1074.0, 450.0]
    assert S.doplata_progowa(cfg, 400.0) == 50 and S.doplata_progowa(cfg, 400.5) == 70 and S.doplata_progowa(cfg, 899) == 70
    assert S.doplata_progowa(cfg, 900) == 90
    S.KONTO["ustawienia"] = {}


def test_xlsx_bez_wstrzykiwania_formul():
    _setup()
    req = {"oid": "2", "klient": "=HYPERLINK(\"http://zly\")", "pojazdy": [{"rej": "=1+1", "pojazd": "@SUM(A1)", "rozmiar": "205/55 R16",
           "ilosc": 4, "nowe": True}], "wybor": {"205/55 R16": {"wszystkie": [1]}}}
    code, res = S.handle("/api/offer", req)
    assert code == 200
    from openpyxl import load_workbook
    ws = load_workbook(res["plik"]).active
    assert ws.cell(5, 1).value == " =1+1" and ws.cell(5, 2).value == " @SUM(A1)"
    assert str(ws.cell(5, 11).value).startswith("=I5*J5")


ODDZ = {"Latex Wrocław": {"nazwa": "LATEX SERWIS WROCŁAW", "adres": "ul. Krakowska 54a, 50-425 Wrocław", "tel": "71 341 30 60"},
        "Latex Opole": {"nazwa": "LATEX SERWIS OPOLE", "adres": "ul. Krapkowicka 18A, 45-732 Opole", "tel": "77 474 80 89"}}


def _pdf(oddzialy, body_pdf, req_extra=None):
    _setup()
    S.KONTO.update(oddzialy=oddzialy, oddzialy_dane=ODDZ, kto="Ania")
    req = {"oid": "20261105_120000", "klient": "Jan <b>Kowalski</b>", "rabat": "10",
           "pojazdy": [{"rej": "dw1", "pojazd": "Octavia", "rozmiar": "205/55 R16", "ilosc": 4, "nowe": True, "wymiana": True, "tpms": 4, "przech": "opony"}],
           "wybor": {"205/55 R16": {"wszystkie": [1]}}, **(req_extra or {})}
    assert S.handle("/api/offer", req)[0] == 200
    return S.handle("/api/pdf", body_pdf)


def test_pdf_oferty_pozycje_rabat_i_oddzial():
    code, r = _pdf(["Latex Wrocław", "Latex Opole"], {"id": 1, "oddzial": "Latex Opole"})
    assert code == 200 and r["oddzial"] == "Latex Opole", r
    h = r["html"]
    assert "LATEX SERWIS OPOLE" in h and "77 474 80 89" in h and "WROCŁAW" not in h
    assert "Jan &lt;b&gt;Kowalski&lt;/b&gt;" in h and "<b>Kowalski" not in h          # tekst klienta nie staje się HTML
    for txt in ("Opona BRIDGESTONE", "Wymiana opon", "Czujnik ciśnienia TPMS", "Depozyt", "Rabat 10% na opony", "DO ZAPŁATY BRUTTO", "OF/2026/11/05-1200"):
        assert txt in h, txt
    assert "{{" not in h and "}}" not in h


def test_pdf_tylko_oddzial_z_konta():
    # pracownik Opola nie wybierze danych Wrocławia, nawet gdy strona je wyśle
    code, r = _pdf(["Latex Opole"], {"id": 1, "oddzial": "Latex Wrocław"})
    assert code == 200 and r["oddzial"] == "Latex Opole" and "WROCŁAW" not in r["html"]
    # konto bez oddziału -> brak PDF
    code, r = _pdf([], {"id": 1})
    assert code == 500 and "oddziału" in r["error"]
    # oddział bez danych (np. Stangum) -> brak PDF zamiast pustego nagłówka
    code, r = _pdf(["Stangum Opole"], {"id": 1})
    assert code == 500 and "Brak danych oddziału" in r["error"]


def test_pdf_bez_uslug_i_bez_klienta():
    code, r = _pdf(["Latex Wrocław"], {"id": 1}, {"klient": "", "rabat": "", "pojazdy": [{"rozmiar": "205/55 R16", "ilosc": 2, "nowe": True}]})
    h = r["html"]
    assert code == 200 and "Wymiana opon" not in h and "Depozyt" not in h and "TPMS" not in h and "Rabat" not in h
    assert ">Dla<" not in h and "Ważna do" in h and "2 szt." in h


def test_foto_z_api():
    xml = (b"<r><success>true</success><productsCount>1</productsCount><product><productId>7</productId><name>X</name>"
           b"<imageUrl>https://img.example.com/opona.jpg</imageUrl><ean>590</ean></product></r>")
    _, it = S.parse_products(xml)
    assert it[0]["foto"] == "https://img.example.com/opona.jpg" and "imageUrl" in it[0]["pola"]
    _, it = S.parse_products(xml.replace(b"https://img.example.com/opona.jpg", b"http://zly/x.jpg"))
    assert it[0]["foto"] == ""   # tylko https


CSV_TEST = ("﻿LP;Indeks;\"Kod produktu\";Nazwa;Ilość;\"Ilość Opole\";\"Cena katalogowa netto[pln]\";\"Cena zakupu netto[pln]\";"
            "\"Cena zakupu brutto[pln]\";EAN1;Asortyment;Producent;\"Kod EPREL\";Klasa;Sezon;Średnica;Szerokość;Profil;"
            "\"Opory toczenia\";\"Przyczepność na mokrej nawierzchni\";Hałas;\"Poziom hałasu\";\"Przyczepność na śniegu\";Struktura\r\n"
            "1;270722;15310;\"BRIDGESTONE Z205/55 R16 BLIZZAK LM005 91H DOT2026\";50;50;666.00;312.10;383.88;3286341531015;OPONY;"
            "BRIDGESTONE;381909;PREMIUM;ZIMOWA;R16;205;55;C;A;B;\"71 dB\";X;STANDARD\r\n"
            "2;1;;\"CENA ZERO 205/55 R16\";5;5;0;0;0;;OPONY;X;;BUDGET;LETNIA;R16;205;55;;;;;;STANDARD\r\n").encode("utf-8")


def _sync():
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
    import xp_oferta_sync
    return xp_oferta_sync


def test_plik_ofertowy_jak_api():
    X = _sync()
    rows = X.czytaj_csv(CSV_TEST)
    assert len(rows) == 1                      # cena 0 pominięta jak w API
    r = rows[0]
    assert (r["id"], r["szer"], r["profil"], r["sred"], r["ilosc"]) == (270722, 205, 55, 16, 50)
    d = r["dane"]
    assert d["netto"] == 312.10 and d["magazyny"] == {"Opole": 50} and d["ean"] == "3286341531015"
    e = S.enrich(dict(S.DEFAULT_CFG), d)      # silnik czyta produkt z pliku tak samo jak z API
    assert (e["sezon"], e["klasa"], e["producent"], e["mokra"], e["opory"], e["halas"], e["dot"]) == ("Zimowa", "PREMIUM", "BRIDGESTONE", "A", "C", 71, "2026")
    try:
        X.czytaj_csv(b"LP;Nazwa\r\n1;x\r\n")
        assert False, "zły format powinien zatrzymać synchronizację"
    except X.Blad:
        pass


def test_sync_chroni_przed_uciętym_plikiem_i_wysyla_tylko_zmiany():
    X = _sync()
    rows = X.czytaj_csv(CSV_TEST)
    wyw = []
    def http(method, path, key, body=None, prefer=None, timeout=120):
        wyw.append((method, path.split("?")[0], len(body) if isinstance(body, list) else body))
        if method == "GET":
            return [{"id": i, "h": "x"} for i in range(1, 11)] if "offset=0" in path else []
        return None
    X._http = http
    try:
        X.synchronizuj(rows, "k")
        assert False, "1 opona przy 10 w tabeli = plik podejrzany"
    except X.Blad:
        pass
    assert not [w for w in wyw if w[0] in ("POST", "DELETE")]   # nic nie zmieniono
    wyw.clear()
    X._http = lambda method, path, key, body=None, prefer=None, timeout=120: (wyw.append((method, path, body)) or
              ([{"id": 270722, "h": rows[0]["h"]}] if method == "GET" else None))
    s = X.synchronizuj(rows, "k")
    assert s["zmienione"] == 0 and s["usuniete"] == 0 and s["ile"] == 1
    assert not [w for w in wyw if w[0] == "POST" and "xp_oferta" in w[1]]   # bez zmian = bez wysyłania


def test_wyszukiwanie_z_pliku_i_etykieta_eprel():
    _setup()
    X = _sync()
    dane = X.czytaj_csv(CSV_TEST)[0]["dane"]
    S.CECHY.clear()
    S.KONTO.update(katalog=lambda s: [dane] if s == "205/55 R16" else [], katalog_info=lambda: "z pliku",
                   oddzialy=["Latex Wrocław"], oddzialy_dane=ODDZ, kto="T")
    c, r = S.handle("/api/search", {"pojazdy": [{"rozmiar": "205/55 R16", "ilosc": 4, "nowe": True}]})
    assert c == 200 and r["zrodlo"] == "z pliku" and [p["id"] for g in r["wyniki"]["205/55 R16"].values() for p in g] == [270722]
    # oferta odświeża produkt z API (bez EPREL/śniegu) – cechy z pliku zostają zapamiętane
    api = dict(dane, attrs={k: v for k, v in dane["attrs"].items() if k not in ("Kod EPREL", "Przyczepność na śniegu")})
    stary = S.get_product
    S.get_product = lambda cfg, pid: dict(api)
    try:
        _test_pdf_z_pliku(api)
    finally:
        S.get_product = stary
        S.KONTO.pop("katalog", None); S.KONTO.pop("katalog_info", None)


def _test_pdf_z_pliku(api):
    assert S.handle("/api/offer", {"oid": "20261106_090000", "pojazdy": [{"rozmiar": "205/55 R16", "ilosc": 4, "nowe": True}],
                                   "wybor": {"205/55 R16": {"x": [270722]}}})[0] == 200
    h = S.handle("/api/pdf", {"id": 270722})[1]["html"]
    assert "tyres/381909/labels" in h and "3PMSF" in h and "{{" not in h
    # bez kopii pliku -> API (katalog zwraca None)
    S.KONTO.update(katalog=lambda s: None, katalog_info=lambda: "")
    assert S.handle("/api/search", {"pojazdy": [{"rozmiar": "205/55 R16", "ilosc": 4, "nowe": True}]})[1]["zrodlo"].startswith("xPartner na żywo")


def test_etykieta_eprel_wstawiana_lub_zastepcza():
    from oferty import okno
    html = ('<p><object class="eprel" data="https://eprel.ec.europa.eu/api/products/tyres/99999999999/labels?format=PNG" '
            'type="image/png"><div class="eul">RYSOWANA</div></object></p>')
    stary = okno.urllib.request.urlopen
    try:
        def brak(*a, **k):
            raise OSError("offline")
        okno.urllib.request.urlopen = brak
        h = okno.wstaw_etykiete_eprel(html)        # rejestr UE nie odpowiada -> od razu rysowana, bez <object>
        assert h == '<p><div class="eul">RYSOWANA</div></p>', h
        class R:
            def __enter__(self): return self
            def __exit__(self, *a): pass
            def read(self, n=0): return b"\x89PNG\r\n\x1a\n" + b"0" * 50
        okno.urllib.request.urlopen = lambda *a, **k: R()
        h = okno.wstaw_etykiete_eprel(html)        # pobrana -> wstawiona do strony (Edge nie pobiera z sieci)
        assert '<img class="eprel" src="data:image/png;base64,' in h and "eprel.ec.europa.eu" not in h and "RYSOWANA" not in h
    finally:
        okno.urllib.request.urlopen = stary
        import tempfile
        try: os.remove(os.path.join(tempfile.gettempdir(), "LatexOferty_eprel", "99999999999.png"))
        except OSError: pass
