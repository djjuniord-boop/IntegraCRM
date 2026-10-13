"""Moduł MARŻA – podłączenie do silnika bez zmiany obliczeń (wysyłka przez serwer, chmura, przywrócenie smtplib)."""
import os
import sys
import tempfile
import types

from _wspolne import temp_data  # noqa: F401 – ustawia ścieżkę do app/


class _Sesja:
    email = "test@example.com"

    def __init__(self):
        self.calls = []

    def call(self, m, p, b=None, prefer=None):
        self.calls.append((m, p, b))
        return {"ok": True}

    def upload(self, bucket, path, data, ctype):
        self.calls.append(("UP", path, len(data)))


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


def _uruchom(fail=False):
    from marza import runner
    folder = tempfile.mkdtemp()
    open(os.path.join(folder, "k.xlsx"), "wb").write(b"x" * 10)
    open(os.path.join(folder, "r.pdf"), "wb").write(b"%PDF")
    s = _Sesja()
    runner.SESSION = s
    mods = {"silnik_wroclaw": _silnik(folder, fail), "podglad_wroclaw": types.SimpleNamespace()}
    old_load = runner._load
    runner._load = lambda name: mods[name]
    import smtplib as prawdziwy
    try:
        rc = runner._engine(folder, "silnik_wroclaw", "podglad_wroclaw",
                            {"marza_recipients": {"wroclaw": ["a@example.com"]}}, lambda q: False)
    finally:
        runner._load = old_load
        runner.SESSION = None
    return rc, s.calls, sys.modules.get("smtplib") is prawdziwy


def test_przebieg_mail_przez_serwer_kopia_i_wyniki():
    os.environ.pop("LATEX_TRYB_TESTOWY", None)
    rc, calls, smtp_ok = _uruchom()
    assert rc == 0 and smtp_ok
    mail = [c for c in calls if c[1] == "/functions/v1/send-mail"]
    assert mail and mail[0][2]["action"] == "raw" and mail[0][2]["to"] == ["a@example.com"]
    assert any(c[0] == "UP" and c[1].endswith("/k.xlsx") for c in calls)
    assert any(c[0] == "UP" and c[1].endswith("/r.pdf") for c in calls)
    wynik = [c for c in calls if c[1] == "/rest/v1/marza_results"][0][2][0]
    assert wynik["margin"] == 12345.5 and wynik["target"] == 300000.0 and wynik["done"] == 120000.5


def test_awaria_silnika_przywraca_smtplib_i_nie_zapisuje_wynikow():
    rc, calls, smtp_ok = _uruchom(fail=True)
    assert rc == 1 and smtp_ok
    assert not [c for c in calls if c[1] == "/rest/v1/marza_results"]


def test_silniki_bez_adresow_w_kodzie():
    from pathlib import Path
    from _wspolne import APP
    for f in ("silnik_wroclaw.py", "silnik_opole.py"):
        s = (APP / "marza" / f).read_text(encoding="utf-8")
        assert "@" not in s.split("EMAIL_ODBIORCY = ")[1].split("\n")[0], f
        assert "latexopony" not in s and "latexserwis.pl" not in s, f
    assert Path(APP / "marza" / "runner.py").exists()
