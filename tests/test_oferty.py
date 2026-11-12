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


def test_rozmiar_ciezarowy_i_dostawczy_nie_gubi_oznaczenia():
    """17,5" to nie 17", a „C” (dostawcze) to inna nośność – oferta nie może pomylić opon."""
    from oferty import silnik as S
    assert S.find_sizes("265/70 R17.5") == ["265/70 R17.5"]
    assert S.find_sizes("205/55R16C 4 szt") == ["205/55 R16C"]
    assert S.find_sizes("2156516c") == ["215/65 R16C"]
    assert S.find_sizes("205/55 R16 CrossClimate") == ["205/55 R16"]
    assert S.find_sizes("205/55R16,5szt") == ["205/55 R16"]          # „,5szt” to ilość, nie połówka
    assert S.find_sizes("265/70R17,5 4 szt") == ["265/70 R17.5"]
    assert S.norm_size("BARUM L185/75 R16C VANIS 3 104/102R") == "185/75 R16C"
    assert S.norm_size("YOKOHAMA 245/70 R17.5 704R 136/134M") == "245/70 R17.5"
    assert S.norm_size("MICHELIN 205/55 R16 PRIMACY 4") == "205/55 R16"
    # wyszukiwanie 205/65 R16 nie pokazuje opon C i odwrotnie (filtr w do_search: norm_size(nazwa) == rozmiar)
    assert S.norm_size("BARUM L205/65 R16C VANIS 3") != S.norm_size("205/65 R16")


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
    assert res["plik"] == "" and "Test" in res["email"]          # bez arkusza Excel (decyzja właściciela 2026-11-09)
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
    ws = load_workbook(S.write_xlsx(S.load_cfg(), req, *S.build_offer(S.load_cfg(), req)[:2])).active   # funkcja zostaje (wyłączona w ofercie)
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
    from openpyxl import load_workbook
    ws = load_workbook(S.write_xlsx(S.load_cfg(), req, *S.build_offer(S.load_cfg(), req)[:2])).active
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
    for txt in ("Opona BRIDGESTONE", "Wymiana opon", "Czujnik ciśnienia TPMS", "Depozyt", "DO ZAPŁATY BRUTTO", "OF/2026/11/05-1200"):
        assert txt in h, txt
    # rabat w wierszu: cena przed, −10%, cena po rabacie, wartość po rabacie; przekreślona cena w ramce; oszczędność
    assert "Cena po rabacie" in h and '<b class="rb">−10%</b>' in h and "<s>445,00 zł</s>" in h and "W tym oszczędzasz" in h
    assert "Razem przed rabatem" not in h
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


def test_pdf_wszystkie_w_jednym():
    _setup()
    S.KONTO.update(oddzialy=["Latex Wrocław"], oddzialy_dane=ODDZ, kto="T")
    assert S.handle("/api/offer", {"oid": "20261106_120000", "pojazdy": [{"rozmiar": "205/55 R16", "ilosc": 4, "nowe": True}],
                                   "wybor": {"205/55 R16": {"wszystkie": [1, 2]}}})[0] == 200
    c, r = S.handle("/api/pdf", {"ids": [1, 2]})
    h = r["html"]
    assert c == 200 and r["stron"] == 2 and h.count('<div class="page">') == 2 and h.count("<body>") == 1 and h.count("</html>") == 1
    assert "break-after:page" in h and "BRIDGESTONE" in h and "BARUM" in h
    assert S.handle("/api/pdf", {"id": 1})[1]["html"].count('<div class="page">') == 1    # pojedynczy bez zmian


def test_nosnosc_predkosc_rant():
    cfg = S.load_cfg()
    p = {"id": 1, "nazwa": "MICHELIN 225/45 R17 PILOT SPORT 5 94Y XL FR", "netto": 400, "ilosc": 8,
         "attrs": {"Indeks nośności": "94", "Indeks prędkości": "Y-300KMH", "Rant ochronny": "X", "Sezon": "Letnia"}}
    e = S.enrich(cfg, p)
    assert (e["nosnosc"], e["predkosc"], e["rant"]) == (94, "Y", True)
    e = S.enrich(cfg, dict(p, nazwa="X 205/55 R16 91H", attrs={"Sezon": "Letnia"}))
    assert (e["nosnosc"], e["predkosc"], e["rant"]) == (91, "H", False)


