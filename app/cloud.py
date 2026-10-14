"""Połączenie z bazą Supabase: logowanie, profil użytkownika (rola, moduły, oddziały), funkcje admina.

Tylko biblioteka standardowa (urllib) – działa na każdej paczce .exe.
Klucz poniżej to publiczny klucz „anon”: bez zalogowania nie daje dostępu do żadnych danych (RLS).
"""
import json
import urllib.error
import urllib.request

import paths

URL = "https://nlrwulrtaocuemfmlfav.supabase.co"
ANON_KEY = ("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5scnd1bHJ0YW9jdWVtZm1sZmF2Iiwi"
            "cm9sZSI6ImFub24iLCJpYXQiOjE3OTE4ODY2NTYsImV4cCI6MjEwNzQ2MjY1Nn0.F6Qd7vvYuDZs4Opt_4dnOPmPpsKB8rzAZ5iF47h6gtk")
TIMEOUT = 20
SESSION_FILE = paths.DATA_DIR / "sesja.json"

MODULES = [("crm", "Kontrola CRM"), ("historia", "Historia"), ("statystyki", "Statystyki"), ("marza", "MARŻA"),
           ("wyniki", "Wyniki"), ("serwis", "SERWIS QR")]
BRANCHES = ["Latex Wrocław", "Latex Opole", "Stangum Opole"]


import threading as _th
_refresh_lock = _th.Lock()


class CloudError(Exception):
    pass


