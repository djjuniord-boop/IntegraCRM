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
}

STATS_INFO = ("Program wysyła anonimowe statystyki użycia: losowy identyfikator instalacji, wersję, "
              "rodzaj zdarzenia (uruchomienie, sprawdzenie, wysłany mail, błąd) i same liczby "
              "(ile numerów, ile braków, czas sprawdzenia). Nie wysyła numerów rejestracyjnych, adresów e-mail, "
              "haseł, nazw plików ani treści maili. Można to wyłączyć w Ustawieniach.")

HELP_STEPS = [
    ("Raport z Integra 7", "Przeciągnij plik PDF na okno programu albo kliknij „Wybierz PDF”."),
    ("Wycinek z CRM", "W CRM zrób wycinek tabeli (Win+Shift+S), wróć tutaj i naciśnij Ctrl+V. "
                      "Można też przeciągnąć plik ze zrzutem ekranu."),
    ("Sprawdź", "Program porówna numery rejestracyjne. Status i inne kolumny są pomijane."),
    ("Wyślij maila", "Jeśli czegoś brakuje, mail jest gotowy – możesz go poprawić i wysłać."),
]


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
    paths.CONFIG_PATH.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")


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
        self.v_name = tk.StringVar(value=cfg.get("sender_name") or mailer.DEFAULT_SENDER)
        row("Nazwa nadawcy", self.v_name)
        row("Twój Gmail (nadawca)", self.v_user)
        self.pass_entry = row("Hasło aplikacji Google", self.v_pass, show="•")
        self.show = tk.BooleanVar()
        ttk.Checkbutton(body, text="Pokaż hasło", variable=self.show,
                        command=lambda: self.pass_entry.config(show="" if self.show.get() else "•")
                        ).grid(row=r[0], column=1, sticky="w", padx=12)
        r[0] += 1
        row("Odbiorcy (po przecinku)", self.v_to)
        self.v_cc = tk.BooleanVar(value=bool(cfg.get("cc_self", True)))
        ttk.Checkbutton(body, text="Wysyłaj kopię (DW) do mnie", variable=self.v_cc
                        ).grid(row=r[0], column=1, sticky="w", padx=12)
        r[0] += 1
        self.v_stats = tk.BooleanVar(value=bool(cfg.get("stats_enabled", True)))
        ttk.Checkbutton(body, text="Wysyłaj anonimowe statystyki użycia (tylko liczby)", variable=self.v_stats
                        ).grid(row=r[0], column=1, sticky="w", padx=12, pady=(6, 0))
        r[0] += 1
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
        }

    def save(self):
        save_config(self.collect())
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