def test_rabat_na_wymiane_i_reczna_cena():
    # cennik R16 osobowy = 44 zł/koło; rabat 10% -> 39,60 -> 40 zł (w górę do pełnych zł, jak opony)
    code, r = _pdf(["Latex Wrocław"], {"id": 1}, {"rabat": "", "rabat_wym": "10"})
    h = r["html"]
    assert code == 200 and h.count('<b class="rb">−10%</b>') == 1 and "<s>" not in h, h[-3000:]   # tylko wymiana z rabatem
    assert "<td class=\"r\">44,00 zł</td><td class=\"c\"><b class=\"rb\">−10%</b></td><td class=\"r\"><b>40,00 zł</b></td><td class=\"r\">160,00 zł</td>" in h
    assert "W tym oszczędzasz dzięki rabatowi</td><td class=\"r\">16,00 zł" in h
    assert "44,00 zł" in h                                     # na PDF pozycja w cenie z cennika, rabat osobną linią
    w = S.handle("/api/offer", dict(S.OSTATNIA["req"]))[1]["wymiany"]
    assert w == [{"klucz": "R16|osobowy", "opis": "Wymiana R16", "cennik": 44.0, "auto": 40.0, "cena": 40.0, "recznie": False}]
    # ręczna cena wymiany: bez rabatu, bez linii rabatu
    code, r = _pdf(["Latex Wrocław"], {"id": 1}, {"rabat": "", "rabat_wym": "10", "ceny_wym": {"R16|osobowy": 30}})
    assert "Cena po rabacie" not in r["html"] and "30,00 zł" in r["html"]          # ręczna cena = bez kolumny rabatu
    # 100% = wymiana gratis
    code, r = _pdf(["Latex Wrocław"], {"id": 1}, {"rabat": "", "rabat_wym": "100"})
    assert '<b class="rb">−100%</b>' in r["html"] and "<b>0,00 zł</b>" in r["html"] and "oszczędzasz dzięki rabatowi</td><td class=\"r\">176,00 zł" in r["html"]


def test_statusy_oddzwonienie_i_zmiany_cen():
    import datetime as dt
    teraz = dt.datetime(2026, 11, 8, 12, tzinfo=dt.timezone.utc)
    assert S.do_oddzwonienia("wyslana", "2026-11-06T11:00:00+00:00", teraz) is True
    assert S.do_oddzwonienia("wyslana", "2026-11-07T11:00:00+00:00", teraz) is False
    assert S.do_oddzwonienia("przyjeta", "2026-11-01T11:00:00Z", teraz) is False and S.do_oddzwonienia("wyslana", "", teraz) is False
    _pdf(["Latex Wrocław"], {"id": 1})
    rows = S.OSTATNIA["rows"]
    snap = S.snap_ofert(rows)
    assert snap and snap[0]["id"] == 1 and S.zmiany_ofert(snap, rows) == []       # bez zmian -> brak ostrzeżeń
    z = S.zmiany_ofert([dict(snap[0], cena=snap[0]["cena"] - 20), {"id": 777, "nazwa": "Znikła", "cena": 1, "ilosc": 1}], rows)
    assert z[0]["w_gore"] is True and "→" in z[0]["co"] and z[1]["nazwa"] == "Znikła"


def test_link_dla_klienta_bez_cen_zakupu():
    _pdf(["Latex Wrocław"], {"id": 1}, {"wybor": {"205/55 R16": {"wszystkie": [1, 2]}}})
    zapis = {}

    class H:
        admin, me = False, "ania@x.pl"
        def link(self, oid, dane):
            zapis.update(oid=oid, dane=dane)
            return "11111111-2222-3333-4444-555555555555"
    stare = S.HIST
    S.HIST = H()
    try:
        code, r = S.handle("/api/link", {"oddzial": "Latex Wrocław"})
    finally:
        S.HIST = stare
    assert code == 200 and r["url"].endswith("oferta.html#11111111-2222-3333-4444-555555555555") and r["url"] in r["sms"]
    d = zapis["dane"]
    assert len(d["modele"]) == 2 and d["o_tel"] == "71 341 30 60"
    zakupy = {S.pl(r["p"]["netto"]) for r in S.OSTATNIA["rows"] if r.get("p")}
    txt = __import__("json").dumps(d, ensure_ascii=False)
    assert not any(z in txt for z in zakupy) and "zakup" not in txt.lower()        # klient nie widzi cen zakupu
    assert all("{{" not in m["html"] for m in d["modele"])


