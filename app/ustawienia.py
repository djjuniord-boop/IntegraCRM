"""Okno Ustawienia (przycisk ⚙ u góry okna)."""
import tkinter as tk
from tkinter import messagebox, ttk
import cloud
from kontrola import mailer
from ui import BG, BLACK, FlatButton, INK, MUTED, RED, SURFACE, set_icon
from konfig import COMPANY, load_config, save_config


# ---------- ustawienia ----------
class SettingsDialog(tk.Toplevel):
    """Konfiguracja maila, OCR i aktualizacji – zapisywana u użytkownika w data/config.json."""

    def __init__(self, parent):
        super().__init__(parent)
        f = parent.fonts
        self.title("Ustawienia")
        self.resizable(False, False)
        self.configure(bg=SURFACE)
        self.transient(parent)
        self.grab_set()
        set_icon(self)
        cfg = load_config()

        tk.Frame(self, bg=RED, height=4).pack(fill="x")
        body = tk.Frame(self, bg=SURFACE, padx=22, pady=16)
        body.pack(fill="both")
        tk.Label(body, text="Ustawienia", bg=SURFACE, fg=BLACK, font=f.h1).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        self.v_user = tk.StringVar(value=cfg["gmail_user"])
        self.v_pass = tk.StringVar(value=cfg["gmail_app_password"])
        self.v_to = tk.StringVar(value=", ".join(cfg["recipients"]))
        self.v_tess = tk.StringVar(value=cfg["tesseract_cmd"])
        self.v_upd = tk.StringVar(value=cfg["update_source"])

        r = [1]

        def section(title):
            tk.Label(body, text=title.upper(), bg=SURFACE, fg=RED, font=f.small).grid(
                row=r[0], column=0, columnspan=2, sticky="w", pady=(10, 2))
            r[0] += 1

        def row(label, var, show=None):
            tk.Label(body, text=label, bg=SURFACE, fg=INK, font=f.body, anchor="w").grid(
                row=r[0], column=0, sticky="w", pady=4)
            e = ttk.Entry(body, textvariable=var, width=46, show=show, font=f.body)
            e.grid(row=r[0], column=1, pady=4, padx=(12, 0), ipady=3)
            r[0] += 1
            return e

        section("Poczta")
        if getattr(parent, "session", None):
            tk.Label(body, text="Po zalogowaniu maile wysyła serwer firmy – Gmail i hasło poniżej są potrzebne\n"
                     "tylko awaryjnie, gdy wysyłka z serwera nie jest skonfigurowana.",
                     bg=SURFACE, fg=MUTED, font=f.small, justify="left").grid(row=r[0], column=0, columnspan=2,
                                                                              sticky="w", pady=(0, 4))
            r[0] += 1
        self.v_name = tk.StringVar(value=cfg.get("sender_name") or mailer.DEFAULT_SENDER)
        self.name_entry = row("Nazwa nadawcy", self.v_name)
        row("Twój Gmail (nadawca)", self.v_user)
        self.pass_entry = row("Hasło aplikacji Google", self.v_pass, show="•")
        self.show = tk.BooleanVar()
        ttk.Checkbutton(body, text="Pokaż hasło", variable=self.show,
                        command=lambda: self.pass_entry.config(show="" if self.show.get() else "•")
                        ).grid(row=r[0], column=1, sticky="w", padx=12)
        r[0] += 1
        sess = getattr(parent, "session", None)
        self.company_mode = "admin" if sess and sess.is_admin else ("locked" if sess else "")
        self.v_by = {}
        if self.company_mode == "locked":   # ustawienia firmowe – tylko do odczytu
            for e in (self.name_entry, row("Odbiorcy (domyślni)", self.v_to)):
                e.config(state="disabled")
            tk.Label(body, text="Nadawcę i odbiorców ustawia administrator (wspólne dla firmy).",
                     bg=SURFACE, fg=MUTED, font=f.small).grid(row=r[0], column=1, sticky="w", padx=12)
            r[0] += 1
        else:
            row("Odbiorcy (domyślni)", self.v_to)
        if self.company_mode == "admin":
            by = COMPANY.get("by_branch") or {}
            for b in cloud.BRANCHES:
                self.v_by[b] = tk.StringVar(value=", ".join(by.get(b) or []))
                row(f"Odbiorcy – {b}", self.v_by[b])
            tk.Label(body, text="Ustawienia firmowe – zapisują się dla wszystkich użytkowników. Puste pole "
                     "oddziału = odbiorcy domyślni.", bg=SURFACE, fg=MUTED, font=f.small).grid(
                row=r[0], column=1, sticky="w", padx=12)
            r[0] += 1
        self.v_cc = tk.BooleanVar(value=bool(cfg.get("cc_self", True)))
        ttk.Checkbutton(body, text="Wysyłaj kopię (DW) do mnie", variable=self.v_cc
                        ).grid(row=r[0], column=1, sticky="w", padx=12)
        r[0] += 1
        self.v_stats = tk.BooleanVar(value=bool(cfg.get("stats_enabled", True)))
        ttk.Checkbutton(body, text="Wysyłaj anonimowe statystyki użycia (tylko liczby)", variable=self.v_stats
                        ).grid(row=r[0], column=1, sticky="w", padx=12, pady=(6, 0))
        r[0] += 1
        self.v_marza = tk.BooleanVar(value=bool(cfg.get("marza_enabled", False)))
        self.v_serwis = tk.BooleanVar(value=bool(cfg.get("serwis_enabled", False)))
        section("Zaawansowane")
        row("Tesseract (puste = auto)", self.v_tess)
        row("Źródło aktualizacji", self.v_upd)
        tk.Label(body, text="puste = GitHub (zalecane)", bg=SURFACE, fg=MUTED, font=f.small).grid(
            row=r[0], column=1, sticky="w", padx=12)
        r[0] += 1

        hint = ("Hasło aplikacji to 16 znaków z konta Google (nie zwykłe hasło do Gmaila):\n"
                "Konto Google → Bezpieczeństwo → Weryfikacja dwuetapowa → Hasła aplikacji.\n"
                + ("Gmail, hasło, Tesseract i źródło aktualizacji zapisują się tylko na tym komputerze "
                   "(hasło zaszyfrowane);\nnadawca i odbiorcy – dla całej firmy."
                   if self.company_mode == "admin" else
                   "Ustawienia zapisują się tylko na tym komputerze, hasło jest zaszyfrowane (Windows)."))
        tk.Label(body, text=hint, bg=BG, fg=MUTED, font=f.small, justify="left",
                 padx=10, pady=8).grid(row=r[0], column=0, columnspan=2, sticky="we", pady=(12, 14))
        r[0] += 1

        btns = tk.Frame(body, bg=SURFACE)
        btns.grid(row=r[0], column=0, columnspan=2, sticky="e")
        FlatButton(btns, "Wyślij test", self.test, "ghost", f.body, 14, 6).pack(side="left", padx=4)
        FlatButton(btns, "Anuluj", self.destroy, "ghost", f.body, 14, 6).pack(side="left", padx=4)
        FlatButton(btns, "Zapisz", self.save, "primary", f.label, 18, 6).pack(side="left", padx=(4, 0))

    def collect(self) -> dict:
        return {
            "gmail_user": self.v_user.get().strip(),
            "gmail_app_password": self.v_pass.get().strip(),
            "recipients": [x.strip() for x in self.v_to.get().split(",") if x.strip()],
            "tesseract_cmd": self.v_tess.get().strip(),
            "update_source": self.v_upd.get().strip(),
            "cc_self": bool(self.v_cc.get()),
            "sender_name": self.v_name.get().strip(),
            "stats_enabled": bool(self.v_stats.get()),
            "marza_enabled": bool(self.v_marza.get()),
            "marza_folder": load_config().get("marza_folder", ""),
            "serwis_enabled": bool(self.v_serwis.get()),
        }

    def save(self):
        old = load_config()
        cfg = dict(old)
        new = self.collect()
        if self.company_mode == "admin":   # firmowe: do bazy (dla wszystkich)
            split = lambda v: [x.strip() for x in v.get().split(",") if x.strip()]
            try:   # świeży stan z bazy – nie kasujemy kluczy, których to okno nie zmienia (np. odbiorców MARŻY)
                value = dict(self.master.session.company() or COMPANY)
                value.update(recipients=new["recipients"], sender_name=new["sender_name"],
                             by_branch={b: split(v) for b, v in self.v_by.items() if split(v)})
                self.master.session.set_company(value)
                COMPANY.clear()
                COMPANY.update(value)
            except Exception as e:
                messagebox.showerror("Ustawienia", f"Nie zapisano ustawień firmowych:\n{e}", parent=self)
                return
        if self.company_mode == "locked":   # tych pól użytkownik nie zmienia
            new.pop("recipients")
            new.pop("sender_name")
        cfg.update(new)     # zachowuje pozostałe ustawienia (np. SERWIS QR)
        save_config(cfg)
        self.destroy()

    def test(self):
        cfg = self.collect()
        if not (cfg["gmail_user"] and cfg["gmail_app_password"] and cfg["recipients"]):
            messagebox.showwarning("Test", "Uzupełnij Gmail, hasło aplikacji i odbiorców.", parent=self)
            return
        try:
            mailer.send("Test – Integra 7 ↔ CRM",
                        "To jest wiadomość testowa z programu kontroli eksportu zleceń.", cfg)
            messagebox.showinfo("Test", "Mail testowy wysłany.", parent=self)
        except Exception as e:
            messagebox.showerror("Test", f"Nie udało się wysłać:\n{e}", parent=self)
