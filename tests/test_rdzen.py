"""Rdzeń: ustawienia (zapis atomowy, firmowe przed lokalnymi), wersje, położenie plików wymaganych przez .exe."""
import json

from _wspolne import APP, temp_data


def test_ustawienia_zapis_i_firmowe_pierwszenstwo():
    d = temp_data()
    import konfig
    cfg = konfig.load_config()
    cfg["recipients"] = ["lokalny@example.com"]
    konfig.save_config(cfg)
    assert json.loads((d / "config.json").read_text(encoding="utf-8"))["recipients"] == ["lokalny@example.com"]
    assert not list(d.glob("*.tmp"))
    konfig.COMPANY.update({"recipients": ["firma@example.com"]})
    try:
        assert konfig.load_config()["recipients"] == ["firma@example.com"]
    finally:
        konfig.COMPANY.clear()


def test_uszkodzone_ustawienia_nie_blokuja_startu():
    d = temp_data()
    (d / "config.json").write_text("{zepsute", encoding="utf-8")
    import konfig
    assert konfig.load_config()["recipients"] == []
    assert (d / "config.bad.json").exists()


def test_wersje():
    import updater
    assert updater._ver("0.14.0-beta") == (0, 14, 0)
    assert updater._ver("v0.13.8") > updater._ver("0.13.7")


def test_pliki_wymagane_przez_stary_updater_i_exe():
    assert (APP / "start.py").exists() and (APP / "version.py").exists()
    import re
    assert re.search(r'^VERSION = "\d+\.\d+\.\d+"$', (APP / "version.py").read_text(encoding="utf-8"), re.M)


def test_okno_sklada_wszystkie_moduly():
    import gui
    for n in ("_build_main", "_build_history", "_build_marza", "_build_serwis", "_build_users", "check", "send_mail",
              "marza_run", "serwis_start", "refresh_users", "show_tab", "_on_close"):
        assert hasattr(gui.App, n), n


def test_logowanie_z_komputerem_i_starsza_baza():
    import cloud
    calls = []

    def fake(method, path, body=None, token=None, prefer=""):
        calls.append(body)
        if "p_device" in (body or {}) and old[0]:
            raise cloud.CloudError("Could not find the function public.app_login(p_device, p_version)")
        return {"email": "a@b.pl", "modules": ["crm"]}
    orig = cloud._http
    cloud._http = fake
    try:
        s = cloud.Session({"access_token": "x", "refresh_token": "y"})
        old = [False]
        assert s.load_profile("0.21.2")["email"] == "a@b.pl" and "p_device" in calls[-1]
        old[0] = True
        assert s.load_profile("0.21.2")["email"] == "a@b.pl" and calls[-1] == {"p_version": "0.21.2"}
    finally:
        cloud._http = orig


def test_czuwanie_zamkniecie_po_8h_i_wersje():
    import czuwanie

    class FakeApp:
        def __init__(self):
            self.zaplanowane = []
            self.session = None
            self.marza_busy = False

        def after(self, ms, fn=None, *a):
            self.zaplanowane.append((ms, getattr(fn, "__name__", "")))
            return "id"

    app = FakeApp()
    czuwanie.start(app)
    ms, nazwa = [z for z in app.zaplanowane if z[1] == "_ostrzez"][0]
    assert ("sprawdz_sesje" in [z[1] for z in app.zaplanowane])   # co 20 s: czy admin nie wylogował
    assert nazwa == "_ostrzez" and abs(ms - (8 * 3600 - 10 * 60) * 1000) < 5000   # ostrzeżenie 10 min przed 8 h
    assert czuwanie._za_stara("99.0.0") and not czuwanie._za_stara("") and not czuwanie._za_stara("0.1.0")
    app.marza_busy = True
    assert czuwanie._zajety(app)          # trwa MARŻA – nie zamykamy
    app.marza_busy = False
    assert not czuwanie._zajety(app)


def test_aktualizacja_zapasowe_zrodlo_gdy_github_niedostepny():
    import json as _j
    import updater
    stary = updater._read_bytes
    proby = []

    def czytaj(loc):
        proby.append(loc)
        if "github.com" in loc or "example.com" in loc:
            raise OSError("zablokowane")
        return _j.dumps({"version": "99.0.0", "package": "integra-99.0.0.zip"}).encode()
    updater._read_bytes = czytaj
    try:
        m, nowsza = updater.check("https://github.com/x/y/releases/latest/download/version.json")
        assert nowsza and m["_base"] == updater.MIRROR, m
        m, _ = updater.check("https://github.com/x/y/releases/download/kanal-beta/version.json")
        assert m["_base"].endswith("/aktualizacja/beta/version.json")
        assert updater._resolve(m["_base"], "integra-99.0.0.zip").endswith("/aktualizacja/beta/integra-99.0.0.zip")
        try:   # inne źródło (folder) – bez zastępstwa
            updater.check("https://example.com/version.json")
        except OSError:
            pass
        else:
            raise AssertionError("brak błędu")
    finally:
        updater._read_bytes = stary


