"""Wygląd programu: kolory Latex Auto Serwis, czcionki, przyciski i drobne elementy okna.
Wspólne dla wszystkich modułów – zmiana tutaj zmienia wygląd całego programu."""
import tkinter as tk
try:
    import tkinter.font as tkfont
except ImportError:   # starsze IntegraCRM.exe nie mają tego modułu
    tkfont = None
import paths


# ---------- identyfikacja wizualna ----------
RED, RED_DARK = "#E30613", "#B8050F"
BLACK, INK, MUTED = "#111111", "#313131", "#7A7A7A"
BG, SURFACE, LINE = "#F5F5F5", "#FFFFFF", "#E4E4E4"
OK, OK_BG = "#1E7D32", "#E8F5E9"
WARN, WARN_BG = "#8A5A00", "#FFF4E0"
ERR_BG = "#FDECEC"
ASSETS = paths.APP_DIR / "assets"


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


def odmiana(n, jeden, kilka, wiele):
    """Polska odmiana po liczbie: odmiana(1,"numer","numery","numerów") → „numer”; 3 → „numery”; 5, 12, 22? → zgodnie z zasadami."""
    n = abs(int(n))
    if n == 1:
        return jeden
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return kilka
    return wiele


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
