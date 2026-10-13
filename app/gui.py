"""Integra 7 ↔ CRM: kontrola eksportu zleceń po numerach rejestracyjnych (okno programu).

Wygląd zgodny z identyfikacją Latex Auto Serwis (wroclaw.latex.net.pl):
czerń + czerwień #E30613, białe tło, jasnoszare sekcje, font Poppins (gdy zainstalowany).
"""
import json
import os
import threading
import tkinter as tk
try:
    import tkinter.font as tkfont
except ImportError:   # starsze IntegraCRM.exe nie mają tego modułu
    tkfont = None
from tkinter import filedialog, messagebox, ttk

import analyze
import cloud
import crm_report
import extract
import mailer
import paths
import plates
import updater

# Moduły dodane w 0.9.0 – starsze IntegraCRM.exe mogą nie mieć potrzebnych bibliotek
# standardowych (np. csv). Wtedy program działa dalej, tylko bez tych funkcji.
try:
    import history
except Exception:   # pragma: no cover
    history = None
try:
    import vault
except Exception:   # pragma: no cover
    class vault:   # noqa: N801 – zastępstwo bez szyfrowania
        PREFIX = "dpapi:"
        protect = staticmethod(lambda x: x)
        unprotect = staticmethod(lambda x: "" if (x or "").startswith("dpapi:") else (x or ""))
try:
    import stats
except Exception:   # pragma: no cover
    stats = None
try:
    import dnd
except Exception:   # pragma: no cover
    dnd = None
from version import CHANGELOG, DEFAULT_UPDATE_SOURCE, RELEASED, VERSION

# ---------- identyfikacja wizualna ----------
RED, RED_DARK = "#E30613", "#B8050F"
BLACK, INK, MUTED = "#111111", "#313131", "#7A7A7A"
BG, SURFACE, LINE = "#F5F5F5", "#FFFFFF", "#E4E4E4"
OK, OK_BG = "#1E7D32", "#E8F5E9"
WARN, WARN_BG = "#8A5A00", "#FFF4E0"
ERR_BG = "#FDECEC"
ASSETS = paths.APP_DIR / "assets"

DEFAULTS = {
    "gmail_user": "",
    "gmail_app_password": "",
    "recipients": [],
    "tesseract_cmd": "",       # puste = automatycznie (folder programu / Program Files)
    "update_source": "",       # puste = DEFAULT_UPDATE_SOURCE z version.py
    "cc_self": True,           # kopia (DW) wysyłanego maila do nadawcy
    "sender_name": "",         # nazwa nadawcy widoczna u odbiorcy (puste = domyślna)
    "stats_enabled": True,     # anonimowe statystyki użycia (tylko liczby)
    "marza_enabled": False,    # zakładka MARŻA (kalkulator marży Wrocław + Opole) – tylko dla właściciela
    "marza_folder": "",        # folder „LATEX Wyniki”
    "serwis_enabled": False,   # zakładka SERWIS QR (beta) – tylko dla właściciela
    "serwis_sb_url": "",       # adres bazy Supabase (puste = tryb lokalny)
    "serwis_sb_key": "",       # klucz publiczny (anon) Supabase
    "serwis_base": "",         # adres strony dla klientów (kod QR)
    "crm_branches": list(crm_report.BRANCHES),   # oddziały liczone z raportu CRM (.xlsx)
}

STATS_INFO = ("Program wysyła anonimowe statystyki użycia: losowy identyfikator instalacji, wersję, "
              "rodzaj zdarzenia (uruchomienie, sprawdzenie, wysłany mail, błąd) i same liczby "
              "(ile numerów, ile braków, czas sprawdzenia). Nie wysyła numerów rejestracyjnych, adresów e-mail, "
              "haseł, nazw plików ani treści maili. Można to wyłączyć w Ustawieniach.")

HELP_STEPS = [
    ("Raport z Integra 7", "Przeciągnij plik PDF na okno programu albo kliknij „Wybierz PDF”."),
    ("Dane z CRM", "Najlepiej: w CRM w „Listy kontrolne” pobierz raport .xlsx i przeciągnij go na okno "
                   "(albo „Raport z CRM (.xlsx)…”). Zaznacz serwisy do sprawdzenia: Latex Wrocław, "
                   "Latex Opole, Stangum Opole – wybór jest zapamiętywany. Można też wkleić wycinek "
                   "tabeli (Win+Shift+S, potem Ctrl+V)."),
    ("Sprawdź", "Program porówna numery rejestracyjne. Status i inne kolumny są pomijane."),
    ("Wyślij maila", "Jeśli czegoś brakuje, mail jest gotowy – możesz go poprawić i wysłać."),
]


COMPANY: dict = {}   # ustawienia firmowe z bazy (odbiorcy, nadawca) – wczytywane po zalogowaniu


def recipients_for(branches, cfg=None) -> list:
    """Odbiorcy maila z brakami: wg oddziałów (ustawienia firmowe), inaczej domyślni."""
    by = COMPANY.get("by_branch") or {}
    out = []
    for b in branches or []:
        for r in by.get(b) or []:
            if r.lower() not in {x.lower() for x in out}:
                out.append(r)
    return out or list((cfg or load_config())["recipients"])


def load_config() -> dict:
    cfg = dict(DEFAULTS)
    if paths.CONFIG_PATH.exists():
        try:
            cfg.update(json.loads(paths.CONFIG_PATH.read_text(encoding="utf-8")))
        except (ValueError, OSError):   # uszkodzony plik – zachowaj kopię i pracuj na domyślnych
            try:
                paths.CONFIG_PATH.replace(paths.CONFIG_PATH.with_suffix(".bad.json"))
            except OSError:
                pass
    cfg["gmail_app_password"] = vault.unprotect(cfg.get("gmail_app_password", ""))
    if COMPANY:   # po zalogowaniu firmowe ustawienia mają pierwszeństwo przed lokalnymi
        if COMPANY.get("recipients"):
            cfg["recipients"] = list(COMPANY["recipients"])
        if COMPANY.get("sender_name"):
            cfg["sender_name"] = COMPANY["sender_name"]
    return cfg


def migrate_config() -> None:
    """Usuwa stare źródło aktualizacji (Dysk Google) i szyfruje hasło zapisane jawnym tekstem."""
    try:
        raw = json.loads(paths.CONFIG_PATH.read_text(encoding="utf-8")) if paths.CONFIG_PATH.exists() else {}
        cfg = load_config()
        changed = False
        if "drive.google.com" in (cfg.get("update_source") or ""):
            cfg["update_source"] = ""
            changed = True
        pw = raw.get("gmail_app_password") or ""
        if pw and not pw.startswith(vault.PREFIX) and vault.protect(pw) != pw:
            changed = True
        if changed:
            save_config(cfg)
    except Exception:
        pass


def save_config(cfg: dict) -> None:
    paths.DATA_DIR.mkdir(parents=True, exist_ok=True)
    out = dict(cfg)
    out["gmail_app_password"] = vault.protect(out.get("gmail_app_password", ""))
    tmp = paths.CONFIG_PATH.with_suffix(".json.tmp")   # zapis atomowy – przerwanie nie psuje ustawień
    tmp.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, paths.CONFIG_PATH)


def update_source(cfg: dict) -> str:
    src = (cfg.get("update_source") or "").strip()
    if "drive.google.com" in src:   # stare źródło (Dysk Google) – od 0.8.3 aktualizacje są na GitHubie
        src = ""
    return src or DEFAULT_UPDATE_SOURCE


# ---------- elementy interfejsu ----------
class Fonts:
    def __init__(self, root):
        fams = set(tkfont.families(root)) if tkfont else set(root.tk.splitlist(root.tk.call("font", "families")))
        base = next((f for f in ("Poppins", "Segoe UI", "Helvetica") if f in fams), "TkDefaultFont")
        self.family = base
        self.body = (base, 10)
        self.small = (base, 9)
        self.label = (base, 10, "bold")
        self.h1 = (base, 15, "bold")
        self.h2 = (base, 12, "bold")
        self.btn = (base, 11, "bold")
        self.big = (base, 13, "bold")
        self.mono = ("Consolas", 10)


class FlatButton(tk.Label):
    """Płaski przycisk w stylu strony (czerwony / czarny / obrys) z efektem najechania."""

    STYLES = {
        "primary": (RED, "white", RED_DARK),
        "dark": (BLACK, "white", "#333333"),
        "ghost": (SURFACE, BLACK, "#EFEFEF"),
    }

    def __init__(self, parent, text, command, kind="primary", font=None, padx=18, pady=9):
        bg, fg, hover = self.STYLES[kind]
        super().__init__(parent, text=text, bg=bg, fg=fg, font=font, padx=padx, pady=pady,
                         cursor="hand2", highlightthickness=1 if kind == "ghost" else 0,
                         highlightbackground=LINE)
        self._c = (bg, fg, hover)
        self._cmd = command
        self._enabled = True
        self.bind("<Enter>", lambda e: self._enabled and self.config(bg=hover))
        self.bind("<Leave>", lambda e: self.config(bg=bg if self._enabled else "#BDBDBD"))
        self.bind("<Button-1>", lambda e: self._enabled and self._cmd())

    def set_enabled(self, on: bool, text: str | None = None):
        self._enabled = on
        self.config(bg=self._c[0] if on else "#BDBDBD", cursor="hand2" if on else "arrow")
        if text:
            self.config(text=text)


def card(parent, **kw):
    return tk.Frame(parent, bg=SURFACE, highlightthickness=1, highlightbackground=LINE, **kw)


def step_badge(parent, n, fonts, bg=SURFACE):
    c = tk.Canvas(parent, width=28, height=28, bg=bg, highlightthickness=0)
    c.create_oval(1, 1, 27, 27, fill=RED, outline=RED)
    c.create_text(14, 14, text=str(n), fill="white", font=(fonts.family, 10, "bold"))
    return c


def set_icon(win):
    try:
        if (ASSETS / "icon.ico").exists():
            win.iconbitmap(str(ASSETS / "icon.ico"))
    except tk.TclError:
        pass


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
                "Ustawienia zapisują się tylko na tym komputerze, hasło jest zaszyfrowane (Windows).")
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
            value = dict(COMPANY, recipients=new["recipients"], sender_name=new["sender_name"],
                         by_branch={b: split(v) for b, v in self.v_by.items() if split(v)})
            try:
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
        changed = []   # zakładki zależą teraz od uprawnień konta (zakładka UŻYTKOWNICY)
        _unused = [n for k, n in (("marza_enabled", "MARŻA"), ("serwis_enabled", "SERWIS QR"))
                   if bool(cfg.get(k)) != bool(old.get(k))]
        if changed:
            messagebox.showinfo("Ustawienia", f"Zmiana zakładki {', '.join(changed)} będzie widoczna "
                                "po ponownym uruchomieniu programu.")

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


# ---------- logowanie (zawsze online) ----------
def _version_ok(sess) -> bool:
    """Wersja programu nie starsza niż minimalna ustawiona przez administratora."""
    try:
        need = sess.min_version()
    except cloud.CloudError:
        return True
    return not need or updater._ver(VERSION) >= updater._ver(need)


def _force_update(root):
    """Za stara wersja: próba aktualizacji; inaczej komunikat i koniec."""
    try:
        m, newer = updater.check(update_source(load_config()))
        if newer:
            messagebox.showinfo("Aktualizacja", f"Wymagana nowsza wersja programu. Instaluję {m['version']}…",
                                parent=root)
            updater.apply(m)
            updater.restart()
    except Exception:
        pass
    messagebox.showerror("Aktualizacja", "Ta wersja programu jest za stara i nie może się połączyć.\n"
                         "Pobierz najnowszą paczkę IntegraCRM z GitHuba.", parent=root)