def _http(method, path, body=None, token=None, prefer="return=representation"):
    req = urllib.request.Request(URL + path, method=method,
                                 data=json.dumps(body).encode("utf-8") if body is not None else None,
                                 headers={"apikey": ANON_KEY, "Content-Type": "application/json", "Prefer": prefer,
                                          "Authorization": f"Bearer {token or ANON_KEY}"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            raw = r.read()
    except urllib.error.HTTPError as e:
        try:
            d = json.loads(e.read().decode("utf-8"))
            msg = d.get("error_description") or d.get("msg") or d.get("message") or d.get("error") or str(d)
        except Exception:
            msg = f"HTTP {e.code}"
        if "Invalid login credentials" in str(msg):
            msg = "Nieprawidłowy e-mail lub hasło."
        raise CloudError(msg) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise CloudError("Brak połączenia z serwerem. Program wymaga internetu – sprawdź połączenie.") from None
    return json.loads(raw.decode("utf-8")) if raw.strip() else None


class Session:
    def __init__(self, data: dict):
        self.access = data["access_token"]
        self.refresh_token = data["refresh_token"]
        self.email = (data.get("user") or {}).get("email", "")
        self.profile: dict = {}

    # --- logowanie ---
    @classmethod
    def login(cls, email: str, password: str) -> "Session":
        return cls(_http("POST", "/auth/v1/token?grant_type=password",
                         {"email": email.strip(), "password": password}))

    @classmethod
    def from_refresh(cls, refresh_token: str) -> "Session":
        return cls(_http("POST", "/auth/v1/token?grant_type=refresh_token", {"refresh_token": refresh_token}))

    def refresh(self):
        with _refresh_lock:   # jeden wątek naraz – token odświeżania jest jednorazowy
            s = Session.from_refresh(self.refresh_token)
            self.access, self.refresh_token = s.access, s.refresh_token

    def logout(self):
        try:
            _http("POST", "/auth/v1/logout", {}, self.access)
        except CloudError:
            pass
        forget()

    # --- zapytania (z odświeżeniem tokenu po wygaśnięciu) ---
    def call(self, method, path, body=None, prefer="return=representation"):
        try:
            return _http(method, path, body, self.access, prefer)
        except CloudError as e:
            if "JWT" not in str(e) and "expired" not in str(e).lower():
                raise
        self.refresh()
        remember(self) if SESSION_FILE.exists() else None
        return _http(method, path, body, self.access, prefer)

    def rpc(self, fn, **args):
        return self.call("POST", f"/rest/v1/rpc/{fn}", args)

    def load_profile(self, version: str) -> dict:
        """Profil z bazy (i zapis ostatniego logowania). Brak konta / zablokowane → CloudError."""
        p = self.rpc("app_login", p_version=version)
        if not p or not p.get("email"):
            raise CloudError("To konto nie ma dostępu do programu albo zostało zablokowane. "
                             "Skontaktuj się z administratorem.")
        p["modules"] = p.get("modules") or []
        p["branches"] = p.get("branches") or []
        self.profile = p
        return p

    @property
    def is_admin(self) -> bool:
        return self.profile.get("role") == "admin"

    def can(self, module: str) -> bool:
        return self.is_admin or module in self.profile.get("modules", [])

    def branches(self) -> list:
        return list(BRANCHES) if self.is_admin else list(self.profile.get("branches", []))

    def min_version(self) -> str:
        rows = self.call("GET", "/rest/v1/app_config?key=eq.min_version&select=value") or []
        return str(rows[0]["value"]) if rows else ""

    def company(self) -> dict:
        """Ustawienia firmowe modułu Kontrola CRM (odbiorcy maili, nadawca) – ustawia administrator."""
        rows = self.call("GET", "/rest/v1/app_config?key=eq.crm&select=value") or []
        return rows[0]["value"] if rows and isinstance(rows[0].get("value"), dict) else {}

    def audit(self, limit: int = 1000, query: str = "") -> list:
        """Dziennik zmian (tylko administrator). query – fragment e-maila, numeru albo nazwy pliku."""
        flt = ""
        if query.strip():
            from urllib.parse import quote
            q = quote("*" + query.strip().replace(",", " ").replace("*", "") + "*")
            flt = f"&or=(email.ilike.{q},label.ilike.{q},entity.ilike.{q},action.ilike.{q})"
        return self.call("GET", f"/rest/v1/audit_log?select=*&order=id.desc&limit={int(limit)}{flt}") or []

    def set_company(self, value: dict):
        self.call("POST", "/rest/v1/app_config?on_conflict=key", {"key": "crm", "value": value},
                  prefer="resolution=merge-duplicates,return=minimal")

    # --- schowek plików (Supabase Storage) ---
    def upload(self, bucket: str, path: str, data: bytes, ctype: str = "application/octet-stream"):
        from urllib.parse import quote
        url = f"{URL}/storage/v1/object/{bucket}/{quote(path)}"
        for attempt in (1, 2):
            req = urllib.request.Request(url, data=data, method="POST", headers={
                "apikey": ANON_KEY, "Authorization": f"Bearer {self.access}", "Content-Type": ctype,
                "x-upsert": "false"})
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    return json.loads(r.read() or b"{}")
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", "replace")
                if attempt == 1 and ("jwt" in body.lower() or "expired" in body.lower()):
                    self.refresh()
                    continue
                raise CloudError(f"Nie zapisano pliku w chmurze: {body[:200]}") from None
            except (urllib.error.URLError, TimeoutError, OSError):
                raise CloudError("Brak połączenia z serwerem – plik nie trafił do chmury.") from None

    def list_files(self, bucket: str, prefix: str) -> list:
        return self.call("POST", f"/storage/v1/object/list/{bucket}",
                         {"prefix": prefix, "limit": 1000, "sortBy": {"column": "name", "order": "desc"}}) or []

    def download(self, bucket: str, path: str) -> bytes:
        from urllib.parse import quote
        req = urllib.request.Request(f"{URL}/storage/v1/object/authenticated/{bucket}/{quote(path)}",
                                     headers={"apikey": ANON_KEY, "Authorization": f"Bearer {self.access}"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            raise CloudError(f"Nie udało się pobrać pliku: HTTP {e.code}") from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise CloudError("Brak połączenia z serwerem.") from None

    # --- administrator ---
    def list_users(self) -> list:
        return self.call("GET", "/rest/v1/app_users?select=*&order=email") or []

    def set_user(self, email, name, role, modules, branches, active):
        self.rpc("admin_set_user", p_email=email, p_name=name, p_role=role,
                 p_modules=modules, p_branches=branches, p_active=active)

    def admin_fn(self, **body):
        r = self.call("POST", "/functions/v1/admin-users", body)
        if isinstance(r, dict) and r.get("error"):
            raise CloudError(r["error"])
        return r


# --- „Zapamiętaj mnie”: token odświeżania zaszyfrowany DPAPI (tylko to konto Windows) ---
def remember(s: Session):
    import vault
    try:
        paths.DATA_DIR.mkdir(parents=True, exist_ok=True)
        SESSION_FILE.write_text(json.dumps({"email": s.email, "t": vault.protect(s.refresh_token)}),
                                encoding="utf-8")
    except OSError:
        pass


def remembered():
    """(email, refresh_token) zapamiętanej sesji albo (email, None)."""
    import vault
    try:
        d = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
        return d.get("email", ""), vault.unprotect(d.get("t", "")) or None
    except (OSError, ValueError):
        return "", None


def forget():
    try:
        SESSION_FILE.unlink()
    except OSError:
        pass
