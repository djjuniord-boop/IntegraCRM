"""Anonimowe statystyki użycia (tylko liczby).

Wysyłane: losowy identyfikator instalacji (nie da się z niego ustalić osoby), wersja programu,
rodzaj zdarzenia i liczby (ile numerów, ile braków, czas sprawdzenia, rodzaj błędu).
NIE są wysyłane: numery rejestracyjne, adresy e-mail, hasła, nazwy plików, treści e-maili, obrazy.
Bez internetu zdarzenia czekają w kolejce (data/statystyki_kolejka.jsonl) i wysyłają się później.
"""
import json
import threading
import uuid
from datetime import datetime, timezone

import paths
from version import VERSION

try:
    from version import STATS_URL
except ImportError:
    STATS_URL = ""

ID_FILE = paths.DATA_DIR / "statystyki_id.txt"
QUEUE = paths.DATA_DIR / "statystyki_kolejka.jsonl"
MAX_QUEUE = 500
ALLOWED = {"n_integra", "n_crm", "n_missing", "n_uncertain", "n_autofix", "n_warnings", "seconds",
           "n_recipients", "error", "where", "detail"}
_lock = threading.Lock()
_sending = threading.Lock()


def install_id() -> str:
    try:
        v = ID_FILE.read_text(encoding="utf-8").strip()
        if v:
            return v
    except OSError:
        pass
    v = uuid.uuid4().hex[:12]
    try:
        paths.DATA_DIR.mkdir(parents=True, exist_ok=True)
        ID_FILE.write_text(v, encoding="utf-8")
    except OSError:
        pass
    return v


def enabled(cfg: dict) -> bool:
    return bool(cfg.get("stats_enabled", True))


SESSION = None   # po zalogowaniu: błędy trafiają do dziennika zmian w bazie, arkusz Google nie jest używany


def event(name: str, cfg: dict, **values) -> None:
    """Dodaje zdarzenie do kolejki i próbuje wysłać w tle. Nigdy nie zgłasza błędu."""
    if SESSION is not None:
        if name == "error":
            def _send(s=SESSION):
                try:
                    s.rpc("log_event", p_action="błąd", p_entity=str(values.get("where", ""))[:60],
                          p_label=str(values.get("error", ""))[:60],
                          p_detail={"wersja": VERSION, "miejsce": str(values.get("detail", ""))[:300]})
                except Exception:
                    pass
            threading.Thread(target=_send, daemon=True).start()
        return
    if not enabled(cfg):
        return
    try:
        rec = {"ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "id": install_id(),
               "v": VERSION, "event": name}
        for k, val in values.items():
            if k not in ALLOWED:
                continue
            if k in ("error", "where", "detail"):
                if isinstance(val, str):
                    rec[k] = val[:300 if k == "detail" else 60]
            elif isinstance(val, (int, float)) and not isinstance(val, bool):
                rec[k] = val
        with _lock:
            paths.DATA_DIR.mkdir(parents=True, exist_ok=True)
            with open(QUEUE, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        threading.Thread(target=flush, daemon=True).start()
    except Exception:
        pass


def flush() -> int:
    """Wysyła kolejkę. Zwraca liczbę wysłanych zdarzeń."""
    if not STATS_URL:
        return 0
    import urllib.request
    if not _sending.acquire(blocking=False):   # wysyłka już trwa w innym wątku
        return 0
    try:
        with _lock:   # pod blokadą tylko szybkie operacje na pliku – nigdy sieć
            try:
                lines = [ln for ln in QUEUE.read_text(encoding="utf-8").splitlines() if ln.strip()]
            except OSError:
                return 0
            if not lines:
                return 0
            lines = lines[-MAX_QUEUE:]
            try:
                QUEUE.write_text("", encoding="utf-8")
            except OSError:
                return 0
        batch = []
        for ln in lines:
            try:
                batch.append(json.loads(ln))
            except ValueError:
                pass
        try:
            req = urllib.request.Request(STATS_URL, data=json.dumps({"events": batch}).encode("utf-8"),
                                         headers={"Content-Type": "text/plain; charset=utf-8",
                                                  "User-Agent": f"IntegraCRM/{VERSION}"})
            with urllib.request.urlopen(req, timeout=15) as r:
                r.read()
        except Exception:
            with _lock:   # nie wysłano – zdarzenia wracają do kolejki (przed nowszymi)
                try:
                    newer = QUEUE.read_text(encoding="utf-8") if QUEUE.exists() else ""
                    keep = (lines + [x for x in newer.splitlines() if x.strip()])[-MAX_QUEUE:]
                    QUEUE.write_text("\n".join(keep) + "\n", encoding="utf-8")
                except OSError:
                    pass
            return 0
        return len(batch)
    finally:
        _sending.release()


def _trace(exc) -> str:
    """Ślad błędu bez treści komunikatu: tylko pliki programu, numery linii i nazwy funkcji.
    (Treść komunikatu może zawierać numery rejestracyjne, ścieżki czy adresy – nie jest wysyłana.)"""
    import os
    import traceback
    parts = []
    for fr in traceback.extract_tb(exc.__traceback__):
        name = os.path.basename(fr.filename)
        if name.endswith(".py"):
            parts.append(f"{name}:{fr.lineno} {fr.name}")
    return " > ".join(parts[-6:])


def report_exception(exc, where: str, cfg: dict, wait: bool = False) -> None:
    """Zgłasza błąd: rodzaj (np. SMTPAuthenticationError), miejsce (np. „wysyłka e-maila”) i ślad w kodzie."""
    try:
        event("error", cfg, error=type(exc).__name__, where=where, detail=_trace(exc))
        if wait:
            flush()
    except Exception:
        pass
