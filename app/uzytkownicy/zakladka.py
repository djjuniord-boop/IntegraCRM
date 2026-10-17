"""Zakładka UŻYTKOWNICY (tylko administrator)."""
import threading
import tkinter as tk
from tkinter import ttk
import cloud
from ui import BG, BLACK, FlatButton, MUTED, OK, RED
from uzytkownicy.okna import AuditWindow, UserDialog


class UzytkownicyMixin:
    """Zakładka UŻYTKOWNICY (tylko administrator).
    Część klasy okna programu (App) – metody korzystają z jej pól (self.*)."""

    # ---------- użytkownicy (administrator) ----------
    def _build_users(self, page):
        f = self.fonts
        bar = tk.Frame(page, bg=BG)
        bar.pack(fill="x", pady=(4, 8))
        tk.Label(bar, text="Użytkownicy programu", bg=BG, fg=BLACK, font=f.h1).pack(side="left")
        FlatButton(bar, "+ Dodaj użytkownika", lambda: UserDialog(self), "primary", f.btn).pack(side="right")
        FlatButton(bar, "Odśwież", lambda: self.refresh_users(), "ghost", f.body, 14, 8).pack(side="right", padx=8)
        FlatButton(bar, "Dziennik zmian", lambda: AuditWindow(self), "dark", f.body, 14, 8).pack(side="right")
        self.users_msg = tk.Label(page, text="", bg=BG, fg=MUTED, font=f.small, anchor="w")
        self.users_msg.pack(fill="x")
        cols = ("email", "name", "role", "modules", "branches", "active", "last", "act", "ver", "dev", "ip")
        heads = ("E-mail", "Imię i nazwisko", "Rola", "Moduły", "Oddziały", "Status", "Logowanie", "Aktywność", "Wersja", "Komputer", "IP")
        widths = (170, 115, 95, 135, 145, 95, 135, 135, 55, 135, 100)
        self.users_tv = ttk.Treeview(page, columns=cols, show="headings", height=18)
        for c, h, w in zip(cols, heads, widths):
            self.users_tv.heading(c, text=h)
            self.users_tv.column(c, width=w, anchor="w")
        self.users_tv.pack(fill="both", expand=True, pady=(6, 0))
        self.users_tv.bind("<Double-1>", lambda e: self._edit_user())
        tk.Label(page, text="Kliknij dwukrotnie wiersz z użytkownikiem, żeby zmienić uprawnienia, hasło albo zablokować konto. „Aktywność” to ostatni sygnał z otwartego programu (co 30 minut) albo ostatnie logowanie. "
                 "Administrator ma zawsze dostęp do wszystkich modułów i oddziałów.",
                 bg=BG, fg=MUTED, font=f.small, wraplength=1300, justify="left").pack(anchor="w", pady=(6, 0))
        self._users = []
        self.after(300, self.refresh_users)

    def refresh_users(self, info=""):
        self.users_msg.config(text="Wczytuję…", fg=MUTED)

        def work():
            try:
                users = self.session.list_users()
                self.after(0, self._show_users, users, info)
            except Exception as e:
                self.after(0, lambda err=str(e): self.users_msg.config(text=f"Błąd: {err}", fg=RED))
        threading.Thread(target=work, daemon=True).start()

    def _show_users(self, users, info):
        self._users = users
        names = dict(cloud.MODULES)
        self.users_tv.delete(*self.users_tv.get_children())
        for i, u in enumerate(users):
            adm = u.get("role") == "admin"
            last = _czas(u.get("last_seen"))
            self.users_tv.insert("", "end", iid=str(i), values=(
                u["email"], u.get("name") or "", "administrator" if adm else "użytkownik",
                "wszystkie" if adm else ", ".join(names.get(m, m) for m in u.get("modules") or []),
                "wszystkie" if adm else ", ".join(u.get("branches") or []),
                "aktywne" if u.get("active") else "zablokowane", last or "nigdy", _czas(u.get("last_active")) or "—",
                u.get("active_version") or u.get("app_version") or "",
                u.get("last_device") or "", u.get("last_ip") or ""))
        self.users_msg.config(text=info or f"Kont: {len(users)}", fg=OK if info else MUTED)

    def _edit_user(self):
        sel = self.users_tv.selection()
        if sel:
            UserDialog(self, self._users[int(sel[0])])


def _czas(iso) -> str:
    """Czas z bazy (UTC) → lokalny „RRRR-MM-DD GG:MM”; brak → pusty tekst."""
    if not iso:
        return ""
    from datetime import datetime
    try:
        return datetime.fromisoformat(str(iso).replace("Z", "+00:00")).astimezone().strftime("%d.%m.%Y %H:%M")
    except ValueError:
        return str(iso)[:16].replace("T", " ")
