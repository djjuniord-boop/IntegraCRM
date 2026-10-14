"""Moduł KONTROLA CRM – logika bez okna (numery, porównanie, raport CRM, historia lokalna, mail)."""
import csv
from datetime import date

from _wspolne import temp_data


def test_numery_normalizacja_i_ocr():
    from kontrola import plates
    assert plates.normalize("dw 123-45") == "DW12345"
    assert plates.ocr_equal("WE9LF81", "WESLF81")          # 9↔S – ten sam numer z wycinka
    assert not plates.ocr_equal("WE9LF81", "WE9LF82")      # 1↔2 to nie pomyłka OCR
    assert plates.extract_crm_plates("8.10.2026, 15:20  KT2277E  Latex Wrocław") == ["KT2277E"]


def test_integra_wzorzec_wiersza():
    from kontrola import plates
    txt = "8.10.2026 3576/Z/SP51/26 (Zak.) D4DDY - SKODA KODIAQ\n8.10.2026 () 0,00"
    nums, ok = plates.extract_integra_plates(txt)
    assert ok and nums == ["D4DDY"]


def test_raport_xlsx_porownanie_dokladne_i_zly_oddzial():
    from kontrola import analyze
    stary = analyze.extract.text_from_pdf
    try:
        _porownanie_dokladne(analyze)
    finally:
        analyze.extract.text_from_pdf = stary


def _porownanie_dokladne(analyze):
    analyze.extract.text_from_pdf = lambda *a, **k: (
        "Zakres dat: od 2026-10-13 do 2026-10-13\n13.10.2026 1/Z/SP1/26 (Zak.) WE9LF81 - SKODA X\n"
        "13.10.2026 2/Z/SP1/26 (Zak.) DW12345 - VW Y\n")
    rows = [{"date": date(2026, 10, 13), "plate": p, "branch": "Latex Wrocław"} for p in ("WESLF81", "DW12345")]
    r = analyze.run("x.pdf", {"rows": rows, "branches": ["Latex Wrocław"]})
    assert r["missing"] == ["WE9LF81"] and not r["autofix"] and not r["uncertain"], r
    zle = [{"date": date(2026, 10, 13), "plate": p, "branch": "Latex Opole"} for p in ("OP11111", "OP22222")]
    r2 = analyze.run("x.pdf", {"rows": zle, "branches": ["Latex Opole"]})
    assert r2["no_overlap"] and r2["warnings"]


def test_raport_crm_csv_jedna_kolumna_i_oddzialy():
    d = temp_data()
    from kontrola import crm_report
    p = d / "r.csv"
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Data", "Rejestracja", "Oddział"])
        w.writerow(["2026-10-13", "DW 12345", "Latex Wrocław"])
        w.writerow(["2026-10-13", "OP 11111", "Latex Opole"])
    rows = crm_report.load(p)
    assert [r["plate"] for r in crm_report.select(rows, ["Latex Opole"])] == ["OP11111"]
    p2 = d / "jedna.csv"
    p2.write_text("Rejestracja\nDW12345\n", encoding="utf-8")
    assert crm_report.load(p2)[0]["plate"] == "DW12345"


def test_historia_lokalna_i_rejestr_tylko_pewne_braki():
    temp_data()
    import importlib
    from kontrola import history
    importlib.reload(history)   # ścieżki plików z nowego data/
    history.SESSION = None
    i = history.add_check("a.pdf", 3, 2, ["DW12345"], [("WE9LF81", "WESLF81")])
    history.mark_sent(i, ["x@example.com"], ["DW12345"])
    assert history.read_all()[-1]["mail_wyslany_do"] == "x@example.com"
    assert list(history.reported()) == ["DW12345"]


def test_mail_temat_i_oznaczenie_zgloszonych():
    from kontrola import mailer
    subj, body = mailer.compose(["DW12345"], [], {"DW12345": "2026-10-12"})
    assert "(1)" in subj and "zgłaszany już 2026-10-12" in body
    subj2, _ = mailer.compose([], [("A1", "B1")])
    assert subj2.startswith("Numery do weryfikacji")


def test_odbiorcy_wg_oddzialow():
    temp_data()
    import konfig
    konfig.COMPANY.clear()
    konfig.COMPANY.update({"recipients": ["domyslny@example.com"], "by_branch": {"Latex Opole": ["opole@example.com"]}})
    try:
        assert konfig.recipients_for(["Latex Opole"]) == ["opole@example.com"]
        assert konfig.recipients_for(["Latex Wrocław"]) == ["domyslny@example.com"]
    finally:
        konfig.COMPANY.clear()


def test_wizyty_z_data_bez_odduplikowania():
    from kontrola import plates
    txt = ("8.10.2026 1/Z/SP1/26 (Zak.) DW12345 - VW\n8.10.2026 2/Z/SP1/26 (Zak.) DW12345 - VW\n"
           "9.10.2026 3/Z/SP1/26 (Zak.) WE9LF81 - SKODA\n9.10.2026 () 0,00\n")
    assert plates.extract_integra_visits(txt) == [("2026-10-08", "DW12345"), ("2026-10-08", "DW12345"),
                                                  ("2026-10-09", "WE9LF81")]
    assert plates.extract_integra_plates(txt) == (["DW12345", "WE9LF81"], True)   # bez zmian


