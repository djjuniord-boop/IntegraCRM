"""Moduł MARŻA – podłączenie do silnika bez zmiany obliczeń (wysyłka przez serwer, chmura, przywrócenie smtplib,
tabela miesięcy dla zakładki WYNIKI)."""
import contextlib
import datetime
import io
import os
import re
import sys
import tempfile
import types
import zipfile

from _wspolne import temp_data  # noqa: F401 – ustawia ścieżkę do app/

MIESIACE = "/rest/v1/marza_months?on_conflict=branch,year,month"


class _Sesja:
    email = "test@example.com"

    def __init__(self, fail_paths=(), fail_upload=False):
        self.calls = []
        self.fail_paths, self.fail_upload = fail_paths, fail_upload

    def call(self, m, p, b=None, prefer=None):
        self.calls.append((m, p, b, prefer))
        if any(p.startswith(f) for f in self.fail_paths):
            import cloud
            raise cloud.CloudError("Brak połączenia z serwerem.")
        return {"ok": True}

    def upload(self, bucket, path, data, ctype):
        self.calls.append(("UP", path, len(data)))
        if self.fail_upload:
            import cloud
            raise cloud.CloudError("Nie zapisano pliku w chmurze.")


def _silnik(folder, fail=False):
    eng = types.SimpleNamespace(XLSX_NAME="k.xlsx", EMAIL_NADAWCA="", EMAIL_ODBIORCY=[], LOG_NAME="log.txt")
    eng.extract_text = lambda p: "tekst"
    eng.parse_report = lambda t, n: {"label": "Październik 2026", "margin_netto": 12345.5, "start_date": "2026-10-01",
                                     "end_date": "2026-10-13", "source": n}
    eng._refresh_podglad = lambda x, log: ("Październik 2026", 300000, "120000.5", set())
    eng._wczytaj_haslo_email = lambda: None

    def main():
        pdf = os.path.join(folder, "r.pdf")
        eng.parse_report(eng.extract_text(pdf), "r.pdf")
        eng._refresh_podglad("k", [])
        import smtplib   # tak jak oryginalny silnik – import w środku funkcji
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as s:
            s.starttls()
            s.login(eng.EMAIL_NADAWCA, eng._wczytaj_haslo_email())
            for o in eng.EMAIL_ODBIORCY:
                s.sendmail(eng.EMAIL_NADAWCA, [o], "MIME...")
        if fail:
            raise RuntimeError("awaria silnika")
    eng.main = main
    return eng


def _kalkulator(path):
    """Kalkulator jak u właściciela (arkusz „Kalkulator marży” z tabelą od nagłówka „Miesiąc” + „Święta PL”).
    Listopad: cel to formuła z wynikiem zapisanym przez Excel; Grudzień: formuła bez wyniku (po zapisie przez
    openpyxl); „Razem”: wiersz bez miesiąca; Październik 2026 dwa razy (silnik pisze do ostatniego)."""
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Kalkulator marży"
    ws["B3"], ws["C3"], ws["D3"] = "Miesiąc", "Cel marży", "Aktualna marża"
    dane = [("Wrzesień 2026", 280000, 291000.25),
            ("Październik 2026", 1, 1),                 # duplikat – wygrywa wiersz niżej
            ("Październik 2026", 300000, 120000.5),
            ("Listopad 2026", "=C6*1.1", None),         # wiersz 7: formuła, Excel zapisał wynik 330000
            ("Grudzień 2026", "=C7*1.1", None),         # formuła bez zapisanego wyniku
            ("Razem", "=SUM(C4:C8)", "=SUM(D4:D8)"),
            ("styczeń 2027", 250000, 0)]
    for i, (lab, cel, akt) in enumerate(dane, start=4):
        ws.cell(row=i, column=2, value=lab)
        ws.cell(row=i, column=3, value=cel)
        ws.cell(row=i, column=4, value=akt)
    sw = wb.create_sheet("Święta PL")
    sw["A1"] = "Data"
    for i, d in enumerate(["2026-01-01", "2026-01-06", "2026-11-01", "2026-11-11", "2026-12-25", "2026-12-26",
                           "2027-01-01", "2027-01-06"], start=2):
        sw.cell(row=i, column=1, value=datetime.datetime.fromisoformat(d))
    wb.save(path)
    # wynik formuły w C7 zapisany tak, jak robi to Excel (<f>…</f><v>330000</v>) – openpyxl tego nie umie
    tmp = path + ".tmp"
    with zipfile.ZipFile(path) as src, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as out:
        for item in src.infolist():
            data = src.read(item.filename)
            if item.filename == "xl/worksheets/sheet1.xml":
                xml = data.decode("utf-8")
                xml2 = re.sub(r'(<c r="C7"[^>]*>)(<f>[^<]*</f>)(<v\s*/>|<v>[^<]*</v>)?', r"\1\2<v>330000</v>", xml)
                assert xml2 != xml, "nie udało się dopisać wyniku formuły"
                data = xml2.encode("utf-8")
            out.writestr(item, data)
    os.replace(tmp, path)


