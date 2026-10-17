"""Czuwanie nad długo otwartym programem (wywołuje rdzeń okna, gui.py):

1. ostatnia aktywność – co 30 min zapis w bazie (app_ping), widoczny w zakładce UŻYTKOWNICY,
2. nowa wersja w trakcie pracy – co 30 min sprawdzenie; propozycja ponownego uruchomienia
   (wersja poniżej minimalnej z bazy: ponowne uruchomienie obowiązkowe),
3. zamknięcie po 8 godzinach – 10 minut wcześniej okno z odliczaniem i możliwością odłożenia.

Praca w tle tylko w wątkach; wynik do okna przez app.after(0, …) (zasada z CLAUDE.md).
"""
import threading
import time
import tkinter as tk

import updater
from konfig import load_config, update_source
from ui import BLACK, FlatButton, RED, SURFACE, odmiana, set_icon
from version import VERSION

LIMIT_GODZ = 8            # po tylu godzinach od uruchomienia program się zamyka
OSTRZEZENIE_MIN = 10      # tyle minut wcześniej pojawia się odliczanie
ODLOZ_MIN = 60            # „Pracuję dalej” odsuwa zamknięcie o tyle minut
SESJA_CO_S = 20           # co tyle sekund: czy administrator nie wylogował konta
PRZERWA_OFERTY_MIN = 120  # po „Później” nowa wersja przypomina się po tym czasie
WYMUSZ_PO_MIN = 15        # wersja poniżej minimalnej – samoczynne uruchomienie ponownie po tym czasie


def start(app):
    """Uruchamia czuwanie (po zbudowaniu okna, z działającą pętlą Tk)."""
    app._czuw = {"start": time.monotonic(), "zamkniecie": LIMIT_GODZ * 3600.0, "oferta_po": 0.0, "okno": None}
    ping(app)
    _plan_zamkniecia(app)
    app.after(SESJA_CO_S * 1000, sprawdz_sesje, app)


def co_30_min(app):
    """Wołane z _keep_session: aktywność i sprawdzenie wersji."""
    ping(app)
    sprawdz_wersje(app)


# ---------- 1. aktywność ----------
def ping(app):
    sess = getattr(app, "session", None)
    if sess is None:
        return

    def work():
        try:
            sess.rpc("app_ping", p_version=VERSION)
        except Exception:   # starsza baza bez funkcji albo brak sieci – bez znaczenia dla pracy
            pass
    threading.Thread(target=work, daemon=True).start()


# ---------- 1a. wylogowanie przez administratora ----------
def sprawdz_sesje(app):
    """Co 20 s pyta bazę, czy sesja istnieje; usunięta (admin kliknął „Wyloguj”) → program się zamyka."""
    sess = getattr(app, "session", None)
    if sess is None or getattr(app, "_ended", False):
        return

    def work():
        try:
            ok = sess.rpc("session_ok")
        except Exception:   # brak sieci albo starsza baza bez funkcji – nic nie robimy
            ok = None
        try:
            if ok is False:
                app.after(0, app._session_ended)
            app.after(SESJA_CO_S * 1000, sprawdz_sesje, app)
        except RuntimeError:   # okno zamknięte
            pass
    threading.Thread(target=work, daemon=True).start()


# ---------- 2. nowa wersja w trakcie pracy ----------
def sprawdz_wersje(app):
    sess = getattr(app, "session", None)
    src = update_source(load_config())
    if sess is None or not src:
        return

    def work():
        try:
            need = sess.min_version()
            m, newer = updater.check(src)
        except Exception:
            return
        try:
            app.after(0, _po_sprawdzeniu, app, m, newer, need)
        except RuntimeError:   # okno zamknięte
            pass
    threading.Thread(target=work, daemon=True).start()


def _za_stara(need: str) -> bool:
    return bool(need) and updater._ver(VERSION) < updater._ver(need)


def _po_sprawdzeniu(app, m, newer, need):
    if not newer:
        return
    wymagana = _za_stara(need)
    teraz = time.monotonic()
    if not wymagana and teraz < app._czuw["oferta_po"]:
        return
    if app._czuw.get("okno") is not None:
        return
    app._czuw["oferta_po"] = teraz + PRZERWA_OFERTY_MIN * 60
    if wymagana:
        tekst = (f"Dostępna jest nowa wersja {m['version']}, a ta wersja ({VERSION}) nie jest już obsługiwana.\n"
                 f"Zapisz pracę – za {WYMUSZ_PO_MIN} minut program sam uruchomi się ponownie w nowej wersji.")
        _okno(app, "Wymagana aktualizacja", tekst,
              [("Uruchom ponownie teraz", lambda: _aktualizuj(app, m))],
              odliczanie=WYMUSZ_PO_MIN * 60, po_czasie=lambda: _aktualizuj(app, m))
    else:
        tekst = (f"Dostępna jest nowa wersja programu: {m['version']} (masz {VERSION}).\n"
                 "Zapisz pracę i kliknij „Uruchom ponownie” – program zaktualizuje się i otworzy od nowa.")
        _okno(app, "Nowa wersja", tekst,
              [("Uruchom ponownie", lambda: _aktualizuj(app, m)), ("Później", None)])


