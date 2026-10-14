"""WYNIKI: obliczenia zakładki (te same wzory co wykres w mailu MARŻY) i wybór oddziałów konta."""
import datetime

from _wspolne import temp_data  # noqa: F401  (ustawia ścieżkę do app/)


def _row(**k):
    r = {"branch": "wroclaw", "year": 2026, "month": 10, "label": "Październik 2026", "target": 300000,
         "done": 120000, "holidays": []}
    r.update(k)
    return r


def test_dni_sprzedazowe_bez_niedziel_i_swiat():
    from wyniki import dane
    dni = dane.dni_sprzedazowe(2026, 11, ["2026-11-01", "2026-11-11", "2025-11-11"])
    assert datetime.date(2026, 11, 1) not in dni          # niedziela i święto
    assert datetime.date(2026, 11, 11) not in dni         # święto (środa)
    assert datetime.date(2026, 11, 2) in dni
    assert all(d.weekday() != 6 for d in dni)
    assert len(dni) == 30 - 5 - 1                         # 5 niedziel w listopadzie 2026 + 11.11


def test_podsumowanie_jak_w_mailu():
    from wyniki import dane
    today = datetime.date(2026, 10, 14)                   # październik 2026: 27 dni sprzedażowych, przed 14.10 – 11
    s = dane.podsumowanie(_row(), today)
    assert (s["dni_all"], s["dni_minelo"], s["dni_zostalo"]) == (27, 11, 16)
    assert round(s["pct"]) == 40
    assert s["brakuje"] == 180000
    plan = 300000 * 11 / 27
    assert abs(s["plan_dzis"] - plan) < 0.01
    assert abs(s["tempo"] - 120000 / plan * 100) < 0.01            # TEMPO z maila
    assert abs(s["prognoza"] - 120000 / 11 * 27) < 0.01            # prognoza z maila
    assert abs(s["potrzeba_dziennie"] - 180000 / 16) < 0.01
    assert abs(s["srednio_dziennie"] - 120000 / 11) < 0.01


def test_brak_celu_lub_wykonania_nie_psuje():
    from wyniki import dane
    today = datetime.date(2026, 10, 14)
    s = dane.podsumowanie(_row(target=None), today)
    assert s["pct"] is None and s["tempo"] is None and s["brakuje"] is None and s["plan_dzis"] is None
    s = dane.podsumowanie(_row(done=None), today)
    assert s["pct"] is None and s["prognoza"] is None and s["plan_dzis"] is not None
    s = dane.podsumowanie(_row(target=0), today)
    assert s["pct"] is None
    assert dane.zl(None) == "—" and dane.zl(128450.4) == "128 450 zł"


def test_pierwszy_dzien_i_miesiac_zamkniety():
    from wyniki import dane
    s = dane.podsumowanie(_row(done=0), datetime.date(2026, 10, 1))
    assert s["dni_minelo"] == 0 and s["tempo"] is None and s["srednio_dziennie"] is None
    s = dane.podsumowanie(_row(month=9, label="Wrzesień 2026", done=310000), datetime.date(2026, 10, 14))
    assert not s["biezacy"] and s["dni_zostalo"] == 0 and s["potrzeba_dziennie"] is None
    assert round(s["pct"]) == 103


def test_wybor_miesiaca_i_poprzednie():
    from wyniki import dane
    rows = [_row(month=m, label=f"m{m}", done=(None if m == 12 else 1000 * m)) for m in (7, 8, 9, 10, 12)]
    today = datetime.date(2026, 10, 14)
    cur = dane.wybierz_miesiac(rows, today)
    assert cur["month"] == 10
    assert [r["month"] for r in dane.poprzednie(rows, cur)] == [9, 8, 7]
    # brak bieżącego miesiąca → ostatni z wykonaniem, nie przyszły
    cur = dane.wybierz_miesiac([r for r in rows if r["month"] != 10], today)
    assert cur["month"] == 9
    assert dane.wybierz_miesiac([], today) is None


def test_punkty_wykresu_z_aktualizacji():
    from wyniki import dane
    today = datetime.date(2026, 10, 14)
    runs = [{"done": 10000, "run_at": "2026-10-02T07:00:00Z"}, {"done": 20000, "run_at": "2026-10-02T15:00:00Z"},
            {"done": 50000, "run_at": "2026-10-07T07:00:00Z"}, {"done": 99, "run_at": "2026-09-30T07:00:00Z"},
            {"done": None, "run_at": "2026-10-08T07:00:00Z"}]
    pts = dane.punkty_wykresu(_row(), runs, today)
    assert pts[0] == (2, 20000.0)                        # z jednego dnia ostatnia aktualizacja; wrzesień pominięty
    assert pts[1] == (6, 50000.0)
    assert pts[-1] == (12, 120000.0)                     # stan z kalkulatora na dziś
    assert [i for i, _ in pts] == sorted(i for i, _ in pts)


def test_oddzialy_konta():
    import cloud
    from wyniki.zakladka import WynikiMixin

    class S(cloud.Session):
        def __init__(self, role, mods, brs):
            self.access = self.refresh_token = "x"
            self.email = "t@example.com"
            self.profile = {"role": role, "modules": mods, "branches": brs}

    def oddz(sess):
        o = WynikiMixin()
        o.session = sess
        return o.wyniki_oddzialy()
    assert oddz(S("admin", [], [])) == ["wroclaw", "opole"]
    assert oddz(S("user", ["marza"], ["Latex Wrocław"])) == ["wroclaw", "opole"]
    assert oddz(S("user", ["wyniki"], ["Latex Wrocław"])) == ["wroclaw"]
    assert oddz(S("user", ["wyniki"], ["Latex Opole", "Stangum Opole"])) == ["opole"]
    assert oddz(S("user", ["wyniki"], ["Stangum Opole"])) == []
