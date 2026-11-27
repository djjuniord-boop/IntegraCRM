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

    def save(self, oid, klient, dane, szukaj, owner=""):
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


def test_szybkie_po_indeksie_i_kodzie_producenta():
    """2026-11-23: „258797” / „3940900” w szybkim poleceniu -> rozmiar, marka i sezon tej opony + podświetlenie."""
    d = {"id": 258797, "nazwa": "PIRELLI Z245/40 R20 PZERO WINTER 99V XL *MO RG DOT2026", "netto": 900.0, "ilosc": 12,
         "kod": "3940900", "attrs": {"Producent": "PIRELLI", "Sezon": "ZIMOWA"}}

    class Kat:
        def produkt(self, k):
            return [d] if k in ("258797", "3940900") else []
    stary = S.KONTO.get("katalog")
    S.KONTO["katalog"] = Kat()
    try:
        for t in ("258797", " 3940900 "):
            st, q = S.handle("/api/quick", {"text": t})
            assert st == 200 and q["pojazdy"][0]["rozmiar"] == "245/40 R20" and q["szukany"]["id"] == 258797, q
            assert q["producenci"] == "PIRELLI" and q["sezony"] == ["Zimowa"], q
        assert S.handle("/api/quick", {"text": "999999"})[1]["pojazdy"] == []
        assert "szukany" not in S.handle("/api/quick", {"text": "2055516"})[1]   # rozmiar ma pierwszeństwo
    finally:
        S.KONTO["katalog"] = stary


def test_run_flat_oznaczony():
    """2026-11-23: run flat (cecha „Struktura” albo RFT/R/F w nazwie) – znaczek RFT w wynikach i „RUN FLAT” w PDF."""
    rf = {"nazwa": "PIRELLI Z285/45 R21 SCORPION WINTER 113V XL R/F * RG", "attrs": {"Struktura": "RUN FLAT"}}
    assert S.is_standard(rf) is False
    assert S.is_standard({"nazwa": "BRIDGESTONE Z285/45 R21 BLIZZAK LM001 113V XL * RFT RG", "attrs": {}}) is False
    assert S.is_standard({"nazwa": "PIRELLI Z285/45 R21 SCORPION WINTER 2 113V XL", "attrs": {"Struktura": "STANDARD"}}) is True
    src = (Path(S.__file__).parent / "index.html").read_text(encoding="utf-8")
    assert "p.standard===false?' <span class=\"rft\"" in src
    assert '" · RUN FLAT" if p.get("standard") is False' in Path(S.__file__).read_text(encoding="utf-8")


def test_homologacja_z_cechy_xpartner():
    """2026-11-23: Pirelli 258847 „… RG NC0” (cecha NC0_PORSCHE) była bez homologacji – filtr Porsche jej nie pokazywał."""
    def p(n, h=""):
        return {"nazwa": n, "attrs": {"Homologacja": h} if h else {}}
    assert S.homol_of(p("PIRELLI Z285/45 R21 SCORPION WINTER 2 113V XL RG NC0 DOT2026", "NC0_PORSCHE")) == ["N", "FR"]
    assert S.homol_cecha(p("X", "NC0_PORSCHE")) == ("NC0", ["N"])
    assert S.homol_of(p("PIRELLI Z285/45 R21 SCORPION WINTER 2 113V XL RG NC0")) == ["N", "FR"]   # bez cechy – z nazwy
    assert S.homol_cecha(p("X", "MOBMW_MERCEDES/BMW/MINI"))[1] == ["MO", "*"]
    assert S.homol_cecha(p("X", "MGT_MASERATI"))[1] == ["Maserati"]
    assert S.homol_of(p("OPONA 205/55 R16 91V")) == []


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
    assert res["ulotki"][0]["szt"] == 2   # ilość do koszyka z oferty
    w = res["warianty"][0]
    # 344,10 × 1,05 × 1,23 = 444,41 → 445 zł; rabat 10% → 400,50 → 401 zł; 2 szt.; wymiana 2 × 44; TPMS 4 × 150; przechowalnia 120
    assert (w["opony"], w["wymiana"], w["tpms"], w["przech"]) == (802.0, 88.0, 600.0, 120.0)
    assert "plik" not in res and "email" not in res         # bez arkusza Excel (decyzja właściciela 2026-11-09)
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
    assert code == 200 and "DEMO" in str(res["ulotki"]) + str(S.OSTATNIA["rows"])
    assert not hasattr(S, "write_xlsx")   # arkusz Excel z ofertą usunięty – decyzja właściciela


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
    for txt in ("Opona BRIDGESTONE", "Wymiana opon", "Obsługa czujnika ciśnienia TPMS przy wymianie opony", "Depozyt", "DO ZAPŁATY BRUTTO", "OF/2026/11/05-1200"):
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


