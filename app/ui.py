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
BLACK, INK, MUTED = "#111111", "#313131", "#666666"   # MUTED: kontrast 5,7:1 na białym (WCAG AA)
BG, SURFACE, LINE = "#F5F5F5", "#FFFFFF", "#E4E4E4"
OK, OK_BG = "#1E7D32", "#E8F5E9"
WARN, WARN_BG = "#8A5A00", "#FFF4E0"
ERR_BG = "#FDECEC"
OFF_BG, OFF_FG = "#ECECEC", "#767676"   # przycisk wyłączony: tekst 4,5:1
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
    """Płaski przycisk w stylu strony (czerwony / czarny / obrys / „usuń”) z efektem najechania.
    Działa też z klawiatury: Tab przechodzi na przycisk (czerwona obwódka), Enter lub Spacja go naciska."""

    STYLES = {
        "primary": (RED, "white", RED_DARK),
        "dark": (BLACK, "white", "#333333"),
        "ghost": (SURFACE, BLACK, "#EFEFEF"),
        "danger": (SURFACE, RED_DARK, ERR_BG),   # akcje nieodwracalne (usuń konto, wyczyść)
    }

    def __init__(self, parent, text, command, kind="primary", font=None, padx=18, pady=9):
        bg, fg, hover = self.STYLES[kind]
        ramka = kind in ("ghost", "danger")
        gr = 1 if ramka else 2   # obwódka fokusu; przy pełnych przyciskach w kolorze tła (niewidoczna bez fokusu)
        super().__init__(parent, text=text, bg=bg, fg=fg, font=font, padx=max(0, padx - (gr - 1)),
                         pady=max(0, pady - (gr - 1)), cursor="hand2", takefocus=1, highlightthickness=gr,
                         highlightbackground=(RED_DARK if kind == "danger" else LINE) if ramka else bg,
                         highlightcolor=RED if kind != "primary" else BLACK)
        self._c = (bg, fg, hover)
        self._cmd = command
        self._enabled = True
        self.bind("<Enter>", lambda e: self._enabled and self.config(bg=hover))
        self.bind("<Leave>", lambda e: self.config(bg=bg if self._enabled else OFF_BG))
        self.bind("<Button-1>", lambda e: self._enabled and self._cmd())
        self.bind("<Return>", self._klawisz)
        self.bind("<KP_Enter>", self._klawisz)
        self.bind("<space>", self._klawisz)

    def _klawisz(self, e=None):
        if self._enabled:
            self._cmd()
        return "break"

    def set_enabled(self, on: bool, text: str | None = None):
        self._enabled = on
        bg, fg, _ = self._c
        self.config(bg=bg if on else OFF_BG, fg=fg if on else OFF_FG, cursor="hand2" if on else "arrow")
        if not on and self.cget("highlightbackground") == bg:
            self.config(highlightbackground=OFF_BG)
        elif on and self.cget("highlightbackground") == OFF_BG:
            self.config(highlightbackground=bg)
        if text:
            self.config(text=text)


def esc_zamyka(root):
    """Esc w każdym oknie dialogowym działa jak „Anuluj” / zamknięcie okna (to samo co krzyżyk)."""
    def esc(e):
        try:
            top = e.widget.winfo_toplevel()
        except (tk.TclError, AttributeError):
            return
        if top is root or not top.winfo_exists() or top.winfo_class() != "Toplevel":   # nie lista rozwijana
            return
        try:
            cmd = top.protocol("WM_DELETE_WINDOW")
            if cmd:
                top.tk.call(cmd)
            else:
                top.destroy()
        except tk.TclError:
            pass
    root.bind_all("<Escape>", esc, add="+")


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