def test_uzytkownicy_logowanie_nowsze_niz_aktywnosc():
    import cloud

    class S(cloud.Session if hasattr(cloud, "Session") else object):
        def __init__(self):
            pass

        def call(self, method, path, *a, **k):
            if "app_users" in path:
                return [{"email": "p@x.pl", "last_seen": "2026-10-17T05:24:34.1+00:00", "app_version": "0.21.2"}]
            return [{"email": "p@x.pl", "last_active": "2026-10-16T15:49:40+00:00", "app_version": "0.21.7"}]
    u = cloud.Session.list_users(S())[0]
    assert u["active_version"] == "0.21.2" and u["last_active"].startswith("2026-10-17"), u


def test_aktualizacja_paczka_z_lustra_i_404_bez_lustra():
    import urllib.error
    import updater
    stary = updater._read_bytes
    pobrane = []

    def czytaj(loc):
        pobrane.append(loc)
        if "github.com" in loc and loc.endswith(".zip"):
            raise OSError("serwer plików zablokowany")
        raise RuntimeError("stop po pobraniu")   # dalsza instalacja nie jest tu testowana
    updater._read_bytes = czytaj
    try:
        try:
            updater.apply({"_base": "https://github.com/x/y/releases/latest/download/version.json",
                           "package": "integra-1.0.0.zip", "version": "1.0.0"})
        except RuntimeError:
            pass
        assert pobrane[-1].endswith("/aktualizacja/latest/integra-1.0.0.zip"), pobrane

        def http404(loc):
            raise urllib.error.HTTPError(loc, 404, "brak", None, None)
        updater._read_bytes = http404
        try:
            updater.check("https://github.com/x/y/releases/latest/download/version.json")
        except urllib.error.HTTPError as e:
            assert e.code == 404
    finally:
        updater._read_bytes = stary


def test_wylogowanie_przez_administratora_konczy_sesje():
    import io
    import urllib.error
    import cloud
    stary = cloud.urllib.request.urlopen

    def odrzuc(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 400, "bad", None, io.BytesIO(b'{"error_description":"Invalid Refresh Token"}'))
    cloud.urllib.request.urlopen = odrzuc
    try:
        try:
            cloud._http("POST", "/auth/v1/token?grant_type=refresh_token", {"refresh_token": "x"})
        except cloud.SessionEnded:
            pass
        else:
            raise AssertionError("brak SessionEnded")
        try:   # złe hasło przy logowaniu to zwykły błąd, nie „wylogowano”
            cloud._http("POST", "/auth/v1/token?grant_type=password", {})
        except cloud.SessionEnded:
            raise AssertionError("złe hasło nie może kończyć sesji")
        except cloud.CloudError:
            pass
    finally:
        cloud.urllib.request.urlopen = stary


def test_sprawdzanie_sesji_wylogowuje_tylko_przy_false():
    import czuwanie

    class Okno:
        def __init__(self, wynik):
            self.wynik, self.konce = wynik, []
            self.session = self

        def rpc(self, fn, **a):
            if isinstance(self.wynik, Exception):
                raise self.wynik
            return self.wynik

        def _session_ended(self):
            self.konce.append(1)

        def after(self, ms, fn, *a):
            if fn == self._session_ended:
                fn()
    stary = czuwanie.threading.Thread

    class Od:   # wątek wykonany od razu
        def __init__(self, target, daemon):
            self.t = target

        def start(self):
            self.t()
    czuwanie.threading.Thread = Od
    try:
        for wynik, ile in ((False, 1), (True, 0), (None, 0), (RuntimeError("sieć"), 0)):
            o = Okno(wynik)
            czuwanie.sprawdz_sesje(o)
            assert len(o.konce) == ile, (wynik, o.konce)
    finally:
        czuwanie.threading.Thread = stary


def test_pracuje_teraz():
    from datetime import datetime, timezone
    from uzytkownicy.zakladka import pracuje_teraz
    t = datetime(2026, 10, 17, 8, 0, tzinfo=timezone.utc)
    assert pracuje_teraz("2026-10-17T07:55:00+00:00", t)
    assert not pracuje_teraz("2026-10-17T07:50:00+00:00", t)
    assert not pracuje_teraz(None, t) and not pracuje_teraz("zle", t)
    assert not pracuje_teraz("2026-10-17T09:00:00+00:00", t)   # czas z przyszłości – nie zgadujemy