def test_felgi_parametry_szukanie_oferta_pdf():
    """2026-11-26: felgi z pliku xPartner – parametry z cech („17\"”, „57,1”) i z nazwy, szybkie polecenie, komplet, PDF."""
    from oferty import felgi as FG
    alu = {"id": 231798, "kod": "NEV17", "attrs": {"ET": "46", "Typ": "ALUMINIOWA", "Model": "NEVE CZARNY", "Producent": "DIEWE",
           "Średnica": '17"', "Szerokość": '7"', "Rozstaw śrub": "5X112", "Otwór centralny": "57,1"},
           "ilosc": 4, "nazwa": "DIEWE NEVE 7X17 5X112 ET46/57.1 CZARNY", "netto": 375.72, "brutto_zak": 462.14}
    stal = {"id": 190362, "attrs": {}, "nazwa": "9832165180 OBRĘCZ PEUGEOT 6.5X16 4X108 ET32/65.1 STRUKTURA", "netto": 300.0, "ilosc": 1}
    f = FG.info(alu, 13, 23)
    assert (f["szer"], f["sred"], f["pcd"], f["et"], f["otwor"], f["rodzaj"]) == ("7", "17", "5x112", "46", "57.1", "aluminiowa")
    assert f["cena"] == 523.0   # 375,72 × 1,13 × 1,23 = 522,23 → w górę
    g = FG.info(stal)
    assert (g["pcd"], g["et"], g["otwor"], g["rodzaj"], g["oe"], g["marki"]) == ("4x108", "32", "65.1", "stalowa", "9832165180", ["Peugeot"])
    assert [x["id"] for x in FG.szukaj([alu, stal], "5x112 r17 et46")[0]] == [231798]
    assert [x["id"] for x in FG.szukaj([alu, stal], "stalowe peugeot 16")[0]] == [190362]
    assert [x["id"] for x in FG.szukaj([alu, stal], "diewe neve")[0]] == [231798]
    assert [x["id"] for x in FG.szukaj([alu, stal], "190362")[0]] == [190362]
    assert FG.szukaj([alu, stal], "5x120")[0] == []
    vw = {"id": 7, "attrs": {"Typ": "ALUMINIOWA"}, "nazwa": "OEM VW GOLF 6X17 5X112 ET48/57.1", "netto": 400.0, "ilosc": 8}
    au = {"id": 8, "attrs": {"Typ": "ALUMINIOWA"}, "nazwa": "OEM AUDI A3 6X17 5X112 ET48/57.1", "netto": 100.0, "ilosc": 8}
    assert [x["id"] for x in FG.szukaj([au, vw], "vw alu")[0]] == [7, 8]   # wpisana marka przed pokrewną, mimo wyższej ceny
    _setup()
    cfg = S.load_cfg()
    poz, razem = FG.oferta(cfg, f, 4, {"id": 1, "nazwa": "OPONA X", "cena_brutto": 400.0}, 4, {"id": 2, "nazwa": "CZ"}, 4, True, "osobowy", "kola", 120.0)
    nazwy = [p["nazwa"] for p in poz]
    assert nazwy[0].startswith("Felga DIEWE") and nazwy[1] == "Opona OPONA X" and nazwy[2].startswith("Czujnik")
    assert any(n.startswith("Obsługa czujnika") for n in nazwy) and any(n.startswith("Montaż") for n in nazwy) and any("Przechowalnia kół" in n for n in nazwy)
    assert razem == round(sum(p["w"] for p in poz), 2) and poz[0]["w"] == 4 * 523.0
    S.KONTO.update(katalog=type("K", (), {"felgi": lambda self: [dict(alu), dict(stal)]})(), oddzialy=["Latex Wrocław"], oddzialy_dane=ODDZ, kto="T")
    try:
        st, r = S.handle("/api/felgi", {"q": "5x112"})
        assert st == 200 and [x["id"] for x in r["lista"]] == [231798] and r["marza"] == 13
        st, r = S.handle("/api/felgi_oferta", {"felga": 231798, "ilosc": 4, "montaz": True})
        p = r["propozycje"][0]
        assert st == 200 and p["razem"] == p["pozycje"][0]["w"] + p["pozycje"][1]["w"]
        st, r = S.handle("/api/felgi_pdf", {"felga": 231798, "ilosc": 4, "klient": "<Jan>"})
        assert st == 200 and "DIEWE NEVE" in r["html"] and "&lt;Jan&gt;" in r["html"] and "<Jan>" not in r["html"]
        u = "https://xpartner.net.pl/descriptionFiles/images/10837/abc123.jpg"
        assert u in S.handle("/api/felgi_pdf", {"felga": 231798, "ilosc": 4, "fotos": {"231798": [u]}})[1]["html"]
        assert "evil" not in S.handle("/api/felgi_pdf", {"felga": 231798, "ilosc": 4, "fotos": {"231798": ["https://evil.pl/x.jpg"]}})[1]["html"]
    finally:
        S.KONTO.pop("katalog", None)


