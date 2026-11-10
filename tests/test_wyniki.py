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


def test_parsowanie_kwoty_po_polsku():
    from wyniki import dane
    assert dane.parsuj_kwote("300 000") == 300000
    assert dane.parsuj_kwote("128 450,50") == 128450.5
    assert dane.parsuj_kwote("128 450,5 zł") == 128450.5
    assert dane.parsuj_kwote("128.450,50") == 128450.5
    assert dane.parsuj_kwote("128.450") == 128450
    assert dane.parsuj_kwote("1500.5") == 1500.5
    assert dane.parsuj_kwote(" 42 ") == 42
    for zle in ("", "  ", "abc", "0", "-5", "0,00", "1,2,3", "200000000"):
        try:
            dane.parsuj_kwote(zle)
        except ValueError as e:
            assert str(e)                                   # komunikat dla użytkownika
        else:
            raise AssertionError(f"przyjęto błędną kwotę: {zle!r}")
    assert dane.kwota_do_pola(300000) == "300 000" and dane.kwota_do_pola(128450.5) == "128 450,50"
    assert dane.kwota_do_pola(None) == ""
    assert dane.parsuj_kwote(dane.kwota_do_pola(128450.5)) == 128450.5


def test_parametry_i_wywolanie_rpc():
    import threading
    from wyniki import dane
    from wyniki.zakladka import WynikiMixin
    assert dane.parametry_rpc("opole", 2026, 9, 160000.0) == {"p_branch": "opole", "p_year": 2026, "p_month": 9,
                                                              "p_target": 160000.0}
    assert dane.parametry_rpc("wroclaw", "2025", "3", 1.0, 2.0)["p_done"] == 2.0

    calls, results = [], []

    class Sess:
        is_admin = True

        def rpc(self, fn, **a):
            calls.append((fn, a, threading.current_thread() is threading.main_thread()))
            if a.get("p_month") == 13:
                raise RuntimeError("Tylko administrator może zmieniać cele (42501)")

    o = WynikiMixin()
    o.session = Sess()
    o.after = lambda ms, fn, *a: results.append((fn, a))   # wynik ma wrócić przez after, nie wprost z wątku
    o.wyniki_zapisz(dane.parametry_rpc("wroclaw", 2024, 5, 250000.0, 231000.0), lambda e: None).join(5)
    assert calls[0][0] == "admin_set_month" and calls[0][2] is False             # w wątku
    assert calls[0][1] == {"p_branch": "wroclaw", "p_year": 2024, "p_month": 5, "p_target": 250000.0,
                           "p_done": 231000.0}
    assert results[0][1] == (None,)
    o.wyniki_zapisz({"p_month": 13}, lambda e: None).join(5)
    assert isinstance(results[1][1][0], RuntimeError)
    assert dane.opis_bledu(results[1][1][0]) == "Tylko administrator może zmieniać cele."
    assert "wkleić" in dane.opis_bledu("Could not find the function public.admin_set_month (PGRST202)")


def test_brak_edycji_dla_nie_admina():
    import cloud
    from wyniki.zakladka import WynikiMixin

    class S(cloud.Session):
        def __init__(self, role):
            self.access = self.refresh_token = "x"
            self.email = "t@example.com"
            self.profile = {"role": role, "modules": ["wyniki", "marza"], "branches": ["Latex Wrocław"]}

    o = WynikiMixin()
    o.session = S("user")
    assert o._wyn_admin() is False
    assert o.wyniki_zmien_cel({"year": 2026, "month": 9}) is None and o.wyniki_dodaj_miesiac() is None
    o.session = S("admin")
    assert o._wyn_admin() is True
    o.session = None
    assert o._wyn_admin() is False


def test_oznaczenia_reczny_i_czeka_na_excel():
    from wyniki import dane
    zwykly = _row(month=9, label="Wrzesień 2026", done=310000)
    vals, tag = dane.wiersz_tabeli(zwykly)
    assert vals == ("Wrzesień 2026", "310 000 zł", "300 000 zł", "103%") and tag == ("ok",)
    vals, tag = dane.wiersz_tabeli(dict(zwykly, target_pending=True, target=400000))
    assert vals[2] == "400 000 zł ✎" and vals[3] == "78%" and tag == ("bad",)
    reczny = {"branch": "wroclaw", "year": 2023, "month": 2, "label": "Luty 2023", "target": 200000, "done": 150000,
              "holidays": None, "manual": True}
    vals, _ = dane.wiersz_tabeli(reczny)
    assert vals[0] == "Luty 2023 (ręcznie)" and vals[3] == "75%"
    assert dane.oznaczenie(reczny) == "(ręcznie)" and "Excel" in dane.oznaczenie({"target_pending": True})
    assert dane.wiersz_tabeli(dict(reczny, target=None, done=None))[0][1:] == ("—", "—", "—")
    # ręczny stary miesiąc trafia do tabeli jak pozostałe, we właściwej kolejności; nie zostaje „bieżącym”
    today = datetime.date(2026, 10, 14)
    rows = [_row(), _row(month=9, label="Wrzesień 2026"), reczny]
    cur = dane.wybierz_miesiac(rows, today)
    assert cur["month"] == 10
    assert [(r["year"], r["month"]) for r in dane.poprzednie(rows, cur)] == [(2026, 9), (2023, 2)]
    assert dane.znajdz_miesiac(rows, 2023, 2) is reczny and dane.znajdz_miesiac(rows, 2023, 3) is None