def login_flow():
    """Okno logowania. Zwraca zalogowaną sesję (z profilem) albo None (zamknięto okno)."""
    root = tk.Tk()
    root.title(f"Latex Serwis – logowanie  v{VERSION}")
    root.configure(bg=BG)
    root.resizable(False, False)
    set_icon(root)
    fonts = Fonts(root)
    result = {"s": None}

    def finish(sess):
        if not _version_ok(sess):
            _force_update(root)
            root.destroy()
            return
        result["s"] = sess
        root.destroy()

    # 1. zapamiętana sesja – bez wpisywania hasła (ale zawsze z weryfikacją na serwerze)
    email0, tok = cloud.remembered()
    if tok:
        try:
            s = cloud.Session.from_refresh(tok)
            s.load_profile(VERSION)
            cloud.remember(s)
            root.withdraw()
            root.after(0, finish, s)
            root.mainloop()
            return result["s"]
        except cloud.CloudError as e:
            if "połączenia" in str(e):
                messagebox.showerror("Brak internetu", str(e), parent=root)
            cloud.forget()

    box = card(root, padx=34, pady=26)
    box.pack(padx=30, pady=30)
    try:
        if (ASSETS / "logo.png").exists():
            root._logo = tk.PhotoImage(file=str(ASSETS / "logo.png"))
            tk.Label(box, image=root._logo, bg=SURFACE).pack(pady=(0, 10))
    except tk.TclError:
        pass
    tk.Label(box, text="Zaloguj się", bg=SURFACE, fg=BLACK, font=fonts.h1).pack(anchor="w")
    tk.Label(box, text="Konto zakłada administrator programu.", bg=SURFACE, fg=MUTED,
             font=fonts.small).pack(anchor="w", pady=(0, 12))
    v_email, v_pass, v_rem = tk.StringVar(value=email0), tk.StringVar(), tk.BooleanVar(value=True)
    for label, var, show in (("E-mail", v_email, None), ("Hasło", v_pass, "•")):
        tk.Label(box, text=label, bg=SURFACE, fg=INK, font=fonts.label).pack(anchor="w")
        e = tk.Entry(box, textvariable=var, show=show, width=34, font=fonts.body, relief="solid", bd=1)
        e.pack(anchor="w", ipady=4, pady=(2, 10))
        if (label == "E-mail") == (not email0):
            e.focus_set()
    tk.Checkbutton(box, text="Zapamiętaj mnie na tym komputerze", variable=v_rem, bg=SURFACE,
                   activebackground=SURFACE, font=fonts.small).pack(anchor="w")
    msg = tk.Label(box, text="", bg=SURFACE, fg=RED, font=fonts.small, wraplength=300, justify="left")
    msg.pack(anchor="w", pady=(8, 4))
    btn = FlatButton(box, "ZALOGUJ", lambda: go(), "primary", fonts.btn)
    btn.pack(fill="x", pady=(4, 0))

    def go():
        if not v_email.get().strip() or not v_pass.get():
            msg.config(text="Wpisz e-mail i hasło.")
            return
        btn.set_enabled(False, "Łączę…")
        msg.config(text="")
        email, pw, rem = v_email.get().strip(), v_pass.get(), v_rem.get()

        def work():
            try:
                s = cloud.Session.login(email, pw)
                s.load_profile(VERSION)
                if rem:
                    cloud.remember(s)
                else:
                    cloud.forget()
                root.after(0, finish, s)
            except cloud.CloudError as e:
                root.after(0, lambda err=str(e): (msg.config(text=err), btn.set_enabled(True, "ZALOGUJ")))
        threading.Thread(target=work, daemon=True).start()

    root.bind("<Return>", lambda e: go())
    root.mainloop()
    return result["s"]


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


