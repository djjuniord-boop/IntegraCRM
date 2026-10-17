"""Zakładka UŻYTKOWNICY (tylko administrator)."""
import threading
import tkinter as tk
from tkinter import ttk
import cloud
from ui import BG, BLACK, FlatButton, MUTED, OK, RED

TERAZ_MIN = 7         # program zapisuje aktywność co 5 min – świeższy sygnał = „pracuje teraz”
TERAZ_BG = "#C8E6C9"  # wyraźniejsza zieleń niż OK_BG – widoczna także na słabym monitorze
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
        self.users_tv.tag_configure("teraz", background=TERAZ_BG)
        self.users_tv.pack(fill="both", expand=True, pady=(6, 0))
        self.users_tv.bind("<Double-1>", lambda e: self._edit_user())
        tk.Label(page, text="Kliknij dwukrotnie wiersz z użytkownikiem, żeby zmienić uprawnienia, hasło albo zablokować konto. Zielony wiersz i „● pracuje teraz” – program tej osoby jest otwarty (sygnał co 5 minut). "
                 "Administrator ma zawsze dostęp do wszystkich modułów i oddziałów.",
                 bg=BG, fg=MUTED, font=f.small, wraplength=1300, justify="left").pack(anchor="w", pady=(6, 0))
        self._users = []
        self.after(300, self.refresh_users)
        self.after(60 * 1000, self._users_auto)

    def _users_auto(self):
        """Co minutę odświeża listę, gdy zakładka UŻYTKOWNICY jest otwarta (kto pracuje teraz)."""
        if getattr(self, "current_tab", "") == "users":
            self.refresh_users(quiet=True)
        self.after(60 * 1000, self._users_auto)

    def refresh_users(self, info="", quiet=False):
        if not quiet:
            self.users_msg.config(text="Wczytuję…", fg=MUTED)

        def work():
            try:
                users = self.session.list_users()
                self.after(0, self._show_users, users, info)
            except Exception as e:
                if quiet:   # automatyczne odświeżanie – lista może być nieaktualna
                    from datetime import datetime
                    godz = datetime.now().strftime("%H:%M")
                    self.after(0, lambda: self.users_msg.config(
                        text=f"Nie udało się odświeżyć listy ({godz}) – pokazany jest wcześniejszy stan.", fg=RED))
                else:
                    self.after(0, lambda err=str(e): self.users_msg.config(text=f"Błąd: {err}", fg=RED))
        threading.Thread(target=work, daemon=True).start()

    def _show_users(self, users, info):
        sel = self.users_tv.selection()
        self._users = users
        names = dict(cloud.MODULES)
        self.users_tv.delete(*self.users_tv.get_children())
        teraz = 0
        for u in users:
            adm = u.get("role") == "admin"
            last = _czas(u.get("last_seen"))
            on = pracuje_teraz(u.get("last_active"))
            teraz += on
            self.users_tv.insert("", "end", iid=u["email"], tags=("teraz",) if on else (), values=(
                u["email"], u.get("name") or "", "administrator" if adm else "użytkownik",
                "wszystkie" if adm else ", ".join(names.get(m, m) for m in u.get("modules") or []),
                "wszystkie" if adm else ", ".join(u.get("branches") or []),
                "aktywne" if u.get("active") else "zablokowane", last or "nigdy",
                "● pracuje teraz" if on else (_czas(u.get("last_active")) or "—"),
                u.get("active_version") or u.get("app_version") or "",
                u.get("last_device") or "", u.get("last_ip") or ""))
        for iid in sel:
            if self.users_tv.exists(iid):
                self.users_tv.selection_add(iid)
        self.users_msg.config(text=info or f"Kont: {len(users)} · pracuje teraz: {teraz}", fg=OK if info else MUTED)

    def _edit_user(self):
        sel = self.users_tv.selection()
        if sel:
            u = next((x for x in self._users if x["email"] == sel[0]), None)
            if u:
                UserDialog(self, u)


def pracuje_teraz(iso, teraz=None) -> bool:
    """Czy ostatni sygnał z programu jest świeższy niż TERAZ_MIN minut."""
    if not iso:
        return False
    from datetime import datetime, timezone
    try:
        t = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return False
    teraz = teraz or datetime.now(timezone.utc)
    return -120 <= (teraz - t).total_seconds() <= TERAZ_MIN * 60   # 2 min zapasu na różnicę zegarów


def _czas(iso) -> str:
    """Czas z bazy (UTC) → lokalny „RRRR-MM-DD GG:MM”; brak → pusty tekst."""
    if not iso:
        return ""
    from datetime import datetime
    try:
        return datetime.fromisoformat(str(iso).replace("Z", "+00:00")).astimezone().strftime("%d.%m.%Y %H:%M")
    except ValueError:
        return str(iso)[:16].replace("T", " ")
