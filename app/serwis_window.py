"""SERWIS QR (beta): panel jako okno programu (silnik Edge WebView2 przez pywebview).

Uruchamiane jako osobny proces:  IntegraCRM.exe --serwis   (albo: python app/start.py --serwis)
– dzięki temu okno panelu nie blokuje głównego okna (Tkinter) i odwrotnie.
Dane panelu (tryb lokalny) są w data/serwis_webview – aktualizacje programu ich nie ruszają.
"""
import json
import os
import sys
import threading
import time
from pathlib import Path

import paths
import serwis_qr

STORAGE = paths.DATA_DIR / "serwis_webview"
TITLE = "Latex Serwis – historia serwisowa (beta)"


def _load_cfg() -> dict:
    try:
        return json.loads(paths.CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


class Api:
    """Funkcje programu dostępne z panelu (window.pywebview.api.*)."""

    def __init__(self):
        self.window = None

    def open_url(self, url):
        u = str(url or "")
        if not u.startswith(("https://", "http://", "tel:", "mailto:")):
            return False
        if hasattr(os, "startfile"):
            os.startfile(u)
        else:   # pragma: no cover
            import webbrowser
            webbrowser.open(u)
        return True

    def save_backup(self, text, name):
        import webview
        r = self.window.create_file_dialog(webview.SAVE_DIALOG, save_filename=str(name or "serwis-kopia.json"),
                                           file_types=("Kopia panelu (*.json)",))
        if not r:
            return ""
        path = Path(r if isinstance(r, str) else r[0])
        if path.suffix.lower() != ".json":
            path = path.with_suffix(".json")
        path.write_text(str(text), encoding="utf-8")
        return str(path)

    def version(self):
        from version import VERSION
        return VERSION


def _selftest(window, out_file: str):
    """Test w GitHub Actions: czy panel się wczytał, rysuje QR i zapamiętuje dane między uruchomieniami."""
    res = {"ok": False}
    try:
        t_end = time.time() + 40
        while time.time() < t_end:
            try:
                if window.evaluate_js("typeof openService==='function' && document.readyState==='complete'"):
                    break
            except Exception:
                pass
            time.sleep(0.5)
        time.sleep(1.5)
        js = window.evaluate_js
        res["cfg_base"] = js("(window.SERWIS_CFG||{}).base||''")
        res["qr_lib"] = js("typeof QRCode")
        res["bridge"] = js("!!(window.pywebview&&window.pywebview.api)")
        res["cars_before"] = js("store.load('cars',[]).length")
        res["app_mode_text"] = js("(document.getElementById('demoTxt')||{}).textContent||''")
        js("openService(null);1")
        time.sleep(0.5)
        js("$('fPlate').value='TEST '+Date.now()%100000;$('fKm').value='12345';preview();1")
        time.sleep(0.8)
        res["qr_drawn"] = js("!!document.querySelector('#previewBox .qr img, #previewBox .qr canvas')")
        js("saveService();1")
        time.sleep(1.0)
        res["cars_after"] = js("store.load('cars',[]).length")
        res["status"] = read_status().get("state")
        res["ok"] = (res["status"] == "loaded" and res["qr_lib"] == "function" and res["qr_drawn"] and res["bridge"] and "w programie" in res["app_mode_text"]
                     and res["cars_after"] == res["cars_before"] + 1)
        shot = os.environ.get("INTEGRA_SHOT")
        if shot:
            from PIL import ImageGrab
            js("show('list');1")
            time.sleep(1.0)
            ImageGrab.grab().save(str(Path(shot) / "9-serwis-panel.png"))
    except Exception as e:
        import traceback
        res["error"] = f"{e}\n{traceback.format_exc()}"
    Path(out_file).write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    window.destroy()


STATUS = paths.DATA_DIR / "serwis_status.json"
LOG = paths.DATA_DIR / "serwis.log"


def _status(state: str, **extra) -> None:
    """Stan okna dla głównego programu: starting → window → shown → loaded / error."""
    try:
        STATUS.write_text(json.dumps({"state": state, "pid": os.getpid(), "time": time.time(), **extra},
                                     ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def read_status() -> dict:
    try:
        return json.loads(STATUS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def log_tail(n: int = 12) -> str:
    try:
        return "\n".join(LOG.read_text(encoding="utf-8", errors="replace").splitlines()[-n:])
    except OSError:
        return ""


def _setup_log():
    import logging
    paths.DATA_DIR.mkdir(parents=True, exist_ok=True)
    h = logging.FileHandler(LOG, mode="w", encoding="utf-8")
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.addHandler(h)
    root.setLevel(logging.INFO)
    logging.getLogger("pywebview").addHandler(h)
    return logging.getLogger("serwis")


def run() -> int:
    paths.DATA_DIR.mkdir(parents=True, exist_ok=True)
    _status("starting")
    log = _setup_log()
    try:
        log.info("start, python %s, frozen=%s, root=%s", sys.version.split()[0], getattr(sys, "frozen", False), paths.ROOT)
        import webview
        log.info("pywebview %s", getattr(webview, "__version__", "?"))
        if not serwis_qr.PANEL.exists():
            raise FileNotFoundError(f"Brak pliku panelu: {serwis_qr.PANEL}")
        serwis_qr.write_config(_load_cfg())
        STORAGE.mkdir(parents=True, exist_ok=True)
        api = Api()
        w = webview.create_window(TITLE, url=serwis_qr.PANEL.as_uri(), js_api=api,
                                  width=1320, height=900, min_size=(960, 640), text_select=True)
        api.window = w

        def raise_window():
            # wysuń okno na wierzch (Windows potrafi otworzyć je za oknem głównym);
            # osobny wątek – nie wolno blokować wątku okna, bo panel by się nie wczytał
            try:
                time.sleep(0.3)
                w.on_top = True
                time.sleep(0.8)
                w.on_top = False
            except Exception:
                log.exception("on_top")

        def on_shown():
            log.info("okno widoczne")
            _status("shown")
            threading.Thread(target=raise_window, daemon=True).start()

        def on_loaded():
            log.info("panel wczytany: %s", w.get_current_url())
            _status("loaded")

        w.events.shown += on_shown
        w.events.loaded += on_loaded
        test_out = os.environ.get("INTEGRA_SERWIS_TEST")
        icon = paths.APP_DIR / "assets" / "icon.ico"
        kw = dict(private_mode=False, storage_path=str(STORAGE), icon=str(icon) if icon.exists() else None)
        if sys.platform == "win32":
            kw["gui"] = "edgechromium"   # nigdy stary silnik Internet Explorera
        _status("window")
        log.info("uruchamiam okno (%s)", kw.get("gui", "auto"))
        if test_out:
            webview.start(_selftest, (w, test_out), **kw)
        else:
            webview.start(**kw)
        log.info("okno zamknięte")
        _status("closed")
        return 0
    except Exception as e:
        log.exception("błąd okna panelu")
        _status("error", error=f"{type(e).__name__}: {e}")
        raise


def is_available() -> str:
    """Pusty tekst = okno w programie jest możliwe; inaczej powód (np. stara wersja .exe)."""
    import importlib.util
    try:
        if importlib.util.find_spec("webview") is None:
            return "Ta wersja IntegraCRM.exe nie ma silnika okna panelu – pobierz nową paczkę .exe z kanału beta."
    except Exception:
        return "Nie udało się sprawdzić silnika okna panelu."
    return ""


def launch():
    """Uruchamia okno panelu w osobnym procesie. Zwraca obiekt procesu."""
    import subprocess
    if getattr(sys, "frozen", False):
        cmd = [sys.executable, "--serwis"]
    else:
        cmd = [sys.executable, str(paths.APP_DIR / "start.py"), "--serwis"]
    env = dict(os.environ)
    env.pop("INTEGRA_SHOT", None)
    env.pop("INTEGRA_SELFTEST", None)
    return subprocess.Popen(cmd, cwd=str(paths.ROOT), env=env)