# ---------- okno główne ----------
class App(tk.Tk):
    def __init__(self, session=None):
        super().__init__()
        self.session = session   # zalogowany użytkownik (rola, moduły, oddziały)
        migrate_config()
        if session and history is not None:   # historia i rejestr zgłoszeń – wspólne, w bazie
            history.SESSION = session
            if stats is not None:
                stats.SESSION = session
            try:
                COMPANY.update(session.company())
            except Exception:
                pass

            def _sync():
                try:
                    n = history.migrate_local()
                    history.reported(refresh=True)
                    if n:
                        self.after(0, lambda: self.say(f"Przeniesiono do bazy {n} pozycji (stara historia "
                                                       "i zgłoszone numery)."))
                        self.after(0, self.refresh_history)
                except Exception:
                    pass
            threading.Thread(target=_sync, daemon=True).start()
        if session:   # SERWIS QR korzysta z tej samej bazy co logowanie
            try:
                _c = load_config()
                if not _c.get("serwis_sb_url"):
                    _c.update(serwis_sb_url=cloud.URL, serwis_sb_key=cloud.ANON_KEY)
                    _c.setdefault("serwis_base", "")
                    if not _c.get("serwis_base"):
                        _c["serwis_base"] = "https://djjuniord-boop.github.io/IntegraCRM/"
                    save_config(_c)
            except Exception:
                pass
        self.fonts = Fonts(self)
        self.title(f"Latex Serwis – kontrola eksportu zleceń  v{VERSION}")
        self.geometry("1000x820")
        try:
            self.state("zoomed")   # Windows: pełny ekran roboczy – więcej miejsca na wynik i mail
        except tk.TclError:
            pass
        self.minsize(860, 680)
        self.configure(bg=BG)
        set_icon(self)
        self._style()
        self.pdf_path = tk.StringVar()
        self.crm_img = None
        self.crm_rows = None     # raport .xlsx z „Listy kontrolne”
        self.crm_file = ""
        self.branch_vars = {}
        self._thumb = None
        self._logo = None
        self.result = None
        self.hist_index = None
        self._build()
        self.dnd_ok = dnd.enable(self, self.on_drop) if dnd else False
        self.bind("<Control-v>", self._on_ctrl_v)
        self.bind("<Control-V>", self._on_ctrl_v)
        shot = os.environ.get("INTEGRA_SHOT")   # tryb zrzutów ekranu (kontrola wyglądu w GitHub Actions)
        if shot:
            self.after(2500, self._screenshots, shot)
            return
        _c = load_config()
        if not self.session and not (_c["gmail_user"] and _c["gmail_app_password"]):   # po zalogowaniu maile wysyła serwer
            self.after(400, lambda: SettingsDialog(self))
        self.after(900, lambda: self.check_updates(manual=False))
        if self.session:
            self.after(30 * 60 * 1000, self._keep_session)
        self._stat("start")

    def _screenshots(self, out_dir):
        try:
            self._screenshots_inner(out_dir)
        except Exception:
            import traceback
            with open(f"{out_dir}/error.txt", "w", encoding="utf-8") as fh:
                fh.write(traceback.format_exc())
        finally:
            os._exit(0)

    def _simulate_drop(self, path):
        """Test: wysyła do okna komunikat WM_DROPFILES, jak przy upuszczeniu pliku z Eksploratora."""
        import ctypes
        import struct
        data = path.encode("utf-16-le") + b"\0\0\0\0"
        header = struct.pack("<IiiII", 20, 0, 0, 0, 1)        # DROPFILES: pFiles=20, pt, fNC, fWide=1
        k32 = ctypes.windll.kernel32
        k32.GlobalAlloc.restype = ctypes.c_void_p
        k32.GlobalLock.restype = ctypes.c_void_p
        k32.GlobalLock.argtypes = [ctypes.c_void_p]
        k32.GlobalUnlock.argtypes = [ctypes.c_void_p]
        h = k32.GlobalAlloc(0x0042, len(header) + len(data))   # GHND
        ptr = k32.GlobalLock(h)
        ctypes.memmove(ptr, header + data, len(header) + len(data))
        k32.GlobalUnlock(h)
        u32 = ctypes.windll.user32
        u32.PostMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]
        u32.PostMessageW(self.winfo_id(), 0x0233, h, 0)

    def _screenshots_inner(self, out_dir):
        from PIL import ImageGrab

        def grab(win, name):
            win.update()
            x, y = win.winfo_rootx(), win.winfo_rooty()
            ImageGrab.grab((x, y, x + win.winfo_width(), y + win.winfo_height())).save(f"{out_dir}/{name}.png")
        self.lift()
        self.attributes("-topmost", True)
        with open(f"{out_dir}/dnd.txt", "w", encoding="utf-8") as fh:
            fh.write(f"enable={self.dnd_ok}\n")
        if self.dnd_ok:
            self._simulate_drop(r"C:\Raporty\Integra zakończone 09.10.pdf")
            import time
            t_end = time.time() + 1.5
            while time.time() < t_end:
                self.update()
                time.sleep(0.05)
        grab(self, "1-kontrola")
        with open(f"{out_dir}/dnd.txt", "a", encoding="utf-8") as fh:
            fh.write(f"pdf_after_drop={self.pdf_path.get()}\n")
        self.set_chips(["DW12345", "WE7A071"], [("DX7806F", "DX78O6F")])
        self.set_banner("bad", "✖  W CRM brakuje 2 i 1 do weryfikacji z 12 zleceń. Mail jest gotowy.")
        self.subject.set("Brak zleceń w CRM – prośba o eksport")
        self.mail_body.insert("1.0", "Dzień dobry,\n\nw CRM brakuje zleceń o numerach: DW12345, WE7A071.\n")
        self.btn_send.set_enabled(True)
        grab(self, "2-wynik")
        mw = self.edit_mail_big()
        mw.attributes("-topmost", True)
        grab(mw, "6-mail-duzy")
        mw.destroy()
        self.show_tab("help")
        grab(self, "3-pomoc")
        self.show_tab("hist")
        grab(self, "5-historia")
        if "marza" in self.pages:
            self.show_tab("marza")
            grab(self, "7-marza")
        if "serwis" in self.pages:
            import time
            self.show_tab("serwis")
            t_end = time.time() + 60
            while time.time() < t_end and not self._serwis_hwnd:
                self.update()
                time.sleep(0.1)
            for _ in range(20):
                self.update()
                time.sleep(0.1)
            with open(f"{out_dir}/serwis_embed.txt", "w", encoding="utf-8") as fh:
                fh.write(f"embedded={bool(self._serwis_hwnd)}\nmsg={self.serwis_msg.cget('text')}\n")
            grab(self, "8-serwis")
            self.show_tab("hist")
            self.update()
            time.sleep(0.5)
            grab(self, "8b-serwis-ukryty")
            self.serwis_stop()
        d = SettingsDialog(self)
        d.attributes("-topmost", True)
        grab(d, "4-ustawienia")

    def _style(self):
        s = ttk.Style(self)
        try:
            s.theme_use("clam")
        except tk.TclError:
            pass
        f = self.fonts
        s.configure("TEntry", fieldbackground=SURFACE, bordercolor=LINE, lightcolor=LINE,
                    darkcolor=LINE, padding=4)
        s.map("TEntry", bordercolor=[("focus", RED)], lightcolor=[("focus", RED)])
        s.configure("TCheckbutton", background=SURFACE, foreground=INK, font=f.body)
        s.map("TCheckbutton", background=[("active", SURFACE)], indicatorcolor=[("selected", RED)])
        s.configure("Vertical.TScrollbar", background="#DDDDDD", troughcolor=BG, bordercolor=BG,
                    arrowcolor=MUTED, lightcolor="#DDDDDD", darkcolor="#DDDDDD")

    # ---------- układ ----------
    def _build(self):
        f = self.fonts
        head = tk.Frame(self, bg=SURFACE, padx=22, pady=8)
        head.pack(fill="x")
        logo_ok = False
        try:
            if (ASSETS / "logo.png").exists():
                self._logo = tk.PhotoImage(file=str(ASSETS / "logo.png"))
                tk.Label(head, image=self._logo, bg=SURFACE).pack(side="left")
                logo_ok = True
        except tk.TclError:
            pass
        if not logo_ok:
            tk.Label(head, text="LATEX", bg=SURFACE, fg=RED, font=(f.family, 20, "bold")).pack(side="left")
        titles = tk.Frame(head, bg=SURFACE)
        titles.pack(side="left", padx=(18, 0))
        tk.Label(titles, text="Kontrola eksportu zleceń", bg=SURFACE, fg=BLACK, font=f.h1).pack(anchor="w")
        tk.Label(titles, text=f"Integra 7 → CRM   ·   wersja {VERSION}", bg=SURFACE, fg=MUTED,
                 font=f.small).pack(anchor="w")
        FlatButton(head, "⚙  Ustawienia", lambda: SettingsDialog(self), "ghost", f.body, 14, 7).pack(side="right")
        if self.session:
            FlatButton(head, "Wyloguj", self.logout, "ghost", f.body, 14, 7).pack(side="right", padx=(0, 8))
            who = self.session.profile.get("name") or self.session.email
            tk.Label(head, text=f"{who}\n{'administrator' if self.session.is_admin else 'użytkownik'}",
                     bg=SURFACE, fg=MUTED, font=f.small, justify="right").pack(side="right", padx=12)
        tk.Frame(self, bg=RED, height=4).pack(fill="x")

        # zakładki jako przyciski (czytelniejsze niż systemowy Notebook)
        tabs = tk.Frame(self, bg=BLACK)
        tabs.pack(fill="x")
        self.pages, self.tab_btns = {}, {}
        holder = tk.Frame(self, bg=BG)
        holder.pack(fill="both", expand=True)
        shot = bool(os.environ.get("INTEGRA_SHOT"))
        can = (lambda m: shot or self.session.can(m)) if self.session else (lambda m: True)
        tab_list = []
        if can("crm"):
            tab_list += [("main", "KONTROLA"), ("hist", "HISTORIA")]
        if can("marza"):
            tab_list.append(("marza", "MARŻA"))
        if can("serwis"):
            tab_list.append(("serwis", "SERWIS QR  β"))
        if self.session and self.session.is_admin:
            tab_list.append(("users", "UŻYTKOWNICY"))
        tab_list.append(("help", "POMOC I WERSJE"))
        self.current_tab = tab_list[0][0]
        for key, label in tab_list:
            b = tk.Label(tabs, text=label, bg=BLACK, fg="#BBBBBB", font=f.label, padx=20, pady=9,
                         cursor="hand2")
            b.pack(side="left")
            b.bind("<Button-1>", lambda e, k=key: self.show_tab(k))
            self.tab_btns[key] = b
            self.pages[key] = tk.Frame(holder, bg=BG, padx=22, pady=10)
        if "main" in self.pages:
            self._build_main(self.pages["main"])
            self._build_history(self.pages["hist"])
        else:   # bez modułu kontroli – elementy używane przez inne funkcje okna
            self._build_main(tk.Frame(self))
            self._build_history(tk.Frame(self))
        self._build_help(self.pages["help"])
        if "users" in self.pages:
            self._build_users(self.pages["users"])
        if "marza" in self.pages:
            self._build_marza(self.pages["marza"])
        if "serwis" in self.pages:
            try:
                self._build_serwis(self.pages["serwis"])
            except Exception as e:   # beta nie może zablokować reszty programu
                tk.Label(self.pages["serwis"], text=f"Nie udało się wczytać zakładki SERWIS QR: {e}",
                         bg=BG, fg=RED, font=self.fonts.body).pack(anchor="w")
        self.show_tab(self.current_tab)

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
        cols = ("email", "name", "role", "modules", "branches", "active", "last", "ver")
        heads = ("E-mail", "Imię i nazwisko", "Rola", "Moduły", "Oddziały", "Status", "Ostatnie logowanie", "Wersja")
        widths = (220, 160, 100, 180, 260, 90, 140, 70)
        self.users_tv = ttk.Treeview(page, columns=cols, show="headings", height=18)
        for c, h, w in zip(cols, heads, widths):
            self.users_tv.heading(c, text=h)
            self.users_tv.column(c, width=w, anchor="w")
        self.users_tv.pack(fill="both", expand=True, pady=(6, 0))
        self.users_tv.bind("<Double-1>", lambda e: self._edit_user())
        tk.Label(page, text="Kliknij dwukrotnie użytkownika, żeby zmienić uprawnienia, hasło albo zablokować konto. "
                 "Administrator ma zawsze dostęp do wszystkich modułów i oddziałów.",
                 bg=BG, fg=MUTED, font=f.small).pack(anchor="w", pady=(6, 0))
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
            last = (u.get("last_seen") or "")[:16].replace("T", " ")
            self.users_tv.insert("", "end", iid=str(i), values=(
                u["email"], u.get("name") or "", "administrator" if adm else "użytkownik",
                "wszystkie" if adm else ", ".join(names.get(m, m) for m in u.get("modules") or []),
                "wszystkie" if adm else ", ".join(u.get("branches") or []),
                "aktywne" if u.get("active") else "ZABLOKOWANE", last or "nigdy", u.get("app_version") or ""))
        self.users_msg.config(text=info or f"Kont: {len(users)}", fg=OK if info else MUTED)

    def _edit_user(self):
        sel = self.users_tv.selection()
        if sel:
            UserDialog(self, self._users[int(sel[0])])

    def logout(self):
        if not messagebox.askyesno("Wyloguj", "Wylogować się? Program zostanie zamknięty."):
            return
        try:
            self.session.logout()
        except Exception:
            pass
        self._on_close() if hasattr(self, "_on_close") else self.destroy()

    def _build_history(self, page):
        f = self.fonts
        top = tk.Frame(page, bg=BG)
        top.pack(fill="x", pady=(0, 10))
        tk.Label(top, text="Historia sprawdzeń", bg=BG, fg=BLACK, font=f.h1).pack(side="left")
        FlatButton(top, "Otwórz w Excelu", self.open_history_file, "ghost", f.body, 14, 6).pack(side="right")
        FlatButton(top, "Odśwież", self.refresh_history, "ghost", f.body, 14, 6).pack(side="right", padx=8)
        box = card(page, padx=2, pady=2)
        box.pack(fill="both", expand=True)
        cols = ("data", "kto", "plik", "integra", "crm", "brakuje", "mail")
        s = ttk.Style(self)
        s.configure("H.Treeview", font=f.body, rowheight=26, background=SURFACE, fieldbackground=SURFACE)
        s.configure("H.Treeview.Heading", font=f.label, background=BG)
        s.map("H.Treeview", background=[("selected", RED)], foreground=[("selected", "white")])
        self.hist_tree = ttk.Treeview(box, columns=cols, show="headings", style="H.Treeview")
        for c, t, w in (("data", "Data", 130), ("kto", "Kto / oddział", 200), ("plik", "Plik PDF", 170),
                        ("integra", "Integra", 70),
                        ("crm", "CRM", 60), ("brakuje", "Brakuje w CRM", 260), ("mail", "Mail wysłany do", 200)):
            self.hist_tree.heading(c, text=t, anchor="w")
            self.hist_tree.column(c, width=w, anchor="w")
        sb = ttk.Scrollbar(box, command=self.hist_tree.yview)
        self.hist_tree.config(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.hist_tree.pack(fill="both", expand=True)
        tk.Label(page, text="Numery zgłoszone już wcześniej są oznaczane przy kolejnych sprawdzeniach "
                 "(„zgłoszony …”), żeby nie wysyłać ich ponownie bez potrzeby.",
                 bg=BG, fg=MUTED, font=f.small, wraplength=900, justify="left").pack(anchor="w", pady=(8, 0))
        self.refresh_history()

    def refresh_history(self):
        if history is None:
            return

        def work():   # historia może być w bazie – pobieranie w tle
            try:
                rows = history.read_all()
            except Exception as e:
                rows = [{"data": "", "plik_pdf": f"Nie udało się wczytać historii: {e}"}]
            self.after(0, self._show_history, rows)
        threading.Thread(target=work, daemon=True).start()

    def _show_history(self, rows):
        t = self.hist_tree
        t.delete(*t.get_children())
        for r in reversed(rows):
            who = " · ".join(x for x in (r.get("kto", ""), r.get("oddzialy", "")) if x)
            t.insert("", "end", values=(r.get("data", ""), who or "—", r.get("plik_pdf", ""), r.get("integra", ""),
                                        r.get("crm", ""), r.get("brakuje", "") or "—",
                                        r.get("mail_wyslany_do", "") or "—"))

    def open_history_file(self):
        if history is None:
            return
        import tempfile
        out = os.path.join(tempfile.gettempdir(), "IntegraCRM-historia.csv")

        def work():
            try:
                history.export_csv(out)
                os.startfile(out)   # Windows: otwiera w Excelu
            except Exception as e:
                self.after(0, lambda err=str(e): messagebox.showinfo("Historia", f"Nie udało się otworzyć historii:\n{err}"))
        threading.Thread(target=work, daemon=True).start()

    # ---------- SERWIS QR (beta) – panel osadzony w zakładce ----------
    def _build_serwis(self, page):
        f = self.fonts
        cfg = load_config()
        self._serwis_proc = None
        self._serwis_hwnd = 0
        self._serwis_gen = 0          # numer uruchomienia – stare sprawdzania po „Uruchom ponownie” same się kończą
        self._serwis_settings_open = False
        page.configure(padx=0, pady=0)
        bar = tk.Frame(page, bg=SURFACE, padx=16, pady=6, highlightthickness=1, highlightbackground=LINE)
        bar.pack(fill="x")
        tk.Label(bar, text="Historia serwisowa", bg=SURFACE, fg=BLACK, font=f.label).pack(side="left")
        tk.Label(bar, text=" BETA ", bg=WARN_BG, fg=WARN, font=f.small).pack(side="left", padx=8)
        self.serwis_banner = tk.Label(bar, text="", bg=SURFACE, fg=MUTED, font=f.small, anchor="w")
        self.serwis_banner.pack(side="left", padx=(8, 0), fill="x", expand=True)
        FlatButton(bar, "Uruchom ponownie", self.serwis_restart, "ghost", f.small, 10, 3).pack(side="right")
        self.btn_sv_settings = FlatButton(bar, "⚙  Ustawienia panelu", self.serwis_toggle_settings, "ghost", f.small, 10, 3)
        self.btn_sv_settings.pack(side="right", padx=(0, 8))

        # ustawienia (chowane) – przykrywają panel, gdy otwarte
        self.serwis_settings = box = tk.Frame(page, bg=BG, padx=22, pady=12)
        inner = card(box, padx=16, pady=12)
        inner.pack(fill="x")
        tk.Label(inner, text="Ustawienia panelu", bg=SURFACE, fg=BLACK, font=f.label).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        self.v_sv_base = tk.StringVar(value=cfg.get("serwis_base", ""))
        self.v_sv_url = tk.StringVar(value=cfg.get("serwis_sb_url", ""))
        self.v_sv_key = tk.StringVar(value=cfg.get("serwis_sb_key", ""))
        rows = (("Adres strony dla klientów (QR)", self.v_sv_base, "np. https://serwis.latex.net.pl/  – puste: kod QR "
                 "nie zadziała u klienta, panel działa normalnie"),
                ("Baza Supabase – adres", self.v_sv_url, "puste = tryb lokalny (dane w folderze programu na tym komputerze)"),
                ("Baza Supabase – klucz anon", self.v_sv_key, "klucz publiczny „anon” z Supabase → Project Settings → API"))
        for i, (lab, var, hint) in enumerate(rows):
            tk.Label(inner, text=lab, bg=SURFACE, fg=INK, font=f.body, anchor="w").grid(row=1 + 2 * i, column=0, sticky="w", pady=(4, 0))
            ttk.Entry(inner, textvariable=var, width=70, font=f.body).grid(row=1 + 2 * i, column=1, sticky="we", padx=(12, 0), pady=(4, 0), ipady=2)
            tk.Label(inner, text=hint, bg=SURFACE, fg=MUTED, font=f.small, anchor="w").grid(row=2 + 2 * i, column=1, sticky="w", padx=(12, 0))
        inner.grid_columnconfigure(1, weight=1)
        btns = tk.Frame(inner, bg=SURFACE)
        btns.grid(row=8, column=1, sticky="e", pady=(10, 0))
        FlatButton(btns, "Zamknij", self.serwis_toggle_settings, "ghost", f.body, 14, 6).pack(side="right")
        FlatButton(btns, "Zapisz ustawienia", self.serwis_save, "dark", f.body, 14, 6).pack(side="right", padx=8)
        info = card(box, padx=16, pady=12)
        info.pack(fill="x", pady=(10, 0))
        tk.Label(info, text="Ważne w wersji beta", bg=SURFACE, fg=BLACK, font=f.label).pack(anchor="w")
        for line in ("• Tryb lokalny: dane są w folderze programu (data\\serwis_webview) – w panelu używaj „Zapisz kopię” "
                     "(np. raz w tygodniu).",
                     "• Przenosząc program na inny komputer, skopiuj cały folder razem z „data” albo wczytaj kopię w panelu.",
                     "• Naklejki z prawdziwym kodem QR drukuj dopiero po ustawieniu adresu strony dla klientów.",
                     "• Zakładka jest widoczna tylko u osób, które włączą ją w Ustawieniach na kanale beta."):
            tk.Label(info, text=line, bg=SURFACE, fg=INK, font=f.small, anchor="w", justify="left",
                     wraplength=900).pack(anchor="w", pady=1)

        # miejsce na panel
        self.serwis_host = tk.Frame(page, bg=SURFACE)
        self.serwis_host.pack(fill="both", expand=True)
        self.serwis_msg = tk.Label(self.serwis_host, text="", bg=SURFACE, fg=MUTED, font=f.body, justify="center")
        self.serwis_msg.place(relx=0.5, rely=0.4, anchor="center")
        self.serwis_host.bind("<Configure>", lambda e: self._serwis_fit())
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.serwis_refresh()

    def _on_close(self):
        self.serwis_stop()
        try:
            import serwis_qr
            serwis_qr.clear_token()
        except Exception:
            pass
        self.destroy()

    def _keep_session(self):
        """Co 30 min odświeża logowanie (token ważny ok. 1 godz.) i przekazuje go panelowi SERWIS QR."""
        def work():
            try:
                self.session.refresh()
                if cloud.SESSION_FILE.exists():
                    cloud.remember(self.session)
                import serwis_qr
                if serwis_qr.TOKEN_FILE.exists():
                    serwis_qr.write_token(self.session.access)
            except Exception:
                pass
        threading.Thread(target=work, daemon=True).start()
        self.after(30 * 60 * 1000, self._keep_session)

    def serwis_refresh(self):
        import serwis_qr
        cfg = load_config()
        m = "chmura (Supabase)" if serwis_qr.mode(cfg) == "cloud" else "tryb lokalny"
        base = (cfg.get("serwis_base") or "").strip()
        txt = f"{m}  ·  " + (f"kody QR → {base}" if base else "⚠ brak adresu strony dla klientów (QR)")
        if not self._serwis_hwnd:
            self._serwis_banner("idle", txt)
        else:
            self._serwis_banner("ok", txt)

    def _serwis_banner(self, kind, text):
        fg = {"ok": OK, "warn": WARN, "bad": RED}.get(kind, MUTED)
        self.serwis_banner.config(text=text, fg=fg)

    def _serwis_msg(self, text, kind="idle"):
        fg = {"warn": WARN, "bad": RED}.get(kind, MUTED)
        self.serwis_msg.config(text=text, fg=fg)
        self.serwis_msg.lift()

    def serwis_on_show(self):
        """Wywoływane przy wejściu na zakładkę: uruchamia panel albo go pokazuje."""
        import embed_win
        if self._serwis_settings_open:
            return
        proc = self._serwis_proc
        if self._serwis_hwnd and embed_win.alive(self._serwis_hwnd):
            embed_win.show(self._serwis_hwnd, True)
            self._serwis_fit()
            return
        if proc is None or proc.poll() is not None:
            self.serwis_start()

    def serwis_on_hide(self):
        import embed_win
        if self._serwis_hwnd:
            embed_win.show(self._serwis_hwnd, False)

    def serwis_start(self):
        import time
        import serwis_qr
        import serwis_window
        why = serwis_window.is_available()
        if why:
            self._serwis_msg(why + "\n\nPobierz paczkę IntegraCRM-…-exe.zip z wydania „kanal-beta” na GitHubie,\n"
                             "rozpakuj do nowego folderu i skopiuj do niego swój folder „data”.", "warn")
            return
        cfg = load_config()
        try:
            if self.session:
                cfg["serwis_sso"] = True
                serwis_qr.write_token(self.session.access)
            serwis_qr.write_config(cfg)
            try:
                serwis_window.STATUS.unlink()
            except OSError:
                pass
            self._serwis_hwnd = 0
            self._serwis_gen += 1
            serwis_window.reset_log()
            self._serwis_proc = serwis_window.launch(embed=True)
            self._serwis_t0 = time.time()
            self._serwis_loaded_t = 0.0
            serwis_window.gui_log(f"start panelu #{self._serwis_gen}, pid {self._serwis_proc.pid}")
            self._stat("serwis_open")
            self._serwis_msg("Wczytywanie panelu…")
            gen = self._serwis_gen
            self.after(500, lambda: self._serwis_check_started(gen))
        except Exception as e:
            self._serwis_msg(f"Nie udało się uruchomić panelu:\n{e}", "bad")

    def serwis_stop(self):
        import serwis_window
        self._serwis_gen = getattr(self, "_serwis_gen", 0) + 1   # unieważnia zaplanowane sprawdzania
        proc = getattr(self, "_serwis_proc", None)
        if proc is not None:
            serwis_window.kill_tree(proc)   # razem z procesami Edge WebView2 – nic nie zostaje na pasku zadań
        self._serwis_proc = None
        self._serwis_hwnd = 0

    def serwis_restart(self):
        self.serwis_stop()
        if self._serwis_settings_open:
            self.serwis_toggle_settings()
        self.serwis_start()

    def _serwis_fit(self):
        import embed_win
        if self._serwis_hwnd:
            self.serwis_host.update_idletasks()
            embed_win.resize(self._serwis_hwnd, self.serwis_host.winfo_width(), self.serwis_host.winfo_height())

    def _serwis_check_started(self, gen):
        import time
        import embed_win
        import serwis_window
        proc = self._serwis_proc
        if proc is None or gen != self._serwis_gen:
            return
        st = serwis_window.read_status()
        state = st.get("state", "")
        waited = time.time() - self._serwis_t0
        code = proc.poll()
        if code is not None or state == "error":
            err = st.get("error") or f"kod zakończenia {code}"
            self._serwis_proc = None
            self._serwis_fail(err)
            return
        if state == "loaded":
            if not self._serwis_loaded_t:
                self._serwis_loaded_t = time.time()
            hwnd = embed_win.find_window(proc.pid, serwis_window.TITLE)
            if hwnd:
                serwis_window.gui_log(f"znaleziono okno panelu {hwnd:#x}, osadzam")
                self.serwis_host.update_idletasks()
                if embed_win.embed(hwnd, self.serwis_host.winfo_id(), self.serwis_host.winfo_width(),
                                   self.serwis_host.winfo_height()):
                    self._serwis_hwnd = hwnd
                    self._serwis_msg("")
                    if self.current_tab != "serwis" or self._serwis_settings_open:
                        embed_win.show(hwnd, False)
                    self.serwis_refresh()
                    serwis_window.gui_log("panel osadzony w zakładce")
                    self.after(2000, lambda: self._serwis_watch(gen))
                    return
                serwis_window.gui_log("osadzanie nie powiodło się")
            elif time.time() - self._serwis_loaded_t > 10:
                serwis_window.gui_log("panel wczytany, ale okna nie znaleziono: "
                                      + "; ".join(embed_win.list_windows(proc.pid)))
                self._serwis_fail("nie znaleziono okna panelu do osadzenia", kill=True)
                return
        if waited > 45:
            self._serwis_fail(f"przekroczony czas, etap: {state or 'start'}", kill=True)
            return
        label = {"": "uruchamianie…", "starting": "wczytywanie silnika…", "window": "tworzenie okna…",
                 "shown": "wczytywanie panelu…", "loaded": "osadzanie w programie…"}.get(state, state)
        self._serwis_msg(f"Wczytywanie panelu – {label}")
        self.after(400, lambda: self._serwis_check_started(gen))

    def _serwis_watch(self, gen):
        """Pilnuje, czy panel działa; gdy jego proces się zakończy – pokazuje komunikat."""
        import embed_win
        proc = self._serwis_proc
        if proc is None or gen != self._serwis_gen:   # po „Uruchom ponownie” stary strażnik kończy pracę
            return
        if proc.poll() is not None or not embed_win.alive(self._serwis_hwnd):
            self.serwis_stop()
            self._serwis_msg("Panel został zamknięty.\nKliknij „Uruchom ponownie” na pasku powyżej.", "warn")
            self.serwis_refresh()
            return
        self.after(2000, lambda: self._serwis_watch(gen))

    def _serwis_fail(self, err, kill=False):
        import serwis_window
        serwis_window.gui_log(f"błąd: {err}")
        if kill:
            self.serwis_stop()
        tail = serwis_window.log_tail(6)
        self._serwis_msg(f"Panel nie uruchomił się.\n\nPowód: {err}\n\n"
                         + (f"Dziennik (data\\serwis.log):\n{tail}\n\n" if tail else "")
                         + "Kliknij „Uruchom ponownie” na pasku powyżej.", "bad")

    def serwis_toggle_settings(self):
        import embed_win
        self._serwis_settings_open = not self._serwis_settings_open
        if self._serwis_settings_open:
            embed_win.show(self._serwis_hwnd, False)
            self.serwis_host.pack_forget()
            self.serwis_settings.pack(fill="both", expand=True)
            self.btn_sv_settings.config(text="✕  Zamknij ustawienia")
        else:
            self.serwis_settings.pack_forget()
            self.serwis_host.pack(fill="both", expand=True)
            self.btn_sv_settings.config(text="⚙  Ustawienia panelu")
            self.serwis_on_show()

    def _serwis_collect(self):
        import serwis_qr
        base, url, key = self.v_sv_base.get().strip(), self.v_sv_url.get().strip(), self.v_sv_key.get().strip()
        prob = serwis_qr.check_base(base) or serwis_qr.check_supabase(url, key)
        return {"serwis_base": base, "serwis_sb_url": url.rstrip("/"), "serwis_sb_key": key}, prob

    def serwis_save(self, quiet=False):
        import serwis_qr
        vals, prob = self._serwis_collect()
        if prob:
            messagebox.showwarning("SERWIS QR", prob)
            return False
        cfg = load_config()
        old_base = (cfg.get("serwis_base") or "").strip()
        if old_base and vals["serwis_base"] != old_base and not messagebox.askyesno(
                "SERWIS QR", "Zmieniasz adres strony dla klientów.\n\nNaklejki wydrukowane ze starym adresem "
                f"({old_base}) przestaną działać.\n\nZapisać nowy adres?"):
            return False
        changed = any(vals[k] != (cfg.get(k) or "").strip() for k in vals)
        cfg.update(vals)
        save_config(cfg)
        try:
            if self.session:
                cfg["serwis_sso"] = True
                serwis_qr.write_token(self.session.access)
            serwis_qr.write_config(cfg)
        except OSError as e:
            messagebox.showerror("SERWIS QR", f"Nie udało się zapisać ustawień panelu:\n{e}")
            return False
        self.serwis_refresh()
        if changed and self._serwis_proc is not None:   # panel musi wczytać nowe ustawienia
            self.serwis_stop()
        if not quiet:
            messagebox.showinfo("SERWIS QR", "Zapisano. Panel uruchomi się z nowymi ustawieniami po zamknięciu ustawień.")
        return True

    # ---------- MARŻA ----------
    def _build_marza(self, page):
        f = self.fonts
        self.marza_busy = False
        top = card(page, padx=16, pady=12)
        top.pack(fill="x")
        h = tk.Frame(top, bg=SURFACE)
        h.pack(fill="x")
        tk.Label(h, text="Kalkulator marży – Wrocław + Opole", bg=SURFACE, fg=BLACK, font=f.h2).pack(side="left")
        FlatButton(h, "Zmień folder…", self.marza_pick_folder, "ghost", f.small, 10, 4).pack(side="right")
        self.marza_folder_lbl = tk.Label(top, text="", bg=SURFACE, fg=MUTED, font=f.small, anchor="w", justify="left")
        self.marza_folder_lbl.pack(fill="x", pady=(4, 8))
        links = tk.Frame(top, bg=SURFACE)
        links.pack(anchor="w")
        for txt, rel in (("Kalkulator Wrocław", ("Wrocław", "kalkulator_marzy_Wroclaw.xlsx")),
                         ("Kalkulator Opole", ("Opole", "kalkulator_marzy_Opole.xlsx")),
                         ("Folder LATEX Wyniki", ())):
            FlatButton(links, txt, lambda r=rel: self.marza_open(*r), "ghost", f.small, 10, 4).pack(side="left", padx=(0, 8))

        drop = card(page, padx=16, pady=12)
        drop.pack(fill="x", pady=10)
        tk.Label(drop, text="Raporty sprzedaży z Integry („Raport sprzedaży towarów i usług”, od 1. dnia miesiąca)",
                 bg=SURFACE, fg=BLACK, font=f.label).pack(anchor="w")
        self.marza_drop = tk.Label(drop, text="Przeciągnij tutaj PDF-y z Wrocławia i Opola albo kliknij, aby wybrać\n"
                                   "(oddział jest rozpoznawany z treści raportu)",
                                   bg=BG, fg=MUTED, font=f.body, pady=10, cursor="hand2", justify="center")
        self.marza_drop.pack(fill="x", pady=(8, 6))
        self.marza_drop.bind("<Button-1>", lambda e: self.marza_pick_files())
        qh = tk.Frame(drop, bg=SURFACE)
        qh.pack(fill="x")
        tk.Label(qh, text="Kolejka (najwyżej 1 raport na oddział):", bg=SURFACE, fg=MUTED, font=f.small).pack(side="left")
        FlatButton(qh, "Wyczyść kolejkę", self.marza_clear, "ghost", f.small, 8, 2).pack(side="right")
        self.marza_queue = tk.Frame(drop, bg=SURFACE)
        self.marza_queue.pack(fill="x", pady=(4, 0))

        self.btn_marza = FlatButton(page, "AKTUALIZUJ WSZYSTKO", self.marza_run, "primary", f.big, 18, 8)
        self.btn_marza.pack(fill="x", pady=(0, 8))
        self.marza_banner = tk.Label(page, text="", bg=SURFACE, fg=MUTED, font=f.label, anchor="w", padx=16, pady=8,
                                     highlightthickness=1, highlightbackground=LINE, justify="left", wraplength=900)
        self.marza_banner.pack(fill="x")
        out = card(page, padx=10, pady=8)
        out.pack(fill="both", expand=True, pady=(8, 0))
        self.marza_log = tk.Text(out, font=f.mono, bg=SURFACE, fg=INK, relief="flat", wrap="word", height=8)
        sb = ttk.Scrollbar(out, command=self.marza_log.yview)
        self.marza_log.config(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.marza_log.pack(fill="both", expand=True)
        self._marza_autodetect()
        self.marza_refresh()

    def _marza_autodetect(self):
        """Jeśli folder nie jest ustawiony, szuka „LATEX Wyniki” w typowych miejscach."""
        if self._marza_root():
            return
        home = os.path.expanduser("~")
        bases = [os.path.join(home, x) for x in ("Desktop", "Pulpit", "Documents", "Dokumenty", "Downloads",
                                                   os.path.join("OneDrive", "Desktop"),
                                                   os.path.join("OneDrive", "Pulpit"), "")]
        bases += [r"G:\Mój dysk", r"G:\My Drive", "C:\\", "D:\\"]
        from marza import runner
        for b in bases:
            cand = os.path.join(b, "LATEX Wyniki")
            if os.path.isdir(cand) and not runner.check_folder(cand):
                cfg = load_config()
                cfg["marza_folder"] = cand
                save_config(cfg)
                return

    def _marza_root(self):
        return load_config().get("marza_folder", "")

    def marza_refresh(self):
        from marza import runner
        root = self._marza_root()
        prob = runner.check_folder(root)
        self.marza_folder_lbl.config(text=(f"Folder: {root}" if not prob else "⚠ " + prob),
                                     fg=MUTED if not prob else WARN)
        missing = runner.deps_ok()
        if missing:
            self.marza_set_banner("warn", f"⚠ Ta wersja IntegraCRM.exe nie ma bibliotek: {missing}. "
                                  "Pobierz najnowszą paczkę .exe z GitHuba.")
        elif prob:
            self.marza_set_banner("warn", "⚠ Wskaż folder „LATEX Wyniki” (przycisk „Zmień folder…”).")
        else:
            self.marza_set_banner("idle", "Dodaj raporty i kliknij „AKTUALIZUJ WSZYSTKO”. "
                                  "Bez nowych raportów odświeżony zostanie tylko podgląd dla handlowców.")
        self.marza_refresh_pending_only()

    def marza_set_banner(self, kind, text):
        colors = {"idle": (SURFACE, MUTED), "ok": (OK_BG, OK), "warn": (WARN_BG, WARN),
                  "bad": (ERR_BG, RED_DARK), "busy": (SURFACE, INK)}
        bg, fg = colors[kind]
        self.marza_banner.config(text=text, bg=bg, fg=fg)

    def marza_pick_folder(self):
        d = filedialog.askdirectory(title="Wskaż folder „LATEX Wyniki”")
        if d:
            cfg = load_config()
            cfg["marza_folder"] = d
            save_config(cfg)
            self.marza_refresh()

    def marza_open(self, *rel):
        root = self._marza_root()
        if not root:
            if messagebox.askyesno("MARŻA", "Nie wskazano jeszcze folderu „LATEX Wyniki”.\n\nWskazać go teraz?"):
                self.marza_pick_folder()
            root = self._marza_root()
            if not root:
                return
        path = os.path.join(root, *rel)
        try:
            os.startfile(path)
        except Exception as e:
            messagebox.showinfo("Otwórz", f"{path}\n\n{e}")

    def marza_pick_files(self):
        fs = filedialog.askopenfilenames(filetypes=[("PDF", "*.pdf")])
        if fs:
            self.marza_add(list(fs))

    def marza_add(self, files):
        from marza import runner
        root = self._marza_root()
        prob = runner.check_folder(root)
        if prob:
            messagebox.showwarning("MARŻA", prob)
            return
        def ask_replace(branch, old):
            return messagebox.askyesno("MARŻA", f"W kolejce jest już raport dla oddziału "
                                       f"{runner.BRANCH_NAMES[branch]}:\n{old}\n\nZastąpić go nowym?")
        added, rejected = runner.add_reports(root, files, ask_replace)
        self.marza_refresh_pending_only()
        if rejected:
            messagebox.showwarning("MARŻA – nie dodano",
                                   "\n\n".join(f"{n}\n→ {why}" for n, why in rejected))
        if added:
            self.marza_set_banner("idle", "Dodano: " + ", ".join(f"{n} ({runner.BRANCH_NAMES[b]})" for n, b in added)
                                  + ". Kliknij „AKTUALIZUJ WSZYSTKO”.")

    def marza_run(self):
        from marza import runner
        if self.marza_busy:
            return
        root = self._marza_root()
        prob = runner.check_folder(root) or (("Brak bibliotek: " + runner.deps_ok()) if runner.deps_ok() else "")
        if prob:
            messagebox.showwarning("MARŻA", prob)
            return
        self.marza_busy = True
        self.btn_marza.set_enabled(False, "AKTUALIZUJĘ…")
        self.marza_log.delete("1.0", "end")
        self.marza_set_banner("busy", "Trwa aktualizacja… (rozdzielanie raportów, kalkulatory, podgląd, e-maile)")
        threading.Thread(target=self._marza_work, args=(root,), daemon=True).start()

    def _marza_ask(self, question):
        """Pytanie z wątku roboczego – odpowiedź z okna."""
        ev, box = threading.Event(), {}

        def _q():
            box["a"] = messagebox.askyesno("MARŻA – potwierdzenie", question + "\n\nZapisać mimo to?")
            ev.set()
        self.after(0, _q)
        ev.wait()
        return box.get("a", False)

    def _marza_work(self, root):
        from marza import runner

        def logline(line):
            self.after(0, lambda l=line: (self.marza_log.insert("end", l + "\n"), self.marza_log.see("end")))
        try:
            res = runner.run_all(root, load_config(), log=logline, ask=self._marza_ask)
            n = sum(res.get("counts", {}).values())
            self._stat("marza", n_integra=n)
            if res["ok"]:
                self.after(0, self.marza_set_banner, "ok", f"✔  Gotowe – przetworzono raportów: {n}. Szczegóły poniżej.")
            else:
                self.after(0, self.marza_set_banner, "warn", "⚠  Są uwagi – przeczytaj podsumowanie poniżej.")
        except Exception as e:
            self._report(e, "kalkulator marży")
            self.after(0, self.marza_set_banner, "bad", f"✖  Błąd: {e}")
        finally:
            def done():
                self.marza_busy = False
                self.btn_marza.set_enabled(True, "AKTUALIZUJ WSZYSTKO")
                try:
                    self.marza_refresh_pending_only()
                except Exception:
                    pass
            self.after(0, done)

    def marza_refresh_pending_only(self):
        from marza import runner
        f = self.fonts
        for w in self.marza_queue.winfo_children():
            w.destroy()
        root = self._marza_root()
        items = runner.pending_info(root) if root and not runner.check_folder(root) else []
        if not items:
            tk.Label(self.marza_queue, text="Brak raportów w kolejce.", bg=SURFACE, fg=MUTED, font=f.small
                     ).pack(anchor="w")
            return
        for name, branch in items:
            row = tk.Frame(self.marza_queue, bg=BG)
            row.pack(fill="x", pady=2)
            tag = runner.BRANCH_NAMES.get(branch, "NIEROZPOZNANY")
            tk.Label(row, text=f" {tag} ", bg=(BLACK if branch else RED), fg="white", font=f.small
                     ).pack(side="left", padx=(6, 8), pady=4)
            tk.Label(row, text=name, bg=BG, fg=INK, font=f.body).pack(side="left")
            FlatButton(row, "✕ Usuń", lambda n=name: self.marza_remove(n), "ghost", f.small, 8, 2
                       ).pack(side="right", padx=6, pady=3)

    def marza_remove(self, name):
        from marza import runner
        if self.marza_busy:
            return
        runner.remove_pending(self._marza_root(), name)
        self.marza_refresh_pending_only()
        self._marza_banner_after_change(f"Usunięto z kolejki: {name}.")

    def marza_clear(self):
        from marza import runner
        if self.marza_busy:
            return
        root = self._marza_root()
        for n in runner.pending(root) if root else []:
            runner.remove_pending(root, n)
        self.marza_refresh_pending_only()
        self._marza_banner_after_change("Kolejka wyczyszczona.")

    def _marza_banner_after_change(self, msg):
        from marza import runner
        root = self._marza_root()
        left = runner.pending_info(root) if root and not runner.check_folder(root) else []
        if left:
            names = ", ".join(f"{n} ({runner.BRANCH_NAMES.get(b, '?')})" for n, b in left)
            self.marza_set_banner("idle", f"{msg} W kolejce: {names}. Kliknij „AKTUALIZUJ WSZYSTKO”.")
        else:
            self.marza_set_banner("idle", f"{msg} Kolejka pusta – dodaj raporty sprzedaży (PDF).")

    def show_tab(self, key):
        for k, p in self.pages.items():
            p.pack_forget()
            self.tab_btns[k].config(fg="#BBBBBB", bg=BLACK)
        self.current_tab = key
        self.pages[key].pack(fill="both", expand=True)
        self.tab_btns[key].config(fg="white", bg=RED)
        if "serwis" in self.pages and hasattr(self, "serwis_host"):
            try:
                if key == "serwis":
                    self.after(50, self.serwis_on_show)
                else:
                    self.serwis_on_hide()
            except Exception:
                pass

    def _build_main(self, page):
        f = self.fonts
        steps = tk.Frame(page, bg=BG)
        steps.pack(fill="x")
        steps.columnconfigure(0, weight=1, uniform="s")
        steps.columnconfigure(1, weight=1, uniform="s")

        # krok 1 – PDF
        c1 = card(steps, padx=14, pady=10)
        c1.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        h = tk.Frame(c1, bg=SURFACE)
        h.pack(fill="x")
        step_badge(h, 1, f).pack(side="left")
        tk.Label(h, text="Raport z Integra 7 (PDF)", bg=SURFACE, fg=BLACK, font=f.h2).pack(side="left", padx=8)
        self.pdf_box = tk.Label(c1, text="Przeciągnij tutaj plik PDF\nalbo kliknij, aby wybrać", bg=BG, fg=MUTED, font=f.body, anchor="w",
                                padx=12, pady=6, cursor="hand2", justify="center")
        self.pdf_box.pack(fill="x", pady=(8, 8))
        self.pdf_box.bind("<Button-1>", lambda e: self.pick_pdf())
        FlatButton(c1, "Wybierz PDF", self.pick_pdf, "dark", f.body, 14, 6).pack(anchor="w")

        # krok 2 – CRM
        c2 = card(steps, padx=14, pady=10)
        c2.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        h = tk.Frame(c2, bg=SURFACE)
        h.pack(fill="x")
        step_badge(h, 2, f).pack(side="left")
        tk.Label(h, text="Dane z CRM – raport lub wycinek", bg=SURFACE, fg=BLACK, font=f.h2).pack(side="left", padx=8)
        self.preview = tk.Label(c2, text="Przeciągnij raport .xlsx z „Listy kontrolne”\n"
                                "albo naciśnij Ctrl+V po zrobieniu wycinka (Win+Shift+S)",
                                bg=BG, fg=MUTED, font=f.body, pady=6, cursor="hand2", justify="center")
        self.preview.pack(fill="x", pady=(8, 8))
        self.preview.bind("<Button-1>", lambda e: self.paste())
        r = tk.Frame(c2, bg=SURFACE)
        r.pack(fill="x")
        FlatButton(r, "Raport z CRM (.xlsx)…", self.pick_report, "dark", f.body, 14, 6).pack(side="left")
        FlatButton(r, "Wklej wycinek", self.paste, "ghost", f.body, 12, 6).pack(side="left", padx=8)
        FlatButton(r, "Obraz z pliku…", self.pick_img, "ghost", f.body, 12, 6).pack(side="left")
        bl = tk.Frame(c2, bg=SURFACE)
        bl.pack(fill="x", pady=(8, 0))
        tk.Label(bl, text="Sprawdzaj serwisy:", bg=SURFACE, fg=MUTED, font=f.small).pack(side="left")
        self.branch_box = tk.Frame(bl, bg=SURFACE)
        self.branch_box.pack(side="left", padx=(6, 0))
        self._build_branches(crm_report.BRANCHES)

        # krok 3 – sprawdź
        self.btn_check = FlatButton(page, "SPRAWDŹ", self.check, "primary", f.big, 18, 8)
        self.btn_check.pack(fill="x", pady=(10, 8))

        # wynik
        self.banner = tk.Label(page, text="Wybierz PDF i wklej wycinek z CRM, potem kliknij „Sprawdź”.",
                               bg=SURFACE, fg=MUTED, font=f.label, anchor="w", padx=16, pady=8,
                               highlightthickness=1, highlightbackground=LINE, justify="left", wraplength=900)
        self.banner.pack(fill="x")

        bottom = tk.Frame(page, bg=BG)
        bottom.pack(fill="both", expand=True, pady=(8, 0))
        bottom.columnconfigure(0, weight=2, uniform="b")
        bottom.columnconfigure(1, weight=3, uniform="b")
        bottom.rowconfigure(0, weight=1)

        # lewa kolumna – numery
        left = card(bottom, padx=14, pady=10)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        FlatButton(left, "Szczegóły odczytu…", self.show_details, "ghost", f.small, 10, 4
                   ).pack(side="bottom", anchor="w", pady=(6, 0))
        lh = tk.Frame(left, bg=SURFACE)
        lh.pack(fill="x")
        tk.Label(lh, text="Brakuje w CRM", bg=SURFACE, fg=BLACK, font=f.h2).pack(side="left")
        self.btn_copy_all = FlatButton(lh, "Kopiuj wszystkie", self.copy_all, "ghost", f.small, 10, 4)
        self.btn_copy_all.pack(side="right")
        tk.Label(left, text="Kliknij numer, aby go skopiować", bg=SURFACE, fg=MUTED, font=f.small
                 ).pack(anchor="w", pady=(2, 0))
        self.chips = tk.Frame(left, bg=SURFACE)
        self.chips.pack(fill="x", pady=(6, 6))
        self.copy_info = tk.Label(left, text="", bg=SURFACE, fg=OK, font=f.small)
        self.copy_info.pack(anchor="w")
        # pełny dziennik w osobnym, dużym oknie (tutaj tylko przechowywany)
        self.log = tk.Text(self, font=f.mono)

        # prawa kolumna – mail
        right = card(bottom, padx=14, pady=10)
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        hr = tk.Frame(right, bg=SURFACE)
        hr.pack(fill="x")
        step_badge(hr, 3, f).pack(side="left")
        tk.Label(hr, text="Mail do handlowców", bg=SURFACE, fg=BLACK, font=f.h2).pack(side="left", padx=8)
        tk.Label(right, text="Temat", bg=SURFACE, fg=MUTED, font=f.small).pack(anchor="w", pady=(6, 2))
        self.subject = tk.StringVar()
        ttk.Entry(right, textvariable=self.subject, font=f.body).pack(fill="x", ipady=2)
        th = tk.Frame(right, bg=SURFACE)
        th.pack(fill="x", pady=(8, 2))
        tk.Label(th, text="Treść (możesz poprawić przed wysłaniem)", bg=SURFACE, fg=MUTED,
                 font=f.small).pack(side="left")
        FlatButton(th, "⤢  Powiększ", self.edit_mail_big, "ghost", f.small, 10, 3).pack(side="right")
        self.mail_body = tk.Text(right, height=8, font=f.body, bg=SURFACE, fg=INK, relief="flat",
                                 wrap="word", highlightthickness=1, highlightbackground=LINE,
                                 highlightcolor=RED, padx=8, pady=6)
        self.btn_send = FlatButton(right, "Wyślij maila", self.send_mail, "dark", f.btn, 18, 8)
        self.btn_send.pack(side="bottom", anchor="e", pady=(8, 0))   # zawsze widoczny
        self.mail_body.pack(fill="both", expand=True)
        self.btn_send.set_enabled(False)

    def _build_help(self, page):
        f = self.fonts
        top = card(page, padx=18, pady=14)
        top.pack(fill="x")
        tk.Label(top, text=f"Wersja {VERSION}", bg=SURFACE, fg=BLACK, font=f.h1).pack(anchor="w")
        tk.Label(top, text=f"wydana {RELEASED}", bg=SURFACE, fg=MUTED, font=f.small).pack(anchor="w")
        self.upd_status = tk.Label(top, text="", bg=SURFACE, fg=INK, font=f.body, anchor="w", justify="left")
        self.upd_status.pack(fill="x", pady=(8, 8))
        r = tk.Frame(top, bg=SURFACE)
        r.pack(anchor="w")
        self.btn_update = FlatButton(r, "Sprawdź aktualizacje", lambda: self.check_updates(manual=True),
                                     "primary", f.body, 14, 6)
        self.btn_update.pack(side="left")
        FlatButton(r, "Przywróć poprzednią wersję", self.rollback, "ghost", f.body, 14, 6).pack(side="left", padx=8)

        tk.Label(top, text="Prywatność: " + STATS_INFO, bg=SURFACE, fg=MUTED, font=f.small,
                 wraplength=880, justify="left").pack(anchor="w", pady=(10, 0))
        how = card(page, padx=18, pady=14)
        how.pack(fill="x", pady=12)
        tk.Label(how, text="Jak używać", bg=SURFACE, fg=BLACK, font=f.h2).pack(anchor="w", pady=(0, 8))
        for i, (t, d) in enumerate(HELP_STEPS, 1):
            row = tk.Frame(how, bg=SURFACE)
            row.pack(fill="x", pady=3)
            step_badge(row, i, f).pack(side="left", anchor="n")
            tx = tk.Frame(row, bg=SURFACE)
            tx.pack(side="left", padx=10, fill="x")
            tk.Label(tx, text=t, bg=SURFACE, fg=BLACK, font=f.label).pack(anchor="w")
            tk.Label(tx, text=d, bg=SURFACE, fg=INK, font=f.body, wraplength=780, justify="left").pack(anchor="w")

        log = card(page, padx=18, pady=14)
        log.pack(fill="both", expand=True)
        tk.Label(log, text="Historia zmian", bg=SURFACE, fg=BLACK, font=f.h2).pack(anchor="w", pady=(0, 6))
        box = tk.Text(log, font=f.body, wrap="word", relief="flat", bg=SURFACE, fg=INK, padx=2)
        sb = ttk.Scrollbar(log, command=box.yview)
        box.config(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        box.pack(fill="both", expand=True)
        box.tag_config("ver", font=f.label, foreground=RED, spacing1=8)
        box.tag_config("date", foreground=MUTED, font=f.small)
        for e in CHANGELOG:
            box.insert("end", f"Wersja {e['version']}", "ver")
            box.insert("end", f"   {e['date']}\n", "date")
            for ch in e["changes"]:
                box.insert("end", f"  •  {ch}\n")
        box.config(state="disabled")

    # ---------- wynik ----------
    def set_banner(self, kind, text):
        colors = {"idle": (SURFACE, MUTED), "ok": (OK_BG, OK), "warn": (WARN_BG, WARN),
                  "bad": (ERR_BG, RED_DARK), "busy": (SURFACE, INK)}
        bg, fg = colors[kind]
        self.banner.config(text=text, bg=bg, fg=fg)

    def copy_text(self, text, info=None):
        self.clipboard_clear()
        self.clipboard_append(text)
        self.copy_info.config(text=info or f"✔ Skopiowano: {text}")
        self.after(3000, lambda: self.copy_info.config(text=""))

    def copy_all(self):
        if not self.result or not (self.result[0] or self.result[1]):
            self.copy_info.config(text="Nie ma numerów do skopiowania.")
            return
        allp = list(self.result[0]) + [a for a, _ in self.result[1]]
        self.copy_text("\n".join(allp), f"✔ Skopiowano {len(allp)} numer(y) – każdy w osobnej linii")

    def _text_window(self, title, content, editable=False, on_save=None):
        f = self.fonts
        w = tk.Toplevel(self)
        w.title(title)
        w.geometry("900x620")
        w.configure(bg=SURFACE)
        w.transient(self)
        set_icon(w)
        tk.Frame(w, bg=RED, height=4).pack(fill="x")
        bar = tk.Frame(w, bg=SURFACE, padx=14, pady=10)
        bar.pack(side="bottom", fill="x")
        box = tk.Frame(w, bg=SURFACE, padx=14, pady=10)
        box.pack(fill="both", expand=True)
        t = tk.Text(box, font=f.mono if not editable else (f.family, 11), wrap="word", bg=SURFACE, fg=INK,
                    relief="flat", highlightthickness=1, highlightbackground=LINE, padx=10, pady=8)
        sb = ttk.Scrollbar(box, command=t.yview)
        t.config(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        t.pack(fill="both", expand=True)
        t.insert("1.0", content)
        if not editable:
            t.config(state="disabled")
        FlatButton(bar, "Kopiuj całość", lambda: self.copy_text(t.get("1.0", "end").strip(), "✔ Skopiowano tekst"),
                   "ghost", f.body, 12, 5).pack(side="left")
        if editable:
            def save():
                on_save(t.get("1.0", "end").strip())
                w.destroy()
            FlatButton(bar, "Zapisz zmiany", save, "primary", f.label, 16, 5).pack(side="right")
            FlatButton(bar, "Anuluj", w.destroy, "ghost", f.body, 12, 5).pack(side="right", padx=8)
        else:
            FlatButton(bar, "Zamknij", w.destroy, "dark", f.body, 14, 5).pack(side="right")
        t.focus_set()
        return w

    def show_details(self):
        content = self.log.get("1.0", "end").strip() or "Brak szczegółów – najpierw kliknij „Sprawdź”."
        self._text_window("Szczegóły odczytu", content)

    def edit_mail_big(self):
        def save(txt):
            self.mail_body.delete("1.0", "end")
            self.mail_body.insert("1.0", txt)
        return self._text_window(f"Treść maila – {self.subject.get() or 'bez tematu'}",
                          self.mail_body.get("1.0", "end").strip(), editable=True, on_save=save)

    def set_chips(self, missing, uncertain):
        for w in self.chips.winfo_children():
            w.destroy()
        f = self.fonts
        if not missing and not uncertain:
            tk.Label(self.chips, text="—", bg=SURFACE, fg=MUTED, font=f.body).pack(anchor="w")
            return
        wrap = tk.Frame(self.chips, bg=SURFACE)
        wrap.pack(fill="x")
        col = 0
        reg = history.reported() if history else {}
        for p in missing:
            cell = tk.Frame(wrap, bg=SURFACE)
            cell.grid(row=col // 3, column=col % 3, padx=(0, 6), pady=3, sticky="w")
            chip = tk.Label(cell, text=p, bg=RED, fg="white", font=(f.family, 11, "bold"), padx=10, pady=4,
                            cursor="hand2")
            chip.pack(anchor="w")
            chip.bind("<Button-1>", lambda e, v=p: self.copy_text(v))
            chip.bind("<Enter>", lambda e, w=chip: w.config(bg=RED_DARK))
            chip.bind("<Leave>", lambda e, w=chip: w.config(bg=RED))
            if p in reg:
                tk.Label(cell, text=f"zgłoszony {reg[p]}", bg=SURFACE, fg=MUTED, font=f.small).pack(anchor="w")
            col += 1
        if uncertain:
            tk.Label(self.chips, text="Do weryfikacji (podobny numer w CRM):", bg=SURFACE, fg=WARN,
                     font=f.small).pack(anchor="w", pady=(8, 2))
            for a, b in uncertain:
                u = tk.Label(self.chips, text=f"{a}  ≈  {b}", bg=WARN_BG, fg=WARN, font=f.label, padx=8, pady=3,
                             cursor="hand2")
                u.pack(anchor="w", pady=2)
                u.bind("<Button-1>", lambda e, v=a: self.copy_text(v))

    # ---------- aktualizacje ----------
    def set_update_status(self, text):
        self.upd_status.config(text=text)

    def check_updates(self, manual: bool):
        src = update_source(load_config())
        if not src:
            self.set_update_status("Aktualizacje wyłączone – nie ustawiono źródła (Ustawienia).")
            if manual:
                messagebox.showinfo("Aktualizacje", "Nie ustawiono źródła aktualizacji.\nWpisz je w Ustawieniach.")
            return
        self.set_update_status("Sprawdzam aktualizacje…")
        threading.Thread(target=self._update_worker, args=(src, manual), daemon=True).start()

    def _update_worker(self, src, manual):
        try:
            m, newer = updater.check(src)
            self.after(0, self._update_checked, m, newer, manual, None)
        except Exception as e:
            if manual:
                self._report(e, "sprawdzanie aktualizacji")
            self.after(0, self._update_checked, None, False, manual, e)

    def _update_checked(self, m, newer, manual, err):
        if err:
            self.set_update_status(f"Nie udało się sprawdzić aktualizacji: {err}")
            if manual:
                messagebox.showerror("Aktualizacje", f"Nie udało się sprawdzić aktualizacji:\n{err}")
            return
        if not newer:
            self.set_update_status(f"✔ Masz najnowszą wersję ({VERSION}).")
            if manual:
                messagebox.showinfo("Aktualizacje", f"Masz najnowszą wersję ({VERSION}).")
            return
        notes = "\n".join("• " + n for n in m.get("notes", []))
        messagebox.showinfo("Aktualizacja", f"Dostępna nowa wersja {m['version']}.\n"
                            "Program zaktualizuje się teraz i uruchomi ponownie.\n\n" + notes)
        self.set_update_status(f"Aktualizuję do wersji {m['version']}…")
        self.btn_update.set_enabled(False)
        threading.Thread(target=self._apply_worker, args=(m,), daemon=True).start()

    def _apply_worker(self, m):
        try:
            updater.apply(m)
            self.after(0, self._restart)
        except Exception as e:
            self._report(e, "instalacja aktualizacji")
            self.after(0, self._apply_failed, e)

    def _restart(self):
        self.destroy()
        updater.restart()

    def _apply_failed(self, e):
        self.btn_update.set_enabled(True)
        self.set_update_status(f"Aktualizacja nie powiodła się: {e}")
        messagebox.showerror("Aktualizacja", f"Aktualizacja nie powiodła się:\n{e}\n\n"
                             f"Program działa dalej w wersji {VERSION}.")

    def rollback(self):
        if not updater.has_backup():
            messagebox.showinfo("Przywracanie", "Brak zapisanej poprzedniej wersji.")
            return
        if not messagebox.askyesno("Przywracanie", "Przywrócić poprzednią wersję programu?\n"
                                   "Program uruchomi się ponownie."):
            return
        try:
            updater.rollback(pin=True)
        except Exception as e:
            self._report(e, "przywracanie wersji")
            messagebox.showerror("Przywracanie", f"Nie udało się przywrócić:\n{e}")
            return
        self._restart()

    def _report(self, exc, where):
        if stats is not None:
            try:
                stats.report_exception(exc, where, load_config())
            except Exception:
                pass

    def report_callback_exception(self, exc, val, tb):
        """Nieobsłużony błąd w oknie: zapis do data/error.log, zgłoszenie i komunikat zamiast cichej awarii."""
        import datetime
        import traceback
        try:
            paths.DATA_DIR.mkdir(parents=True, exist_ok=True)
            with open(paths.LOG_PATH, "a", encoding="utf-8") as f:
                f.write(f"\n[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}]\n"
                        + "".join(traceback.format_exception(exc, val, tb)))
        except OSError:
            pass
        self._report(val, "okno programu")
        try:
            messagebox.showerror("Błąd", f"Wystąpił nieoczekiwany błąd:\n{val}\n\nZostał zapisany i zgłoszony autorowi.")
        except Exception:
            pass

    def _stat(self, name, **values):
        if stats is not None:
            try:
                stats.event(name, load_config(), **values)
            except Exception:
                pass

    def _on_ctrl_v(self, event):
        # w polach tekstowych (temat, treść maila) Ctrl+V ma wklejać tekst, nie obraz
        if isinstance(event.widget, (tk.Entry, ttk.Entry, tk.Text)):
            return None
        self.paste()
        return "break"

    # ---------- pliki / schowek ----------
    def pick_pdf(self):
        p = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf")])
        if p:
            self.set_pdf(p)

    def set_pdf(self, p):
        self.pdf_path.set(p)
        name = p.replace("\\", "/").split("/")[-1]
        self.pdf_box.config(text=f"✔  {name}", fg=OK, bg=OK_BG)

    def on_drop(self, files):
        """Upuszczone pliki: PDF → krok 1, obraz → krok 2 (na zakładce MARŻA – raporty marży)."""
        if getattr(self, "current_tab", "") == "marza":
            self.marza_add(files)
            return
        used = False
        for fp in files:
            low = fp.lower()
            if low.endswith(".pdf"):
                self.set_pdf(fp)
                used = True
            elif low.endswith((".xlsx", ".csv")):
                self.set_report(fp)
                used = True
            elif low.endswith((".png", ".jpg", ".jpeg", ".bmp")):
                try:
                    from PIL import Image
                    self.set_image(Image.open(fp))
                    used = True
                except Exception as e:
                    messagebox.showerror("Obraz", f"Nie udało się otworzyć obrazu:\n{e}")
        if not used:
            messagebox.showinfo("Przeciągnij plik", "Przeciągnij raport PDF z Integry, raport .xlsx z CRM albo obraz (zrzut z CRM).")

    # ---------- raport z CRM (.xlsx) i wybór serwisów ----------
    def _build_branches(self, names):
        chosen = {crm_report._key(b) for b in load_config().get("crm_branches", crm_report.BRANCHES)}
        if self.session and not self.session.is_admin:   # tylko oddziały przydzielone użytkownikowi
            allowed = {crm_report._key(b) for b in self.session.branches()}
            names = [n for n in names if crm_report._key(n) in allowed]
        for n in names:
            if n in self.branch_vars:
                continue
            v = tk.BooleanVar(value=crm_report._key(n) in chosen)
            self.branch_vars[n] = v
            tk.Checkbutton(self.branch_box, text=n, variable=v, command=self._branches_changed,
                           bg=SURFACE, activebackground=SURFACE, font=self.fonts.small,
                           selectcolor=SURFACE).pack(side="left", padx=(0, 6))

    def chosen_branches(self):
        return [n for n, v in self.branch_vars.items() if v.get()]

    def _branches_changed(self):
        cfg = load_config()
        cfg["crm_branches"] = self.chosen_branches()
        try:
            save_config(cfg)
        except OSError:
            pass
        self._show_report()

    def pick_report(self):
        p = filedialog.askopenfilename(filetypes=[("Raport CRM", "*.xlsx *.csv")])
        if p:
            self.set_report(p)

    def set_report(self, p):
        try:
            rows = crm_report.load(p)
        except Exception as e:
            messagebox.showerror("Raport z CRM", f"Nie udało się wczytać raportu:\n{e}")
            return
        self.crm_rows, self.crm_file, self.crm_img = rows, os.path.basename(p), None
        self._build_branches(crm_report.branches(rows))
        self._show_report()

    def _show_report(self):
        if not self.crm_rows:
            return
        counts = {}
        for r in self.crm_rows:
            counts[r["branch"]] = counts.get(r["branch"], 0) + 1
        sel = set(self.chosen_branches())
        n = sum(c for b, c in counts.items() if b in sel)
        ds = sorted(r["date"] for r in self.crm_rows if r["date"])
        rng = f"{ds[0]:%d.%m} – {ds[-1]:%d.%m.%Y}" if ds else "bez dat"
        det = ",  ".join(f"{b}: {c}" for b, c in counts.items())
        self.preview.config(image="", text=f"✔  {self.crm_file}   ({rng})\n{det}\nDo sprawdzenia: {n} numerów",
                            fg=OK if n else WARN, bg=OK_BG if n else WARN_BG)

    def pick_img(self):
        p = filedialog.askopenfilename(filetypes=[("Obrazy", "*.png *.jpg *.jpeg *.bmp")])
        if p:
            from PIL import Image
            self.set_image(Image.open(p))

    def paste(self):
        img = extract.image_from_clipboard()
        if img is None:
            messagebox.showwarning("Schowek", "W schowku nie ma obrazu.\n"
                                   "Zrób wycinek ekranu (Win+Shift+S) i wklej ponownie.")
            return
        self.set_image(img)

    def set_image(self, img):
        from PIL import ImageTk
        self.crm_img = img.copy()
        self.crm_rows = None
        th = img.copy()
        th.thumbnail((420, 110))
        self._thumb = ImageTk.PhotoImage(th)
        self.preview.config(image=self._thumb, text="", bg=OK_BG, pady=6)

    # ---------- logika ----------
    def say(self, text):
        """Bezpieczne z wątku roboczego – dopisuje linię do „Szczegółów”."""
        def _do():
            self.log.insert("end", text + "\n")
            self.log.see("end")
        self.after(0, _do)

    def ui(self, fn, *a):
        self.after(0, fn, *a)

    def check(self):
        if not self.pdf_path.get():
            messagebox.showwarning("Brak PDF", "Wybierz raport PDF z Integry.")
            return
        if self.crm_img is None and not self.crm_rows:
            messagebox.showwarning("Brak danych z CRM", "Wczytaj raport .xlsx z „Listy kontrolne” "
                                   "albo wklej wycinek ekranu z CRM (Ctrl+V).")
            return
        if self.crm_rows is not None and not self.chosen_branches():
            messagebox.showwarning("Serwisy", "Zaznacz co najmniej jeden serwis do sprawdzenia.")
            return
        self.btn_check.set_enabled(False, "SPRAWDZAM…")
        self.btn_send.set_enabled(False)
        self.log.delete("1.0", "end")
        self.set_chips([], [])
        self.set_banner("busy", "Sprawdzam… odczyt wycinka może potrwać kilka sekund.")
        # Tkinter nie jest bezpieczny dla wątków – wszystko z okna odczytujemy tutaj
        pdf = self.pdf_path.get()
        if self.crm_rows is not None:
            br = self.chosen_branches()
            src = {"rows": crm_report.select(self.crm_rows, br), "branches": br}
        else:
            src = self.crm_img
        threading.Thread(target=self._check_work, args=(pdf, src), daemon=True).start()

    def _check_work(self, pdf, src):
        try:
            tess = paths.find_tesseract(load_config().get("tesseract_cmd", ""))
            import time as _t
            _t0 = _t.time()
            res = analyze.run(pdf, src, tess, self.say)
            self._stat("check", n_integra=len(res["integra"]), n_crm=len(res["crm_main"]),
                       n_missing=len(res["missing"]), n_uncertain=len(res["uncertain"]),
                       n_autofix=len(res.get("autofix", [])), n_warnings=len(res["warnings"]),
                       seconds=round(_t.time() - _t0, 1))
            integra, crm, crm_main = res["integra"], res["crm"], res["crm_main"]
            warn = res["warnings"]

            self.result = None
            if not integra:
                self.ui(self.set_banner, "warn", "⚠  W PDF z Integry nie znaleziono żadnego numeru "
                        "rejestracyjnego – sprawdź, czy to właściwy plik.")
                return
            if not crm:
                self.ui(self.set_banner, "warn", "⚠  W raporcie z CRM nie ma numerów dla zaznaczonych serwisów."
                        if res.get("crm_source") == "report" else
                        "⚠  Na wycinku z CRM nie odczytano numerów – zrób wycinek "
                        "tabeli z kolumną „Rejestracja” i wklej ponownie.")
                return
            for w in warn:
                self.say("⚠ " + w)

            missing, uncertain = res["missing"], res["uncertain"]
            self.result = (missing, uncertain)
            try:
                if history is None:
                    raise RuntimeError("brak modułu historii – pobierz nową wersję .exe")
                name = os.path.basename(pdf)
                self.hist_index = history.add_check(name, len(integra), len(crm_main), missing, uncertain,
                                                    src.get("branches", []) if isinstance(src, dict) else [])
                self.last_branches = src.get("branches", []) if isinstance(src, dict) else []
                self.ui(self.refresh_history)
            except Exception as e:
                self.say(f"Historia: nie zapisano ({e})")
            self.ui(self.set_chips, missing, uncertain)
            wtxt = ("\n⚠  " + "\n⚠  ".join(warn)) if warn else ""
            fixed = res.get("autofix", [])
            if fixed:
                wtxt = (f"\nℹ  {len(fixed)} numer(y) dopasowano mimo błędu odczytu wycinka: "
                        + ", ".join(f"{a} (odczyt: {b})" for a, b in fixed)) + wtxt
            if not missing and not uncertain:
                self.ui(self.set_banner, "warn" if warn else "ok",
                        f"✔  Jest dobrze – wszystkie {len(integra)} zlecenia z Integry są w CRM.{wtxt}")
                self.ui(self.subject.set, "")
                self.ui(self.mail_body.delete, "1.0", "end")
                return
            if res.get("no_overlap"):   # prawie nic się nie pokrywa – mail byłby fałszywym alarmem
                self.ui(self.set_banner, "warn", f"⚠  Dane z CRM nie pasują do raportu Integry "
                        f"(wspólne numery: {res.get('n_common', 0)} z {len(integra)}). Sprawdź zaznaczone "
                        "serwisy i zakres dat. Mail nie został przygotowany." + wtxt)
                self.ui(self.subject.set, "")
                self.ui(self.mail_body.delete, "1.0", "end")
                return
            try:
                reg = history.reported(refresh=True) if history else {}
            except Exception:
                reg = history.reported() if history else {}
            subj, body = mailer.compose(missing, uncertain, reg)

            def fill():
                self.subject.set(subj)
                self.mail_body.delete("1.0", "end")
                self.mail_body.insert("1.0", body)
                self.btn_send.set_enabled(True, "Wyślij maila")
            self.ui(fill)
            parts = []
            if missing:
                parts.append(f"brakuje {len(missing)}")
            if uncertain:
                parts.append(f"{len(uncertain)} do weryfikacji")
            self.ui(self.set_banner, "bad", f"✖  W CRM {' i '.join(parts)} z {len(integra)} zleceń. "
                    "Mail jest gotowy – sprawdź treść i kliknij „Wyślij maila”." + wtxt)
        except Exception as e:
            self.say(f"Błąd: {e}")
            self._report(e, "sprawdzanie")
            self.ui(self.set_banner, "bad", f"✖  Błąd: {e}")
        finally:
            self.ui(self.btn_check.set_enabled, True, "SPRAWDŹ")

    def send_mail(self):
        if not self.result or not (self.result[0] or self.result[1]):
            messagebox.showinfo("Wyślij maila", "Nie ma czego wysyłać – mail przygotowuje się tylko wtedy, "
                                "gdy czegoś brakuje w CRM.")
            return
        cfg = load_config()
        cfg["recipients"] = recipients_for(getattr(self, "last_branches", []), cfg)
        server = self.session is not None   # po zalogowaniu mail wysyła serwer (bez hasła Gmail na komputerze)
        if server and not cfg["recipients"]:
            messagebox.showwarning("Odbiorcy", "Brak odbiorców – administrator ustawia ich w Ustawieniach.")
            return
        if not server and not (cfg["gmail_user"] and cfg["gmail_app_password"] and cfg["recipients"]):
            messagebox.showwarning("Ustawienia", "Uzupełnij swój Gmail, hasło aplikacji i odbiorców.")
            SettingsDialog(self)
            return
        if not messagebox.askyesno("Wyślij maila", f"Wysłać do: {', '.join(cfg['recipients'])}?"):
            return
        branch = ", ".join(getattr(self, "last_branches", []))
        subj, body = self.subject.get(), self.mail_body.get("1.0", "end").strip()
        missing = list(self.result[0])
        hist_index = self.hist_index if self.hist_index is not None else -1
        self.btn_send.set_enabled(False, "WYSYŁAM…")
        self.set_banner("busy", "Wysyłam maila…")

        def work():   # wysyłka w tle – okno nie zamarza przy wolnym internecie
            try:
                sent = False
                if server:
                    try:
                        frm = mailer.send_server(self.session, subj, body, cfg["recipients"], cfg.get("cc_self", True))
                        cfg["gmail_user"] = self.session.email if cfg.get("cc_self", True) else frm
                        sent = True
                    except mailer.NotConfigured:
                        if not (cfg["gmail_user"] and cfg["gmail_app_password"]):
                            raise RuntimeError("Wysyłka z serwera nie jest jeszcze skonfigurowana, a na tym "
                                               "komputerze nie ma ustawionego Gmaila.") from None
                if not sent:
                    mailer.send(subj, body, cfg)
            except Exception as e:
                self._report(e, "wysyłka maila")
                self.ui(self.set_banner, "bad", f"✖  Nie udało się wysłać: {e}")
                self.ui(self.btn_send.set_enabled, True, "Wyślij maila")
                return
            cc = f" (kopia: {cfg['gmail_user']})" if cfg.get("cc_self", True) else ""
            self.ui(self.set_banner, "ok", f"✔  Mail wysłany do: {', '.join(cfg['recipients'])}{cc}")
            self.ui(self.btn_send.set_enabled, False, "Wysłano ✔")
            try:
                if history is None:
                    raise RuntimeError
                self._stat("mail_sent", n_recipients=len(cfg["recipients"]))
                # do rejestru „zgłoszone” trafiają tylko pewne braki, nie pozycje „do weryfikacji”
                history.mark_sent(hist_index, cfg["recipients"], missing, branch)
                self.ui(self.refresh_history)
            except Exception:
                pass
        threading.Thread(target=work, daemon=True).start()


def main():
    if os.environ.get("INTEGRA_SELFTEST"):   # test bez okna (GitHub Actions)
        import selftest
        os._exit(selftest.run(os.environ["INTEGRA_SELFTEST"]))
    try:  # ostrzejszy tekst na ekranach z powiększeniem
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    if os.environ.get("INTEGRA_SHOT"):   # zrzuty ekranu w GitHub Actions – bez logowania
        App(None).mainloop()
        return
    sess = login_flow()
    if sess is None:
        return
    App(sess).mainloop()
