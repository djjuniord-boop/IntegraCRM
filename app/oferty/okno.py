"""OFERTY OPON (beta): okno modułu (Edge WebView2 przez pywebview) – osobny proces jak panel SERWIS QR.

Uruchamiane:  IntegraCRM.exe --oferty   (albo: python app/start.py --oferty)
Strona: oferty/index.html; polecenia strony -> Api.call -> silnik.handle.
Logowanie: token programu głównego (serwis_qr.read_token) – baza: oferty_konta (login API, ustawienia), oferty (historia).
"""
import base64
import json
import datetime
import os
import re
import shutil
import sys
import threading
import time
import urllib.request
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
    """Historia ofert w bazie (tabela oferty): użytkownik – swoje, administrator – wszystkie (RLS)."""
    admin = False

    @property
    def me(self):
        return _email(_token())

    def get(self, oid):   # własna oferta (nadpisywanie pliku przy kolejnym przeliczeniu)
        me = _email(_token())
        rows = _db("GET", "/rest/v1/oferty?select=dane&oid=eq." + urllib.parse.quote(oid)
                   + "&owner=eq." + urllib.parse.quote(me)) or []
        return rows[0]["dane"] if rows else None

    def get_id(self, rid):
        rows = _db("GET", "/rest/v1/oferty?select=dane&id=eq." + str(int(rid))) or []
        return rows[0]["dane"] if rows else None

    def save(self, oid, klient, dane, szukaj):
        _db("POST", "/rest/v1/oferty?on_conflict=owner,oid",
            {"oid": oid, "klient": klient or "", "dane": dane, "szukaj": szukaj[:2000],
             "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
            prefer="resolution=merge-duplicates,return=minimal")

    def link(self, oid, dane):
        """Link dla klienta: migawka stron PDF w bazie, zwraca token (uuid)."""
        return _db("POST", "/rest/v1/rpc/oferty_link", {"p_oid": oid, "p_dane": dane})

    def status(self, oid, status):
        _db("POST", "/rest/v1/rpc/oferty_status", {"p_oid": oid, "p_status": status}, prefer="return=minimal")

    def list(self, q=""):
        flt = ""
        q = (q or "").strip().lower().replace("*", "").replace(",", " ").replace("(", " ").replace(")", " ")
        if q:
            w = urllib.parse.quote("*" + q + "*")
            flt = f"&or=(szukaj.ilike.{w},owner.ilike.{w})"
        try:   # status i link (od 0.25); bez tych kolumn w bazie – stara lista
            rows = _db("GET", "/rest/v1/oferty?select=id,owner,dane,status,status_at,link_at,link_otwarta,klient_odp"
                              "&order=updated_at.desc&limit=1000" + flt) or []
        except Exception:
            rows = _db("GET", "/rest/v1/oferty?select=id,owner,dane&order=updated_at.desc&limit=1000" + flt) or []
        try:
            names = {u["email"].lower(): (u.get("name") or "") for u in _db("GET", "/rest/v1/app_users?select=email,name") or []}
        except Exception:
            names = {}
        for r in rows:
            r["kto"] = names.get((r.get("owner") or "").lower()) or r.get("owner") or ""
        return [r for r in rows if isinstance(r.get("dane"), dict)]


def wczytaj_konto():
    """Login API i ustawienia zalogowanego użytkownika -> silnik.KONTO."""
    from oferty import silnik
    e = _email(_token())
    rows = _db("GET", "/rest/v1/oferty_konta?select=*&email=eq." + urllib.parse.quote(e)) or [] if e else []
    r = rows[0] if rows else {}
    # hasło xPartner: z zaszyfrowanego sejfu przez funkcję bazy (tylko własne); przed etapem 2 – jawna kolumna
    try:
        haslo = _db("POST", "/rest/v1/rpc/oferty_moje_haslo", {}) or ""
    except Exception:
        haslo = r.get("xp_haslo") or ""
    silnik.KONTO.update(login=r.get("xp_login") or "", password=haslo if isinstance(haslo, str) else "",
                        ustawienia=r.get("ustawienia") or {},
                        zapisz=lambda dane: _db("POST", "/rest/v1/rpc/oferty_zapisz_ustawienia", {"p": dane}))
    h = Historia()
    try:
        prof = _db("POST", "/rest/v1/rpc/is_admin", {})
        h.admin = prof is True
    except Exception:
        h.admin = False
    silnik.HIST = h
    wczytaj_oddzialy(h.admin)
    k = Katalog()
    silnik.KONTO.update(katalog=k, katalog_info=k.info, katalog_cechy=k.cechy)


class Katalog:
    """Wyszukiwanie w kopii pliku ofertowego xPartner (tabela xp_oferta). None = użyj API (kopia pusta/nieaktualna/błąd)."""
    MAKS_WIEK = 3 * 3600

    def __init__(self):
        self.stan, self.stan_t, self.uzyty = None, 0.0, None

    def _stan(self):
        if time.time() - self.stan_t > 120:
            try:
                rows = _db("GET", "/rest/v1/app_config?key=eq.xp_oferta_stan&select=value") or []
                self.stan = rows[0]["value"] if rows else None
            except Exception:
                self.stan = None
            self.stan_t = time.time()
        return self.stan

    def swiezy(self):
        s = self._stan()
        try:
            t = datetime.datetime.fromisoformat(str(s["czas"]).replace("Z", "+00:00"))
            return (datetime.datetime.now(datetime.timezone.utc) - t).total_seconds() < self.MAKS_WIEK and int(s.get("ile") or 0) > 0
        except Exception:
            return False

    def __call__(self, size_txt):
        m = re.match(r"(\d{3})/(\d{2}) R(\d{2})", size_txt or "")
        if not m or not self.swiezy():
            self.uzyty = False
            return None
        w, p, r = m.groups()
        rows = _db("GET", "/rest/v1/xp_oferta?select=dane&szer=eq.%s&profil=eq.%s&sred=eq.%s&limit=5000" % (w, p, r)) or []
        self.uzyty = True
        return [x["dane"] for x in rows if isinstance(x.get("dane"), dict)]

    def cechy(self, pid):
        """Cechy z pliku (EPREL, śnieg, lód) dla oferty otwartej bez wyszukiwania (np. z historii)."""
        rows = _db("GET", "/rest/v1/xp_oferta?select=dane&id=eq.%d" % int(pid)) or []
        return ((rows[0].get("dane") or {}).get("attrs") or {}) if rows else {}

    def info(self):
        if not self.uzyty:
            return ""
        t = datetime.datetime.fromisoformat(str(self.stan["czas"]).replace("Z", "+00:00")).astimezone()
        return "Oferta xPartner z godz. %s (kopia odświeżana co 30 min; ceny i stany w ofercie – na żywo)" % t.strftime("%H:%M")


def wczytaj_oddzialy(admin=False):
    """Oddziały konta (z bazy – nie do zmiany przez pracownika) i dane oddziałów do PDF (app_config 'oddzialy')."""
    from oferty import silnik
    try:
        me = _db("POST", "/rest/v1/rpc/me", {})
        me = (me[0] if isinstance(me, list) and me else me) or {}
    except Exception:
        me = {}
    try:
        rows = _db("GET", "/rest/v1/app_config?key=eq.oddzialy&select=value") or []
        dane = rows[0]["value"] if rows and isinstance(rows[0].get("value"), dict) else {}
    except Exception:
        dane = {}
    moje = list(dane) if admin else [b for b in (me.get("branches") or [])]
    silnik.KONTO.update(oddzialy=moje, oddzialy_dane=dane, kto=me.get("name") or me.get("email") or "", admin=admin,
                        zamowienia="zamowienia" in (me.get("modules") or []))


def zapisz_oddzialy(dane: dict):
    """Administrator: dane oddziałów do PDF (bazę i tak chroni zasada admin_write)."""
    czyste = {}
    for nazwa, o in (dane or {}).items():
        if isinstance(o, dict) and str(nazwa).strip():
            czyste[str(nazwa).strip()[:60]] = {k: str(o.get(k) or "").strip()[:120] for k in ("nazwa", "adres", "tel", "kom", "www", "email")}
    _db("POST", "/rest/v1/app_config?on_conflict=key", {"key": "oddzialy", "value": czyste}, prefer="resolution=merge-duplicates,return=minimal")
    wczytaj_oddzialy(True)


# ---------- PDF oferty: przeglądarka Edge (jest w każdym Windows 10/11) drukuje stronę do pliku ----------
def _przegladarka():
    kand = [os.environ.get("OFERTY_PRZEGLADARKA", "")]
    for base in (os.environ.get("ProgramFiles(x86)", ""), os.environ.get("ProgramFiles", ""), os.environ.get("LOCALAPPDATA", "")):
        if base:
            kand += [os.path.join(base, "Microsoft", "Edge", "Application", "msedge.exe"),
                     os.path.join(base, "Google", "Chrome", "Application", "chrome.exe")]
    return next((k for k in kand if k and os.path.isfile(k)), "")


_PDF_LOCK = threading.Lock()
_EPREL_RE = re.compile(r'<object class="eprel" data="(https://eprel\.ec\.europa\.eu/api/products/tyres/(\d{1,12})/labels\?format=PNG)" type="image/png">(.*?)</object>', re.S)


def wstaw_etykiete_eprel(html: str) -> str:
    """Etykieta UE pobrana przez program (limit 5 s, pamięć na dysku 30 dni) i wstawiona do strony –
    Edge nie musi niczego pobierać z sieci. Gdy rejestr UE nie odpowie: od razu etykieta rysowana."""
    import tempfile
    m = _EPREL_RE.search(html)
    if not m:
        return html
    url, nr, zastepcza = m.groups()
    kat = os.path.join(tempfile.gettempdir(), "LatexOferty_eprel")
    plik = os.path.join(kat, nr + ".png")
    dane = b""
    try:
        if os.path.isfile(plik) and time.time() - os.path.getmtime(plik) < 30 * 86400:
            with open(plik, "rb") as f:
                dane = f.read()
        else:
            req = urllib.request.Request(url, headers={"User-Agent": "PanelLatexSerwis-Oferty"})
            with urllib.request.urlopen(req, timeout=5) as r:
                dane = r.read(2_000_000)
            if dane[:8] == b"\x89PNG\r\n\x1a\n":
                os.makedirs(kat, exist_ok=True)
                with open(plik + ".tmp", "wb") as f:
                    f.write(dane)
                os.replace(plik + ".tmp", plik)
    except Exception:
        dane = b""
    if dane[:8] != b"\x89PNG\r\n\x1a\n":
        return html[:m.start()] + zastepcza + html[m.end():]
    img = '<img class="eprel" src="data:image/png;base64,%s" alt="Etykieta UE">' % base64.b64encode(dane).decode()
    return html[:m.start()] + img + html[m.end():]


def zrob_pdf(html: str, nazwa: str) -> str:
    """HTML oferty -> plik PDF w folderze ofert. Zwraca ścieżkę PDF (albo HTML, gdy brak Edge/Chrome).
    Jeden stały profil Edge (szybszy start niż nowy profil za każdym razem) – dlatego PDF-y po kolei (blokada)."""
    import subprocess, tempfile
    from oferty import silnik
    html = wstaw_etykiete_eprel(html)
    os.makedirs(silnik.OUT_DIR, exist_ok=True)
    nazwa = re.sub(r"[^0-9A-Za-z._-]+", "_", nazwa).strip("_")[:90] or "oferta"
    pdf = os.path.join(silnik.OUT_DIR, nazwa + ".pdf")
    tmp = tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8")
    tmp.write(html)
    tmp.close()
    exe = _przegladarka()
    try:
        if exe:
            prof = os.path.join(tempfile.gettempdir(), "LatexOferty_pdf_profil")
            args = [exe, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check", "--disable-extensions",
                    "--disable-sync", "--disable-background-networking", "--disable-component-update", "--disable-default-apps",
                    "--user-data-dir=" + prof, "--no-pdf-header-footer", "--print-to-pdf-no-header", "--print-to-pdf=" + pdf,
                    Path(tmp.name).as_uri()]
            kw = {"creationflags": 0x08000000} if os.name == "nt" else {}   # bez okna konsoli
            if os.name != "nt":   # tylko testy na Linuksie (root)
                args.insert(1, "--no-sandbox")
            with _PDF_LOCK:
                if os.path.exists(pdf):
                    os.remove(pdf)
                subprocess.run(args, timeout=90, capture_output=True, **kw)
            if os.path.isfile(pdf) and os.path.getsize(pdf) > 1000:
                return pdf
        dst = os.path.join(silnik.OUT_DIR, nazwa + ".html")   # awaryjnie: strona do wydruku „Zapisz jako PDF”
        shutil.copyfile(tmp.name, dst)
        return dst
    finally:
        try:
            os.remove(tmp.name)
        except OSError:
            pass


def logo_uri() -> str:
    p = Path(__file__).resolve().parent.parent / "assets" / "logo.png"
    try:
        return "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode()
    except OSError:
        return ""


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
        path = str(path or "")
        if path == "/api/oddzialy":   # administrator: dane oddziałów do PDF
            if not silnik.KONTO.get("admin"):
                return {"code": 403, "body": {"error": "Dane oddziałów zmienia tylko administrator."}}
            try:
                zapisz_oddzialy((body or {}).get("oddzialy") or {})
                return {"code": 200, "body": {"ok": True}}
            except Exception as e:
                return {"code": 502, "body": {"error": f"Nie zapisano danych oddziałów: {e}"}}
        if path == "/api/pdf":
            code, res = silnik.handle(path, dict(body or {}, logo=logo_uri()), open_path=_open_path)
            if code != 200:
                return {"code": code, "body": res}
            try:
                plik = zrob_pdf(res["html"], (body or {}).get("nazwa") or "oferta")
            except Exception as e:
                return {"code": 500, "body": {"error": f"Nie udało się zapisać PDF: {e}"}}
            _open_path(plik)
            return {"code": 200, "body": {"plik": plik, "pdf": plik.endswith(".pdf"), "oddzial": res.get("oddzial")}}
        code, res = silnik.handle(path, body, open_path=_open_path)
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
