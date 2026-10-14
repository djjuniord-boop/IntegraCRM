"""Okno Ustawienia (przycisk ⚙ u góry okna)."""
import tkinter as tk
from tkinter import messagebox, ttk
import cloud
from kontrola import mailer
from ui import BLACK, FlatButton, INK, MUTED, RED, SURFACE, set_icon
from konfig import COMPANY, load_config, save_config


# ---------- ustawienia ----------
class SettingsDialog(tk.Toplevel):
    """Pracownik: podgląd odbiorców, kopia do mnie, statystyki. Administrator: nadawca i odbiorcy firmy (baza),
    Tesseract i źródło aktualizacji (ten komputer). Gmail na komputerze nie jest już używany."""

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
        # treść w przewijanym obszarze – na małych ekranach (laptop 1366×768, skala 125%) przyciski
        # Zapisz/Anuluj zostają widoczne pod spodem
        outer = tk.Frame(self, bg=SURFACE)
        outer.pack(fill="both", expand=True)
        self._canvas = tk.Canvas(outer, bg=SURFACE, highlightthickness=0)
        self._sb = ttk.Scrollbar(outer, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=self._sb.set)
        self._canvas.pack(side="left", fill="both", expand=True)
        body = tk.Frame(self._canvas, bg=SURFACE, padx=22, pady=16)
        self._canvas.create_window((0, 0), window=body, anchor="nw")
        tk.Label(body, text="Ustawienia", bg=SURFACE, fg=BLACK, font=f.h1).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        sess = getattr(parent, "session", None)
        self.company_mode = "admin" if sess and sess.is_admin else ("locked" if sess else "")
        admin = self.company_mode != "locked"
        self.v_to = tk.StringVar(value=", ".join(cfg["recipients"]))
        self.v_tess = tk.StringVar(value=cfg["tesseract_cmd"])
        self.v_upd = tk.StringVar(value=cfg["update_source"])
        self.v_name = tk.StringVar(value=cfg.get("sender_name") or mailer.DEFAULT_SENDER)

        r = [1]

        def section(title):
            tk.Label(body, text=title.upper(), bg=SURFACE, fg=RED, font=f.small).grid(
                row=r[0], column=0, columnspan=2, sticky="w", pady=(10, 2))
            r[0] += 1

        def note(text, col=1):
            tk.Label(body, text=text, bg=SURFACE, fg=MUTED, font=f.small, justify="left").grid(
                row=r[0], column=col, columnspan=2 - col, sticky="w", padx=12 if col else 0, pady=(0, 4))
            r[0] += 1

        def row(label, var):
            tk.Label(body, text=label, bg=SURFACE, fg=INK, font=f.body, anchor="w").grid(
                row=r[0], column=0, sticky="w", pady=4)
            e = ttk.Entry(body, textvariable=var, width=46, font=f.body)
            e.grid(row=r[0], column=1, pady=4, padx=(12, 0), ipady=3)
            r[0] += 1
            return e

        section("Poczta")
        self.v_by = {}
        by = COMPANY.get("by_branch") or {}
        if admin:
            note("Maile wysyła serwer firmy. Nadawca i odbiorcy są wspólni – zapisują się dla wszystkich.", 0)
            row("Nazwa nadawcy", self.v_name)
            row("Odbiorcy (domyślni)", self.v_to)
            for b in cloud.BRANCHES:
                self.v_by[b] = tk.StringVar(value=", ".join(by.get(b) or []))
                row(f"Odbiorcy – {b}", self.v_by[b])
            note("Kilka adresów oddziel przecinkiem. Puste pole oddziału = odbiorcy domyślni.\n"
                 "Odbiorców maili MARŻY ustawiasz w zakładce MARŻA → „Odbiorcy maili”.")
        else:
            moje = sess.branches() if sess else []
            linie = [f"{b}: {', '.join(by.get(b) or cfg['recipients']) or '—'}" for b in moje]
            tk.Label(body, text="Odbiorcy maili", bg=SURFACE, fg=INK, font=f.body, anchor="nw").grid(
                row=r[0], column=0, sticky="nw", pady=4)
            tk.Label(body, text="\n".join(linie) or ", ".join(cfg["recipients"]) or "—", bg=SURFACE, fg=BLACK,
                     font=f.body, justify="left").grid(row=r[0], column=1, sticky="w", padx=12, pady=4)
            r[0] += 1
            note("Maile wysyła serwer firmy. Odbiorców ustawia administrator.")
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
        if admin:
            section("Zaawansowane")
            row("Tesseract (puste = auto)", self.v_tess)
            note("tylko do skanów PDF z Integry (zdjęcie strony zamiast tekstu)")
            row("Źródło aktualizacji", self.v_upd)
            note("puste = GitHub (zalecane). Zapisuje się tylko na tym komputerze.")

        bar = tk.Frame(self, bg=SURFACE, padx=22, pady=12)
        bar.pack(fill="x")
        btns = tk.Frame(bar, bg=SURFACE)
        btns.pack(side="right")
        if self.company_mode == "admin":
            FlatButton(btns, "Wyślij test", self.test, "ghost", f.body, 14, 6).pack(side="left", padx=4)
        FlatButton(btns, "Anuluj", self.destroy, "ghost", f.body, 14, 6).pack(side="left", padx=4)
        FlatButton(btns, "Zapisz", self.save, "primary", f.label, 18, 6).pack(side="left", padx=(4, 0))
        self._fit(body)

    def _fit(self, body):
        """Okno nie wyższe niż ekran; gdy treść się nie mieści – pasek przewijania i kółko myszy."""
        self.update_idletasks()
        bw, bh = body.winfo_reqwidth(), body.winfo_reqheight()
        maxh = max(300, self.winfo_screenheight() - 220)   # miejsce na pasek tytułu, przyciski i pasek zadań
        self._canvas.configure(width=bw, height=min(bh, maxh), scrollregion=(0, 0, bw, bh))
        if bh > maxh:
            self._sb.pack(side="right", fill="y")
            scroll = lambda n: self._canvas.yview_scroll(n, "units")
            self.bind("<MouseWheel>", lambda e: scroll(-1 if e.delta > 0 else 1))
            self.bind("<Button-4>", lambda e: scroll(-1))
            self.bind("<Button-5>", lambda e: scroll(1))

    def collect(self) -> dict:
        return {
            "gmail_user": "",            # wysyłka tylko z serwera – stare hasło Gmail usuwamy z komputera
            "gmail_app_password": "",
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
            for k in ("recipients", "sender_name", "tesseract_cmd", "update_source"):
                new.pop(k)
        cfg.update(new)     # zachowuje pozostałe ustawienia (np. SERWIS QR)
        save_config(cfg)
        self.destroy()

    def test(self):
        """Mail testowy przez serwer firmy do odbiorców domyślnych (tylko administrator)."""
        to = self.collect()["recipients"]
        if not to:
            messagebox.showwarning("Test", "Wpisz odbiorców domyślnych.", parent=self)
            return
        try:
            mailer.send_server(self.master.session, "Test – Integra 7 ↔ CRM",
                               "To jest wiadomość testowa z programu kontroli eksportu zleceń.", to,
                               bool(self.v_cc.get()))
            messagebox.showinfo("Test", f"Mail testowy wysłany do: {', '.join(to)}", parent=self)
        except Exception as e:
            messagebox.showerror("Test", f"Nie udało się wysłać:\n{e}", parent=self)
