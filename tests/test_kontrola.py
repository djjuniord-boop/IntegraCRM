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