def _uruchom(fail=False, prawdziwy_kalkulator=False, sesja=None):
    from marza import runner, podglad_wroclaw
    folder = tempfile.mkdtemp()
    if prawdziwy_kalkulator:
        _kalkulator(os.path.join(folder, "k.xlsx"))
    else:
        open(os.path.join(folder, "k.xlsx"), "wb").write(b"x" * 10)   # nie da się go odczytać jako Excel
    open(os.path.join(folder, "r.pdf"), "wb").write(b"%PDF")
    s = sesja or _Sesja()
    runner.SESSION = s
    # podgląd: prawdziwa funkcja odczytu z podglądu Wrocławia (bez podmiany atrybutów samego modułu)
    pod = types.SimpleNamespace(_read_source_months=podglad_wroclaw._read_source_months)
    mods = {"silnik_wroclaw": _silnik(folder, fail), "podglad_wroclaw": pod}
    old_load = runner._load
    runner._load = lambda name: mods[name]
    import smtplib as prawdziwy
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out):
            rc = runner._engine(folder, "silnik_wroclaw", "podglad_wroclaw",
                                {"marza_recipients": {"wroclaw": ["a@example.com"]}}, lambda q: False)
    finally:
        runner._load = old_load
        runner.SESSION = None
    return rc, s.calls, sys.modules.get("smtplib") is prawdziwy, out.getvalue()


def test_przebieg_mail_przez_serwer_kopia_i_wyniki():
    os.environ.pop("LATEX_TRYB_TESTOWY", None)
    rc, calls, smtp_ok, log = _uruchom()
    assert rc == 0 and smtp_ok
    mail = [c for c in calls if c[1] == "/functions/v1/send-mail"]
    assert mail and mail[0][2]["action"] == "raw" and mail[0][2]["to"] == ["a@example.com"]
    assert any(c[0] == "UP" and c[1].endswith("/k.xlsx") for c in calls)
    assert not any(c[0] == "UP" and c[1].lower().endswith(".pdf") for c in calls), calls   # PDF-ów nie wysyłamy
    wynik = [c for c in calls if c[1] == "/rest/v1/marza_results"][0][2][0]
    assert wynik["margin"] == 12345.5 and wynik["target"] == 300000.0 and wynik["done"] == 120000.5
    # kalkulatora nie da się odczytać → tylko linia w dzienniku, przebieg OK, nic nie poszło do marza_months
    assert "Uwaga: wyniki dla zakładki WYNIKI nie zostały zapisane:" in log
    assert not [c for c in calls if c[1] == MIESIACE]


def test_awaria_silnika_przywraca_smtplib_i_nie_zapisuje_wynikow():
    os.environ.pop("LATEX_TRYB_TESTOWY", None)
    rc, calls, smtp_ok, _ = _uruchom(fail=True, prawdziwy_kalkulator=True)
    assert rc == 1 and smtp_ok
    assert not [c for c in calls if c[1] == "/rest/v1/marza_results"]
    assert not [c for c in calls if c[1] == MIESIACE]