def test_felgi_kilka_propozycji_ceny_porownanie_historia():
    """2026-11-26: do 3 felg w ofercie (propozycje), wspólne opony i usługi, rabaty felgi/opony/montaż, ceny ręczne,
    felga spoza ostatniego wyszukiwania (z Historii), opony R18 do felgi 17" = błąd i blokada PDF, porównanie, zapis w historii."""
    from oferty import felgi as FG
    _setup()
    alu = {"id": 231798, "attrs": {"Typ": "ALUMINIOWA", "Średnica": '17"', "Szerokość": '7"'}, "ilosc": 4,
           "nazwa": "DIEWE NEVE 7X17 5X112 ET46/57.1 CZARNY", "netto": 375.72, "brutto_zak": 462.14}
    b18 = {"id": 5, "attrs": {"Typ": "ALUMINIOWA"}, "nazwa": "GMP ATOM 8X18 5X112 ET35/66.5", "netto": 500.0, "ilosc": 8}
    c18 = {"id": 6, "attrs": {"Typ": "ALUMINIOWA"}, "nazwa": "OEM AUDI 8.5X18 5X112 ET43/57.1", "netto": 900.0, "ilosc": 8}
    zapisane = {}
    class H:
        def save(self, oid, klient, rec, hay, owner=""):
            zapisane[oid] = (rec, hay)
    S.HIST = H()
    S.KONTO.update(katalog=type("K", (), {"felgi": lambda self: [dict(alu), dict(b18), dict(c18)]})(), oddzialy=["Latex Wrocław"], oddzialy_dane=ODDZ, kto="T")
    stary_gp = S.get_product
    S.get_product = lambda cfg, pid: {9: {"id": 9, "nazwa": "WINDFORCE 225/40 R18 92W", "netto": 150.0, "kod": "W1"}}.get(pid)
    S.CZESCI_XP.clear()
    try:
        S.FELGI_OSTATNIE.clear()   # oferta z Historii – felg nie ma w ostatnim wyszukiwaniu
        assert FG.sred_opony({"rozmiar": "225/40 R18"}) == "18" and FG.sred_opony({"nazwa": "DUNLOP 215/65R16C 109T"}) == "16"
        op = {"id": 9, "nazwa": "WINDFORCE 225/40 R18 92W", "netto": 150.0, "rozmiar": "225/40 R18"}
        body = {"felgi": [5, 6, 231798, 99], "ilosc": 4, "opona": op, "montaz": True, "typ": "osobowy", "il_tp": 4, "depozyt": "kola",
                "rabat": {"f": "10", "o": "0", "m": "50"}, "ceny": {"6": "1500"}, "ceny_wym": {"R18|osobowy": "30"}, "oid": "20261126_101010", "klient": "Kowalski"}
        st, r = S.handle("/api/felgi_oferta", body)
        assert st == 200 and not zapisane   # samo przeliczenie (klik w felgę) nie zapisuje w Historii
        body["zapisz"] = 1
        st, r = S.handle("/api/felgi_oferta", body)
        assert st == 200 and [p["nr"] for p in r["propozycje"]] == [1, 2, 3]   # najwyżej 3 felgi (czwarta pominięta)
        p1, p2, p3 = r["propozycje"]
        f1 = p1["pozycje"][0]
        assert f1["k"] == "felga" and f1["c"] == S.cena_po_rabacie(FG.info(b18)["cena"], 10)   # rabat 10% na felgi
        assert p2["pozycje"][0]["c"] == 1500.0   # cena wpisana ręcznie wygrywa z rabatem
        assert [x["k"] for x in p1["pozycje"]] == ["felga", "opona", "tpms", "montaz", "przech"]
        mont = [x for x in p1["pozycje"] if x["k"] == "montaz"][0]
        assert mont["c"] == 30.0 and mont["q"] == 4   # ręczna cena montażu R18
        assert not p1["blad"] and not p2["blad"] and 'Felga 3 ma 17"' in p3["blad"]
        e = {(x["k"], x["id"]): x for x in r["edycja"]}
        assert e[("felga", 6)]["recznie"] and e[("opona", 9)]["auto"] == S.sell_price(S.load_cfg(), 150.0)
        assert {w["klucz"] for w in r["wymiany"]} == {"R18|osobowy", "R17|osobowy"}
        rec, hay = zapisane["20261126_101010"]
        assert rec["typ_oferty"] == "felgi" and [f["id"] for f in rec["felgi_dane"]] == [5, 6, 231798] and "felgi" in hay and "kowalski" in hay
        assert len(rec["warianty"]) == 3 and rec["warianty"][0]["modele"] == [b18["nazwa"], op["nazwa"]]
        st, r = S.handle("/api/felgi_pdf", dict(body, porownanie=1))
        assert st != 200 and "nie pasują" in r["error"]   # porównanie zablokowane, dopóki opony nie pasują do każdej felgi
        st, r = S.handle("/api/felgi_pdf", dict(body, nr=2))
        assert st != 200 and "nie pasują" in r["error"]
        st, r = S.handle("/api/felgi_pdf", dict(body, nr=1))
        assert st == 200 and "OEM AUDI" in r["html"] and "1 500,00" in r["html"] and "Felga FELGA" not in r["html"]
        st, r = S.handle("/api/felgi_pdf", dict(body, felgi=[5, 6], porownanie=1))
        assert st == 200 and "PROPOZYCJA 1" in r["html"] and "PROPOZYCJA 2" in r["html"] and "GMP ATOM" in r["html"] and "Koła kompletne" in r["html"]
        assert "W każdej propozycji" in r["html"] and "WINDFORCE" in r["html"]
        st, r = S.handle("/api/felgi_pdf", dict(body, felgi=[5], porownanie=1))
        assert st != 200   # porównanie potrzebuje 2 felg
        # opona z okna z podrobioną nazwą / ceną – liczy się tylko indeks, reszta z xPartner (XSS w Historii, ceny)
        zapisane.clear()
        zly = dict(body, zapisz=1, opona={"id": 9, "nazwa": "<img src=x onerror=alert(1)>", "netto": 1}, felgi=[5])
        st, r = S.handle("/api/felgi_oferta", zly)
        rec, _ = zapisane["20261126_101010"]
        assert rec["opona"]["nazwa"] == "WINDFORCE 225/40 R18 92W" and rec["opona"]["netto"] == 150.0
        assert r["propozycje"][0]["pozycje"][1]["c"] == S.sell_price(S.load_cfg(), 150.0)
        st, r = S.handle("/api/felgi_oferta", dict(body, opona={"id": "<b>"}, felgi=[5]))
        assert st == 200 and [x["k"] for x in r["propozycje"][0]["pozycje"]][:2] == ["felga", "tpms"]   # zły indeks = bez opon
        st, r = S.handle("/api/felgi_oferta", dict(body, opona={"id": 77}, felgi=[5]))
        assert st != 200 and "nie ma już w xPartner" in r["error"]
        # felga bez ceny w pliku – błąd zamiast oferty za 0 zł
        S.FELGI_OSTATNIE.clear()
        S.KONTO["katalog"] = type("K", (), {"felgi": lambda self: [dict(b18, netto=0)]})()
        st, r = S.handle("/api/felgi_oferta", {"felgi": [5], "ilosc": 4})
        assert st != 200 and "nie ma ceny" in r["error"]
    finally:
        S.KONTO.pop("katalog", None)
        S.HIST = _Hist()
        S.get_product = stary_gp


