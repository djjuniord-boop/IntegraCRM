"""STATYSTYKI: listy kontrolne na 10 zleceń, miesiące, prognoza."""
import datetime

from _wspolne import temp_data  # noqa: F401  (ustawia ścieżkę do app/)

DZIS = datetime.date(2026, 10, 14)


def _r(day, v, l_, m=0, b="Latex Wrocław"):
    return {"branch": b, "day": day, "visits": v, "lists": l_, "missing": m}


def test_miesiace_grupowanie_i_kolejnosc():
    from statystyki import dane
    rows = [_r("2026-09-01", 20, 18), _r("2026-09-02", 20, 16), _r("2026-10-01", 10, 9, 1)]
    m = dane.miesiace(rows)
    assert [x["klucz"] for x in m] == ["2026-10", "2026-09"]
    assert m[0]["nazwa"] == "Październik 2026"
    assert (m[1]["visits"], m[1]["lists"], m[1]["dni"]) == (40, 34, 2)
    assert round(m[1]["na10"], 1) == 8.5


def test_okres_90_dni_i_filtr_oddzialu():
    from statystyki import dane
    rows = [_r("2026-05-01", 100, 100), _r("2026-10-01", 10, 8), _r("2026-10-02", 10, 6, b="Latex Opole")]
    o = dane.okres(rows, 90, DZIS)
    assert (o["visits"], o["lists"]) == (20, 14)
    w = dane.okres(dane.filtruj(rows, "Latex Wrocław"), 90, DZIS)
    assert (w["visits"], w["lists"], w["na10"]) == (10, 8, 8.0)
    assert dane.okres([], 90, DZIS)["na10"] is None


def test_prognoza_srodek_i_widelki():
    from statystyki import dane
    rows = [_r("2026-08-10", 100, 80), _r("2026-09-10", 100, 90), _r("2026-10-05", 100, 85)]
    p = dane.prognoza(1000, rows, DZIS)
    assert p["srodek"] == 850 and p["od"] == 800 and p["do"] == 900
    assert p["miesiecy"] == 3 and p["zakres"] == "ostatnich 90 dni"


def test_prognoza_bez_danych_i_stare_dane():
    from statystyki import dane
    assert dane.prognoza(1000, [], DZIS) is None
    assert dane.prognoza(0, [_r("2026-10-01", 10, 9)], DZIS) is None
    p = dane.prognoza(1000, [_r("2025-01-10", 10, 7)], DZIS)     # tylko stare dane → wszystkie
    assert p["srodek"] == 700 and p["od"] == p["do"] == 700
    assert p["zakres"] == "wszystkich zebranych danych"


def test_liczba_i_formaty():
    from statystyki import dane
    assert dane.liczba("1 000") == 1000 and dane.liczba("1.000") == 1000
    assert dane.liczba("") is None and dane.liczba("abc") is None
    assert dane.fmt_na10(8.5) == "8,5" and dane.fmt_na10(None) == "—"
    assert dane.fmt_int(12345) == "12 345"