def test_wyniki_miesiace_z_kalkulatora():
    os.environ.pop("LATEX_TRYB_TESTOWY", None)
    rc, calls, smtp_ok, log = _uruchom(prawdziwy_kalkulator=True)
    assert rc == 0 and smtp_ok
    zap = [c for c in calls if c[1] == MIESIACE]
    assert len(zap) == 1, zap
    m, _, rows, prefer = zap[0]
    assert m == "POST" and prefer == "resolution=merge-duplicates,return=minimal"
    by = {(r["year"], r["month"]): r for r in rows}
    assert sorted(by) == [(2026, 9), (2026, 10), (2026, 11), (2026, 12), (2027, 1)], sorted(by)   # bez „Razem”
    for r in rows:
        assert set(r) == {"branch", "year", "month", "label", "target", "done", "holidays", "updated_at"}
        assert r["branch"] == "wroclaw"
        assert r["target"] is None or type(r["target"]) is float
        assert r["done"] is None or type(r["done"]) is float
        datetime.datetime.fromisoformat(r["updated_at"])
    paz = by[(2026, 10)]
    assert paz["label"] == "Październik 2026" and paz["target"] == 300000.0 and paz["done"] == 120000.5
    assert paz["holidays"] == []
    lis = by[(2026, 11)]
    assert lis["target"] == 330000.0          # formuła → wynik zapisany przez Excel
    assert lis["done"] is None                # pusta komórka → None, nie 0
    assert lis["holidays"] == ["2026-11-01", "2026-11-11"]
    gru = by[(2026, 12)]
    assert gru["target"] is None              # formuła bez zapisanego wyniku → None, nie 0
    assert gru["holidays"] == ["2026-12-25", "2026-12-26"]
    sty = by[(2027, 1)]
    assert sty["label"] == "Styczeń 2027" and sty["target"] == 250000.0 and sty["done"] == 0.0
    assert sty["holidays"] == ["2027-01-01", "2027-01-06"]   # święta tylko z tego roku i miesiąca
    assert by[(2026, 9)]["done"] == 291000.25
    assert "Zakładka WYNIKI: zapisano 5 miesięcy (Wrocław)." in log
    assert "formuły bez wyliczonej wartości" in log and "(1)" in log


def test_wyniki_blad_sesji_nie_przerywa_przebiegu():
    os.environ.pop("LATEX_TRYB_TESTOWY", None)
    rc, calls, smtp_ok, log = _uruchom(prawdziwy_kalkulator=True, sesja=_Sesja(fail_paths=("/rest/v1/marza_months",)))
    assert rc == 0 and smtp_ok
    assert [c for c in calls if c[1] == "/rest/v1/marza_results"]
    assert "Uwaga: wyniki dla zakładki WYNIKI nie zostały zapisane: Brak połączenia z serwerem." in log
    assert "Zakładka WYNIKI: zapisano" not in log


def test_wyniki_zapisane_mimo_bledu_kopii_i_wynikow():
    os.environ.pop("LATEX_TRYB_TESTOWY", None)
    s = _Sesja(fail_paths=("/rest/v1/marza_results",), fail_upload=True)
    rc, calls, smtp_ok, log = _uruchom(prawdziwy_kalkulator=True, sesja=s)
    assert rc == 0 and smtp_ok
    assert "Uwaga: kopia w chmurze nie powiodła się" in log
    assert "Uwaga: zapis wyników w bazie nie powiódł się" in log
    assert [c for c in calls if c[1] == MIESIACE] and "Zakładka WYNIKI: zapisano 5 miesięcy (Wrocław)." in log


def test_tryb_testowy_nic_nie_wysyla_do_bazy():
    old = os.environ.get("LATEX_TRYB_TESTOWY")
    os.environ["LATEX_TRYB_TESTOWY"] = "1"
    try:
        rc, calls, smtp_ok, log = _uruchom(prawdziwy_kalkulator=True)
    finally:
        if old is None:
            os.environ.pop("LATEX_TRYB_TESTOWY", None)
        else:
            os.environ["LATEX_TRYB_TESTOWY"] = old
    assert rc == 0 and smtp_ok
    assert not [c for c in calls if c[0] == "UP" or c[1].startswith("/rest/v1/")], calls
    assert "[TRYB TESTOWY] Wyniki i kalkulator NIE zostały zapisane w chmurze." in log