class WheelProgress(tk.Canvas):
    """Postęp jako koło: szary pierścień, czerwony łuk od godz. 12 zgodnie z zegarem, w środku obracająca się
    opona z felgą i procent. start() → set(0..1) → done('ok'|'warn'|'bad'); po done() nic nie jest zaplanowane.
    Wołać wyłącznie z wątku okna (z wątku roboczego – przez self.after)."""

    TICK = 40   # ms między klatkami

    def __init__(self, parent, size=140, bg=SURFACE, family="TkDefaultFont", caption=None):
        super().__init__(parent, width=size, height=size, bg=bg, highlightthickness=0, bd=0)
        k = size / 140.0
        c = self._c = size / 2.0
        self._k = k
        self.caption = caption   # opcjonalna etykieta z opisem kroku (set(text=…))
        r, w = 62 * k, 8 * k
        self.create_oval(c - r, c - r, c + r, c + r, outline=LINE, width=w)
        self._arc = self.create_arc(c - r, c - r, c + r, c + r, start=90, extent=0, style="arc",
                                    outline=RED, width=w, state="hidden")
        self._tire = self.create_oval(c - 48 * k, c - 48 * k, c + 48 * k, c + 48 * k, fill="#1B1B1B", outline="")
        self._rim = self.create_oval(c - 34 * k, c - 34 * k, c + 34 * k, c + 34 * k, fill="#D8D8D8", outline="")
        self._spokes = [self.create_line(0, 0, 0, 0, fill="#9A9A9A", width=max(2, 6 * k), capstyle="round")
                        for _ in range(6)]
        self._hub = self.create_oval(c - 8 * k, c - 8 * k, c + 8 * k, c + 8 * k, fill="#888888", outline="")
        fnt = (family, max(9, int(17 * k)), "bold")
        self._shadow = self.create_text(c + 1, c + 2, text="0%", fill="#000000", font=fnt)
        self._pct = self.create_text(c, c, text="0%", fill="white", font=fnt)
        self._mark = self.create_text(c, c, text="", font=(family, max(12, int(40 * k)), "bold"), state="hidden")
        self._job = None
        self._angle = 0.0
        self._shown = 0.0
        self._target = 0.0
        self.bind("<Destroy>", lambda e: e.widget is self and self._cancel())
        self._draw()

    # ---------- publiczne ----------
    def start(self):
        """Zaczyna obrót od 0% (np. na początku aktualizacji)."""
        self.reset()
        self._schedule()

    def set(self, fraction, text=None):
        """Ustawia postęp 0..1 (łuk dochodzi do niego płynnie); text → etykieta kroku (gdy podano caption)."""
        try:
            f = float(fraction)
        except (TypeError, ValueError):
            f = 0.0
        self._target = min(1.0, max(0.0, f))
        if text is not None and self.caption is not None:
            try:
                self.caption.config(text=text)
            except tk.TclError:
                pass
        if self._job is None and self.itemcget(self._mark, "state") == "hidden":
            self._schedule()

    def done(self, kind="ok"):
        """Koniec: zatrzymuje obrót (bez zaplanowanych klatek) i pokazuje ✔ / ⚠ / ✖."""
        self._cancel()
        mark, col = {"ok": ("✔", OK), "warn": ("⚠", WARN), "bad": ("✖", RED)}.get(kind, ("✔", OK))
        if kind == "ok":
            self._target = self._shown = 1.0
        self._shown = self._target
        self._draw()
        self.itemconfigure(self._arc, outline=col)
        for it in self._spokes + [self._hub, self._pct, self._shadow, self._tire, self._rim]:
            self.itemconfigure(it, state="hidden")
        self.itemconfigure(self._mark, text=mark, fill=col, state="normal")

    def reset(self):
        """Stan początkowy: 0%, bez znaku, bez animacji."""
        self._cancel()
        self._shown = self._target = 0.0
        self._angle = 0.0
        self.itemconfigure(self._arc, outline=RED)
        for it in self._spokes + [self._hub, self._pct, self._shadow, self._tire, self._rim]:
            self.itemconfigure(it, state="normal")
        self.itemconfigure(self._mark, text="", state="hidden")
        self._draw()

    @property
    def running(self):
        return self._job is not None

    # ---------- wewnętrzne ----------
    def _schedule(self):
        if self._job is None:
            self._job = self.after(self.TICK, self._tick)

    def _cancel(self):
        if self._job is not None:
            try:
                self.after_cancel(self._job)
            except tk.TclError:
                pass
            self._job = None

    def _tick(self):
        self._job = None
        self._angle = (self._angle + 9.0) % 360.0
        d = self._target - self._shown
        self._shown = self._target if abs(d) < 0.004 else self._shown + d * 0.18
        self._draw()
        self._schedule()

    def _draw(self):
        import math
        c, k = self._c, self._k
        for i, ln in enumerate(self._spokes):
            a = math.radians(self._angle + i * 60)
            ca, sa = math.cos(a), math.sin(a)
            self.coords(ln, c + 12 * k * ca, c + 12 * k * sa, c + 30 * k * ca, c + 30 * k * sa)
        ext = -359.9 * self._shown
        self.itemconfigure(self._arc, extent=ext, state="normal" if self._shown > 0.003 else "hidden")
        txt = f"{int(round(self._target * 100))}%"
        self.itemconfigure(self._pct, text=txt)
        self.itemconfigure(self._shadow, text=txt)