def test_rozmiar_bez_c_pokazuje_tez_dostawcze():
    """2026-11-26: „2057516” – 3 osobowe + 119 dostawczych R16C; razem, opony C z rozmiarem „R16C”. Wpisane C = tylko C."""
    _setup()
    def opona(i, roz):
        return {"id": i, "nazwa": "MARKA %s MODEL 110R" % roz, "netto": 300.0, "ilosc": 50, "attrs": {"Sezon": "CAŁOROCZNA"}}
    lista = [opona(1, "205/75 R16"), opona(2, "205/75 R16C"), opona(3, "215/75 R16C")]
    S.KONTO.update(katalog=lambda s: list(lista), katalog_info=lambda: "z pliku", oddzialy=["Latex Wrocław"], oddzialy_dane=ODDZ, kto="T")
    try:
        r = S.handle("/api/search", {"pojazdy": [{"rozmiar": "205/75 R16", "ilosc": 4, "nowe": True}]})[1]
        assert sorted((p["id"], p["rozmiar"]) for g in r["wyniki"]["205/75 R16"].values() for p in g) == [(1, "205/75 R16"), (2, "205/75 R16C")]
        r = S.handle("/api/search", {"pojazdy": [{"rozmiar": "205/75 R16C", "ilosc": 4, "nowe": True}]})[1]
        assert [p["id"] for g in r["wyniki"]["205/75 R16C"].values() for p in g] == [2]
    finally:
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


def test_porownanie_2_3_modele():
    _pdf(["Latex Wrocław"], {"id": 1}, {"wybor": {"205/55 R16": {"wszystkie": [1, 2]}}})
    code, r = S.handle("/api/pdf", {"ids": [1, 2], "porownanie": 1})
    h = r["html"]
    assert code == 200 and "EKONOMICZNA" in h and "PREMIUM" in h and "{{" not in h
    assert h.index("BARUM") < h.index("BRIDGESTONE")                                   # od najtańszej
    code, r = S.handle("/api/pdf", {"ids": [1], "porownanie": 1})
    assert code == 500 and "2 lub 3" in r["error"]


def test_szukaj_pokazuje_zbyt_maly_stan_z_ostrzezeniem():
    """Potrzeba 2 szt. -> opona z 1 szt. jest widoczna (na końcu) z oznaczeniem za_malo; rozmiar C razem (znaczek C)."""
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
    assert [p["id"] for p in lst][-1] == 1 and sorted(p["id"] for p in lst) == [1, 2, 3, 4]   # z dostawczą R17C (2026-11-26)
    assert [p["za_malo"] for p in sorted(lst, key=lambda p: p["id"])] == [True, False, False, False]
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


def test_marza_wspolna_wroclaw_ustala_admin():
    stare = dict(S.KONTO)
    zapis = []
    try:
        S.KONTO.update(oddzialy_konta=["Latex Wrocław"], admin=False, ustawienia={"marza_proc": 30.0},
                       ceny_oddz={"Latex Wrocław": {"marza_proc": 12.0, "narzut_tryb": "procent", "progi": []}},
                       zapisz=lambda d: None, zapisz_ceny=lambda o, d: zapis.append((o, d)))
        assert S.load_cfg()["marza_proc"] == 12.0          # osobista 30% nie działa
        code, c = S.handle("/api/cfg")
        assert c["ceny_oddzial"] == "Latex Wrocław" and c["ceny_edycja"] is False
        S.handle("/api/cfg", {"marza_proc": 50, "waznosc_dni": 9})
        assert not zapis and S.load_cfg()["marza_proc"] == 12.0 and S.load_cfg()["waznosc_dni"] == 9
        S.KONTO["admin"] = True
        S.handle("/api/cfg", {"marza_proc": 15})
        assert zapis == [("Latex Wrocław", {"marza_proc": 15, "narzut_tryb": "procent", "progi": []})]
        S.KONTO.update(oddzialy_konta=["Latex Opole"], admin=False)
        assert S.load_cfg()["marza_proc"] == 30.0 and S.handle("/api/cfg")[1]["ceny_edycja"] is True
    finally:
        S.KONTO.clear(); S.KONTO.update(stare)


def test_ceny_uslug_wroclaw_ustala_admin():
    """2026-11-24: wymiana, TPMS i przechowalnia we Wrocławiu – wspólne, zmienia tylko administrator."""
    stare = dict(S.KONTO)
    zapis = []
    try:
        S.KONTO.update(oddzialy_konta=["Latex Wrocław"], admin=False,
                       ustawienia={"tpms_cena": 999, "wymiana_kolo": {"16": 1}, "przech_kola_do19": 1},
                       ceny_oddz={"Latex Wrocław": {"marza_proc": 12.0, "tpms_cena": 5, "wymiana_kolo": {"16": 55},
                                                    "przech_kola_do19": 260}},
                       zapisz=lambda d: None, zapisz_ceny=lambda o, d: zapis.append((o, d)))
        c = S.load_cfg()
        assert c["tpms_cena"] == 5 and c["wymiana_kolo"] == {"16": 55} and c["przech_kola_do19"] == 260
        S.handle("/api/cfg", {"tpms_cena": 1, "wymiana_kolo": {"16": 2}})   # pracownik – bez skutku
        assert not zapis and S.load_cfg()["tpms_cena"] == 5
        S.KONTO["admin"] = True
        S.handle("/api/cfg", {"tpms_cena": 7})
        assert zapis[-1][1]["tpms_cena"] == 7 and zapis[-1][1]["marza_proc"] == 12.0 and zapis[-1][1]["wymiana_kolo"] == {"16": 55}
        S.KONTO.update(oddzialy_konta=["Latex Opole"], admin=False)
        assert S.load_cfg()["tpms_cena"] == 999   # inne oddziały – jak dotąd, ustawienia osobiste
    finally:
        S.KONTO.clear(); S.KONTO.update(stare)


