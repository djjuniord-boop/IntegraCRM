"""Pojedyncza instancja głównego okna: druga próba uruchomienia programu nie otwiera kolejnego
okna, tylko podnosi już otwarte (Windows, nazwany mutex). Okna-dzieci (--oferty/--serwis) tego
nie dotyczą – kończą pracę w start.py wcześniej. Na innych systemach (testy) nic nie blokuje."""
import sys
import time

MUTEX_NAZWA = "IntegraCRM_glowne_okno_v1"
_UCHWYT = None   # trzyma mutex przy życiu procesu (zwalniany przez system przy zamknięciu)


def _czy_glowne(tytul: str) -> bool:
    """Czy tytuł okna należy do głównego programu (logowanie albo panel), a nie do okien OFERT/SERWIS."""
    t = tytul or ""
    return t.startswith("Panel Latex Serwis") or "– logowanie" in t


def _podnies_istniejace():
    """Przywraca i wysuwa na wierzch już otwarte główne okno (best-effort)."""
    import ctypes
    from ctypes import wintypes
    u = ctypes.windll.user32
    znalezione = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def _cb(hwnd, _):
        if not u.IsWindowVisible(hwnd):
            return True
        n = u.GetWindowTextLengthW(hwnd)
        if n:
            buf = ctypes.create_unicode_buffer(n + 1)
            u.GetWindowTextW(hwnd, buf, n + 1)
            if _czy_glowne(buf.value):
                znalezione.append(hwnd)
                return False   # wystarczy pierwsze
        return True

    u.EnumWindows(_cb, 0)
    for hwnd in znalezione:
        u.ShowWindow(hwnd, 9)          # SW_RESTORE – odminimalizuj
        u.SetForegroundWindow(hwnd)


def tylko_jedna(czekaj: bool = False) -> bool:
    """True = ta instancja może działać (zajęła blokadę). False = inne okno już otwarte
    (zostało podniesione, ta instancja ma się zakończyć).
    czekaj=True (start po aktualizacji) – poczekaj, aż poprzedni proces zwolni blokadę,
    żeby restart nie został zablokowany przez samego siebie; mimo to w końcu wystartuj."""
    global _UCHWYT
    if sys.platform != "win32":
        return True
    try:
        import ctypes
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        k.CreateMutexW.restype = ctypes.c_void_p
        k.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
    except Exception:
        return True   # w razie wątpliwości nie blokuj startu
    ERROR_ALREADY_EXISTS = 183
    proby = 25 if czekaj else 1        # ~5 s na zwolnienie blokady po restarcie
    for i in range(proby):
        try:
            h = k.CreateMutexW(None, 0, MUTEX_NAZWA)
            err = ctypes.get_last_error()
        except Exception:
            return True
        if err != ERROR_ALREADY_EXISTS:
            _UCHWYT = h                # jesteśmy pierwsi – trzymamy mutex
            return True
        try:
            ctypes.windll.kernel32.CloseHandle(h)
        except Exception:
            pass
        if i + 1 < proby:
            time.sleep(0.2)
    if czekaj:                         # po aktualizacji nie zostawiaj użytkownika bez okna
        try:
            _UCHWYT = k.CreateMutexW(None, 0, MUTEX_NAZWA)
        except Exception:
            pass
        return True
    try:
        _podnies_istniejace()
    except Exception:
        pass
    return False