def test_porownanie_2_3_modele():
    _pdf(["Latex Wrocław"], {"id": 1}, {"wybor": {"205/55 R16": {"wszystkie": [1, 2]}}})
    code, r = S.handle("/api/pdf", {"ids": [1, 2], "porownanie": 1})
    h = r["html"]
    assert code == 200 and "EKONOMICZNA" in h and "PREMIUM" in h and "{{" not in h
    assert h.index("BARUM") < h.index("BRIDGESTONE")                                   # od najtańszej
    code, r = S.handle("/api/pdf", {"ids": [1], "porownanie": 1})
    assert code == 500 and "2 lub 3" in r["error"]


def test_szukaj_pokazuje_zbyt_maly_stan_z_ostrzezeniem():
    """Potrzeba 2 szt. -> opona z 1 szt. jest widoczna (na końcu) z oznaczeniem za_malo; rozmiar C osobno."""
    cfg = S.load_cfg()
    baza = [{"id": i, "nazwa": "MARKA%d 225/45 R17 MODEL 91W" % i, "netto": 300 + i, "ilosc": il, "attrs": {"Sezon": "Letnia"}}
            for i, il in ((1, 1), (2, 2), (3, 30))] + [{"id": 4, "nazwa": "MARKA 225/45 R17C MODEL 104T", "netto": 200, "ilosc": 9, "attrs": {"Sezon": "Letnia"}}]
    stare = S.search_size
    S.search_size = lambda cfg, s: [dict(p) for p in baza]
    try:
        r = S.do_search(cfg, {"pojazdy": [{"rozmiar": "225/45 R17", "ilosc": 2, "nowe": True}], "min_stan": 50})
    finally:
        S.search_size = stare
    lst = list(r["wyniki"]["225/45 R17"].values())[0]
    assert [p["id"] for p in lst][-1] == 1 and sorted(p["id"] for p in lst) == [1, 2, 3]   # bez dostawczej R17C
    assert [p["za_malo"] for p in sorted(lst, key=lambda p: p["id"])] == [True, False, False]
    assert S.norm_size("2254517c") == "225/45 R17C" and S.norm_size("225/45 17C") == "225/45 R17C"



def test_szybkie_polecenie_nosnosc_predkosc():
    for txt, wynik in (("2254517 lato 91w 2szt", (91, "W")), ("205/55 R16 94 V zimowe", (94, "V")), ("225/45r17 91/88y", (91, "Y")),
                       ("2254517 lato 2szt", (0, "")), ("205/55 r 16 4 szt", (0, "")), ("2055516 8 szt", (0, ""))):
        q = S.parse_quick(txt)
        assert (q["nosnosc"], q["predkosc"]) == wynik, (txt, q["nosnosc"], q["predkosc"])
    assert S.parse_quick("2254517 lato 91w 2szt")["pojazdy"][0]["ilosc"] == 2


def test_szybkie_polecenie_z_rejestracja_i_autem():
    p = S.parse_quick("skoda octavia 2055516 dw5444lw z wymianą 4 czujniki")["pojazdy"]
    assert [(x["rej"], x["pojazd"], x["rozmiar"]) for x in p] == [("DW5444LW", "Skoda Octavia", "205/55 R16")]
    p = S.parse_quick("205/55 r16 3 oferty premium zimowe 4 szt")["pojazdy"]
    assert (p[0]["rej"], p[0]["pojazd"]) == ("", "")    # same słowa polecenia to nie auto
    for t, rej in (("2254517 91v xl zimowe", ""), ("225/45 r17 zimowe bez demo run flat", ""),
                   ("golf 2055516 94v xl zima", ""), ("dw5444lw 2055516 91v", "DW5444LW")):
        p = S.parse_quick(t)["pojazdy"][0]
        assert (p["rej"], p["pojazd"]) == (rej, ""), (t, p)   # indeks, XL, „run flat” to nie model auta