def test_uwagi_do_oferty_zapis():
    """Uwagi wewnętrzne: zapis przez Historia.uwagi (oid albo id), brak historii = 400."""
    stary = S.HIST
    zap = []

    class H:
        def uwagi(self, txt, rid=None, oid=None, owner=""):
            zap.append((txt, rid, oid))
    try:
        S.HIST = H()
        code, _ = S.handle("/api/uwagi", {"oid": "20261116_082600", "uwagi": "Dla p. Kowalskiego" + "x" * 2000})
        assert code == 200 and zap[0][2] == "20261116_082600" and len(zap[0][0]) == 1000
        S.HIST = _Hist()
        assert S.handle("/api/uwagi", {"oid": "x", "uwagi": "a"})[0] == 400
    finally:
        S.HIST = stary


def test_szybkie_ten_sam_model():
    q = S.parse_quick("2754020 3153520 wielosezonowe 2 szt ten sam model")
    assert q["ten_sam"] is True and len(q["pojazdy"]) == 2
    assert S.parse_quick("2754020 3153520 2 szt")["ten_sam"] is False


def test_niepelny_rozmiar_rozpoznanie():
    """Niepełny rozmiar w szybkim poleceniu (decyzja właściciela 2026-11-17): 20555, R20, 205 R16, sama marka / sezon."""
    przyp = {"zima pirelli": "*/* R*", "zima pirelli r20": "*/* R20", "zima pirelli 20555": "205/55 R*", "firestone": "*/* R*",
             "R20": "*/* R20", "205/55 zimowe 4 szt": "205/55 R*", "205 r16": "205/* R16", "r17c": "*/* R17C",
             "michelin 18 cali": "*/* R18", "bmw 320 r18": "*/* R18", "2055516": "205/55 R16", "205/55 R16 91V": "205/55 R16"}
    for t, oczek in przyp.items():
        assert [v["rozmiar"] for v in S.parse_quick(t)["pojazdy"]] == [oczek], t
    assert S.parse_quick("8 szt")["pojazdy"] == []
    q = S.parse_quick("zima pirelli r20")
    assert q["producenci"] == "PIRELLI" and q["sezony"] == ["Zimowa"]
    assert S.pasuje_wzorzec("*/* R20", "245/45 R20") and not S.pasuje_wzorzec("*/* R17", "215/60 R17C")
    assert S.pasuje_wzorzec("*/* R17C", "215/60 R17C") and not S.pasuje_wzorzec("205/55 R*", "205/55 R17.5")
    assert S.opis_wzorca("205/55 R*") == "205/55 – każda średnica" and S.opis_wzorca("*/* R20") == "R20 – wszystkie rozmiary"


def test_niepelny_rozmiar_wyszukiwanie_i_limit():
    """Wzorzec szuka w kopii pliku (marka/sezon przekazane do bazy), każda opona ma swój rozmiar, limit 1000."""
    _setup()
    wolania = []

    class Kat:
        def __call__(self, s):
            return None

        def wzorzec(self, wz, marki, sezony):
            wolania.append((wz, list(marki), list(sezony)))
            return [dict(p) for p in DB]
    stare = dict(S.KONTO)
    try:
        S.KONTO.update(katalog=Kat(), katalog_info=lambda: "z pliku")
        c, r = S.handle("/api/search", {"pojazdy": [{"rozmiar": "*/* R*", "ilosc": 4, "nowe": True}], "producenci": "PIRELLI, BARUM",
                                        "sezony": ["Zimowa", "Całoroczna"]})
        assert c == 200, r
        assert wolania == [("*/* R*", ["PIRELLI", "BARUM"], ["Zimowa", "Całoroczna"])]
        lista = [p for g in r["wyniki"]["*/* R*"].values() for p in g]
        assert sorted((p["id"], p["rozmiar"]) for p in lista) == [(2, "205/55 R16"), (4, "215/55 R17")]
        assert r["czesc"]["*/* R*"]["opis"] == "wszystkie rozmiary" and r["czesc"]["*/* R*"]["wszystkie"] == 2
        r = S.handle("/api/search", {"pojazdy": [{"rozmiar": "*/* R16", "ilosc": 4, "nowe": True}]})[1]
        assert {p["rozmiar"] for g in r["wyniki"]["*/* R16"].values() for p in g} == {"205/55 R16"}
        stary = S.WZOR_LIMIT
        S.WZOR_LIMIT = 1
        try:
            r = S.handle("/api/search", {"pojazdy": [{"rozmiar": "*/* R*", "ilosc": 4, "nowe": True}]})[1]
            cz = r["czesc"]["*/* R*"]
            assert cz["pokazano"] == 1 and cz["wszystkie"] == 4   # cena 0 (Nokian) odpada
            assert [p["id"] for g in r["wyniki"]["*/* R*"].values() for p in g] == [2]   # największy stan
        finally:
            S.WZOR_LIMIT = stary
        # kopia niedostępna -> jasny komunikat (API wymaga pełnego rozmiaru)
        Kat.wzorzec = lambda self, *a: None
        c, r = S.handle("/api/search", {"pojazdy": [{"rozmiar": "205/55 R*", "ilosc": 4, "nowe": True}]})
        assert c == 502 and "pełny rozmiar" in r["error"]
    finally:
        S.KONTO.clear(); S.KONTO.update(stare)


def test_whatsapp_tylko_pdf_z_folderu_ofert():
    """2026-11-18: „Wyślij przez WhatsApp” kopiuje do schowka tylko PDF z folderu ofert (nic innego z dysku)."""
    import tempfile, os
    from oferty import okno
    stary = S.OUT_DIR
    d = tempfile.mkdtemp()
    try:
        S.OUT_DIR = d
        pdf = os.path.join(d, "Oferta_1.pdf")
        open(pdf, "wb").write(b"%PDF-1.4 test")
        assert okno.whatsapp_pdf(pdf)["plik"] == os.path.realpath(pdf)
        inny = os.path.join(tempfile.mkdtemp(), "x.pdf")
        open(inny, "wb").write(b"%PDF")
        for zly in (inny, os.path.join(d, "brak.pdf"), os.path.join(d, "..", "x.pdf"), ""):
            try:
                okno.whatsapp_pdf(zly)
                assert False, zly
            except ValueError:
                pass
    finally:
        S.OUT_DIR = stary


