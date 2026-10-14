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
