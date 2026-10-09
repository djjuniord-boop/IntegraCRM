"""Treść i wysyłka maila z listą brakujących numerów (Gmail przez SMTP + hasło aplikacji)."""
import smtplib
import ssl
from datetime import datetime
from email.message import EmailMessage

from version import VERSION


def compose(missing: list[str], uncertain: list[tuple[str, str]], reported: dict | None = None) -> tuple[str, str]:
    """Zwraca (temat, treść) maila. reported = {numer: data} – numery zgłaszane już wcześniej."""
    reported = reported or {}
    today = datetime.now().strftime("%d.%m.%Y")
    lines = [
        "Dzień dobry,",
        "",
        "w CRM brakuje poniższych numerów rejestracyjnych zakończonych zleceń "
        "z Integra 7. Proszę o sprawdzenie i wyeksportowanie ich do CRM:",
        "",
    ]
    lines += [f"  • {p}" + (f"   (zgłaszany już {reported[p]})" if p in reported else "")
              for p in missing] or ["  (brak pewnych braków – patrz niżej)"]
    if uncertain:
        lines += ["", "Do ręcznej weryfikacji (podobne numery w CRM – możliwy błąd odczytu):"]
        lines += [f"  • Integra: {a}  ↔  CRM: {b}" for a, b in uncertain]
    lines += ["", f"Data sprawdzenia: {today}",
              f"Wiadomość wygenerowana automatycznie (program Integra–CRM v{VERSION})."]
    subject = f"Brakujące zlecenia w CRM ({len(missing)}) – {today}"
    return subject, "\n".join(lines)


def send(subject: str, body: str, cfg: dict) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = cfg["gmail_user"]
    msg["To"] = ", ".join(cfg["recipients"])
    if cfg.get("cc_self", True) and cfg["gmail_user"] not in cfg["recipients"]:
        msg["Cc"] = cfg["gmail_user"]
    msg.set_content(body)
    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx) as s:
        s.login(cfg["gmail_user"], cfg["gmail_app_password"].replace(" ", ""))
        s.send_message(msg)
