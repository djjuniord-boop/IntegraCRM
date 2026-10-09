"""Historia sprawdzeń (data/historia.csv) i rejestr zgłoszonych już numerów (data/zgloszone.json)."""
import csv
import json
from datetime import datetime

import paths

HISTORY = paths.DATA_DIR / "historia.csv"
REPORTED = paths.DATA_DIR / "zgloszone.json"
FIELDS = ["data", "plik_pdf", "integra", "crm", "brakuje", "do_weryfikacji", "mail_wyslany_do"]


def add_check(pdf_name: str, n_integra: int, n_crm: int, missing, uncertain) -> int:
    """Dopisuje sprawdzenie, zwraca numer wiersza (do późniejszego oznaczenia wysyłki)."""
    paths.DATA_DIR.mkdir(parents=True, exist_ok=True)
    rows = read_all()
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


def mark_sent(index: int, recipients, plates_sent) -> None:
    rows = read_all()
    if 0 <= index < len(rows):
        rows[index]["mail_wyslany_do"] = ", ".join(recipients)
        _write(rows)
    reg = reported()
    today = datetime.now().strftime("%Y-%m-%d")
    for p in plates_sent:
        reg.setdefault(p, today)
    REPORTED.write_text(json.dumps(reg, indent=1, ensure_ascii=False), encoding="utf-8")


def reported() -> dict:
    """{numer: data pierwszego zgłoszenia}"""
    try:
        return json.loads(REPORTED.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def read_all() -> list[dict]:
    try:
        with open(HISTORY, newline="", encoding="utf-8-sig") as f:
            return list(csv.DictReader(f, delimiter=";"))
    except OSError:
        return []


def _write(rows) -> None:
    # utf-8-sig + średnik: plik otwiera się poprawnie w polskim Excelu
    with open(HISTORY, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, delimiter=";")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})
