"""OFERTY OPON (beta): okno modułu (Edge WebView2 przez pywebview) – osobny proces jak panel SERWIS QR.

Uruchamiane:  IntegraCRM.exe --oferty   (albo: python app/start.py --oferty)
Strona: oferty/index.html; polecenia strony -> Api.call -> silnik.handle.
Logowanie: token programu głównego (serwis_qr.read_token) – baza: oferty_konta (login API, ustawienia), oferty (historia).
"""
import base64
import json
import os
import sys
import time
import urllib.parse
from pathlib import Path

import paths

HTML = Path(__file__).resolve().parent / "index.html"
TITLE = "Latex Serwis – oferty opon (beta)"
STATUS = paths.DATA_DIR / "oferty_status.json"
LOG = paths.DATA_DIR / "oferty.log"
STORAGE = paths.DATA_DIR / "oferty_webview"


# ---------- baza (Supabase) ----------
def _token() -> str:
    from serwis import serwis_qr
    return serwis_qr.read_token() or ""


def _email(token: str) -> str:
    try:
        part = token.split(".")[1]
        part += "=" * (-len(part) % 4)
        return (json.loads(base64.urlsafe_b64decode(part)).get("email") or "").lower()
    except Exception:
        return ""


def _db(method, path, body=None, prefer="return=representation"):
    import cloud
    return cloud._http(method, path, body, _token(), prefer)


class Historia:
    """Historia ofert w bazie (tabela oferty) – każdy widzi tylko swoje (RLS)."""

    def get(self, oid):
        rows = _db("GET", "/rest/v1/oferty?select=dane&oid=eq." + urllib.parse.quote(oid)) or []
        return rows[0]["dane"] if rows else None

    def save(self, oid, klient, dane, szukaj):
        _db("POST", "/rest/v1/oferty?on_conflict=owner,oid",
            {"oid": oid, "klient": klient or "", "dane": dane, "szukaj": szukaj[:2000],
             "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
            prefer="resolution=merge-duplicates,return=minimal")

    def list(self, q=""):
        flt = ""
        q = (q or "").strip().lower().replace("*", "").replace(",", " ")
        if q:
            flt = "&szukaj=ilike." + urllib.parse.quote("*" + q + "*")
        rows = _db("GET", "/rest/v1/oferty?select=dane&order=updated_at.desc&limit=300" + flt) or []
        return [r["dane"] for r in rows if isinstance(r.get("dane"), dict)]


def wczytaj_konto():
    """Login API i ustawienia zalogowanego użytkownika -> silnik.KONTO."""
    from oferty import silnik
    e = _email(_token())
    rows = _db("GET", "/rest/v1/oferty_konta?select=xp_login,xp_haslo,ustawienia&email=eq." + urllib.parse.quote(e)) or [] if e else []
    r = rows[0] if rows else {}
    silnik.KONTO.update(login=r.get("xp_login") or "", password=r.get("xp_haslo") or "",
                        ustawienia=r.get("ustawienia") or {},
                        zapisz=lambda dane: _db("POST", "/rest/v1/rpc/oferty_zapisz_ustawienia", {"p": dane}))
    silnik.HIST = Historia()


# ---------- funkcje dla strony (window.pywebview.api.*) ----------
class Api:
    def __init__(self):
        self._window = None

    def call(self, path, body=None):
        from oferty import silnik
        try:
            if not silnik.KONTO.get("zapisz"):
                wczytaj_konto()
        except Exception as e:
            return {"code": 502, "body": {"error": f"Nie udało się wczytać konta z bazy: {e}"}}
        code, res = silnik.handle(str(path or ""), body, open_path=_open_path)
        return {"code": code, "body": res}

    def open_url(self, url):
        u = str(url or "")
        if not u.startswith("https://xpartner.net.pl/"):
            return False
        _open_path(u)
        return True


def _open_path(p):
    if hasattr(os, "startfile"):
        os.startfile(p)
    else:   # pragma: no cover – Linux (testy)
        import webbrowser
        webbrowser.open(p)


# ---------- stan okna i dziennik (dla zakładki w programie) ----------
def _status(state, **extra):
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


def log_tail(n=6) -> str:
    try:
        return "\n".join(LOG.read_text(encoding="utf-8", errors="replace").splitlines()[-n:])
    except OSError:
        return ""


def reset_log():
    try:
        paths.DATA_DIR.mkdir(parents=True, exist_ok=True)
        LOG.write_text("", encoding="utf-8")
        STATUS.unlink()
    except OSError:
        pass


def gui_log(msg):
    try:
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} INFO program: {msg}\n")
    except OSError:
        pass


