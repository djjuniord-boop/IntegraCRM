"""Okno MARŻY: odbiorcy e-maili z wykresem (ustawienia firmowe). Okna „wyniki online” i „kopie” usunięto w 0.26.1."""
import tkinter as tk

from ui import BLACK, FlatButton, INK, MUTED, RED, SURFACE, set_icon
from konfig import COMPANY


# ---------- MARŻA w chmurze ----------
MARZA_BRANCHES = [("wroclaw", "Wrocław"), ("opole", "Opole")]


class MarzaRecipientsDialog(tk.Toplevel):
    """Odbiorcy e-maili MARŻY: zaznacz, kto ma dostawać, albo dopisz nowy adres (zapis dla całej firmy)."""

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("Odbiorcy e-maili – MARŻA")
        self.configure(bg=SURFACE, padx=22, pady=16)
        self.transient(app)
        self.resizable(False, False)
        set_icon(self)
        f = app.fonts
        self.admin = app.session.is_admin
        data = COMPANY.get("marza") or {}
        self.rows = {}
        tk.Label(self, text="Kto dostaje e-mail po aktualizacji MARŻY", bg=SURFACE, fg=BLACK,
                 font=f.h2).pack(anchor="w", pady=(0, 8))
        for key, name in MARZA_BRANCHES:
            box = tk.LabelFrame(self, text=f"  {name}  ", bg=SURFACE, fg=INK, font=f.label, padx=10, pady=6)
            box.pack(fill="x", pady=6)
            lst = tk.Frame(box, bg=SURFACE)
            lst.pack(fill="x")
            self.rows[key] = []
            for r in data.get(key) or []:
                self._add_row(key, lst, r.get("email", ""), bool(r.get("on", True)))
            if self.admin:
                add = tk.Frame(box, bg=SURFACE)
                add.pack(fill="x", pady=(6, 0))
                v = tk.StringVar()
                e = tk.Entry(add, textvariable=v, width=34, font=f.body, relief="solid", bd=1)
                e.pack(side="left", ipady=3)
                cb = lambda k=key, l=lst, var=v: self._add_new(k, l, var)
                e.bind("<Return>", lambda ev, c=cb: c())
                FlatButton(add, "+ Dodaj", cb, "ghost", f.small, 10, 4).pack(side="left", padx=6)
        self.msg = tk.Label(self, text="" if self.admin else "Odbiorców zmienia administrator.",
                            bg=SURFACE, fg=MUTED, font=f.small)
        self.msg.pack(anchor="w", pady=(8, 4))
        bar = tk.Frame(self, bg=SURFACE)
        bar.pack(fill="x")
        if self.admin:
            FlatButton(bar, "Zapisz", self.save, "primary", f.btn).pack(side="right")
        FlatButton(bar, "Zamknij", self.destroy, "ghost", f.body, 14, 8).pack(side="right", padx=8)

    def _add_row(self, key, parent, email, on):
        v = tk.BooleanVar(value=on)
        row = tk.Frame(parent, bg=SURFACE)
        row.pack(fill="x")
        tk.Checkbutton(row, text=email, variable=v, bg=SURFACE, activebackground=SURFACE,
                       font=self.app.fonts.body, state="normal" if self.admin else "disabled").pack(side="left")
        item = {"email": email, "var": v, "row": row}
        if self.admin:
            x = tk.Label(row, text="✕", bg=SURFACE, fg=MUTED, cursor="hand2", font=self.app.fonts.small)
            x.pack(side="left", padx=6)
            x.bind("<Button-1>", lambda e: (row.destroy(), self.rows[key].remove(item)))
        self.rows[key].append(item)

    def _add_new(self, key, parent, var):
        e = var.get().strip().lower()
        if not e or "@" not in e or "." not in e.split("@")[-1]:
            self.msg.config(text="Wpisz poprawny adres e-mail.", fg=RED)
            return
        if any(i["email"].lower() == e for i in self.rows[key]):
            self.msg.config(text="Ten adres już jest na liście.", fg=RED)
            return
        self._add_row(key, parent, e, True)
        var.set("")
        self.msg.config(text="")

    def save(self):
        mz = {k: [{"email": i["email"], "on": bool(i["var"].get())} for i in items] for k, items in self.rows.items()}
        try:   # świeży stan z bazy – zmieniamy tylko listę MARŻY, reszta ustawień firmowych zostaje
            value = dict(self.app.session.company() or COMPANY)
            value["marza"] = mz
            self.app.session.set_company(value)
        except Exception as e:
            self.msg.config(text=f"Nie zapisano: {e}", fg=RED)
            return
        COMPANY.clear()
        COMPANY.update(value)
        self.destroy()