def test_wzorzec_odkaza_marke_bez_wstrzykniecia_do_filtra():
    """Marka z przecinkiem/nawiasem nie może rozbić filtra PostgREST and=(...) – do wzorca idą tylko znaki alfanumeryczne."""
    import datetime
    import time as _t
    import urllib.parse
    from oferty import okno
    zlapane = []
    stare = okno._db
    okno._db = lambda method, path, *a, **k: (zlapane.append(path), [])[1]
    try:
        kat = okno.Katalog()
        kat.stan = {"czas": datetime.datetime.now(datetime.timezone.utc).isoformat(), "ile": 9}
        kat.stan_t = _t.time()
        kat.wzorzec("205/55 R16", marki=["x),or(yy", "PIRELLI"], sezony=["Zimowa"])
    finally:
        okno._db = stare
    assert zlapane, "wzorzec nie zbudował zapytania"
    unq = urllib.parse.unquote(zlapane[-1])
    assert "x*o*r*y*y" in unq, unq            # przecinek i nawiasy wycięte, znaki połączone gwiazdką
    assert "x),or(yy" not in unq, unq         # surowa marka nie trafia do filtra
    assert "P*I*R*E*L*L*I" in unq, unq        # zwykła marka działa jak dotąd
    assert unq.count("(") == unq.count(")"), unq   # struktura and=(...) się nie rozjechała


def test_ustawienia_w_zakladkach_ceny_bez_zmian_i_nowe_opcje():
    """2026-11-26: ustawienia w zakładkach. Zapis oddziału bez nowych kluczy = ceny jak dotąd; zaokrąglanie, progi felg,
    marża czujników, limity rabatów, „tylko ostrzeżenie” przy średnicy, limit felg, teksty PDF oddziału, bezpiecznik koszyka."""
    from oferty import felgi as FG, koszyk as K
    _setup()
    stare = {"Latex Wrocław": {"marza_proc": 10, "narzut_tryb": "procent", "marza_felgi": 13, "tpms_cena": 5}}   # jak dziś w bazie
    S.KONTO.update(admin=False, oddzialy_konta=["Latex Wrocław"], ceny_oddz=stare, ustawienia={})
    try:
        cfg = S.load_cfg()
        assert (cfg["zaokr_opony"], cfg["zaokr_felgi"], cfg["felgi_max"], cfg["rabat_max_opony"], cfg["koszyk_max_szt"]) == (1, 1, 3, 90, 200)
        assert S.sell_price(cfg, 300.0) == 406.0   # 300 × 1,10 × 1,23 = 405,90 → 406 (bez zmian)
        S.KONTO["ustawienia"] = {"zaokr_opony": 10, "rabat_max_opony": 100, "marza_czujniki": 0, "min_stan": 7}
        c1 = S.load_cfg()   # Wrocław: wspólne reguły nie przychodzą z ustawień osobistych pracownika
        assert (c1["zaokr_opony"], c1["rabat_max_opony"], c1["marza_czujniki"], c1["min_stan"]) == (1, 90, 13, 7)
        S.KONTO["ustawienia"] = {}
        assert S.cena_felgi(cfg, 375.72) == 523.0 and S.cena_czujnika(cfg, 100.0) == 139.0   # jak FG.info() wcześniej
        # złe wartości w bazie nie psują cen (zakresy pilnowane przy wczytaniu)
        S.KONTO["ceny_oddz"] = {"Latex Wrocław": dict(stare["Latex Wrocław"], zaokr_opony=0, rabat_max_opony=-5, felgi_max=9, felgi_tryb="x", koszyk_max_szt="abc")}
        c2 = S.load_cfg()
        assert (c2["zaokr_opony"], c2["rabat_max_opony"], c2["felgi_max"], c2["felgi_tryb"], c2["koszyk_max_szt"]) == (1, 0, 3, "procent", 200)
        # zaokrąglanie do 5 / 10 zł, progi kwotowe felg, osobna marża czujników
        S.KONTO["ceny_oddz"] = {"Latex Wrocław": dict(stare["Latex Wrocław"], zaokr_opony=5, zaokr_felgi=10, felgi_tryb="kwota",
                                                       felgi_progi=[{"do": 500, "kwota": 60}, {"do": None, "kwota": 100}], marza_czujniki=20)}
        c3 = S.load_cfg()
        assert S.sell_price(c3, 300.0) == 410.0 and S.zaokr(400.0, 5) == 400.0 and S.zaokr(400.01, 5) == 405.0
        assert S.cena_felgi(c3, 300.0) == 430.0   # 369 brutto + 60 = 429 → w górę do 10 zł
        assert S.cena_felgi(c3, 500.0) == 720.0   # 615 brutto + 100 = 715 → 720
        assert S.cena_czujnika(c3, 100.0) == 150.0   # 100 × 1,20 × 1,23 = 147,60 → 150
        # felgi: rabat ograniczony ustawieniem, limit felg, „tylko ostrzeżenie”, cena liczona od zakupu przy każdej ofercie
        alu = {"id": 1, "attrs": {"Typ": "ALUMINIOWA"}, "nazwa": "FELGA ALU 7X17 5X112 ET46/57.1", "netto": 300.0, "ilosc": 8}
        b18 = {"id": 2, "attrs": {"Typ": "ALUMINIOWA"}, "nazwa": "FELGA ALU 8X18 5X112 ET35/66.5", "netto": 500.0, "ilosc": 8}
        S.KONTO.update(katalog=type("K", (), {"felgi": lambda self: [dict(alu), dict(b18)]})(), oddzialy=["Latex Wrocław"], oddzialy_dane=ODDZ, kto="T")
        S.FELGI_OSTATNIE.clear()
        S.KONTO["ceny_oddz"] = {"Latex Wrocław": dict(stare["Latex Wrocław"], rabat_max_felgi=5, felgi_max=1, felgi_srednica="ostrzez")}
        op = {"id": 9}
        stary_gp = S.get_product
        S.get_product = lambda cfg, pid: {"id": 9, "nazwa": "OPONA 225/40 R18 92W", "netto": 150.0} if pid == 9 else None
        S.CZESCI_XP.clear()
        st, r = S.handle("/api/felgi_oferta", {"felgi": [1, 2], "ilosc": 4, "opona": op, "rabat": {"f": 50}})
        S.get_product = stary_gp
        assert st == 200 and len(r["propozycje"]) == 1   # limit felg z ustawień
        p = r["propozycje"][0]
        assert p["pozycje"][0]["c"] == S.cena_po_rabacie(S.cena_felgi(S.load_cfg(), 300.0), 5)   # rabat 50% obcięty do 5%
        assert not p["blad"] and 'Felga 1 ma 17"' in p["ostrz"]
        S.get_product = lambda cfg, pid: {"id": 9, "nazwa": "OPONA 225/40 R18 92W", "netto": 150.0}
        st, r = S.handle("/api/felgi_pdf", {"felgi": [1], "ilosc": 4, "opona": op})
        S.get_product = stary_gp
        assert st == 200   # „tylko ostrzeżenie” – PDF powstaje
        # teksty PDF oddziału (puste = domyślne, {data} i {vat}, zabezpieczone znaki)
        odd = dict(ODDZ["Latex Wrocław"], warunki="Ważna do {data}, VAT {vat} <b>", cta_t="Umów się", por_t="Wybierz numer")
        S.KONTO["oddzialy_dane"] = {"Latex Wrocław": odd}
        h = S.handle("/api/felgi_pdf", {"felgi": [1], "ilosc": 4})[1]["html"]
        assert "Umów się" in h and "Zarezerwuj termin" not in h and "Zadzwoń – dobierzemy dogodną godzinę" in h
        assert "Ważna do " in h and "VAT 23%" in h and "&lt;b&gt;" in h and "Termin montażu do uzgodnienia" not in h
        S.KONTO["ceny_oddz"] = {"Latex Wrocław": dict(stare["Latex Wrocław"], felgi_max=3)}
        h = S.handle("/api/felgi_pdf", {"felgi": [1, 2], "ilosc": 4, "porownanie": 1})[1]["html"]
        assert "Wybierz numer" in h and "Którą propozycję" not in h
        S.KONTO["oddzialy_dane"] = ODDZ
        h = S.handle("/api/felgi_pdf", {"felgi": [1], "ilosc": 4})[1]["html"]
        assert "Zarezerwuj termin montażu" in h and "Termin montażu do uzgodnienia telefonicznie" in h   # bez tekstów = jak dotąd
        for f, por in (("pdf_wzor.html", False), ("pdf_porownanie.html", True)):   # wzory opon: teksty też działają
            h = (Path(S.__file__).parent / f).read_text(encoding="utf-8").replace("{{wazna}}", "03.12.2026").replace("{{vat_proc}}", "23")
            o = S.teksty_pdf(h, {"warunki": "W {data} {vat}", "cta_t": "A", "cta_p": "B", "por_t": "C", "por_p": "D"}, por)
            assert ("<b>C</b><br><span>D</span>" if por else "<b>A</b><br><span>B</span>") in o and (por or "W 03.12.2026 23%" in o)
        # bezpiecznik koszyka z ustawień
        zam = {"recipientId": 1, "deliveryPlaceId": 2, "pozycje": [{"id": 5, "ilosc": 30}]}
        K.order_xml(zam)
        try:
            K.order_xml(zam, 20)
            assert False, "30 szt. przy limicie 20 powinno być odrzucone"
        except K.Blad:
            pass
    finally:
        S.KONTO.pop("katalog", None)
        S.KONTO.update(admin=False, oddzialy_konta=[], ceny_oddz={}, ustawienia={})


