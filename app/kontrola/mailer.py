"""Treść e-maila z listą brakujących numerów (wysyła go serwer firmy)."""
import re
import smtplib
import ssl
from datetime import datetime
from email.message import EmailMessage
from email.utils import formataddr

from version import VERSION

DEFAULT_SENDER = "Panel Latex Serwis"


def compose(missing: list[str], uncertain: list[tuple[str, str]], reported: dict | None = None) -> tuple[str, str]:
    """Zwraca (temat, treść) e-maila. reported = {numer: data} – numery zgłaszane już wcześniej."""
    reported = reported or {}
    today = datetime.now().strftime("%d.%m.%Y")
    lines = [
        "Dzień dobry,",
        "",
        "w CRM brakuje poniższych numerów rejestracyjnych zakończonych zleceń "
        "z Integry 7. Proszę o sprawdzenie i wyeksportowanie ich do CRM:",
        "",
    ]
    lines += [f"  • {p}" + (f"   (zgłoszony już {reported[p]})" if p in reported else "")
              for p in missing] or ["  (brak numerów, których na pewno brakuje – patrz niżej)"]
    if uncertain:
        lines += ["", "Do ręcznej weryfikacji (podobne numery w CRM – możliwy błąd odczytu):"]
        lines += [f"  • Integra: {a}  ↔  CRM: {b}" for a, b in uncertain]
    lines += ["", f"Data sprawdzenia: {today}",
              f"Wiadomość wygenerowana automatycznie (Panel Latex Serwis, wersja {VERSION})."]
    subject = (f"Brakujące zlecenia w CRM ({len(missing)}) – {today}" if missing
               else f"Numery do weryfikacji w CRM ({len(uncertain)}) – {today}")
    return subject, "\n".join(lines)


def send(subject: str, body: str, cfg: dict) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    name = (cfg.get("sender_name") or DEFAULT_SENDER).strip()
    msg["From"] = formataddr((name, cfg["gmail_user"])) if name else cfg["gmail_user"]
    msg["To"] = ", ".join(cfg["recipients"])
    if cfg.get("cc_self", True) and cfg["gmail_user"].lower() not in {r.lower() for r in cfg["recipients"]}:
        msg["Cc"] = cfg["gmail_user"]
    msg.set_content(body)
    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx, timeout=30) as s:
        s.login(cfg["gmail_user"], cfg["gmail_app_password"].replace(" ", ""))
        s.send_message(msg)


class NotConfigured(Exception):
    """Wysyłka z serwera nie jest skonfigurowana – można użyć Gmaila z tego komputera."""


def send_server(session, subject: str, body: str, recipients, cc_self: bool = True) -> str:
    """Wysyłka przez serwer (Gmail firmy w sekretach Supabase). Zwraca adres nadawcy."""
    import cloud
    try:
        r = session.call("POST", "/functions/v1/send-mail",
                         {"subject": subject, "body": body, "to": list(recipients), "cc_self": cc_self})
    except cloud.CloudError as e:
        if "nie jest skonfigurowana" in str(e):
            raise NotConfigured(str(e)) from None
        raise
    if isinstance(r, dict) and r.get("error"):
        raise RuntimeError(r["error"])
    return (r or {}).get("from", "")


_ADRES = re.compile(r"^[^@\s,;<>]+@[^@\s,;<>]+\.[a-z]{2,}$", re.I)


def parse_recipients(text: str):
    """„a@x.pl, b@y.pl; c@z.pl” → (poprawne adresy bez powtórzeń, błędne wpisy)."""
    ok, bad = [], []
    for part in re.split(r"[,;\s]+", text or ""):
        a = part.strip()
        if not a:
            continue
        if not _ADRES.match(a):
            bad.append(a)
        elif a.lower() not in {x.lower() for x in ok}:
            ok.append(a)
    return ok, bad