def test_etykieta_miesiaca():
    from marza.runner import _label_ym, _liczba, _ile_miesiecy
    assert _label_ym("Październik 2026") == (2026, 10)
    assert _label_ym(" październik  2026 ") == (2026, 10)
    assert _label_ym("Styczeń 2027") == (2027, 1)
    for zla in ("Razem", "Październik", "Foo 2026", "Październik 26a", None, 2026, "Październik 1999",
                "Październik 2026²", "Październik 2026 r."):
        assert _label_ym(zla) is None, zla
    assert _liczba(300000) == 300000.0 and type(_liczba(300000)) is float
    assert _liczba("120 000,50") == 120000.5
    for brak in (None, "", "=SUM(C4:C8)", "abc", True, float("nan")):
        assert _liczba(brak) is None, brak
    assert [_ile_miesiecy(n) for n in (1, 2, 5, 12, 22)] == \
        ["1 miesiąc", "2 miesiące", "5 miesięcy", "12 miesięcy", "22 miesiące"]


def test_silniki_bez_adresow_w_kodzie():
    from pathlib import Path
    from _wspolne import APP
    for f in ("silnik_wroclaw.py", "silnik_opole.py"):
        s = (APP / "marza" / f).read_text(encoding="utf-8")
        assert "@" not in s.split("EMAIL_ODBIORCY = ")[1].split("\n")[0], f
        assert "latexopony" not in s and "latexserwis.pl" not in s, f
    assert Path(APP / "marza" / "runner.py").exists()


# ---------- raporty PDF nie są przechowywane, czytelny przebieg, polskie liczby ----------
def _pdf(path, linie):
    from reportlab.pdfgen import canvas
    c = canvas.Canvas(path)
    y = 800
    for l in linie:
        c.drawString(40, y, l)
        y -= 16
    c.save()


def _raport(path, oddzial, od, do, kwota):
    _pdf(path, ["Raport sprzedazy towarow i uslug", f"Serwis {oddzial}", f"Zakres dat: od {od} do {do}",
                f"Marza towary + sprzedaz uslug netto: {kwota}"])


def test_dodanie_do_kolejki_przenosi_plik():
    from marza import runner
    root, src = tempfile.mkdtemp(), tempfile.mkdtemp()
    for sub in ("Wrocław", "Opole"):
        os.makedirs(os.path.join(root, sub))
    f = os.path.join(src, "raport.pdf")
    _raport(f, "Wroclaw", "2026-10-01", "2026-10-13", "154 186,54")
    added, rejected, notes = runner.add_reports(root, [f])
    assert added == [("raport.pdf", "wroclaw")] and not rejected and not notes
    assert not os.path.exists(f), "oryginał miał zostać przeniesiony"
    assert os.path.isfile(os.path.join(root, runner.WRZUC, "raport.pdf"))


def test_dodanie_plik_zablokowany_kopia_i_uwaga():
    from marza import runner
    root, src = tempfile.mkdtemp(), tempfile.mkdtemp()
    for sub in ("Wrocław", "Opole"):
        os.makedirs(os.path.join(root, sub))
    f = os.path.join(src, "raport.pdf")
    _raport(f, "Opole", "2026-10-01", "2026-10-13", "1 000,00")
    o_move, o_remove = runner.shutil.move, runner.os.remove

    def zly_move(a, b):
        raise PermissionError("plik jest używany")

    def zly_remove(x):
        if x == f:
            raise PermissionError("plik jest używany")
        return o_remove(x)
    runner.shutil.move, runner.os.remove = zly_move, zly_remove
    try:
        added, rejected, notes = runner.add_reports(root, [f])
    finally:
        runner.shutil.move, runner.os.remove = o_move, o_remove
    assert added == [("raport.pdf", "opole")] and not rejected
    assert os.path.isfile(os.path.join(root, runner.WRZUC, "raport.pdf")) and os.path.isfile(f)
    assert len(notes) == 1 and "nie udało się usunąć oryginału" in notes[0][1]


