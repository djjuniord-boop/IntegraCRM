"""Historia sprawdzeń i rejestr zgłoszonych już numerów.

Po zalogowaniu (SESSION ustawione przez okno programu) – wspólne dla wszystkich komputerów, w bazie.
Bez sesji (testy) – pliki lokalne data/historia.csv i data/zgloszone.json.
"""
import csv
import json
import os
from datetime import datetime, timedelta

import paths

HISTORY = paths.DATA_DIR / "historia.csv"
REPORTED = paths.DATA_DIR / "zgloszone.json"
KEEP_DAYS = 60   # po tylu dniach numer nie jest już oznaczany „zgłoszony już”
FIELDS = ["data", "plik_pdf", "integra", "crm", "brakuje", "do_weryfikacji", "mail_wyslany_do"]


def _local_add_check(pdf_name: str, n_integra: int, n_crm: int, missing, uncertain) -> int:
    """Dopisuje sprawdzenie, zwraca numer wiersza (do późniejszego oznaczenia wysyłki)."""
    paths.DATA_DIR.mkdir(parents=True, exist_ok=True)
    rows = _local_read_all()
    rows.append({
        "data": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "plik_pdf": pdf_name,
        "integra": n_integra,
        "crm": n_crm,
        "brakuje": " ".join(missing),
        "do_weryfikacji": " ".join(f"{a}~{b}" for a, b in uncertain),
        "mail_wyslany_do": "",
    })
    _write(rows)
    return len(rows) - 1


def _local_mark_sent(index: int, recipients, plates_sent) -> None:
    rows = _local_read_all()
    if 0 <= index < len(rows):
        rows[index]["mail_wyslany_do"] = ", ".join(recipients)
        _write(rows)
    reg = _local_reported()
    today = datetime.now().strftime("%Y-%m-%d")
    for p in plates_sent:
        reg.setdefault(p, today)
    _atomic(REPORTED, json.dumps(reg, indent=1, ensure_ascii=False))


