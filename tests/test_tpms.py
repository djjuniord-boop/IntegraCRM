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
    assert _ids("kia sportage") == [(1, 1), (2, 2), (4, 3), (9, 3)]
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