def test_pelny_przebieg_usuwa_zapisany_raport_i_zostawia_pominiety():
    """Prawdziwe silniki (tryb testowy): Wrocław zapisany → PDF usunięty, Opole z miesiącem spoza tabeli →
    pominięty, leży w _ODRZUCONE. Wynik ma dane do kart (miesiąc, było → jest, cel, kroki)."""
    from marza import runner
    root = tempfile.mkdtemp()
    for sub, x in (("Wrocław", "kalkulator_marzy_Wroclaw.xlsx"), ("Opole", "kalkulator_marzy_Opole.xlsx")):
        os.makedirs(os.path.join(root, sub))
        _kalkulator(os.path.join(root, sub, x))
    wrz = os.path.join(root, runner.WRZUC)
    os.makedirs(wrz)
    _raport(os.path.join(wrz, "wro.pdf"), "Wroclaw", "2026-10-01", "2026-10-13", "154 186,54")
    _raport(os.path.join(wrz, "opo.pdf"), "Opole", "2025-03-01", "2025-03-31", "1 000,00")
    linie = []
    res = runner.run_all(root, {}, log=linie.append, test_mode=True)
    tekst = "\n".join(linie)
    w, o = res["results"]["wroclaw"], res["results"]["opole"]
    assert not os.path.exists(os.path.join(root, "Wrocław", "wro.pdf"))
    assert not os.path.isdir(os.path.join(root, "Wrocław", "przetworzone"))
    assert not [n for n in os.listdir(os.path.join(root, "Wrocław")) if n.lower().endswith(".pdf")]
    assert "Raporty zapisane w kalkulatorze zostały usunięte" in tekst
    # uproszczony kalkulator testowy nie wystarcza podglądowi – jedyna uwaga Wrocławia to podgląd
    assert w["uwagi"] == ["Nie udało się odświeżyć podglądu dla handlowców – szczegóły w „Szczegóły przebiegu”."], w
    assert w["miesiac"] == "Październik 2026" and w["bylo"] == 120000.5 and w["jest"] == 154186.54
    assert w["zmiana"] == 34186.04 and w["kroki"]["podglad"] is False
    assert w["kroki"]["raport"] is True and w["kroki"]["kalkulator"] is True
    assert w["kroki"]["dysk"] is None and w["kroki"]["baza"] is None     # tryb testowy / bez logowania
    assert "marża netto = 154 186,54 zł" in tekst and "120 000,50 zł → 154 186,54 zł" in tekst   # polskie kwoty
    assert o["status"] == "UWAGA" and o["odrzucone"] == ["opo.pdf"]
    assert os.path.isfile(os.path.join(wrz, "_ODRZUCONE", "opo.pdf"))
    assert any("_ODRZUCONE" in u for u in o["uwagi"])
    assert not res["ok"] and "SĄ UWAGI – przeczytaj powyżej" in tekst
    assert "--- Krok 2/3: Wrocław ---" in linie and "--- Krok 3/3: Opole ---" in linie


def _log_silnika(tekst):
    from marza import rozdziel
    root = tempfile.mkdtemp()
    rozdziel.configure(root)
    folder = os.path.join(root, "Wrocław")
    os.makedirs(os.path.join(folder, "silnik"))

    def run():
        with open(os.path.join(folder, "silnik", "log_aktualizacji.txt"), "a", encoding="utf-8") as f:
            f.write(tekst)
        return 0
    return rozdziel.uruchom_silnik("WROCŁAW", folder, run, {
        "reports": [{"source": "r.pdf", "label": "Październik 2026", "margin_netto": 900.0, "margin_raw": 1000.0,
                     "deduction": 100.0, "deduction_details": [("Opony / C", 100.0, False), ("Opony / R", 0.0, True)]}],
        "chmura": {"baza": True, "uwagi": []}})


