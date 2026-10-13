"""Okna administratora: edycja konta (UserDialog) i Dziennik zmian (AuditWindow)."""
import threading
import tkinter as tk
from tkinter import messagebox, ttk
import cloud
from ui import BG, FlatButton, INK, MUTED, RED, SURFACE, set_icon


# ---------- zakładka UŻYTKOWNICY (tylko administrator) ----------
class UserDialog(tk.Toplevel):
    def __init__(self, app, user=None):
        super().__init__(app)
        self.app, self.user = app, user or {}
        self.title("Użytkownik" if user else "Nowy użytkownik")
        self.configure(bg=SURFACE, padx=22, pady=18)
        self.transient(app)
        self.resizable(False, False)
        set_icon(self)
        f = app.fonts
        u = self.user
        self.v_email = tk.StringVar(value=u.get("email", ""))
        self.v_name = tk.StringVar(value=u.get("name") or "")
        self.v_pass = tk.StringVar()
        self.v_admin = tk.BooleanVar(value=u.get("role") == "admin")
        self.v_active = tk.BooleanVar(value=u.get("active", True))
        self.v_mod = {k: tk.BooleanVar(value=k in (u.get("modules") or [])) for k, _ in cloud.MODULES}
        self.v_br = {b: tk.BooleanVar(value=b in (u.get("branches") or [])) for b in cloud.BRANCHES}

        def entry(label, var, show=None, state="normal"):
            tk.Label(self, text=label, bg=SURFACE, fg=INK, font=f.label).pack(anchor="w")
            tk.Entry(self, textvariable=var, show=show, width=40, font=f.body, relief="solid", bd=1,
                     state=state).pack(anchor="w", ipady=3, pady=(2, 8))
        entry("E-mail", self.v_email, state="disabled" if u else "normal")
        entry("Imię i nazwisko", self.v_name)
        entry("Nowe hasło (min. 8 znaków)" if u else "Hasło startowe (min. 8 znaków)", self.v_pass)
        if u:
            tk.Label(self, text="Zostaw puste, żeby nie zmieniać hasła.", bg=SURFACE, fg=MUTED,
                     font=f.small).pack(anchor="w", pady=(0, 6))

        def group(title, items):
            tk.Label(self, text=title, bg=SURFACE, fg=INK, font=f.label).pack(anchor="w", pady=(6, 0))
            row = tk.Frame(self, bg=SURFACE)
            row.pack(anchor="w")
            for text, var in items:
                tk.Checkbutton(row, text=text, variable=var, bg=SURFACE, activebackground=SURFACE,
                               font=f.body).pack(side="left", padx=(0, 10))
        group("Moduły", [(n, self.v_mod[k]) for k, n in cloud.MODULES])
        group("Oddziały", [(b, self.v_br[b]) for b in cloud.BRANCHES])
        group("Konto", [("Administrator (dostęp do wszystkiego)", self.v_admin), ("Aktywne", self.v_active)])

        self.msg = tk.Label(self, text="", bg=SURFACE, fg=RED, font=f.small, wraplength=380, justify="left")
        self.msg.pack(anchor="w", pady=(10, 4))
        bar = tk.Frame(self, bg=SURFACE)
        bar.pack(fill="x")
        self.btn = FlatButton(bar, "Zapisz", self.save, "primary", f.btn)
        self.btn.pack(side="right")
        FlatButton(bar, "Anuluj", self.destroy, "ghost", f.body, 14, 8).pack(side="right", padx=8)
        if u and u.get("email", "").lower() != app.session.email.lower():
            FlatButton(bar, "Usuń konto", self.delete, "dark", f.body, 14, 8).pack(side="left")
        self.grab_set()

    def _run(self, fn, done_text):
        self.btn.set_enabled(False, "Zapisuję…")

        def work():
            try:
                fn()
                self.app.after(0, lambda: (self.destroy(), self.app.refresh_users(done_text)))
            except Exception as e:
                self.app.after(0, lambda err=str(e): (self.msg.config(text=err),
                                                      self.btn.set_enabled(True, "Zapisz")))
        threading.Thread(target=work, daemon=True).start()

    def save(self):
        email = self.v_email.get().strip().lower()
        pw = self.v_pass.get()
        role = "admin" if self.v_admin.get() else "user"
        mods = [k for k, v in self.v_mod.items() if v.get()]
        brs = [b for b, v in self.v_br.items() if v.get()]
        if not email or "@" not in email:
            self.msg.config(text="Wpisz poprawny e-mail.")
            return
        if (not self.user or pw) and len(pw) < 8:
            self.msg.config(text="Hasło musi mieć co najmniej 8 znaków.")
            return
        if role != "admin" and (not mods or not brs):
            self.msg.config(text="Zaznacz co najmniej jeden moduł i jeden oddział.")
            return
        s, name, active = self.app.session, self.v_name.get().strip(), self.v_active.get()

        def fn():
            if not self.user:
                s.admin_fn(action="create", email=email, password=pw, name=name, role=role,
                           modules=mods, branches=brs)
                if not active:
                    s.set_user(email, name, role, mods, brs, False)
            else:
                s.set_user(email, name, role, mods, brs, active)
                if pw:
                    s.admin_fn(action="set_password", email=email, password=pw)
        self._run(fn, f"Zapisano: {email}" + (" – przekaż użytkownikowi hasło." if pw else ""))

    def delete(self):
        email = self.user["email"]
        if not messagebox.askyesno("Usuń konto", f"Usunąć konto {email}?\nTej operacji nie można cofnąć.",
                                   parent=self):
            return
        self._run(lambda: self.app.session.admin_fn(action="delete", email=email), f"Usunięto: {email}")


