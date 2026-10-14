"""Ustawienia programu: lokalne (data/config.json) i firmowe z bazy (COMPANY – odbiorcy maili,
nadawca, lista MARŻY). Po zalogowaniu firmowe mają pierwszeństwo przed lokalnymi."""
import json
import os
import paths
from version import DEFAULT_UPDATE_SOURCE
from kontrola import crm_report
try:
    import vault
except Exception:   # pragma: no cover
    class vault:   # noqa: N801 – zastępstwo bez szyfrowania
        PREFIX = "dpapi:"
        protect = staticmethod(lambda x: x)
        unprotect = staticmethod(lambda x: "" if (x or "").startswith("dpapi:") else (x or ""))


DEFAULTS = {
    "gmail_user": "",
    "gmail_app_password": "",
    "recipients": [],
    "tesseract_cmd": "",       # puste = automatycznie (folder programu / Program Files)
    "update_source": "",       # puste = DEFAULT_UPDATE_SOURCE z version.py
    "cc_self": True,           # kopia (DW) wysyłanego maila do nadawcy
    "sender_name": "",         # nazwa nadawcy widoczna u odbiorcy (puste = domyślna)
    "stats_enabled": True,     # anonimowe statystyki użycia (tylko liczby)
    "marza_enabled": False,    # zakładka MARŻA (kalkulator marży Wrocław + Opole) – tylko dla właściciela
    "marza_folder": "",        # folder „LATEX Wyniki”
    "serwis_enabled": False,   # zakładka SERWIS QR (beta) – tylko dla właściciela
    "serwis_sb_url": "",       # adres bazy Supabase (puste = tryb lokalny)
    "serwis_sb_key": "",       # klucz publiczny (anon) Supabase
    "serwis_base": "",         # adres strony dla klientów (kod QR)
    "crm_branches": list(crm_report.BRANCHES),   # oddziały liczone z raportu CRM (.xlsx)
}


COMPANY: dict = {}   # ustawienia firmowe z bazy (odbiorcy, nadawca) – wczytywane po zalogowaniu


def recipients_for(branches, cfg=None) -> list:
    """Odbiorcy maila z brakami: wg oddziałów (ustawienia firmowe), inaczej domyślni."""
    by = COMPANY.get("by_branch") or {}
    out = []
    for b in branches or []:
        for r in by.get(b) or []:
            if r.lower() not in {x.lower() for x in out}:
                out.append(r)
    return out or list((cfg or load_config())["recipients"])


def load_config() -> dict:
    cfg = dict(DEFAULTS)
    if paths.CONFIG_PATH.exists():
        try:
            cfg.update(json.loads(paths.CONFIG_PATH.read_text(encoding="utf-8")))
        except (ValueError, OSError):   # uszkodzony plik – zachowaj kopię i pracuj na domyślnych
            try:
                paths.CONFIG_PATH.replace(paths.CONFIG_PATH.with_suffix(".bad.json"))
            except OSError:
                pass
    cfg["gmail_app_password"] = vault.unprotect(cfg.get("gmail_app_password", ""))
    if COMPANY:   # po zalogowaniu firmowe ustawienia mają pierwszeństwo przed lokalnymi
        if COMPANY.get("recipients"):
            cfg["recipients"] = list(COMPANY["recipients"])
        if COMPANY.get("sender_name"):
            cfg["sender_name"] = COMPANY["sender_name"]
    return cfg


def migrate_config() -> None:
    """Usuwa stare źródło aktualizacji (Dysk Google) i szyfruje hasło zapisane jawnym tekstem."""
    try:
        raw = json.loads(paths.CONFIG_PATH.read_text(encoding="utf-8")) if paths.CONFIG_PATH.exists() else {}
        cfg = load_config()
        changed = False
        if "drive.google.com" in (cfg.get("update_source") or ""):
            cfg["update_source"] = ""
            changed = True
        pw = raw.get("gmail_app_password") or ""
        if pw and not pw.startswith(vault.PREFIX) and vault.protect(pw) != pw:
            changed = True
        if changed:
            save_config(cfg)
    except Exception:
        pass


def save_config(cfg: dict) -> None:
    paths.DATA_DIR.mkdir(parents=True, exist_ok=True)
    out = dict(cfg)
    out["gmail_app_password"] = vault.protect(out.get("gmail_app_password", ""))
    tmp = paths.CONFIG_PATH.with_suffix(".json.tmp")   # zapis atomowy – przerwanie nie psuje ustawień
    tmp.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, paths.CONFIG_PATH)


def update_source(cfg: dict) -> str:
    src = (cfg.get("update_source") or "").strip()
    if "drive.google.com" in src:   # stare źródło (Dysk Google) – od 0.8.3 aktualizacje są na GitHubie
        src = ""
    return src or DEFAULT_UPDATE_SOURCE