def test_wszystkie_poprzednie_i_domyslny_nowy_miesiac():
    from wyniki import dane
    today = datetime.date(2026, 10, 14)
    rows = [_row()] + [_row(year=y, month=m, label=f"{m}.{y}") for y in (2025, 2026) for m in range(1, 13)
                       if (y, m) < (2026, 10)] + [_row(year=2022, month=5, label="Maj 2022", manual=True)]
    out = dane.poprzednie(rows, dane.wybierz_miesiac(rows, today))
    assert len(out) == 22 and out[-1]["manual"]                 # wszystkie zamknięte, także stary ręczny
    assert dane.domyslny_nowy_miesiac(rows, today) == (2022, 4)  # przed najstarszym w wynikach
    assert dane.domyslny_nowy_miesiac([_row(year=2025, month=1)], today) == (2024, 12)
    assert dane.domyslny_nowy_miesiac([], today) == (2026, 9)


def test_zmiana_recznego_miesiaca_wysyla_zrobione():
    import tkinter as tk
    from wyniki.zakladka import WynikiMixin
    from ui import Fonts
    calls = []

    class Sess:
        is_admin = True

    def _zapisz(w):                       # klik „Zapisz”
        def find(x):
            for c in x.winfo_children():
                if getattr(c, "_cmd", None) and c.cget("text") == "Zapisz":
                    return c
                r = find(c)
                if r:
                    return r
        find(w)._cmd()

    class App(WynikiMixin, tk.Tk):
        pass
    app = App()
    try:
        app.withdraw()
        app.session, app.fonts, app.wyn_branch, app.wyn_branches = Sess(), Fonts(app), "wroclaw", ["wroclaw"]
        app.wyn_data, app.wyn_info = {}, tk.Label(app)
        app.wyniki_zapisz = lambda params, cb: calls.append(params)
        reczny = {"year": 2023, "month": 2, "label": "Luty 2023", "target": 200000, "done": 150000, "manual": True}
        w = app.wyniki_zmien_cel(reczny)
        _zapisz(w)
        assert calls == [{"p_branch": "wroclaw", "p_year": 2023, "p_month": 2, "p_target": 200000.0,
                          "p_done": 150000.0}]
        w.destroy()
        w = app.wyniki_zmien_cel(dict(reczny, manual=False))         # miesiąc z kalkulatora – bez p_done
        _zapisz(w)
        assert "p_done" not in calls[1]
    finally:
        app.destroy()


def test_srednia_i_prognoza_licza_dzisiejszy_dzien_po_dzisiejszej_aktualizacji():
    """Listopad 2026: 1.11 niedziela. Raporty z 2.11 i 3.11 wgrane 3.11 wieczorem → miną 2 dni, nie 1."""
    import datetime
    from wyniki import dane
    row = {"year": 2026, "month": 11, "target": 387292, "done": 27660, "holidays": ["2026-11-11"],
           "updated_at": "2026-11-03T18:32:00+00:00"}
    s = dane.podsumowanie(row, datetime.date(2026, 11, 3))
    assert s["dni_minelo"] == 2 and s["dzien_dzis"] == 2, s
    assert round(s["srednio_dziennie"]) == 13830 and round(s["prognoza"]) == 13830 * s["dni_all"]
    # dane z wczoraj (bez dzisiejszej aktualizacji) – dziś jeszcze trwa, nie liczy się
    s2 = dane.podsumowanie(dict(row, updated_at="2026-11-02T18:00:00+00:00"), datetime.date(2026, 11, 3))
    assert s2["dni_minelo"] == 1 and s2["dzien_dzis"] == 2


def test_wykres_data_lokalna_i_kwota_po_zaokragleniu():
    from wyniki import dane as D
    row = {"year": 2026, "month": 11, "holidays": ["2026-11-01", "2026-11-11"], "done": None}
    runs = [{"run_at": "2026-11-02T23:30:00+00:00", "done": 1000}]   # 3.11 0:30 czasu polskiego
    from unittest import mock   # strefa czasowa komputera bywa inna (CI: UTC) – podstawiamy przeliczenie na czas polski
    pl = datetime.timezone(datetime.timedelta(hours=1))
    with mock.patch.object(D, "_data_lokalna",
                           lambda v: datetime.datetime.fromisoformat(str(v)).astimezone(pl).date()):
        pkt = D.punkty_wykresu(row, runs, today=datetime.date(2026, 11, 20))
    assert pkt == [(2, 1000.0)]          # 3.11 = drugi dzień sprzedażowy (1.11 święto), nie 2.11
    for zle in ("0,004", "0"):
        try:
            D.parsuj_kwote(zle)
        except ValueError:
            pass
        else:
            raise AssertionError(zle)
    assert D.parsuj_kwote("0,005") == 0.01 or D.parsuj_kwote("0,006") == 0.01
