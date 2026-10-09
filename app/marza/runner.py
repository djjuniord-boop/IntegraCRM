"""Kalkulator marży (Wrocław + Opole) – uruchamiany z zakładki MARŻA.

Odpowiednik „2. AKTUALIZUJ WSZYSTKO.bat” + _system/rozdziel_i_aktualizuj.py, ale silniki działają
w procesie programu (bez osobnego Pythona). Same silniki to niezmienione skrypty
aktualizuj_kalkulator.py / generuj_podglad.py – podmieniane są tylko ścieżki, hasło do poczty
i pytanie „Zapisać mimo to?” (okno zamiast konsoli).

Dane zostają w folderze „LATEX Wyniki” użytkownika: kalkulatory, kopie zapasowe, logi, PDF-y.
"""
import contextlib
import datetime
import importlib
import io
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

ODDZIALY = [
    # klucz, nazwa, podfolder, moduł silnika, moduł podglądu
    ("wroclaw", "WROCŁAW", "Wrocław", "silnik_wroclaw", "podglad_wroclaw"),
    ("opole", "OPOLE", "Opole", "silnik_opole", "podglad_opole"),
]
WRZUC = "1. WRZUC RAPORTY TUTAJ"


def deps_ok() -> str:
    """Pusty tekst = wszystko jest; inaczej opis braku (np. stara wersja IntegraCRM.exe)."""
    missing = []
    for mod in ("openpyxl", "pypdf", "matplotlib"):
        try:
            importlib.import_module(mod)
        except Exception:
            missing.append(mod)
    return ", ".join(missing)


def check_folder(root: str) -> str:
    if not root or not os.path.isdir(root):
        return "Nie wskazano folderu „LATEX Wyniki”."
    for _, _, sub, _, _ in ODDZIALY:
        if not os.path.isdir(os.path.join(root, sub)):
            return f"W folderze nie ma podfolderu „{sub}” – wskaż główny folder „LATEX Wyniki”."
    return ""


BRANCH_NAMES = {"wroclaw": "Wrocław", "opole": "Opole"}


def inspect(path: str):
    """Sprawdza PDF przed dodaniem. Zwraca (oddział 'wroclaw'|'opole'|None, opis)."""
    try:
        import pypdf
        text = pypdf.PdfReader(path).pages[0].extract_text() or ""
    except Exception as e:
        return None, f"nie da się odczytać PDF ({e})"
    t = text.lower()
    if "raport sprzedaży towarów i usług" not in t and "raport sprzedazy towarow i uslug" not in t:
        first = (text.strip().splitlines() or ["?"])[0][:60]
        return None, f"to nie jest „Raport sprzedaży towarów i usług” (to: „{first}”)"
    wro = "serwis wrocław" in t or "serwis wroclaw" in t
    opo = "serwis opole" in t
    if wro and not opo:
        return "wroclaw", ""
    if opo and not wro:
        return "opole", ""
    return None, "w nagłówku nie ma „Serwis Wrocław” ani „Serwis Opole”"


def add_reports(root: str, files, replace=lambda branch, old: True):
    """Sprawdza i kopiuje PDF-y do „1. WRZUC RAPORTY TUTAJ” – najwyżej jeden raport na oddział.
    replace(oddział, stara_nazwa) decyduje, czy podmienić raport już czekający w kolejce.
    Zwraca (dodane: [(nazwa, oddział)], odrzucone: [(nazwa, powód)])."""
    dst = os.path.join(root, WRZUC)
    os.makedirs(dst, exist_ok=True)
    added, rejected = [], []
    for f in files:
        name = os.path.basename(f)
        if not f.lower().endswith(".pdf"):
            rejected.append((name, "to nie jest plik PDF"))
            continue
        branch, why = inspect(f)
        if not branch:
            rejected.append((name, why))
            continue
        queued = [n for n, b in pending_info(root) if b == branch]
        if queued:
            if not replace(branch, queued[0]):
                rejected.append((name, f"w kolejce jest już raport dla oddziału {BRANCH_NAMES[branch]}"))
                continue
            for n in queued:
                remove_pending(root, n)
        target = _wolna(dst, name)
        shutil.copy2(f, target)
        added.append((os.path.basename(target), branch))
    return added, rejected


def pending_info(root: str):
    """[(nazwa, oddział lub None)] dla PDF-ów czekających w kolejce."""
    d = os.path.join(root, WRZUC)
    return [(n, inspect(os.path.join(d, n))[0]) for n in pending(root)]


def remove_pending(root: str, name: str) -> None:
    """Usuwa raport z kolejki (tylko kopię w „1. WRZUC RAPORTY TUTAJ” – oryginał zostaje tam, skąd był dodany)."""
    p = os.path.join(root, WRZUC, os.path.basename(name))
    if os.path.isfile(p):
        os.remove(p)


def pending(root: str) -> list:
    d = os.path.join(root, WRZUC)
    try:
        return sorted(f for f in os.listdir(d) if f.lower().endswith(".pdf"))
    except OSError:
        return []


def _wolna(folder, nazwa):
    cel = os.path.join(folder, nazwa)
    if not os.path.exists(cel):
        return cel
    base, ext = os.path.splitext(nazwa)
    i = 2
    while os.path.exists(os.path.join(folder, f"{base}_{i}{ext}")):
        i += 1
    return os.path.join(folder, f"{base}_{i}{ext}")