WS_GOLF = {"data": [{"slug": "abc123", "name": "1.5 eTSI", "trim": "1.5 eTSI", "start_year": 2019, "end_year": 2024,
                     "make": {"slug": "volkswagen", "name": "Volkswagen"}, "model": {"slug": "golf", "name": "Golf"},
                     "generation": {"slug": "mk8", "name": "Mk8 (CD1)", "start": 2019, "end": 2024},
                     "engine": {"fuel": "Petrol", "capacity": "1.5", "power": {"kW": 110, "PS": 150, "hp": 148}},
                     "technical": {"wheel_fasteners": {"type": "Lug bolts", "thread_size": "M14 x 1.5"}, "wheel_tightening_torque": "140 Nm",
                                   "bolt_pattern": "5x112", "centre_bore": "57.1", "pcd": 112, "stud_holes": 5},
                     "wheels": [
                         {"is_stock": True, "showing_fp_only": True, "front": {"rim": "7.5Jx17 ET51", "rim_diameter": 17.0, "rim_width": 7.5, "rim_offset": 51.0,
                                                                               "tire_full": "225/45ZR17 91W", "tire": "225/45ZR17", "load_index": 91, "speed_index": "W",
                                                                               "tire_pressure": {"bar": 2.4, "psi": 35, "kPa": 240}}, "rear": {}},
                         {"is_stock": True, "showing_fp_only": True, "front": {"rim": "7Jx16 ET48", "rim_diameter": 16.0, "rim_width": 7.0, "rim_offset": 48.0,
                                                                               "tire": "205/55R16", "load_index": 91, "speed_index": "V"}, "rear": {}},
                         {"is_stock": False, "is_recommended_for_winter": True, "showing_fp_only": True,
                          "front": {"rim": "7.5Jx18 ET51", "rim_diameter": 18.0, "rim_width": 7.5, "rim_offset": 51.0, "tire": "225/40ZR18", "load_index": 92,
                                    "speed_index": "Y"}, "rear": {}}]}]}


