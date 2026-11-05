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


DB = [_p(1, "BRIDGESTONE Z205/55 R16 BLIZZAK 6 91H", 80, 344.10, "BRIDGESTONE", "BLIZZAK 6", "ZIMOWA", "PREMIUM",
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
    # 344,10 × 1,05 × 1,23 × 0,9 = 399,97 → w górę 400 zł; 2 szt.; wymiana 2 kół × 44; TPMS 4 × 150; przechowalnia 120
    assert (w["opony"], w["wymiana"], w["tpms"], w["przech"]) == (800.0, 88.0, 600.0, 120.0)
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
    ws.append(["DX1209H", "Skoda", "Superb", "2155517", 2, "SUV/4x4", "TAK", 4, "koła"])
    ws.append(["DX3985C", "Skoda", "Octavia", "205/60 16", 0, "osobowy", "TAK", "", "brak"])
    wb.save(path)
    poj = S.czytaj_xlsx(open(path, "rb").read())
    assert len(poj) == 3
    assert poj[1] == {"rej": "DX1209H", "pojazd": "Skoda Superb", "rozmiar": "215/55 R17", "ilosc": 2, "nowe": True,
                      "wymiana": True, "typ": "suv", "tpms": 4, "przech": "kola"}
    assert poj[2]["ilosc"] == 0 and poj[2]["przech"] == "" and poj[2]["wymiana"]


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