def test_rozpoznawanie_nowych_tekstow_silnika():
    w = _log_silnika("Odczytane raporty:\n  r.pdf: Październik 2026 -> marża netto = 900,00 zł\n\n"
                     "Zaktualizowano w Excelu:\n  Październik 2026: 120000.5 -> 900.00 zł  (z pliku r.pdf)\n\n"
                     "Raporty zapisane w kalkulatorze zostały usunięte z komputera (PDF-y nie są przechowywane).\n"
                     "Odświeżono plik podglądowy dla handlowców (P.xlsx):\n"
                     "  Miesiąc: Październik 2026 | Cel: 300 000,00 zł | Zrobione: 154 186,54 zł\n"
                     "Skopiowano na Dysk Google: G:/x\n"
                     "Wysłano 2 powiadomienia e-mail z wykresem (każdy odbiorca widzi w polu „Do” tylko swój adres).\n")
    assert w["status"] == "OK", w
    assert w["emaile"] == 2 and w["cel"] == 300000.0 and w["zrobione"] == 154186.54 and w["procent"] == 51
    assert w["bylo"] == 120000.5 and w["jest"] == 900.0
    assert all(w["kroki"][k] is True for k in ("raport", "kalkulator", "podglad", "dysk", "email", "baza")), w
    assert w["odjete"]["odjeto"] == 100.0 and len(w["odjete"]["pozycje"]) == 2
    w = _log_silnika("Odczytane raporty:\n\nZaktualizowano w Excelu:\n  Październik 2026: None -> 900.00 zł  (z pliku r.pdf)\n"
                     "Uwaga: folder Dysku Google nie znaleziony (G:) — plik podglądowy zapisany tylko lokalnie.\n"
                     "Uwaga: nie udało się wysłać e-maila z powiadomieniem: brak sieci\n")
    assert w["status"] == "UWAGA" and w["kroki"]["dysk"] is False and w["kroki"]["email"] is False
    assert w["bylo"] is None and w["zmiana"] == 900.0
    w = _log_silnika("Odczytane raporty:\n\nZaktualizowano w Excelu:\n  Październik 2026: 1 -> 2.00 zł  (z pliku r.pdf)\n"
                     "E-mail nie został wysłany – brak zaznaczonych odbiorców.\n")
    assert w["emaile"] == 0 and w["kroki"]["email"] is None and w["status"] == "OK"
    w = _log_silnika("BŁĄD: nie mogę zapisać k.xlsx — plik jest teraz otwarty w Excelu.\n")
    assert w["status"] == "BŁĄD" and w["kroki"]["kalkulator"] is False


def test_kwoty_i_odmiana():
    from marza.rozdziel import kwota, odmiana, _na_liczbe
    from marza import silnik_wroclaw as sw, silnik_opole as so
    assert kwota(154186.54) == "154 186,54 zł" and kwota(0) == "0,00 zł" and kwota(None) == "—"
    assert kwota(34186.04, znak=True) == "+34 186,04 zł" and kwota(-1234.5, znak=True) == "-1 234,50 zł" == sw._zl(-1234.5, znak=True)
    assert _na_liczbe("154 186,54 zł") == 154186.54 and _na_liczbe("154186.54") == 154186.54
    assert _na_liczbe("None") is None
    for m in (sw, so):
        assert m._zl(154186.54) == "154 186,54 zł" and m._zl(12.5, znak=True) == "+12,50 zł"
        assert [m._odmiana(n, "powiadomienie", "powiadomienia", "powiadomień") for n in (1, 2, 5, 12, 22, 0)] == \
            ["powiadomienie", "powiadomienia", "powiadomień", "powiadomień", "powiadomienia", "powiadomień"]
    assert odmiana(3, "a", "b", "c") == "b"


def test_krok_w_pasku():
    import importlib
    z = importlib.import_module("marza.zakladka")
    assert z.marza_step_text("--- Krok 2/3: Wrocław ---") == "Krok 2/3: Wrocław…"
    assert z.marza_step_text("Zaktualizowano w Excelu:") == "Krok 2/3: Wrocław – zapis w kalkulatorze…"
    assert z.marza_step_text("cokolwiek") is None


def test_okno_kopii_bez_pdf():
    from _wspolne import APP
    s = (APP / "marza" / "runner.py").read_text(encoding="utf-8")
    assert "application/pdf" not in s and '"pdfs"' not in s


