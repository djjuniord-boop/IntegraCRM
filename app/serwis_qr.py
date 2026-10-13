"""SERWIS QR (beta): panel historii serwisowej z naklejkami QR.

Sam panel to strona app/serwis/index.html otwierana w przeglądarce. Program zapisuje dla niej
ustawienia do data/serwis_config.js (adres bazy Supabase, klucz publiczny, adres strony dla QR).
Bez bazy panel działa lokalnie – dane zostają w przeglądarce na tym komputerze.
"""
import json
import os
import re
from pathlib import Path

import paths

PANEL = paths.APP_DIR / "serwis" / "index.html"
CONFIG_JS = paths.DATA_DIR / "serwis_config.js"


def check_base(base: str) -> str:
    """Zwraca opis problemu z adresem strony dla klientów albo pusty tekst, gdy jest w porządku."""
    b = (base or "").strip()
    if not b:
        return ""
    if not re.match(r"^https://[^\s/]+\.[^\s]+$", b):
        return "Adres strony musi zaczynać się od https:// (np. https://serwis.latex.net.pl/)."
    return ""


def check_supabase(url: str, key: str) -> str:
    u, k = (url or "").strip(), (key or "").strip()
    if not u and not k:
        return ""
    if not u or not k:
        return "Podaj oba pola: adres bazy i klucz publiczny – albo zostaw oba puste (tryb lokalny)."
    if not re.match(r"^https://[a-z0-9-]+\.supabase\.co/?$", u):
        return "Adres bazy wygląda nieprawidłowo – powinien mieć postać https://xxxx.supabase.co."
    if len(k) < 30 or " " in k:
        return "Klucz publiczny (anon) wygląda nieprawidłowo – skopiuj go w całości z Supabase."
    return ""


def mode(cfg: dict) -> str:
    return "cloud" if (cfg.get("serwis_sb_url") or "").strip() and (cfg.get("serwis_sb_key") or "").strip() else "local"


def write_config(cfg: dict) -> Path:
    """Zapisuje ustawienia dla panelu. Klucz anon Supabase jest publiczny z założenia (chroni baza)."""
    data = {
        "url": (cfg.get("serwis_sb_url") or "").strip().rstrip("/"),
        "key": (cfg.get("serwis_sb_key") or "").strip(),
        "base": (cfg.get("serwis_base") or "").strip(),
    }
    paths.DATA_DIR.mkdir(parents=True, exist_ok=True)
    text = "window.SERWIS_CFG = " + json.dumps(data, ensure_ascii=False) + ";\n"
    CONFIG_JS.write_text(text, encoding="utf-8")
    return CONFIG_JS


def open_panel(cfg: dict) -> None:
    if not PANEL.exists():
        raise FileNotFoundError(f"Brak pliku panelu: {PANEL}. Zaktualizuj program.")
    write_config(cfg)
    if hasattr(os, "startfile"):
        os.startfile(str(PANEL))          # Windows: domyślna przeglądarka
    else:                                  # pragma: no cover – testy na Linuksie
        import subprocess
        subprocess.Popen(["xdg-open", str(PANEL)])