def test_liczniki_dzienne():
    from kontrola import analyze
    visits = [("2026-10-08", "DW12345"), ("2026-10-08", "DW12345"), ("2026-10-08", "PO9AB12"),
              ("2026-10-09", "WE9LF81"), ("2026-10-12", "KT2277E")]
    rows = [{"date": date(2026, 10, 8), "plate": "DW12345", "branch": "W"},
            {"date": date(2026, 10, 8), "plate": "DW77777", "branch": "W"},
            {"date": date(2026, 10, 9), "plate": "DW12345", "branch": "W"},   # inny dzień – nie liczy się dla 9.10
            {"date": date(2026, 10, 9), "plate": "DW12345", "branch": "W"},
            {"date": date(2026, 10, 20), "plate": "XX12345", "branch": "W"}]  # poza zakresem Integry
    d = analyze.daily_stats(visits, rows, ("2026-10-08", "2026-10-10"))
    assert d == [{"day": "2026-10-08", "visits": 3, "lists": 2, "missing": 1},
                 {"day": "2026-10-09", "visits": 1, "lists": 2, "missing": 1},
                 {"day": "2026-10-10", "visits": 0, "lists": 0, "missing": 0}], d
    # bez zakresu – dni z wizytami
    assert [x["day"] for x in analyze.daily_stats(visits, rows)] == ["2026-10-08", "2026-10-09", "2026-10-12"]


def test_run_zwraca_liczniki_dzienne():
    from kontrola import analyze
    stary = analyze.extract.text_from_pdf
    analyze.extract.text_from_pdf = lambda *a, **k: (
        "Zakres dat: od 2026-10-13 do 2026-10-13\n13.10.2026 1/Z/SP1/26 (Zak.) DW12345 - VW\n"
        "13.10.2026 2/Z/SP1/26 (Zak.) DW12345 - VW\n13.10.2026 3/Z/SP1/26 (Zak.) PO9AB12 - VW\n")
    try:
        rows = [{"date": date(2026, 10, 13), "plate": "DW12345", "branch": "W"}]
        r = analyze.run("x.pdf", {"rows": rows, "branches": ["W"]})
    finally:
        analyze.extract.text_from_pdf = stary
    assert r["daily"] == [{"day": "2026-10-13", "visits": 3, "lists": 1, "missing": 1}], r["daily"]


class _Sesja:
    def __init__(self):
        self.calls = []

    def rpc(self, fn, **args):
        self.calls.append((fn, args))


class _Okno:
    """Minimum pól okna potrzebne _save_daily (bez Tk)."""
    def __init__(self):
        self.lines, self.hist_index = [], 7

    def say(self, t):
        self.lines.append(t)


def test_zapis_statystyk_jeden_oddzial_i_brak_przy_dwoch():
    temp_data()
    from kontrola import history
    from kontrola.zakladka import KontrolaMixin
    res = {"daily": [{"day": "2026-10-13", "visits": 3, "lists": 1, "missing": 1}], "no_overlap": False}
    s = _Sesja()
    stara = history.SESSION
    history.SESSION = s
    try:
        w = _Okno()
        KontrolaMixin._save_daily(w, res, ["Latex Wrocław", "Latex Opole"])
        assert s.calls == [] and "kilka serwisów" in w.lines[-1]
        KontrolaMixin._save_daily(w, res, ["Latex Wrocław"])
        assert s.calls == [("save_visit_stats", {"p_branch": "Latex Wrocław", "p_day": "2026-10-13", "p_visits": 3,
                                                 "p_lists": 1, "p_missing": 1, "p_check_id": 7})], s.calls

        def zly(*a, **k):
            raise RuntimeError("brak sieci")
        s.rpc = zly
        KontrolaMixin._save_daily(w, res, ["Latex Wrocław"])   # błąd zapisu → tylko linia w Szczegółach
        assert "nie zapisano (brak sieci)" in w.lines[-1]
    finally:
        history.SESSION = stara
    assert history.save_visit_stats("Latex Wrocław", res["daily"]) is None   # bez sesji – nic


def test_daily_stats_tylko_dni_z_raportu_crm():
    from datetime import date
    from kontrola import analyze
    visits = [("2026-10-01", "DW1"), ("2026-10-10", "DW2")]
    rows = [{"date": date(2026, 10, 10), "plate": "DW2"}]
    out = analyze.daily_stats(visits, rows, ("2026-10-01", "2026-10-14"))
    assert [d["day"] for d in out] == ["2026-10-10"] and out[0]["missing"] == 0
    assert analyze.daily_stats(visits, [], ("2026-10-01", "2026-10-14")) == []