class AuditWindow(tk.Toplevel):
    """Dziennik zmian: kto, kiedy i co zrobił (auta, wpisy serwisowe, sprawdzenia, maile, użytkownicy)."""

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("Dziennik zmian")
        self.geometry("1150x650")
        self.configure(bg=BG, padx=16, pady=12)
        set_icon(self)
        f = app.fonts
        bar = tk.Frame(self, bg=BG)
        bar.pack(fill="x")
        tk.Label(bar, text="Szukaj (e-mail, numer, plik):", bg=BG, fg=INK, font=f.body).pack(side="left")
        self.v_q = tk.StringVar()
        e = tk.Entry(bar, textvariable=self.v_q, width=30, font=f.body, relief="solid", bd=1)
        e.pack(side="left", padx=8, ipady=3)
        e.bind("<Return>", lambda ev: self.load())
        FlatButton(bar, "Szukaj", self.load, "primary", f.body, 14, 6).pack(side="left")
        self.msg = tk.Label(bar, text="", bg=BG, fg=MUTED, font=f.small)
        self.msg.pack(side="left", padx=12)
        cols = ("at", "email", "action", "entity", "label", "detail")
        self.tv = ttk.Treeview(self, columns=cols, show="headings")
        for c, h, w in zip(cols, ("Kiedy", "Kto", "Co", "Czego", "Dotyczy", "Szczegóły"),
                           (130, 200, 90, 120, 160, 430)):
            self.tv.heading(c, text=h, anchor="w")
            self.tv.column(c, width=w, anchor="w")
        sb = ttk.Scrollbar(self, command=self.tv.yview)
        self.tv.config(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y", pady=(10, 0))
        self.tv.pack(fill="both", expand=True, pady=(10, 0))
        self.load()

    def load(self):
        self.msg.config(text="Wczytuję…")
        q = self.v_q.get()

        def work():
            try:
                rows = self.app.session.audit(query=q)
                self.app.after(0, self.show, rows)
            except Exception as e:
                self.app.after(0, lambda err=str(e): self.msg.config(text=f"Błąd: {err}", fg=RED))
        threading.Thread(target=work, daemon=True).start()

    def show(self, rows):
        if not self.winfo_exists():
            return
        from datetime import datetime as _dt
        self.tv.delete(*self.tv.get_children())
        for r in rows:
            try:
                t = _dt.fromisoformat(str(r["at"]).replace("Z", "+00:00")).astimezone().strftime("%Y-%m-%d %H:%M")
            except ValueError:
                t = str(r.get("at", ""))[:16]
            d = r.get("detail") or {}
            det = "  ·  ".join(f"{k}: {', '.join(map(str, v)) if isinstance(v, list) else v}"
                               for k, v in d.items() if v not in (None, "", []))
            self.tv.insert("", "end", values=(t, r.get("email") or "", r.get("action") or "",
                                              r.get("entity") or "", r.get("label") or "", det))
        self.msg.config(text=f"Pozycji: {len(rows)} (najnowsze na górze, do 1000)", fg=MUTED)
