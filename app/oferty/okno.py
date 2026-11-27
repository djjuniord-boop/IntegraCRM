"""OFERTY OPON: okno modułu (Edge WebView2 przez pywebview) – osobny proces jak panel SERWIS QR.

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
import urllib.error
import urllib.request
import urllib.parse
from pathlib import Path

import paths

HTML = Path(__file__).resolve().parent / "index.html"
TITLE = "Latex Serwis – oferty opon"
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


# ---------- zdjęcia felg w bazie (schowek „felgi-foto” + tabela xp_felgi_foto) ----------
FOTO_BUCKET = "felgi-foto"
MAX_ADRESOW = 2        # zdjęć felgi do bazy (PDF: główne + 1)
TLO_NA_SESJE = 400     # felg pobieranych w tle przy jednym uruchomieniu (xPartner nie lubi automatów)


def _storage(method, nazwa, dane=None, timeout=30):
    import cloud
    url = cloud.URL + ("/storage/v1/object/authenticated/" if method == "GET" else "/storage/v1/object/") + FOTO_BUCKET + "/" + urllib.parse.quote(nazwa)
    h = {"apikey": cloud.ANON_KEY, "Authorization": "Bearer " + _token()}
    if dane is not None:
        h.update({"Content-Type": "image/jpeg", "x-upsert": "true"})
    req = urllib.request.Request(url, data=dane, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        if method == "GET" and e.code in (400, 404):
            return None
        raise RuntimeError("schowek zdjęć: HTTP %d %s" % (e.code, e.read()[:120].decode("utf-8", "replace")))


def _foto_wiersze(ids):
    ids = [int(i) for i in ids][:200]
    if not ids:
        return []
    return _db("GET", "/rest/v1/xp_felgi_foto?select=id,pliki,sprawdzono&id=in.(%s)" % ",".join(map(str, ids))) or []


def _foto_wszystkie():
    out = []
    for od in range(0, 50000, 1000):
        rows = _db("GET", "/rest/v1/xp_felgi_foto?select=id,pliki,sprawdzono&order=id&limit=1000&offset=%d" % od) or []
        out += rows
        if len(rows) < 1000:
            break
    return out


def _foto_zapisz_wiersz(i, pliki):
    _db("POST", "/rest/v1/xp_felgi_foto?on_conflict=id",
        {"id": int(i), "pliki": int(pliki), "sprawdzono": datetime.datetime.now(datetime.timezone.utc).isoformat()},
        prefer="resolution=merge-duplicates,return=minimal")


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

    def save(self, oid, klient, dane, szukaj, owner=""):
        teraz = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        if owner and owner != _email(_token()):   # oferta kolegi z oddziału – aktualizacja jego wpisu (pozwala baza)
            _db("PATCH", "/rest/v1/oferty?owner=eq." + urllib.parse.quote(owner) + "&oid=eq." + urllib.parse.quote(oid),
                {"klient": klient or "", "dane": dane, "szukaj": szukaj[:2000], "updated_at": teraz}, prefer="return=minimal")
            return
        _db("POST", "/rest/v1/oferty?on_conflict=owner,oid",
            {"oid": oid, "klient": klient or "", "dane": dane, "szukaj": szukaj[:2000],
             "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
            prefer="resolution=merge-duplicates,return=minimal")

    def status(self, oid, status, owner=""):
        if owner and owner != _email(_token()):   # oferta kolegi z oddziału (funkcja z 2026-11-17)
            _db("POST", "/rest/v1/rpc/oferty_status_o", {"p_owner": owner, "p_oid": oid, "p_status": status}, prefer="return=minimal")
            return
        _db("POST", "/rest/v1/rpc/oferty_status", {"p_oid": oid, "p_status": status}, prefer="return=minimal")

    def uwagi(self, txt, rid=None, oid=None, owner=""):
        """Wewnętrzne uwagi do oferty (autor albo administrator – sprawdza baza)."""
        if not rid:
            rows = _db("GET", "/rest/v1/oferty?select=id&oid=eq." + urllib.parse.quote(oid)
                       + "&owner=eq." + urllib.parse.quote(owner or _email(_token()))) or []
            if not rows:
                return
            rid = rows[0]["id"]
        _db("POST", "/rest/v1/rpc/oferty_uwagi", {"p_id": int(rid), "p_uwagi": (txt or "")[:1000]}, prefer="return=minimal")

    def list(self, q=""):
        flt = flt_u = ""
        q = (q or "").strip().lower().replace("*", "").replace(",", " ").replace("(", " ").replace(")", " ")
        if q:
            w = urllib.parse.quote("*" + q + "*")
            flt = f"&or=(szukaj.ilike.{w},owner.ilike.{w})"
            flt_u = f"&or=(szukaj.ilike.{w},owner.ilike.{w},uwagi.ilike.{w})"
        try:   # uwagi (od 0.27.8), status (od 0.25); bez tych kolumn w bazie – starsza lista
            rows = _db("GET", "/rest/v1/oferty?select=id,owner,dane,status,status_at,uwagi,uwagi_at,uwagi_kto"
                              "&order=updated_at.desc&limit=1000" + flt_u) or []
        except Exception:
            try:
                rows = _db("GET", "/rest/v1/oferty?select=id,owner,dane,status,status_at"
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


def posrednik_xpartner(m, params, body=None, timeout=30, dziennik=None):
    """Zapytanie do xPartner przez funkcję serwera „xpartner” (login i hasło B2B dokłada serwer)."""
    import cloud
    from oferty import xp
    req = urllib.request.Request(cloud.URL + "/functions/v1/xpartner",
                                 data=json.dumps({"m": m, "params": params, "body": body, "dziennik": dziennik}).encode("utf-8"),
                                 method="POST",
                                 headers={"Content-Type": "application/json", "apikey": cloud.ANON_KEY,
                                          "Authorization": "Bearer " + _token(),
                                          "User-Agent": "PanelLatexSerwis-Oferty"})
    try:
        with urllib.request.urlopen(req, timeout=timeout + 15) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read().decode("utf-8")).get("error") or ""
        except Exception:
            msg = ""
        if e.code == 404:
            msg = "Pośrednik xPartner nie jest jeszcze uruchomiony na serwerze – zgłoś administratorowi."
        elif e.code == 401 and not msg:
            msg = "Sesja wygasła – zamknij okno ofert i otwórz je ponownie."
        if e.code >= 500 or e.code == 408:
            raise xp.BrakOdpowiedzi(msg or "Brak odpowiedzi xPartner (błąd serwera %d)" % e.code)
        raise xp.Blad(msg or "xPartner: odmowa (%d)" % e.code)
    except Exception as e:
        raise xp.BrakOdpowiedzi("Brak połączenia z serwerem (%s)" % e.__class__.__name__)


def posrednik_ws(m, params, timeout=25):
    """Dobór po aucie: zapytanie do wheel-size.com przez funkcję serwera „wheel-size” (klucz API dokłada serwer)."""
    import cloud
    from oferty import silnik
    req = urllib.request.Request(cloud.URL + "/functions/v1/wheel-size", data=json.dumps({"m": m, "params": params}).encode("utf-8"),
                                 method="POST", headers={"Content-Type": "application/json", "apikey": cloud.ANON_KEY,
                                                         "Authorization": "Bearer " + _token(), "User-Agent": "PanelLatexSerwis-Oferty"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read().decode("utf-8")).get("error") or ""
        except Exception:
            msg = ""
        if e.code == 404:
            msg = "Dobór po aucie nie jest jeszcze uruchomiony na serwerze – zgłoś administratorowi."
        elif e.code == 401 and not msg:
            msg = "Sesja wygasła – zamknij okno ofert i otwórz je ponownie."
        elif e.code == 502 and "429" in msg:
            msg = "Wyczerpany dzienny limit zapytań doboru po aucie (darmowy plan) – spróbuj jutro."
        raise silnik.ApiError(msg or "Dobór po aucie: błąd serwera (%d)" % e.code)
    except Exception as e:
        raise silnik.ApiError("Brak połączenia z serwerem doboru po aucie (%s)" % e.__class__.__name__)


def ws_raport(dni=7):
    """Zużycie doboru po aucie (wheel-size) – tylko administrator (funkcja bazy ws_licznik_raport)."""
    return _db("POST", "/rest/v1/rpc/ws_licznik_raport", {"p_dni": int(dni)})


def ws_limit(limit):
    """Dzienny limit zapytań wheel-size (app_config 'wheel_size') – zapis tylko administrator (RLS)."""
    _db("POST", "/rest/v1/app_config?on_conflict=key", {"key": "wheel_size", "value": {"limit": int(limit)}},
        prefer="resolution=merge-duplicates,return=minimal")


def wczytaj_konto():
    """Login API i ustawienia zalogowanego użytkownika -> silnik.KONTO."""
    from oferty import silnik
    e = _email(_token())
    rows = _db("GET", "/rest/v1/oferty_konta?select=*&email=eq." + urllib.parse.quote(e)) or [] if e else []
    r = rows[0] if rows else {}
    # hasło xPartner nie trafia do komputera: zapytania idą przez pośrednika na serwerze (funkcja „xpartner”)
    from oferty import xp
    xp.POSREDNIK = posrednik_xpartner
    silnik.KONTO.update(login=r.get("xp_login") or "", password="",
                        ustawienia=r.get("ustawienia") or {}, ws=posrednik_ws, ws_raport=ws_raport, ws_limit=ws_limit,
                        zapisz=lambda dane: _db("POST", "/rest/v1/rpc/oferty_zapisz_ustawienia", {"p": dane}))
    from oferty import zamowienia as _zam   # „kto zamówił” – z Dziennika zmian, tylko oddział (funkcja w bazie)
    _zam.KTO = lambda nry: _db("POST", "/rest/v1/rpc/zamowienia_kto", {"p_nry": list(nry)})
    _zam.JA = lambda: _email(_token())
    try:   # faktury i zamówienia zrealizowane z poprzednich uruchomień (szybsze „Zrealizowane”)
        import paths as _p
        _zam.PLIK_PAMIECI = str(_p.DATA_DIR / "zamowienia_pamiec.json")
    except Exception:
        pass
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


# kopia obejmuje cały plik xPartner (opony, felgi, koła, TPMS…) – wyszukiwanie opon tylko w asortymencie OPONY
TYLKO_OPONY = "dane->attrs->>Asortyment=eq.OPONY"
TPMS_ASORT = "CZUJNIKI CIŚNIENIA TPMS"


class Katalog:
    """Wyszukiwanie w kopii pliku ofertowego xPartner (tabela xp_oferta). None = użyj API (kopia pusta/nieaktualna/błąd)."""
    MAKS_WIEK = 3 * 3600
    MAKS_WIEK_WZORCA = 72 * 3600   # niepełny rozmiar działa tylko na kopii – starsza kopia lepsza niż brak wyników (ceny w ofercie i tak na żywo)

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

    def swiezy(self, maks=None):
        s = self._stan()
        try:
            t = datetime.datetime.fromisoformat(str(s["czas"]).replace("Z", "+00:00"))
            return (datetime.datetime.now(datetime.timezone.utc) - t).total_seconds() < (maks or self.MAKS_WIEK) and int(s.get("ile") or 0) > 0
        except Exception:
            return False

    def __call__(self, size_txt):
        m = re.match(r"(\d{3})/(\d{2}) R(\d{2}(?:\.5)?)", size_txt or "")   # „C” odsiewa później norm_size
        if not m or not self.swiezy():
            self.uzyty = False
            return None
        w, p, r = m.groups()
        rows = _db("GET", "/rest/v1/xp_oferta?select=dane&szer=eq.%s&profil=eq.%s&sred=eq.%s&%s&limit=5000" % (w, p, r, TYLKO_OPONY)) or []
        self.uzyty = True
        return [x["dane"] for x in rows if isinstance(x.get("dane"), dict)]

    def wzorzec(self, wz, marki=(), sezony=()):
        """Niepełny rozmiar („205/55 R*”, „*/* R20”…) – opony z kopii pliku, od największego stanu (najwyżej
        silnik.WZOR_POBIERZ). Marka i sezon zawężają już w bazie. None = kopia niedostępna/nieaktualna."""
        from oferty import silnik
        m = silnik.WZOR_RE.match(wz or "")
        if not m or not self.swiezy(self.MAKS_WIEK_WZORCA):
            return None
        w, p, r, _c = m.groups()
        q = ["select=dane", TYLKO_OPONY, "order=ilosc.desc", "limit=%d" % silnik.WZOR_POBIERZ]
        for kol, v in (("szer", w), ("profil", p), ("sred", r)):
            if v != "*":
                q.append("%s=eq.%s" % (kol, v))
        warunki = []
        sz = {"Zimowa": "ZIM*", "Całoroczna": "CA*", "Letnia": "LET*"}
        if sezony:
            warunki.append("or(" + ",".join("dane->attrs->>Sezon.ilike.%s" % sz[x] for x in sezony if x in sz) + ")")
        if marki:   # „VKTYRE” -> „V*K*T*Y*R*E*” (pasuje też „VK TYRE”, „GOOD-YEAR”); dokładnie zawęża silnik
            # do wzorca trafiają tylko znaki alfanumeryczne marki – inne (przecinek, nawias) mogłyby rozbić strukturę filtra
            czyste = [c for c in ("*".join(re.sub(r"[^0-9A-Za-z]", "", x or "")) for x in marki) if c]
            if czyste:
                warunki.append("or(" + ",".join("dane->attrs->>Producent.ilike.%s*" % c for c in czyste) + ")")
        warunki = [x for x in warunki if x not in ("or()",)]
        if warunki:
            q.append("and=" + urllib.parse.quote("(" + ",".join(warunki) + ")", safe="(),.*>-"))
        rows = _db("GET", "/rest/v1/xp_oferta?" + "&".join(q)) or []
        self.uzyty = True
        return [x["dane"] for x in rows if isinstance(x.get("dane"), dict)]

    _tpms, _tpms_t = None, 0.0

    def tpms(self):
        """Czujniki TPMS i akcesoria z kopii pliku (ok. 240 pozycji – całość, filtruje silnik); pamiętane 5 min
        (kopia odświeża się co 30 min, a pierwsze zapytanie w bazie bywa wolne). None = kopia niedostępna."""
        if not self.swiezy(self.MAKS_WIEK_WZORCA):
            return None
        if self._tpms is None or time.time() - self._tpms_t > 300:
            rows = _db("GET", "/rest/v1/xp_oferta?select=dane&dane->attrs->>Asortyment=eq."
                       + urllib.parse.quote(TPMS_ASORT) + "&limit=3000") or []
            self._tpms, self._tpms_t = [x["dane"] for x in rows if isinstance(x.get("dane"), dict)], time.time()
        self.uzyty = True
        return [dict(x) for x in self._tpms]

    _felgi, _felgi_t = None, 0.0

    def felgi(self):
        """Felgi z kopii pliku (ok. 3 tys. pozycji – całość, filtruje silnik); pamiętane 5 min. None = kopia niedostępna."""
        if not self.swiezy(self.MAKS_WIEK_WZORCA):
            return None
        if self._felgi is None or time.time() - self._felgi_t > 300:
            rows = []
            for od in range(0, 20000, 1000):   # baza oddaje najwyżej 1000 wierszy naraz
                cz = _db("GET", "/rest/v1/xp_oferta?select=dane&dane->attrs->>Asortyment=eq.FELGA&order=id&limit=1000&offset=%d" % od) or []
                rows += cz
                if len(cz) < 1000:
                    break
            self._felgi, self._felgi_t = [x["dane"] for x in rows if isinstance(x.get("dane"), dict)], time.time()
        self.uzyty = True
        return [dict(x) for x in self._felgi]

    def produkt(self, kod):
        """Opona po indeksie xPartner (id), kodzie producenta albo EAN – szybkie polecenie. [] = brak / kopia niedostępna."""
        k = re.sub(r"[^0-9A-Za-z\-./]", "", kod or "")[:30]
        if not k or not self.swiezy(self.MAKS_WIEK_WZORCA):
            return []
        q = urllib.parse.quote(k, safe="")
        w = ["dane->>kod.eq." + q, "dane->>ean.eq." + q] + (["id.eq." + k] if k.isdigit() and len(k) <= 9 else [])
        rows = _db("GET", "/rest/v1/xp_oferta?select=dane&or=(%s)&limit=10" % ",".join(w)) or []
        if not rows and k.upper() != k:
            rows = _db("GET", "/rest/v1/xp_oferta?select=dane&dane->>kod=eq.%s&limit=10" % urllib.parse.quote(k.upper(), safe="")) or []
        return [x["dane"] for x in rows if isinstance(x.get("dane"), dict)]

    def cechy(self, pid):
        """Cechy z pliku (EPREL, śnieg, lód) dla oferty otwartej bez wyszukiwania (np. z historii)."""
        rows = _db("GET", "/rest/v1/xp_oferta?select=dane&id=eq.%d" % int(pid)) or []
        return ((rows[0].get("dane") or {}).get("attrs") or {}) if rows else {}

    def info(self):
        if not self.uzyty:
            return ""
        t = datetime.datetime.fromisoformat(str(self.stan["czas"]).replace("Z", "+00:00")).astimezone()
        kiedy = ("z godz. %s" % t.strftime("%H:%M")) if t.date() == datetime.date.today() else t.strftime("z %d.%m, godz. %H:%M")
        return "Kopia oferty xPartner %s (ceny i stany w ofercie – na żywo)" % kiedy


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
    try:   # ceny wspólne oddziału (marża / narzut) – ustala tylko administrator (app_config: zapis tylko admin)
        rows = _db("GET", "/rest/v1/app_config?key=eq.oferty_ceny&select=value") or []
        ceny = rows[0]["value"] if rows and isinstance(rows[0].get("value"), dict) else {}
    except Exception:
        ceny = {}
    moje = list(dane) if admin else [b for b in (me.get("branches") or [])]
    silnik.KONTO.update(oddzialy=moje, oddzialy_dane=dane, kto=me.get("name") or me.get("email") or "", admin=admin,
                        zamowienia="zamowienia" in (me.get("modules") or []),
                        zamawianie="zamawianie" in (me.get("modules") or []),
                        felgi="felgi" in (me.get("modules") or []), tpms="tpms" in (me.get("modules") or []),
                        ceny="ceny" in (me.get("modules") or []), dobor="dobor" in (me.get("modules") or []),
                        rabat_osoby=me.get("rabat_max"),
                        oddzialy_konta=list(me.get("branches") or []), ceny_oddz=ceny, zapisz_ceny=zapisz_ceny)   # koszyk: adres wg oddziałów zaznaczonych przy koncie (także admin)



def zapisz_ceny(oddzial: str, dane: dict):
    """Administrator: marża / narzut wspólne dla oddziału (baza przyjmie zapis tylko od administratora)."""
    rows = _db("GET", "/rest/v1/app_config?key=eq.oferty_ceny&select=value") or []
    wsz = rows[0]["value"] if rows and isinstance(rows[0].get("value"), dict) else {}
    wsz[str(oddzial)[:60]] = dane
    _db("POST", "/rest/v1/app_config?on_conflict=key", {"key": "oferty_ceny", "value": wsz}, prefer="resolution=merge-duplicates,return=minimal")
    from oferty import silnik
    silnik.KONTO["ceny_oddz"] = wsz


def zapisz_oddzialy(dane: dict):
    """Administrator: dane oddziałów do PDF (bazę i tak chroni zasada admin_write)."""
    czyste = {}
    for nazwa, o in (dane or {}).items():
        if isinstance(o, dict) and str(nazwa).strip():
            czyste[str(nazwa).strip()[:60]] = dict({k: str(o.get(k) or "").strip()[:120] for k in ("nazwa", "adres", "tel", "kom", "www", "email")},
                                                   **{k: str(o.get(k) or "").strip()[:400] for k in ("warunki", "cta_t", "cta_p", "por_t", "por_p")})
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
KONFIGURATOR = "https://konfigurator.xpartner.net.pl/"
# Skrypt w oknie konfiguratora (ta sama domena co usługa zdjęć – jej ciasteczko logowania xPartner).
# Serwery xPartner blokują zapytania spoza przeglądarki, więc zdjęcia pobiera ukryte okno przeglądarki programu.
ZDJ_JS = """window.__zdj=null;(async()=>{const A='https://konfigurator-api.xpartner.net.pl/';
if(location.hostname!=='konfigurator.xpartner.net.pl')return JSON.stringify({login:true});
const me=await fetch(A+'auth/me',{credentials:'include'}).catch(()=>null);if(!me||me.status!==200)return JSON.stringify({login:true});
const ids=%s,out={};let i=0;async function w(){while(i<ids.length){const id=ids[i++];try{const r=await fetch(A+'xpartner-product-images/'+id,{credentials:'include'});
if(!r.ok)continue;const j=await r.json();out[id]=[...new Set(((j&&j.data)||[]).map(x=>x.url).filter(u=>/^https:\\/\\/xpartner\\.net\\.pl\\/descriptionFiles\\//.test(u)))]}catch(e){}}}
await Promise.all([w(),w(),w(),w(),w(),w()]);return JSON.stringify({zdjecia:out})})().then(x=>{window.__zdj=x},e=>{window.__zdj=JSON.stringify({blad:String(e)})});1"""
XPARTNER_LISTA = "https://xpartner.net.pl/index.php?a=b2b_products"
# Karta produktu xPartner (gdy konfigurator nie ma zdjęć): adresy obrazków descriptionFiles z HTML karty, bez rozmiaru miniatury.
KARTA_JS = """window.__zdj2=null;(async()=>{if(location.hostname!=='xpartner.net.pl')return JSON.stringify({zdjecia:{}});
const ids=%s,out={};let i=0,login=false;async function w(){while(i<ids.length){const id=ids[i++];try{const r=await fetch('/index.php?a=b2b_products&m=productCart&pid='+id,{credentials:'include'});
if(!r.ok)continue;const t=await r.text();if(!/Wyloguj/i.test(t)){login=true;continue}const u=[...t.matchAll(/descriptionFiles\\/images\\/(\\d+)\\/(?:\\d+x\\d+c?\\/)?([0-9a-f]{40}\\.(?:jpe?g|png|webp))/gi)].map(m=>'https://xpartner.net.pl/descriptionFiles/images/'+m[1]+'/'+m[2]);
out[id]=[...new Set(u)]}catch(e){}}}
await Promise.all([w(),w(),w()]);return JSON.stringify({zdjecia:out,login:login})})().then(x=>{window.__zdj2=x},e=>{window.__zdj2=JSON.stringify({zdjecia:{}})});1"""
OBRAZY_JS = """window.__img=null;(async()=>{const out={};for(const u of %s){try{const b=await (await fetch(u,{credentials:'include'})).blob();
out[u]=await new Promise(r=>{const f=new FileReader();f.onload=()=>r(f.result);f.onerror=()=>r('');f.readAsDataURL(b)})}catch(e){}}
return JSON.stringify(out)})().then(x=>{window.__img=x},e=>{window.__img='{}'});1"""
# Zdjęcia felg do bazy: pobrane w oknie xpartner.net.pl (ta sama domena – bez blokad), zmniejszone do JPEG (dłuższy bok 640 px).
MALE_JS = """window.__male=null;(async()=>{const out={};const zm=(im,px,q)=>{const k=Math.min(1,px/Math.max(im.width,im.height));const c=document.createElement('canvas');
c.width=Math.max(1,Math.round(im.width*k));c.height=Math.max(1,Math.round(im.height*k));const x=c.getContext('2d');x.fillStyle='#fff';x.fillRect(0,0,c.width,c.height);
x.drawImage(im,0,0,c.width,c.height);return c.toDataURL('image/jpeg',q)};for(const u of %s){try{const r=await fetch(u,{credentials:'include'});if(!r.ok)continue;
const im=await createImageBitmap(await r.blob());out[u]={d:zm(im,640,0.8),m:zm(im,280,0.72)}}catch(e){}}
return JSON.stringify(out)})().then(x=>{window.__male=x},e=>{window.__male='{}'});1"""
# pywebview 5.4 nie czeka na Promise w evaluate_js – skrypt zapisuje wynik w window.__zdj, program go odpytuje


class Api:
    def __init__(self):
        self._window = None
        self._kw = None
        self._kw_gotowe = threading.Event()
        self._kw_lock = threading.Lock()
        self._tlo_lock = threading.Lock()
        self._xp_lock = threading.Lock()   # jedno pobieranie zdjęć z xPartner naraz (wspólne ukryte okna)
        self._foto = None
        self._tlo_stan = {"trwa": False, "zrobione": 0, "wszystkie": 0, "zapisane": 0, "login": False, "blad": "", "start": False, "zostalo": 0}
        self._kw2 = None
        self._kw2_gotowe = threading.Event()

    def foto(self):
        if self._foto is None:
            from oferty import zdjecia
            self._foto = zdjecia.ZdjeciaBaza(_foto_wiersze, lambda n: _storage("GET", n), lambda n, b: _storage("POST", n, b),
                                             _foto_zapisz_wiersz, dysk=paths.DATA_DIR / "felgi_miniatury")
        return self._foto

    def _zdjecia(self, ids):
        """Miniatury felg dla Panelu: {zdjecia: {id: data:… albo ""}, wkrotce: [id]} – z bazy (bez logowania do xPartner).
        Administrator: felgi jeszcze niesprawdzone pobiera z xPartner i zapisuje w bazie (decyzja właściciela 2026-11-27)."""
        from oferty import silnik
        ids = [int(x) for x in ids if str(x).isdigit()][:80]
        out, brak = self.foto().miniatury(ids)
        wynik = {"zdjecia": {str(k): v for k, v in out.items()}, "wkrotce": brak}
        if brak and silnik.KONTO.get("admin"):
            if not self._xp_lock.acquire(timeout=3):   # tło pobiera partię – Panel nie czeka, felgi „wkrótce”
                return wynik
            try:   # tło mogło właśnie zapisać część tych felg – nie pobieramy ich drugi raz
                juz, brak = self.foto().miniatury(brak)
                wynik["zdjecia"].update({str(k): v for k, v in juz.items()})
                d = self._zdjecia_do_bazy(brak, pokaz=True) if brak else {"zdjecia": {}}
            finally:
                self._xp_lock.release()
            wynik["zdjecia"].update(d.get("zdjecia") or {})
            wynik["wkrotce"] = [i for i in brak if str(i) not in wynik["zdjecia"]]
            for k in ("login", "login_karta"):
                if d.get(k):
                    wynik[k] = True
            if not d.get("login") and self._tlo_stan["login"]:   # administrator już się zalogował – tło rusza od nowa
                with self._tlo_lock:
                    self._tlo_stan.update(start=False, login=False)
                self.tlo_start()
        return wynik

    def _zdjecia_do_bazy(self, ids, pokaz=False):
        """Administrator (z blokadą _xp_lock): adresy zdjęć z xPartner -> zmniejszone JPEG -> baza.
        {zdjecia: {id: miniatura albo ""}, login?, bledy}. „Brak zdjęcia” zapisuje tylko, gdy xPartner wprost go nie ma."""
        d = self._zdjecia_xp(ids, pokaz)
        if d.get("zdjecia") is None:
            return {"zdjecia": {}, "login": True}
        zdj = d["zdjecia"]
        puste = set(d.get("puste_karta") or ())   # karta produktu wczytana, zdjęć brak – pewne „bez zdjęcia”
        adresy = {str(i): list(dict.fromkeys(zdj.get(str(i)) or []))[:MAX_ADRESOW] for i in ids}
        mapa = self._male(sorted({u for v in adresy.values() for u in v}))
        out, bledy = {}, 0
        for i in ids:
            us = adresy[str(i)]
            obrazy = [mapa[u] for u in us if u in mapa]
            if us and not obrazy:
                bledy += 1
                continue   # są adresy, ale nie udało się pobrać – spróbujemy później
            if not us and str(i) not in puste:
                continue   # nie wiadomo, czy zdjęcia są (błąd, brak odpowiedzi, logowanie) – spróbujemy później
            m = self.foto().zapisz(i, [o["d"] for o in obrazy], obrazy[0]["m"] if obrazy else None)
            if m is None:
                bledy += 1
                continue
            out[str(i)] = m
        return {"zdjecia": out, "login_karta": bool(d.get("login_karta")), "bledy": bledy}

    def _male(self, urls):
        """Adresy zdjęć xPartner -> {adres: {d: JPEG 640 px, m: miniatura 280 px}} (ukryte okno na xpartner.net.pl)."""
        import webview
        if not urls:
            return {}
        with self._kw_lock:
            if self._kw2 is None:
                self._kw2_gotowe.clear()
                self._kw2 = webview.create_window("xPartner – zdjęcia felg (karta produktu)", url=XPARTNER_LISTA, hidden=True, width=1000, height=760)
                self._kw2.events.loaded += lambda: self._kw2_gotowe.set()
                self._kw2.events.closed += lambda: setattr(self, "_kw2", None)
        self._kw2_gotowe.wait(25)
        out = {}
        for od in range(0, len(urls), 12):
            w = self._kw2
            if w is None:
                break
            w.evaluate_js(MALE_JS % json.dumps(urls[od:od + 12]))
            wynik = None
            for _ in range(160):
                time.sleep(0.25)
                wynik = w.evaluate_js("window.__male")
                if wynik:
                    break
            try:
                m = json.loads(wynik) if isinstance(wynik, str) else {}
            except ValueError:
                m = {}
            for u, v in m.items():
                if isinstance(v, dict) and all(isinstance(v.get(k), str) and v[k].startswith("data:image/jpeg;base64,") for k in ("d", "m")):
                    out[u] = v
        return out

    def tlo_start(self):
        """Administrator w Felgach: w tle uzupełnia zdjęcia nowych felg (i co tydzień tych bez zdjęcia), najwyżej TLO_NA_SESJE."""
        with self._tlo_lock:
            if self._tlo_stan["start"]:
                return
            self._tlo_stan["start"] = True
        threading.Thread(target=self._tlo, daemon=True).start()

    def _tlo(self):
        from oferty import silnik, zdjecia
        st = self._tlo_stan
        try:
            time.sleep(20)   # najpierw niech Panel się wczyta i pokaże pierwsze felgi
            kat = silnik.KONTO.get("katalog")
            felgi = kat.felgi() if kat else None
            if not felgi:
                return
            lista = zdjecia.do_pobrania([f["id"] for f in felgi], _foto_wszystkie())
            st.update(trwa=True, wszystkie=len(lista), zrobione=0, zostalo=max(0, len(lista) - TLO_NA_SESJE), blad="")
            lista = lista[:TLO_NA_SESJE]   # xPartner blokuje automaty – po trochu, kolejne przy następnym wejściu
            zle = 0
            for od in range(0, len(lista), 10):
                with self._xp_lock:
                    d = self._zdjecia_do_bazy(lista[od:od + 10], pokaz=False)
                if d.get("login"):
                    st["login"] = True
                    break
                st["zrobione"] = min(len(lista), od + 10)
                st["zapisane"] += sum(1 for v in d["zdjecia"].values() if v)
                zle = zle + 1 if (not d["zdjecia"] and d.get("bledy")) or d.get("login_karta") else 0
                if zle >= 3:
                    st["blad"] = ("zaloguj się na stronie xPartner (okienko przy Felgach) – część zdjęć jest tylko po zalogowaniu"
                                  if d.get("login_karta") else "xPartner nie oddaje zdjęć (3 partie z rzędu) – spróbuję przy następnym wejściu")
                    break
                time.sleep(3)
        except Exception as e:
            st["blad"] = str(e)[:200]
            gui_log("zdjęcia felg w tle: %s" % e)
        finally:
            st["trwa"] = False

    def _zdjecia_xp(self, ids, pokaz=True):
        """{id: [adresy zdjęć]} z xPartner. Pierwszy raz otwiera ukryte okno konfiguratora xPartner; gdy xPartner
        prosi o zalogowanie – pokazuje to okno (pokaz=True; użytkownik loguje się sam, ciasteczko zostaje w profilu programu)."""
        import webview
        ids = [int(x) for x in ids if str(x).isdigit()][:80]
        if not ids:
            return {"zdjecia": {}}
        with self._kw_lock:
            if self._kw is None:
                self._kw_gotowe.clear()
                self._kw = webview.create_window("xPartner – zdjęcia felg (zaloguj się, potem zamknij lub zostaw)", url=KONFIGURATOR,
                                                 hidden=True, width=1000, height=760)
                self._kw.events.loaded += lambda: self._kw_gotowe.set()
                self._kw.events.closed += lambda: setattr(self, "_kw", None)
        for _ in range(3):   # strona konfiguratora po zalogowaniu przechodzi przez /callback – poczekaj na stronę główną
            self._kw_gotowe.wait(25)
            time.sleep(1.5)
            w = self._kw
            if w is None:
                return {"login": True}
            w.evaluate_js(ZDJ_JS % json.dumps(ids))
            wynik = None
            for _ in range(120):   # do ~30 s
                time.sleep(0.25)
                wynik = w.evaluate_js("window.__zdj")
                if wynik:
                    break
            try:
                d = json.loads(wynik) if isinstance(wynik, str) else (wynik or {})
            except ValueError:
                d = {}
            if d.get("zdjecia") is not None:
                brak = [i for i in ids if not d["zdjecia"].get(str(i))]
                if brak:   # konfigurator nie ma zdjęć części felg – są na karcie produktu w xPartner
                    try:
                        self._karta_puste = []
                        d["zdjecia"].update(self._zdjecia_karta(brak, pokaz))
                        d["puste_karta"] = list(self._karta_puste)
                        d["diag_karta"] = getattr(self, "_karta_diag", "")
                        if getattr(self, "_karta_login", False):
                            d["login_karta"] = True
                    except Exception as e:
                        d["blad_karta"] = str(e)[:200]
                return d
            self._kw_gotowe.clear()
        if pokaz:
            try:
                self._kw.show()
            except Exception:
                pass
        return {"login": True}

    def _wbuduj_zdjecia(self, html):
        """Adresy zdjęć xPartner w HTML -> obrazki wbudowane (data:), pobrane przez ukryte okno na xpartner.net.pl."""
        import webview
        urls = sorted(set(re.findall(r"https://xpartner\.net\.pl/descriptionFiles/images/\d+/[0-9A-Za-z]+\.(?:jpe?g|png|webp)", html, re.I)))[:6]
        if not urls:
            return html
        with self._kw_lock:
            if self._kw2 is None:
                self._kw2_gotowe.clear()
                self._kw2 = webview.create_window("xPartner – zdjęcia felg (karta produktu)", url=XPARTNER_LISTA, hidden=True, width=1000, height=760)
                self._kw2.events.loaded += lambda: self._kw2_gotowe.set()
                self._kw2.events.closed += lambda: setattr(self, "_kw2", None)
        self._kw2_gotowe.wait(25)
        w = self._kw2
        if w is None:
            return html
        w.evaluate_js(OBRAZY_JS % json.dumps(urls))
        wynik = None
        for _ in range(120):
            time.sleep(0.25)
            wynik = w.evaluate_js("window.__img")
            if wynik:
                break
        try:
            mapa = json.loads(wynik) if isinstance(wynik, str) else {}
        except ValueError:
            mapa = {}
        for u, d in mapa.items():
            if isinstance(d, str) and d.startswith("data:image/"):
                html = html.replace(u, d)
        return html

    def _zdjecia_karta(self, ids, pokaz=True):
        """Zdjęcia z karty produktu xPartner (ta sama sesja co konfigurator) – drugie ukryte okno na xpartner.net.pl."""
        import webview
        with self._kw_lock:
            if self._kw2 is None:
                self._kw2_gotowe.clear()
                self._kw2 = webview.create_window("xPartner – zdjęcia felg (karta produktu)", url=XPARTNER_LISTA, hidden=True, width=1000, height=760)
                self._kw2.events.loaded += lambda: self._kw2_gotowe.set()
                self._kw2.events.closed += lambda: setattr(self, "_kw2", None)
        ok = self._kw2_gotowe.wait(25)
        time.sleep(1)
        w = self._kw2
        self._karta_diag = "okno wczytane" if ok else "okno się nie wczytało (25 s)"
        if w is None:
            self._karta_diag = "brak okna"
            return {}
        w.evaluate_js(KARTA_JS % json.dumps(ids[:40]))
        wynik = None
        for _ in range(160):   # do ~40 s
            time.sleep(0.25)
            wynik = w.evaluate_js("window.__zdj2")
            if wynik:
                break
        try:
            d = json.loads(wynik) if isinstance(wynik, str) else {}
        except ValueError:
            d = {}
        try:
            adres = w.get_current_url()
        except Exception:
            adres = "?"
        self._karta_diag += "; adres: %s; wynik: %s; zdjęć: %d" % (str(adres)[:60], "brak" if not wynik else "jest",
                                                                   sum(len(v or []) for v in (d.get("zdjecia") or {}).values()))
        if d.get("login"):   # w xPartner (strona) trzeba się zalogować – pokaż okno, użytkownik loguje się sam
            self._karta_login = True
            if pokaz:
                try:
                    w.show()
                except Exception:
                    pass
            return {}
        self._karta_login = False
        self._karta_puste = [k for k, v in (d.get("zdjecia") or {}).items() if isinstance(v, list) and not v]
        return {k: v for k, v in (d.get("zdjecia") or {}).items() if v}

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
        if path in ("/api/pdf", "/api/felgi_pdf"):
            code, res = silnik.handle(path, dict(body or {}, logo=logo_uri()), open_path=_open_path)
            if code != 200:
                return {"code": code, "body": res}
            html = res["html"]
            if path == "/api/felgi_pdf":
                try:   # zdjęcia xPartner wbudowane w PDF (Edge bez okna dostaje od xPartner odmowę – serwer blokuje automaty)
                    html = self._wbuduj_zdjecia(html)
                except Exception:
                    pass
            try:
                plik = zrob_pdf(html, (body or {}).get("nazwa") or "oferta")
            except Exception as e:
                return {"code": 500, "body": {"error": f"Nie udało się zapisać PDF: {e}"}}
            if not (body or {}).get("bez_otwierania"):
                _open_path(plik)
            return {"code": 200, "body": {"plik": plik, "pdf": plik.endswith(".pdf"), "oddzial": res.get("oddzial")}}
        if path == "/api/felgi_zdjecia" and not silnik.modul("felgi"):
            return {"code": 403, "body": {"error": "Brak dostępu do felg – poproś administratora (UŻYTKOWNICY → Oferty – felgi)."}}
        if path in ("/api/felgi", "/api/felgi_zdjecia") and silnik.KONTO.get("admin") and silnik.modul("felgi"):
            self.tlo_start()   # zdjęcia nowych felg do bazy – w tle, u administratora w Felgach
        if path == "/api/felgi_zdjecia_pelne" and not silnik.modul("felgi"):
            return {"code": 403, "body": {"error": "Brak dostępu do felg."}}
        if path == "/api/felgi_zdjecia_pelne":   # zdjęcia do PDF – tylko wybrane felgi (oszczędność ruchu bazy)
            try:
                p = self.foto().pelne([int(x) for x in (body or {}).get("ids") or [] if str(x).isdigit()])
                return {"code": 200, "body": {"zdjecia": {str(k): v for k, v in p.items()}}}
            except Exception as e:
                return {"code": 502, "body": {"error": f"Nie udało się pobrać zdjęć felg: {e}"}}
        if path == "/api/felgi_zdjecia":   # zdjęcia felg z bazy; administrator dopisuje brakujące z xPartner (2026-11-27)
            try:
                return {"code": 200, "body": self._zdjecia((body or {}).get("ids") or [])}
            except Exception as e:
                return {"code": 502, "body": {"error": f"Nie udało się pobrać zdjęć felg: {e}"}}
        if path == "/api/felgi_foto_stan":
            if not silnik.KONTO.get("admin"):
                return {"code": 403, "body": {"error": "Tylko administrator."}}
            st = dict(self._tlo_stan)
            try:
                w = _foto_wszystkie()
                st.update(w_bazie=sum(1 for x in w if int(x.get("pliki") or 0)), sprawdzone=len(w), na_sesje=TLO_NA_SESJE)
            except Exception as e:
                st["blad_bazy"] = str(e)[:200]
            return {"code": 200, "body": st}
        if path == "/api/whatsapp":   # PDF do schowka + otwarcie WhatsApp (decyzja właściciela 2026-11-18)
            try:
                return {"code": 200, "body": whatsapp_pdf((body or {}).get("plik") or "")}
            except Exception as e:
                return {"code": 400, "body": {"error": str(e)}}
        code, res = silnik.handle(path, body, open_path=_open_path)
        return {"code": code, "body": res}


def whatsapp_pdf(plik):
    """Kopiuje PDF oferty do schowka Windows (jak „Kopiuj” w Eksploratorze) i otwiera aplikację WhatsApp.
    Pracownik wybiera klienta w WhatsApp i wkleja Ctrl+V. Tylko pliki PDF z folderu ofert."""
    import subprocess
    from oferty import silnik
    p = os.path.realpath(plik)
    folder = os.path.realpath(silnik.OUT_DIR)
    if not (p.lower().endswith(".pdf") and os.path.isfile(p) and os.path.dirname(p) == folder):
        raise ValueError("Najpierw utwórz PDF oferty (plik z folderu ofert).")
    if os.name != "nt":   # pragma: no cover – Linux (testy)
        return {"schowek": False, "whatsapp": False, "plik": p}
    lit = p.replace("'", "''")
    # jedno wywołanie PowerShell: PDF do schowka + gdzie jest WhatsApp (link „whatsapp:”, aplikacja ze Sklepu, stara wersja .exe)
    skrypt = ("$ErrorActionPreference='SilentlyContinue'; Set-Clipboard -LiteralPath '%s'; if($?){'SCHOWEK'};"
              "if(Test-Path 'Registry::HKEY_CLASSES_ROOT\\whatsapp'){'LINK'};"
              "$a=Get-AppxPackage -Name '*WhatsApp*' | Select-Object -First 1; if($a){'APPX:'+$a.PackageFamilyName};"
              "$e=Join-Path $env:LOCALAPPDATA 'WhatsApp\\WhatsApp.exe'; if(Test-Path $e){'EXE:'+$e};"
              # skrót w menu Start (np. WhatsApp zainstalowany jako aplikacja z Edge/Chrome)
              "$l=Get-ChildItem (Join-Path $env:APPDATA 'Microsoft\\Windows\\Start Menu\\Programs'),"
              "(Join-Path $env:ProgramData 'Microsoft\\Windows\\Start Menu\\Programs') -Recurse -Filter 'WhatsApp*.lnk' | "
              "Select-Object -First 1; if($l){'LNK:'+$l.FullName}") % lit
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", skrypt],
                       timeout=30, capture_output=True, text=True, creationflags=0x08000000)
    wyj = [x.strip() for x in (r.stdout or "").splitlines() if x.strip()]
    schowek = "SCHOWEK" in wyj
    appx = next((x[5:] for x in wyj if x.startswith("APPX:")), "")
    exe = next((x[4:] for x in wyj if x.startswith("EXE:")), "")
    lnk = next((x[4:] for x in wyj if x.startswith("LNK:")), "")
    wa = "web"
    try:
        if "LINK" in wyj:
            os.startfile("whatsapp:")
            wa = "aplikacja"
        elif appx:   # aplikacja ze Sklepu Microsoft bez linku „whatsapp:”
            subprocess.Popen(["explorer.exe", "shell:AppsFolder\\%s!App" % appx], creationflags=0x08000000)
            wa = "aplikacja"
        elif exe:
            subprocess.Popen([exe], creationflags=0x08000000)
            wa = "aplikacja"
        elif lnk:
            os.startfile(lnk)
            wa = "aplikacja"
    except OSError:
        wa = "web"
    if wa == "web":   # brak aplikacji – WhatsApp Web w przeglądarce
        import webbrowser
        webbrowser.open("https://web.whatsapp.com/")
    return {"schowek": schowek, "whatsapp": wa, "plik": p}


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