def _local_reported() -> dict:
    """{numer: data pierwszego zgłoszenia}"""
    try:
        reg = json.loads(REPORTED.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    limit = (datetime.now() - timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")
    return {p: d for p, d in reg.items() if str(d) >= limit}   # stare zgłoszenia wygasają


def _local_read_all() -> list[dict]:
    try:
        with open(HISTORY, newline="", encoding="utf-8-sig") as f:
            return list(csv.DictReader(f, delimiter=";"))
    except OSError:
        return []


def _atomic(path, text: str) -> None:
    """Zapis przez plik tymczasowy – przerwanie (np. zanik prądu) nie psuje pliku."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _write(rows) -> None:
    # utf-8-sig + średnik: plik otwiera się poprawnie w polskim Excelu
    tmp = HISTORY.with_suffix(".csv.tmp")
    with open(tmp, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, delimiter=";")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})
    os.replace(tmp, HISTORY)


# ---------- wspólna historia w bazie ----------
SESSION = None          # cloud.Session po zalogowaniu
_reported_cache: dict = {}


def add_check(pdf_name, n_integra, n_crm, missing, uncertain, branches=()):
    """Zapisuje sprawdzenie; zwraca identyfikator (do oznaczenia wysyłki e-maila)."""
    if SESSION is None:
        return _local_add_check(pdf_name, n_integra, n_crm, missing, uncertain)
    r = SESSION.call("POST", "/rest/v1/checks?select=id", {
        "pdf_name": pdf_name, "n_integra": n_integra, "n_crm": n_crm, "branches": list(branches),
        "missing": list(missing), "uncertain": [f"{a}~{b}" for a, b in uncertain]})
    return r[0]["id"] if isinstance(r, list) and r else -1


def mark_sent(index, recipients, plates_sent, branch=""):
    if SESSION is None:
        return _local_mark_sent(index, recipients, plates_sent)
    if index is not None and index >= 0:
        SESSION.call("PATCH", f"/rest/v1/checks?id=eq.{int(index)}",
                     {"mail_to": ", ".join(recipients), "mail_at": datetime.now().astimezone().isoformat()})
    if plates_sent:
        SESSION.rpc("report_plates", p_plates=list(plates_sent), p_branch=branch)
    reported(refresh=True)


def reported(refresh: bool = False) -> dict:
    """{numer: data pierwszego zgłoszenia} – zgłoszenia z ostatnich KEEP_DAYS dni (wszystkie oddziały).
    refresh=False zwraca ostatnio pobrany stan (bez sieci – bezpieczne w wątku okna)."""
    global _reported_cache
    if SESSION is None:
        return _local_reported()
    if refresh:
        since = (datetime.now() - timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")
        rows = SESSION.call("GET", f"/rest/v1/reported?select=plate,first_at&last_at=gte.{since}") or []
        _reported_cache = {r["plate"]: str(r["first_at"])[:10] for r in rows}
    return dict(_reported_cache)


def read_all(limit: int = 500) -> list[dict]:
    """Wiersze historii (najstarsze pierwsze), w układzie pól pliku CSV + „kto” i „oddzialy”."""
    if SESSION is None:
        return _local_read_all()
    rows = SESSION.call("GET", f"/rest/v1/checks?select=*&order=created_at.desc&limit={int(limit)}") or []
    out = []
    for r in reversed(rows):
        t = str(r.get("created_at", ""))
        try:
            t = datetime.fromisoformat(t.replace("Z", "+00:00")).astimezone().strftime("%Y-%m-%d %H:%M")
        except ValueError:
            t = t[:16]
        out.append({"data": t, "plik_pdf": r.get("pdf_name") or "", "integra": r.get("n_integra"),
                    "crm": r.get("n_crm"), "brakuje": " ".join(r.get("missing") or []),
                    "do_weryfikacji": " ".join(r.get("uncertain") or []),
                    "mail_wyslany_do": r.get("mail_to") or "", "kto": r.get("user_email") or "",
                    "oddzialy": ", ".join(r.get("branches") or [])})
    return out


def export_csv(path) -> None:
    """Zapis historii do pliku CSV (otwiera się w Excelu)."""
    rows = read_all(5000)
    fields = FIELDS + (["kto", "oddzialy"] if SESSION is not None else [])
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter=";")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


def migrate_local() -> int:
    """Jednorazowo: lokalny rejestr zgłoszeń i stara historia (historia.csv) trafiają do bazy.
    Zwraca liczbę przeniesionych pozycji."""
    if SESSION is None:
        return 0
    n = 0
    if REPORTED.exists():
        reg = _local_reported()
        if reg:
            SESSION.rpc("report_plates", p_plates=list(reg), p_branch="")
        REPORTED.replace(REPORTED.with_suffix(".przeniesione.json"))
        n += len(reg)
    if HISTORY.exists():
        rows = []
        for r in _local_read_all():
            try:
                at = datetime.strptime(r.get("data", ""), "%Y-%m-%d %H:%M").astimezone().isoformat()
            except ValueError:
                continue
            num = lambda v: int(v) if str(v or "").strip().isdigit() else None
            rows.append({"created_at": at, "pdf_name": r.get("plik_pdf") or "", "imported": True,
                         "n_integra": num(r.get("integra")), "n_crm": num(r.get("crm")),
                         "missing": (r.get("brakuje") or "").split(),
                         "uncertain": (r.get("do_weryfikacji") or "").split(),
                         "mail_to": r.get("mail_wyslany_do") or None})
        if rows:
            SESSION.call("POST", "/rest/v1/checks", rows, prefer="return=minimal")
            SESSION.rpc("log_event", p_action="import", p_entity="historia", p_label="historia.csv",
                        p_detail={"wierszy": len(rows)})
        HISTORY.replace(HISTORY.with_suffix(".przeniesione.csv"))
        n += len(rows)
    return n


def save_visit_stats(branch, daily, check_id=None):
    """Liczniki dzienne (wizyty / listy kontrolne / braki) do statystyk – jeden oddział.
    Bez sesji (testy) nic nie zapisuje i zwraca None; inaczej liczbę zapisanych dni.
    Wywoływać w wątku roboczym (sieć)."""
    if SESSION is None:
        return None
    cid = check_id if isinstance(check_id, int) and check_id >= 0 else None
    for d in daily:
        SESSION.rpc("save_visit_stats", p_branch=branch, p_day=d["day"], p_visits=int(d["visits"]),
                    p_lists=int(d["lists"]), p_missing=int(d["missing"]), p_check_id=cid)
    return len(daily)