def _aktualizuj(app, m):
    if _zajety(app):   # trwa wysyłka albo MARŻA – spróbuj za 2 minuty
        app.after(120 * 1000, _aktualizuj, app, m)
        return
    app._update_checked(m, True, False, None, ask=False)   # jak przy starcie, bez drugiego pytania


# ---------- 3. zamknięcie po 8 godzinach ----------
def _plan_zamkniecia(app):
    czuw = app._czuw
    zostalo = czuw["start"] + czuw["zamkniecie"] - time.monotonic()
    za = max(0.0, zostalo - OSTRZEZENIE_MIN * 60)
    czuw["timer"] = app.after(int(za * 1000), _ostrzez, app)


def _ostrzez(app):
    czuw = app._czuw
    if czuw.get("okno") is not None:   # inne okno czuwania jest otwarte – spróbuj za minutę
        czuw["timer"] = app.after(60 * 1000, _ostrzez, app)
        return
    zostalo = max(0, int(czuw["start"] + czuw["zamkniecie"] - time.monotonic()))
    godz = max(1, round((time.monotonic() - czuw["start"]) / 3600))

    def odloz():
        czuw["zamkniecie"] = time.monotonic() - czuw["start"] + ODLOZ_MIN * 60
        _plan_zamkniecia(app)

    _okno(app, "Zamknięcie programu",
          f"Program jest otwarty od {godz} {odmiana(godz, 'godziny', 'godzin', 'godzin')} i za chwilę się zamknie.\n"
          "Zapisz pracę. Po ponownym uruchomieniu pobierze się najnowsza wersja.",
          [(f"Pracuję dalej ({ODLOZ_MIN} min)", odloz), ("Zamknij teraz", lambda: _zamknij(app))],
          odliczanie=zostalo, po_czasie=lambda: _zamknij(app))


def _zamknij(app):
    if _zajety(app):   # nie przerywamy wysyłki e-maila ani MARŻY
        app.after(5 * 60 * 1000, _zamknij, app)
        return
    app._on_close()


def _zajety(app) -> bool:
    if getattr(app, "marza_busy", False) or getattr(app, "updating", False):
        return True
    btn = getattr(app, "btn_send", None)
    try:
        return btn is not None and "WYSYŁAM" in str(btn.cget("text"))
    except tk.TclError:
        return False


# ---------- okno z przyciskami i odliczaniem (nie blokuje programu) ----------
def _okno(app, tytul, tekst, przyciski, odliczanie=None, po_czasie=None):
    f = app.fonts
    w = tk.Toplevel(app)
    w.title(tytul)
    w.configure(bg=SURFACE)
    w.resizable(False, False)
    w.transient(app)
    w.attributes("-topmost", True)
    set_icon(w)
    app._czuw["okno"] = w
    tk.Frame(w, bg=RED, height=4).pack(fill="x")
    body = tk.Frame(w, bg=SURFACE, padx=22, pady=16)
    body.pack(fill="both")
    tk.Label(body, text=tytul, bg=SURFACE, fg=BLACK, font=f.h2).pack(anchor="w")
    tk.Label(body, text=tekst, bg=SURFACE, fg=BLACK, font=f.body, justify="left", wraplength=460).pack(
        anchor="w", pady=(8, 4))
    licznik = tk.Label(body, text="", bg=SURFACE, fg=RED, font=f.label)
    licznik.pack(anchor="w")
    bar = tk.Frame(w, bg=SURFACE, padx=22, pady=12)
    bar.pack(fill="x")
    stan = {"koniec": time.monotonic() + odliczanie if odliczanie is not None else None, "zadanie": None}

    def zamknij_okno():
        if stan["zadanie"]:
            try:
                app.after_cancel(stan["zadanie"])
            except tk.TclError:
                pass
        app._czuw["okno"] = None
        try:
            w.destroy()
        except tk.TclError:
            pass

    def klik(akcja):
        zamknij_okno()
        if akcja:
            akcja()

    for i, (napis, akcja) in enumerate(przyciski):
        FlatButton(bar, napis, lambda a=akcja: klik(a), "primary" if i == 0 else "ghost", f.body, 14, 6).pack(
            side="right", padx=(8, 0))
    # krzyżyk: przy wyborze = „Później”/„Pracuję dalej”; przy jednym przycisku (wymagana aktualizacja) – nic,
    # odliczanie trwa dalej
    w.protocol("WM_DELETE_WINDOW", (lambda: klik(przyciski[0][1] if "Pracuję" in przyciski[0][0] else przyciski[-1][1]))
               if len(przyciski) > 1 else (lambda: None))

    def tik():
        if stan["koniec"] is None:
            return
        zostalo = int(stan["koniec"] - time.monotonic())
        if zostalo <= 0:
            zamknij_okno()
            if po_czasie:
                po_czasie()
            return
        licznik.config(text=f"Pozostało: {zostalo // 60}:{zostalo % 60:02d}")
        stan["zadanie"] = app.after(1000, tik)
    tik()
    w.update_idletasks()
    x = app.winfo_rootx() + (app.winfo_width() - w.winfo_reqwidth()) // 2
    y = app.winfo_rooty() + 120
    w.geometry(f"+{max(0, x)}+{max(0, y)}")
    return w