def test_dobor_po_aucie_wheel_size():
    """2026-11-27: dobór po aucie – odpowiedzi wheel-size → dane auta, ocena felg (ET ±5 pasuje, ±15 sprawdź), trasa /api/auto
    z pamięcią (mniej zapytań), felgi z oceną, „Dobrane do” na PDF tylko z przełącznikiem."""
    from oferty import auto as AU
    _setup()
    a = AU.auto(WS_GOLF, "abc123")
    assert a["pcd"] == "5x112" and a["cb"] == 57.1 and a["gwint"] == "M14 x 1.5" and a["mocowanie"] == "śruby" and a["moment"] == "140 Nm"
    assert "Volkswagen Golf Mk8" in a["nazwa"] and "110 kW (150 KM)" in a["nazwa"]
    assert [k["oe"] for k in a["kola"]] == [True, True, False] and a["kola"][0]["przod"]["sred"] == 16.0   # fabryczne najpierw, rosnąco
    assert a["kola"][1]["przod"]["cisn"] == 2.4 and a["kola"][2]["zima"]
    assert AU.rozmiar_opony("225/45ZR17") == "225/45 R17" and AU.rozmiar_opony("215/65R16C") == "215/65 R16C"
    assert AU.wersje({"data": [WS_GOLF["data"][0]]})[0]["name"].startswith("1.5 eTSI 110 kW (150 KM)")
    assert AU.lista({"data": [{"slug": 2021, "name": 2021}, {"slug": None}]}) == [{"slug": "2021", "name": "2021"}]
    f = lambda **k: dict({"pcd": "5x112", "otwor": "57.1", "sred": "17", "szer": "7.5", "et": "51"}, **k)
    assert AU.ocena(f(), a)[0] == "ok"
    assert AU.ocena(f(otwor="66.5"), a) == ("zm", "pasuje (jak 7.5Jx17 ET51) · pierścień 66.5→57.1")
    assert AU.ocena(f(et="47"), a)[0] == "zm" and AU.ocena(f(et="45"), a)[0] == "uw" and AU.ocena(f(et="40"), a)[0] == "uw" and AU.ocena(f(et="30"), a)[0] == "nie"
    assert AU.ocena(f(pcd="5x108"), a)[0] == "nie" and AU.ocena(f(otwor="54.1"), a)[0] == "nie"
    assert AU.ocena(f(sred="20"), a)[0] == "uw" and AU.ocena(f(et=""), a)[0] == "uw"
    assert AU.ocena(f(et="40"), a, et_ok=12)[0] == "zm"   # zakres z Ustawień
    # trasa /api/auto z pamięcią
    wolane = []
    def ws(m, par):
        wolane.append(m)
        return {"makes": {"data": [{"slug": "volkswagen", "name": "Volkswagen"}]}, "by_model": WS_GOLF}.get(m, {"data": []})
    S.KONTO["ws"] = ws
    S.AUTO_PAMIEC.clear()
    try:
        st, r = S.handle("/api/auto", {"m": "makes"})
        assert st == 200 and r["lista"][0]["slug"] == "volkswagen"
        S.handle("/api/auto", {"m": "makes"})
        assert wolane == ["makes"]   # drugi raz z pamięci
        st, r = S.handle("/api/auto", {"m": "by_model", "make": "volkswagen", "model": "golf", "modification": "abc123"})
        assert st == 200 and r["auto"]["kola_opony"] == ["205/55 R16", "225/45 R17", "225/40 R18"]
        st, r = S.handle("/api/auto", {"m": "by_model", "make": "volkswagen", "model": "golf", "modification": "abc&x=1"})
        assert st != 200   # parametry tylko z dozwolonych znaków
        st, r = S.handle("/api/auto", {"m": "usun"})
        assert st != 200
        # felgi z oceną (pasujące najpierw, niezaufane dane auta nie wywracają wyszukiwania)
        felgi = [{"id": 1, "attrs": {"Typ": "ALUMINIOWA", "Rozstaw śrub": "5X108", "ET": "45", "Otwór centralny": "63,4"}, "nazwa": "FELGA ALU 7X17 5X108 ET45/63.4", "netto": 300.0, "ilosc": 8},
                 {"id": 2, "attrs": {"Typ": "ALUMINIOWA", "Rozstaw śrub": "5X112", "ET": "51", "Otwór centralny": "57,1"}, "nazwa": "FELGA ALU 7.5X17 5X112 ET51/57.1", "netto": 400.0, "ilosc": 8}]
        S.KONTO.update(katalog=type("K", (), {"felgi": lambda self: [dict(x) for x in felgi]})(), oddzialy=["Latex Wrocław"], oddzialy_dane=ODDZ, kto="T")
        st, r = S.handle("/api/felgi", {"q": "R17", "auto": a})
        assert st == 200 and [(x["id"], x["ocena"]) for x in r["lista"]] == [(2, "ok"), (1, "nie")]
        st, r = S.handle("/api/felgi", {"q": "R17", "auto": {"kola": [{"przod": None}], "pcd": 5}})
        assert st == 200 and len(r["lista"]) == 2
        S.FELGI_OSTATNIE.clear()
        h = S.handle("/api/felgi_pdf", {"felgi": [2], "ilosc": 4, "auto": {"nazwa": "VW Golf <8>"}, "auto_pdf": 1})[1]["html"]
        assert "Dobrane do" in h and "VW Golf &lt;8&gt;" in h
        h = S.handle("/api/felgi_pdf", {"felgi": [2], "ilosc": 4, "auto": {"nazwa": "VW Golf 8"}})[1]["html"]
        assert "Dobrane do" not in h   # przełącznik wyłączony
    finally:
        S.KONTO.pop("ws", None)
        S.KONTO.pop("katalog", None)