def _load(modname):
    """Świeży moduł z pakietu marza (bez pamięci podręcznej – każdy przebieg od zera)."""
    full = f"marza.{modname}"
    if full in sys.modules:
        return importlib.reload(sys.modules[full])
    return importlib.import_module(full)


class _Writer(io.TextIOBase):
    def __init__(self, cb):
        self.cb, self.buf = cb, ""

    def write(self, s):
        self.buf += s
        while "\n" in self.buf:
            line, self.buf = self.buf.split("\n", 1)
            self.cb(line)
        return len(s)

    def flush(self):
        if self.buf:
            self.cb(self.buf)
            self.buf = ""


def run_all(root: str, cfg: dict, log=print, ask=lambda q: False, test_mode=False) -> dict:
    """Pełny przebieg: rozdzielenie raportów, oba silniki, podsumowanie.

    log(str)  – każda linia wyjścia (jak w oknie konsoli),
    ask(str)  – pytanie tak/nie (np. raport obejmuje więcej niż jeden miesiąc),
    zwraca {"ok": bool, "summary": [linie], "results": {...}}.
    """
    sys.dont_write_bytecode = True
    old_env = os.environ.get("LATEX_TRYB_TESTOWY")
    if test_mode:
        os.environ["LATEX_TRYB_TESTOWY"] = "1"
    try:
        with contextlib.redirect_stdout(_Writer(log)):
            return _run(root, cfg, ask, test_mode)
    finally:
        if test_mode:
            if old_env is None:
                os.environ.pop("LATEX_TRYB_TESTOWY", None)
            else:
                os.environ["LATEX_TRYB_TESTOWY"] = old_env


def _run(root, cfg, ask, test_mode):
    roz = _load("rozdziel")
    roz.configure(root)
    print("=" * 64)
    print(" AKTUALIZUJ WSZYSTKO - Wrocław + Opole")
    if test_mode:
        print(" [TRYB TESTOWY - bez maili i bez Dysku Google]")
    print("=" * 64)
    print()
    print("--- Krok 1/3: rozdzielanie raportow ---")
    licznik, odrzucone_na_wejsciu = roz.rozdziel()

    wyniki = {}
    for i, (klucz, nazwa, sub, silnik_mod, podglad_mod) in enumerate(ODDZIALY, start=2):
        print()
        print(f"--- Krok {i}/3: aktualizacja {nazwa} ---")
        folder = os.path.join(root, sub)
        wyniki[klucz] = roz.uruchom_silnik(nazwa, folder,
                                           lambda f=folder, s=silnik_mod, p=podglad_mod: _engine(f, s, p, cfg, ask))

    summary = roz.podsumowanie(licznik, odrzucone_na_wejsciu, wyniki)
    ok = all(w["status"] == "OK" for w in wyniki.values()) and not odrzucone_na_wejsciu
    return {"ok": ok, "summary": summary, "results": wyniki, "counts": licznik}


def _engine(folder, silnik_mod, podglad_mod, cfg, ask) -> int:
    """Uruchamia silnik oddziału w procesie. Zwraca kod wyjścia jak proces (0 = OK)."""
    silnik_dir = os.path.join(folder, "silnik")
    os.makedirs(silnik_dir, exist_ok=True)
    pod = _load(podglad_mod)
    pod.SCRIPT_DIR = silnik_dir            # CSV dla Arkusza Google zostaje w folderze użytkownika
    pod.BASE_DIR = folder
    sys.modules["generuj_podglad"] = pod   # silnik robi „import generuj_podglad”
    eng = _load(silnik_mod)
    eng.SCRIPT_DIR = silnik_dir
    eng.BASE_DIR = folder
    eng.EMAIL_CONFIG_FILE = os.path.join(silnik_dir, "email_config.txt")
    # poczta: konto i hasło z Ustawień IntegraCRM (zaszyfrowane), a gdy ich brak – stary email_config.txt
    user = (cfg.get("gmail_user") or "").strip()
    pw = (cfg.get("gmail_app_password") or "").replace(" ", "")
    if user and pw:
        eng.EMAIL_NADAWCA = user
        eng._wczytaj_haslo_email = lambda: pw
    recips = cfg.get("marza_recipients") or {}
    key = "wroclaw" if silnik_mod.endswith("wroclaw") else "opole"
    if recips.get(key):
        eng.EMAIL_ODBIORCY = list(recips[key])
    # pytanie z konsoli → okno programu
    eng.input = lambda q="": "T" if ask(q.strip()) else "N"
    try:
        eng.main()
        return 0
    except SystemExit as e:
        return int(e.code or 0) if isinstance(e.code, int) else 1
    except Exception as e:
        import traceback
        print()
        print("NIEOCZEKIWANY BŁĄD:", e)
        try:
            teraz = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(os.path.join(silnik_dir, eng.LOG_NAME), "a", encoding="utf-8") as f:
                f.write(f"=== NIEOCZEKIWANY BŁĄD — {teraz} ===\nNIEOCZEKIWANY BŁĄD: {e}\n"
                        f"{traceback.format_exc()}\n\n")
        except Exception:
            pass
        return 1
    finally:
        sys.modules.pop("generuj_podglad", None)
