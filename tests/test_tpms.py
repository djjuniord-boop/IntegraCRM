"""Zakładka „Czujniki TPMS”: rodzaj czujnika i marki aut z nazwy, szybkie polecenie, grupy wyników (bez okna i bez xPartner)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))
from oferty import silnik as S, tpms as T  # noqa: E402


def _t(pid, nazwa, prod, stan=50, netto=89.0, rodzaj="CZUJNIKI"):
    return {"id": pid, "nazwa": nazwa, "ilosc": stan, "netto": netto, "brutto_zak": round(netto * 1.23, 2), "netto_kat": netto,
            "magazyny": {"Ruda Śląska": stan, "Opole": 0},
            "attrs": {"Asortyment": "CZUJNIKI CIŚNIENIA TPMS", "Producent": prod, "Rodzaj": rodzaj}}


DB = [_t(1, "TPMS CZUJNIK CUB KIA SPORTAGE", "CUB", 3), _t(2, "TPMS CZUJNIK KIA/HYUNDAI 52933D4100", "ORYGINAŁ"),
      _t(3, "TPMS CZUJNIK HYUNDAI OE-R S078", "T-PRO"), _t(4, "TPMS CZUJNIK T-PRO HYBRID 3.5 3200 433MHZ SREBRNY", "T-PRO"),
      _t(5, "TPMS CZUJNIK OPEL OE-R S016", "T-PRO"), _t(6, "TPMS CZUJNIK OEM MERCEDES 315 A0009052202Q04 DEMO BEZ NAKRĘTKI", "ORYGINAŁ"),
      _t(7, "ZESTAW NAPRAWCZY SCHRADER TPMS-14", "T-PRO", rodzaj="NARZĘDZIA AKCESORIA"),
      _t(8, "TPMS PROGRAMATOR CZUJNIKÓW AUTEL TS508 WF", "AUTEL", rodzaj="NARZĘDZIA AKCESORIA"),
      _t(9, "TPMS CZUJNIK CUB UNI SENSOR 433 MHZ CZARNY", "CUB"), _t(10, "TPMS CZUJNIK OPEL BEZ CENY", "T-PRO", netto=0.0)]


def _ids(q):
    return [(x["id"], x["grupa"]) for x in T.szukaj(DB, q)[0]]


def test_rodzaj_i_marki_z_nazwy():
    r = {p["id"]: T.rodzaj_z(p) for p in DB}
    assert (r[1], r[2], r[4], r[6], r[7], r[8], r[9]) == ("zam", "oe", "uni", "oe", "nar", "nar", "uni")
    assert T.marki_z_nazwy("TPMS CZUJNIK KIA/HYUNDAI 52933D4100") == ["Hyundai", "KIA"]
    assert T.info(DB[5])["demo"] is True and T.info(DB[3])["zawor"] == "srebrny"


def test_szybkie_polecenie_tpms():
    q = T.zapytanie("Kia Sportage 4 szt bez demo srebrny", ["T-PRO", "CUB"])
    assert q["marki"] == ["KIA"] and q["slowa"] == ["SPORTAGE"] and q["ilosc"] == 4 and q["demo"] == "bez" and q["zawor"] == "srebrny"
    assert T.zapytanie("t-pro uniwersalny", ["T-PRO"])["producent"] == "T-PRO"
    assert T.zapytanie("t-pro uniwersalny", ["T-PRO"])["rodzaje"] == ["uni"]
    assert T.zapytanie("zestaw naprawczy")["akcesoria"] is True


def test_grupy_wynikow():
    # po aucie: dokładne, potem ta sama marka, na końcu uniwersalne; bez akcesoriów i bez ceny 0
    assert _ids("kia sportage") == [(1, 1), (2, 2), (3, 2), (4, 3), (9, 3)]   # Hyundai = ta sama grupa co KIA
    assert _ids("52933-D4100") == [(2, 1)]                     # numer OE z kreską
    assert _ids("opel s016") == [(5, 1), (4, 3), (9, 3)]
    assert _ids("oryginał mercedes bez demo") == []
    assert _ids("zestaw naprawczy") == [(7, 1)] and _ids("programator") == [(8, 1)]
    assert {i for i, _ in _ids("")} == {1, 2, 3, 4, 5, 6, 9}     # wszystkie czujniki, bez akcesoriów


def test_trasa_api_tpms():
    stare = dict(S.KONTO)

    class Kat:
        def tpms(self):
            return [dict(p) for p in DB]
    try:
        S.KONTO.update(katalog=Kat(), katalog_info=lambda: "z pliku")
        c, r = S.handle("/api/tpms", {"q": "kia"})
        assert c == 200 and r["lista"][0]["id"] in (1, 2) and r["zrodlo"] == "z pliku" and "_k" not in r["lista"][0]
        Kat.tpms = lambda self: []
        c, r = S.handle("/api/tpms", {"q": "kia"})
        assert c == 502 and "tylko opony" in r["error"]
    finally:
        S.KONTO.clear(); S.KONTO.update(stare)


DB2 = [_t(20, "TPMS CZUJNIK AUTEL MX ONE SENSOR 433MHZ SREBRNY", "AUTEL"), _t(21, "TPMS CZUJNIK NOVOSENSOR 433 MHZ", "NOVOSENSOR"),
       _t(22, "TPMS CZUJNIK OE-R BLANK 3200 433MHZ", "T-PRO"), _t(23, "TPMS CZUJNIK OEM VW AUDI 5Q0907275", "ORYGINAŁ"),
       _t(24, "TPMS CZUJNIK MG OE-R S513", "T-PRO"), _t(25, "TPMS CZUJNIK LAND ROVER HUF-RDE003", "HUF"),
       _t(26, "TPMS CZUJNIK OEM CITROEN/PEUGEOT 9811536380 DEMO", "SCHRADER"), _t(27, "TPMS CZUJNIK KIA GUMOWY", "CUB"),
       _t(28, "ZESTAW NAPRAWCZY T-PRO ZAWÓR V077", "T-PRO", rodzaj="NARZĘDZIA AKCESORIA"), _t(29, "TPMS S3A101", "T-PRO")]


def test_poprawki_recenzenta():
    """Uniwersalne bez „UNI” w nazwie, „zawór gumowy”, „z demontażu”, marki z 2 słów / Škoda / MG, grupa VW, „oryginał”."""
    r = {p["id"]: T.rodzaj_z(p) for p in DB2}
    assert (r[20], r[21], r[22], r[29]) == ("uni", "uni", "uni", "zam")
    ids = lambda q: [(x["id"], x["grupa"]) for x in T.szukaj(DB2, q)[0]]  # noqa: E731
    assert (27, 1) in ids("kia zawór gumowy") and (27, 1) in ids("czujnik z zaworem gumowym kia")
    assert ids("z demontażu") == [(26, 1)]
    assert ids("zawór") == [(28, 1)]
    assert (25, 1) in ids("range rover") and (24, 2) in ids("mg zs")
    assert (23, 2) in ids("škoda octavia") and (23, 2) in ids("seat leon")      # czujnik VW/Audi w grupie marek
    assert ids("oryginał citroen") == [(26, 1)]                                # „oryginał” to rodzaj, nie producent
    assert {i for i, g in ids("mg zs") if g == 3} == {20, 21, 22}               # uniwersalne na końcu


def test_wyszukiwanie_opon_tylko_asortyment_opony():
    """Kopia obejmuje cały plik xPartner – zapytania o opony muszą mieć filtr Asortyment=OPONY (koła kompletne mają rozmiar opony)."""
    from oferty import okno
    zap = []
    stary = okno._db
    okno._db = lambda m, path, *a, **k: zap.append(path) or []
    try:
        kat = okno.Katalog()
        kat.swiezy = lambda maks=None: True
        kat("205/55 R16")
        kat.wzorzec("*/* R20", ["PIRELLI"], ["Zimowa"])
        assert len(zap) == 2 and all(okno.TYLKO_OPONY in p for p in zap), zap
    finally:
        okno._db = stary
