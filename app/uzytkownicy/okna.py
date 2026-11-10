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
        self.title(f"Konto: {user.get('email', '')}" if user else "Nowe konto")
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

        def group(title, items, kolumny=3):
            tk.Label(self, text=title, bg=SURFACE, fg=INK, font=f.label).pack(anchor="w", pady=(6, 0))
            row = tk.Frame(self, bg=SURFACE)
            row.pack(anchor="w")
            for i, (text, var) in enumerate(items):   # siatka – okno mieści się na ekranie 1280 px
                tk.Checkbutton(row, text=text, variable=var, bg=SURFACE, activebackground=SURFACE,
                               font=f.body).grid(row=i // kolumny, column=i % kolumny, sticky="w", padx=(0, 12))
        group("Moduły", [(n, self.v_mod[k]) for k, n in cloud.MODULES])
        group("Oddziały", [(b, self.v_br[b]) for b in cloud.BRANCHES])
        group("Konto", [("Administrator (dostęp do wszystkiego)", self.v_admin), ("Aktywne", self.v_active)])

        # OFERTY OPON: konto API xPartner tej osoby (każdy ma swoje; hasło nie jest pokazywane)
        self.v_xp_login, self.v_xp_pass = tk.StringVar(), tk.StringVar()
        tk.Label(self, text="xPartner – konto API (moduł Oferty opon)", bg=SURFACE, fg=INK,
                 font=f.label).pack(anchor="w", pady=(10, 0))
        xr = tk.Frame(self, bg=SURFACE)
        xr.pack(anchor="w", pady=(2, 0))
        tk.Label(xr, text="Login", bg=SURFACE, fg=MUTED, font=f.small).grid(row=0, column=0, sticky="w")
        tk.Label(xr, text="Hasło", bg=SURFACE, fg=MUTED, font=f.small).grid(row=0, column=1, sticky="w", padx=(10, 0))
        tk.Entry(xr, textvariable=self.v_xp_login, width=20, font=f.body, relief="solid", bd=1).grid(row=1, column=0, ipady=3)
        tk.Entry(xr, textvariable=self.v_xp_pass, show="•", width=20, font=f.body, relief="solid", bd=1).grid(
            row=1, column=1, ipady=3, padx=(10, 0))
        self.xp_info = tk.Label(self, text="Puste hasło = bez zmiany." if u else "Wpisz login i hasło API xPartner (moduł Oferty opon).", bg=SURFACE, fg=MUTED, font=f.small)
        self.xp_info.pack(anchor="w")
        self._xp_old_login = ""
        if u:
            def load_xp():
                try:
                    rows = app.session.call("GET", "/rest/v1/oferty_konta?select=*&email=eq."
                                            + __import__("urllib.parse").parse.quote(u["email"])) or []
                except Exception:
                    rows = []
                r = rows[0] if rows else {}
                try:   # hasło jest w zaszyfrowanym sejfie – baza mówi tylko, czy jest zapisane
                    jest = app.session.call("POST", "/rest/v1/rpc/oferty_ma_haslo", {"p_email": u["email"]}) is True
                except Exception:
                    jest = bool(r.get("xp_haslo"))

                def show():
                    if not self.winfo_exists():
                        return
                    self._xp_old_login = r.get("xp_login") or ""
                    self.v_xp_login.set(self._xp_old_login)
                    self.xp_info.config(text="Hasło zapisane – puste pole = bez zmiany." if jest
                                        else "Brak hasła – wpisz, żeby moduł Oferty opon działał.")
                app.after(0, show)
            threading.Thread(target=load_xp, daemon=True).start()

        self.msg = tk.Label(self, text="", bg=SURFACE, fg=RED, font=f.small, wraplength=380, justify="left")
        self.msg.pack(anchor="w", pady=(10, 4))
        bar = tk.Frame(self, bg=SURFACE)
        bar.pack(fill="x")
        self.btn = FlatButton(bar, "Zapisz", self.save, "primary", f.btn)
        self.btn.pack(side="right")
        FlatButton(bar, "Anuluj", self.destroy, "ghost", f.body, 14, 8).pack(side="right", padx=8)
        if u and u.get("email", "").lower() != app.session.email.lower():
            FlatButton(bar, "Usuń konto", self.delete, "danger", f.body, 14, 8).pack(side="left")
            FlatButton(bar, "Wyloguj z programu teraz", self.logout, "ghost", f.body, 14, 8).pack(side="left", padx=8)
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
        xp_login, xp_pass = self.v_xp_login.get().strip(), self.v_xp_pass.get()
        xp_change = xp_pass != "" or xp_login != self._xp_old_login

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
            if xp_change:
                s.rpc("oferty_admin_set_konto", p_email=email, p_login=xp_login, p_haslo=xp_pass)
        self._run(fn, f"Zapisano: {email}" + (" – przekaż użytkownikowi hasło." if pw else ""))

    def logout(self):
        email = self.user["email"]
        if not messagebox.askyesno("Wyloguj", f"Wylogować {email}?\nOtwarty program tej osoby zamknie się w ciągu "
                                   "kilkunastu sekund i przy uruchomieniu poprosi o hasło. "
                                   "Konto i uprawnienia zostają bez zmian.", parent=self):
            return
        self._run(lambda: self.app.session.logout_user(email), f"Wylogowano: {email}")

    def delete(self):
        email = self.user["email"]
        if not messagebox.askyesno("Usuń konto", f"Usunąć konto {email}?\nTej operacji nie można cofnąć.",
                                   parent=self):
            return
        self._run(lambda: self.app.session.admin_fn(action="delete", email=email), f"Usunięto: {email}")


class AuditWindow(tk.Toplevel):
    """Dziennik zmian: kto, kiedy i co zrobił (auta, wpisy serwisowe, sprawdzenia, e-maile, użytkownicy)."""

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
        for c, h, w in zip(cols, ("Kiedy", "Kto", "Czynność", "Obiekt", "Dotyczy", "Szczegóły"),
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
            self.tv.insert("", "end", values=(t, r.get("email") or "", "e-mail" if r.get("action") == "mail" else (r.get("action") or ""),
                                              r.get("entity") or "", r.get("label") or "", det))
        self.msg.config(text=f"Pozycji: {len(rows)} (najnowsze na górze, do 1000)", fg=MUTED)