# ---------- okno główne ----------
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        migrate_config()
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
        if not (_c["gmail_user"] and _c["gmail_app_password"]):
            self.after(400, lambda: SettingsDialog(self))
        self.after(900, lambda: self.check_updates(manual=False))
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
        tk.Frame(self, bg=RED, height=4).pack(fill="x")

        # zakładki jako przyciski (czytelniejsze niż systemowy Notebook)
        tabs = tk.Frame(self, bg=BLACK)
        tabs.pack(fill="x")
        self.pages, self.tab_btns = {}, {}
        holder = tk.Frame(self, bg=BG)
        holder.pack(fill="both", expand=True)
        for key, label in (("main", "KONTROLA"), ("hist", "HISTORIA"), ("help", "POMOC I WERSJE")):
            b = tk.Label(tabs, text=label, bg=BLACK, fg="#BBBBBB", font=f.label, padx=20, pady=9,
                         cursor="hand2")
            b.pack(side="left")
            b.bind("<Button-1>", lambda e, k=key: self.show_tab(k))
            self.tab_btns[key] = b
            self.pages[key] = tk.Frame(holder, bg=BG, padx=22, pady=10)
        self._build_main(self.pages["main"])
        self._build_help(self.pages["help"])
        self._build_history(self.pages["hist"])
        self.show_tab("main")

    def _build_history(self, page):
        f = self.fonts
        top = tk.Frame(page, bg=BG)
        top.pack(fill="x", pady=(0, 10))
        tk.Label(top, text="Historia sprawdzeń", bg=BG, fg=BLACK, font=f.h1).pack(side="left")
        FlatButton(top, "Otwórz w Excelu", self.open_history_file, "ghost", f.body, 14, 6).pack(side="right")
        FlatButton(top, "Odśwież", self.refresh_history, "ghost", f.body, 14, 6).pack(side="right", padx=8)
        box = card(page, padx=2, pady=2)
        box.pack(fill="both", expand=True)
        cols = ("data", "plik", "integra", "crm", "brakuje", "mail")
        s = ttk.Style(self)
        s.configure("H.Treeview", font=f.body, rowheight=26, background=SURFACE, fieldbackground=SURFACE)
        s.configure("H.Treeview.Heading", font=f.label, background=BG)
        s.map("H.Treeview", background=[("selected", RED)], foreground=[("selected", "white")])
        self.hist_tree = ttk.Treeview(box, columns=cols, show="headings", style="H.Treeview")
        for c, t, w in (("data", "Data", 130), ("plik", "Plik PDF", 200), ("integra", "Integra", 70),
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
        t = self.hist_tree
        t.delete(*t.get_children())
        if history is None:
            return
        for r in reversed(history.read_all()):
            t.insert("", "end", values=(r.get("data", ""), r.get("plik_pdf", ""), r.get("integra", ""),
                                        r.get("crm", ""), r.get("brakuje", "") or "—",
                                        r.get("mail_wyslany_do", "") or "—"))

    def open_history_file(self):
        if history is None or not history.HISTORY.exists():
            messagebox.showinfo("Historia", "Historia jest jeszcze pusta.")
            return
        try:
            os.startfile(str(history.HISTORY))   # Windows: otwiera w Excelu
        except Exception as e:
            messagebox.showinfo("Historia", f"Plik historii:\n{history.HISTORY}\n\n{e}")

    def show_tab(self, key):
        for k, p in self.pages.items():
            p.pack_forget()
            self.tab_btns[k].config(fg="#BBBBBB", bg=BLACK)
        self.pages[key].pack(fill="both", expand=True)
        self.tab_btns[key].config(fg="white", bg=RED)

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
        tk.Label(h, text="Wycinek z CRM", bg=SURFACE, fg=BLACK, font=f.h2).pack(side="left", padx=8)
        self.preview = tk.Label(c2, text="Kliknij tutaj lub naciśnij Ctrl+V\npo zrobieniu wycinka (Win+Shift+S)",
                                bg=BG, fg=MUTED, font=f.body, pady=6, cursor="hand2", justify="center")
        self.preview.pack(fill="x", pady=(8, 8))
        self.preview.bind("<Button-1>", lambda e: self.paste())
        r = tk.Frame(c2, bg=SURFACE)
        r.pack(fill="x")
        FlatButton(r, "Wklej ze schowka", self.paste, "dark", f.body, 14, 6).pack(side="left")
        FlatButton(r, "Z pliku…", self.pick_img, "ghost", f.body, 12, 6).pack(side="left", padx=8)

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
            messagebox.showerror("Przywracanie", f"Nie udało się przywrócić:\n{e}")
            return
        self._restart()

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
        """Upuszczone pliki: PDF → krok 1, obraz → krok 2."""
        used = False
        for fp in files:
            low = fp.lower()
            if low.endswith(".pdf"):
                self.set_pdf(fp)
                used = True
            elif low.endswith((".png", ".jpg", ".jpeg", ".bmp")):
                try:
                    from PIL import Image
                    self.set_image(Image.open(fp))
                    used = True
                except Exception as e:
                    messagebox.showerror("Obraz", f"Nie udało się otworzyć obrazu:\n{e}")
        if not used:
            messagebox.showinfo("Przeciągnij plik", "Przeciągnij raport PDF z Integry albo obraz (zrzut z CRM).")

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
        if self.crm_img is None:
            messagebox.showwarning("Brak wycinka", "Wklej wycinek ekranu z CRM (Ctrl+V).")
            return
        self.btn_check.set_enabled(False, "SPRAWDZAM…")
        self.btn_send.set_enabled(False)
        self.log.delete("1.0", "end")
        self.set_chips([], [])
        self.set_banner("busy", "Sprawdzam… odczyt wycinka może potrwać kilka sekund.")
        threading.Thread(target=self._check_work, daemon=True).start()

    def _check_work(self):
        try:
            tess = paths.find_tesseract(load_config().get("tesseract_cmd", ""))
            import time as _t
            _t0 = _t.time()
            res = analyze.run(self.pdf_path.get(), self.crm_img, tess, self.say)
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
                self.ui(self.set_banner, "warn", "⚠  Na wycinku z CRM nie odczytano numerów – zrób wycinek "
                        "tabeli z kolumną „Rejestracja” i wklej ponownie.")
                return
            for w in warn:
                self.say("⚠ " + w)

            missing, uncertain = res["missing"], res["uncertain"]
            self.result = (missing, uncertain)
            try:
                if history is None:
                    raise RuntimeError("brak modułu historii – pobierz nową wersję .exe")
                name = os.path.basename(self.pdf_path.get())
                self.hist_index = history.add_check(name, len(integra), len(crm_main), missing, uncertain)
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
            subj, body = mailer.compose(missing, uncertain, history.reported() if history else {})

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
            self._stat("error", error=type(e).__name__)
            self.ui(self.set_banner, "bad", f"✖  Błąd: {e}")
        finally:
            self.ui(self.btn_check.set_enabled, True, "SPRAWDŹ")

    def send_mail(self):
        if not self.result or not (self.result[0] or self.result[1]):
            messagebox.showinfo("Wyślij maila", "Nie ma czego wysyłać – mail przygotowuje się tylko wtedy, "
                                "gdy czegoś brakuje w CRM.")
            return
        cfg = load_config()
        if not (cfg["gmail_user"] and cfg["gmail_app_password"] and cfg["recipients"]):
            messagebox.showwarning("Ustawienia", "Uzupełnij swój Gmail, hasło aplikacji i odbiorców.")
            SettingsDialog(self)
            return
        if not messagebox.askyesno("Wyślij maila", f"Wysłać do: {', '.join(cfg['recipients'])}?"):
            return
        try:
            mailer.send(self.subject.get(), self.mail_body.get("1.0", "end").strip(), cfg)
            cc = f" (kopia: {cfg['gmail_user']})" if cfg.get("cc_self", True) else ""
            self.set_banner("ok", f"✔  Mail wysłany do: {', '.join(cfg['recipients'])}{cc}")
            try:
                if history is None:
                    raise RuntimeError
                self._stat("mail_sent", n_recipients=len(cfg["recipients"]))
                history.mark_sent(self.hist_index if self.hist_index is not None else -1, cfg["recipients"],
                                  list(self.result[0]) + [a for a, _ in self.result[1]])
                self.refresh_history()
            except Exception:
                pass
            self.btn_send.set_enabled(False, "Wysłano ✔")
        except Exception as e:
            self.set_banner("bad", f"✖  Nie udało się wysłać: {e}")


def main():
    if os.environ.get("INTEGRA_SELFTEST"):   # test bez okna (GitHub Actions)
        import selftest
        os._exit(selftest.run(os.environ["INTEGRA_SELFTEST"]))
    try:  # ostrzejszy tekst na ekranach z powiększeniem
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    App().mainloop()
