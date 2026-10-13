"""Moduł SERWIS QR – ustawienia panelu, token logowania z programu, budowa strony dla klientów."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from _wspolne import APP, temp_data


def test_ustawienia_panelu_i_logowanie_z_programu():
    d = temp_data()
    import importlib
    from serwis import serwis_qr
    importlib.reload(serwis_qr)
    serwis_qr.write_config({"serwis_base": "https://x.example/"})
    assert '"sso": false' in serwis_qr.CONFIG_JS.read_text(encoding="utf-8")
    serwis_qr.write_token("abc")
    assert serwis_qr.read_token() == "abc"
    serwis_qr.write_config({})   # okno panelu zapisuje ustawienia samo – logowanie z programu musi zostać
    assert '"sso": true' in serwis_qr.CONFIG_JS.read_text(encoding="utf-8")
    serwis_qr.clear_token()
    assert serwis_qr.read_token() == "" and str(serwis_qr.TOKEN_FILE).startswith(str(d))


def test_walidacja_adresow():
    from serwis import serwis_qr
    assert serwis_qr.check_base("serwis.pl") != ""
    assert serwis_qr.check_base("https://serwis.latex.net.pl/") == ""
    assert serwis_qr.check_supabase("https://abc.supabase.co", "") != ""


def test_strona_klienta_budowana_z_panelu():
    out = Path(tempfile.mkdtemp()) / "pages"
    r = subprocess.run([sys.executable, str(APP.parent / "tools" / "build_pages.py"), str(out)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    html = (out / "index.html").read_text(encoding="utf-8")
    assert '<script src="config.js"></script>' in html and "../../data" not in html
    assert 'name="robots" content="noindex"' in html
    cfg = (out / "config.js").read_text(encoding="utf-8")
    cfg = json.loads(cfg[cfg.index("{"): cfg.rindex("}") + 1])
    assert cfg["url"].startswith("https://") and cfg["key"].startswith("eyJ") and cfg["base"].endswith("/")
    assert (out / "qrcode.min.js").exists() and (out / ".nojekyll").exists()