def _folder_latex():
    from marza import runner
    root = tempfile.mkdtemp()
    for sub, x in (("Wrocław", "kalkulator_marzy_Wroclaw.xlsx"), ("Opole", "kalkulator_marzy_Opole.xlsx")):
        os.makedirs(os.path.join(root, sub))
        _kalkulator(os.path.join(root, sub, x))
    os.makedirs(os.path.join(root, runner.WRZUC))
    return root


def test_plik_z_kolejki_wybrany_ponownie_nie_jest_kasowany():
    from marza import runner
    root = _folder_latex()
    f = os.path.join(root, runner.WRZUC, "wro.pdf")
    _raport(f, "Wroclaw", "2026-10-01", "2026-10-13", "1 000,00")
    pytania = []
    added, rejected, notes = runner.add_reports(root, [f], lambda b, o: pytania.append(o) or True)
    assert added == [("wro.pdf", "wroclaw")] and not rejected and not pytania
    assert os.path.isfile(f)
    # inny plik tego oddziału: pytanie o zastąpienie, stary usunięty, nowy w kolejce
    g = os.path.join(tempfile.mkdtemp(), "nowy.pdf")
    _raport(g, "Wroclaw", "2026-10-01", "2026-10-14", "2 000,00")
    added, _, _ = runner.add_reports(root, [g], lambda b, o: pytania.append(o) or True)
    assert pytania == ["wro.pdf"] and runner.pending(root) == ["nowy.pdf"]


def test_raport_z_odrzuconych_usuwa_powod():
    from marza import runner
    root = _folder_latex()
    odrz = os.path.join(root, runner.WRZUC, "_ODRZUCONE")
    os.makedirs(odrz)
    f = os.path.join(odrz, "wro.pdf")
    _raport(f, "Wroclaw", "2026-10-01", "2026-10-13", "1 000,00")
    open(os.path.join(odrz, "wro_POWOD.txt"), "w").write("powód")
    added, _, _ = runner.add_reports(root, [f])
    assert added == [("wro.pdf", "wroclaw")] and os.listdir(odrz) == []


def test_kalkulator_otwarty_raport_wraca_do_kolejki():
    from marza import runner
    import openpyxl.workbook.workbook as wbm
    root = _folder_latex()
    _raport(os.path.join(root, runner.WRZUC, "wro.pdf"), "Wroclaw", "2026-10-01", "2026-10-13", "154 186,54")
    o_save = wbm.Workbook.save

    def zablokowany(self, path):
        if "kalkulator_marzy" in str(path):
            raise PermissionError("plik otwarty w Excelu")
        return o_save(self, path)
    wbm.Workbook.save = zablokowany
    try:
        res = runner.run_all(root, {}, log=lambda l: None, test_mode=True)
    finally:
        wbm.Workbook.save = o_save
    w = res["results"]["wroclaw"]
    assert runner.pending(root) == ["wro.pdf"], os.listdir(os.path.join(root, runner.WRZUC))
    assert not os.path.isdir(os.path.join(root, runner.WRZUC, "_ODRZUCONE"))
    assert w["status"] == "BŁĄD" and w["w_kolejce"] == ["wro.pdf"] and not w["odrzucone"]
    assert w["kroki"]["kalkulator"] is False


def test_nieoczekiwany_blad_silnika_raport_do_odrzuconych():
    """Błąd silnika bez komunikatu „BŁĄD:” powtórzyłby się – raport nie wraca do kolejki w kółko."""
    import os
    import tempfile
    from marza import rozdziel as roz
    root = tempfile.mkdtemp()
    roz.configure(root)
    folder = os.path.join(root, "Wroclaw")
    os.makedirs(os.path.join(folder, "silnik"), exist_ok=True)
    with open(os.path.join(folder, "r.pdf"), "wb") as f:
        f.write(b"%PDF-1.4")
    w = roz.uruchom_silnik("WROCŁAW", folder, lambda: 1)
    assert "r.pdf" in w["odrzucone"] and not w["w_kolejce"], w
    assert not os.path.exists(os.path.join(roz.WRZUC_DIR, "r.pdf"))