def _selftest(window, out_file):
    """Test w GitHub Actions: strona wczytana, most do Pythona działa, polecenie rozpoznaje rozmiar."""
    res = {"ok": False}
    try:
        t_end = time.time() + 40
        while time.time() < t_end:
            try:
                if window.evaluate_js("typeof quick==='function' && document.readyState==='complete'"):
                    break
            except Exception:
                pass
            time.sleep(0.5)
        time.sleep(1.5)
        js = window.evaluate_js
        res["bridge"] = js("!!(window.pywebview&&window.pywebview.api&&window.pywebview.api.call)")
        from oferty import silnik
        res["parse"] = silnik.handle("/api/quick", {"text": "2055516 zimowe premium"})[1]["pojazdy"][0]["rozmiar"]
        res["status"] = read_status().get("state")
        res["ok"] = bool(res["bridge"]) and res["parse"] == "205/55 R16" and res["status"] == "loaded"
    except Exception as e:
        import traceback
        res["error"] = f"{e}\n{traceback.format_exc()}"
    Path(out_file).write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    window.destroy()


def run() -> int:
    import logging
    paths.DATA_DIR.mkdir(parents=True, exist_ok=True)
    _status("starting")
    h = logging.FileHandler(LOG, mode="a", encoding="utf-8")
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.getLogger().addHandler(h)
    logging.getLogger().setLevel(logging.INFO)
    log = logging.getLogger("oferty")
    try:
        from serwis import serwis_window
        serwis_window.unblock_runtime(log)
        import webview
        if not HTML.exists():
            raise FileNotFoundError(f"Brak pliku modułu: {HTML}")
        STORAGE.mkdir(parents=True, exist_ok=True)
        api = Api()
        embedded = bool(os.environ.get("INTEGRA_EMBED"))
        if embedded:
            w = webview.create_window(TITLE, url=HTML.as_uri(), js_api=api, frameless=True, easy_drag=False,
                                      x=-20000, y=-20000, width=1200, height=800, text_select=True)
        else:
            w = webview.create_window(TITLE, url=HTML.as_uri(), js_api=api, width=1320, height=900,
                                      min_size=(960, 640), text_select=True)
        api._window = w

        def on_shown():
            if embedded:
                try:
                    from serwis import embed_win
                    embed_win.hide_from_taskbar(embed_win.find_window(os.getpid(), TITLE))
                except Exception:
                    log.exception("pasek zadań")
            _status("shown")

        w.events.shown += on_shown
        w.events.loaded += lambda: (log.info("strona wczytana"), _status("loaded"))
        icon = paths.APP_DIR / "assets" / "icon.ico"
        kw = dict(private_mode=False, storage_path=str(STORAGE), icon=str(icon) if icon.exists() else None)
        if sys.platform == "win32":
            kw["gui"] = "edgechromium"
        _status("window")
        test_out = os.environ.get("INTEGRA_OFERTY_TEST")
        if test_out:
            webview.start(_selftest, (w, test_out), **kw)
        else:
            webview.start(**kw)
        _status("closed")
        return 0
    except Exception as e:
        log.exception("błąd okna ofert")
        _status("error", error=f"{type(e).__name__}: {e}")
        raise


def launch(embed=False):
    import subprocess
    if getattr(sys, "frozen", False):
        cmd = [sys.executable, "--oferty"]
    else:
        cmd = [sys.executable, str(paths.APP_DIR / "start.py"), "--oferty"]
    try:
        from serwis import serwis_window
        serwis_window.unblock_runtime()
    except Exception:
        pass
    env = dict(os.environ)
    for k in ("INTEGRA_SHOT", "INTEGRA_SELFTEST"):
        env.pop(k, None)
    if embed:
        env["INTEGRA_EMBED"] = "1"
    else:
        env.pop("INTEGRA_EMBED", None)
    return subprocess.Popen(cmd, cwd=str(paths.ROOT), env=env)
