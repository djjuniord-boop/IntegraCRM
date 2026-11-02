"""Kalkulator marży (Wrocław + Opole) – uruchamiany z zakładki MARŻA.

Odpowiednik „2. AKTUALIZUJ WSZYSTKO.bat” + _system/rozdziel_i_aktualizuj.py, ale silniki działają
w procesie programu (bez osobnego Pythona). Same silniki to niezmienione skrypty
aktualizuj_kalkulator.py / generuj_podglad.py – podmieniane są tylko ścieżki, hasło do poczty
i pytanie „Zapisać mimo to?” (okno zamiast konsoli).

Dane zostają w folderze „LATEX Wyniki” użytkownika: kalkulatory, kopie zapasowe, logi. Raporty PDF nie są
przechowywane: dodanie do kolejki je PRZENOSI, a po zapisie w kalkulatorze silnik je usuwa (pominięte/odrzucone
zostają w „_ODRZUCONE”, żeby można je było poprawić).
"""
import contextlib
import datetime
import importlib
import io
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SESSION = None   # po zalogowaniu (ustawia okno programu): maile przez serwer, wyniki, miesiące dla zakładki WYNIKI
#                  i kopie plików w chmurze

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


_INSPECT_CACHE = {}   # (ścieżka, rozmiar, mtime) → wynik inspect(); ten sam plik nie jest czytany drugi raz


def _file_key(path):
    try:
        st = os.stat(path)
    except OSError:
        return None
    return os.path.normcase(os.path.abspath(path)), st.st_size, st.st_mtime_ns


def inspect(path: str):
    """Sprawdza PDF przed dodaniem. Zwraca (oddział 'wroclaw'|'opole'|None, opis).
    Wynik zapamiętany wg (ścieżka, rozmiar, czas zmiany) – odświeżanie kolejki nie czyta PDF-ów ponownie."""
    key = _file_key(path)
    if key is not None and key in _INSPECT_CACHE:
        return _INSPECT_CACHE[key]
    res = _inspect(path)
    if key is not None and not _nieodczytany(res):   # porażek odczytu nie pamiętamy (plik mógł być w zapisie)
        if len(_INSPECT_CACHE) > 200:
            _INSPECT_CACHE.clear()
        _INSPECT_CACHE[key] = res
    return res


def _remember(path, res):
    """Plik przeniesiony do kolejki ma tę samą treść – wynik inspect() bez ponownego czytania."""
    key = _file_key(path)
    if key is not None and not _nieodczytany(res):
        _INSPECT_CACHE[key] = res


def _nieodczytany(res):
    return not res[0] and str(res[1]).startswith("nie da się odczytać")


def _inspect(path):
    try:
        import pypdf
        with open(path, "rb") as fh:   # tylko 1. strona; strict=False – bez wolnych prób „naprawy” pliku
            text = pypdf.PdfReader(fh, strict=False).pages[0].extract_text() or ""
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


def add_reports(root: str, files, replace=lambda branch, old: True, times=None):
    """Sprawdza i PRZENOSI PDF-y do „1. WRZUC RAPORTY TUTAJ” – najwyżej jeden raport na oddział (oryginał znika
    z miejsca, skąd go wybrano; gdy przeniesienie się nie uda – kopia i próba usunięcia oryginału).
    replace(oddział, stara_nazwa) decyduje, czy podmienić raport już czekający w kolejce.
    times – słownik, do którego dopisywane są sekundy: „odczyt” (PDF), „przeniesienie” (plik).
    Zwraca (dodane: [(nazwa, oddział)], odrzucone: [(nazwa, powód)], uwagi: [(nazwa, uwaga)])."""
    import time
    times = {} if times is None else times
    times.setdefault("odczyt", 0.0)
    times.setdefault("przeniesienie", 0.0)
    dst = os.path.join(root, WRZUC)
    os.makedirs(dst, exist_ok=True)
    added, rejected, notes = [], [], []
    for f in files:
        name = os.path.basename(f)
        if not f.lower().endswith(".pdf"):
            rejected.append((name, "to nie jest plik PDF"))
            continue
        t0 = time.perf_counter()
        res = inspect(f)
        branch, why = res
        times["odczyt"] += time.perf_counter() - t0
        if not branch:
            rejected.append((name, why))
            continue
        src_dir = os.path.normcase(os.path.abspath(os.path.dirname(f)))
        if src_dir == os.path.normcase(os.path.abspath(dst)):
            added.append((name, branch))   # plik już leży w kolejce – bez pytania o zastąpienie, nic nie kasujemy
            continue
        queued = [n for n, b in pending_info(root) if b == branch]
        if queued:
            if not replace(branch, queued[0]):
                rejected.append((name, f"w kolejce jest już raport dla oddziału {BRANCH_NAMES[branch]}"))
                continue
            me = os.path.normcase(os.path.abspath(f))
            for n in queued:
                if os.path.normcase(os.path.abspath(os.path.join(dst, n))) != me:   # nigdy nie kasuj wybieranego
                    remove_pending(root, n)
        target = _wolna(dst, name)
        t0 = time.perf_counter()
        try:
            shutil.move(f, target)
        except OSError:
            try:   # np. plik zablokowany – kopia do kolejki, potem próba usunięcia oryginału
                if not os.path.exists(target):
                    shutil.copy2(f, target)
            except OSError as e:
                rejected.append((name, f"nie udało się dodać pliku do kolejki ({e})"))
                continue
            try:
                os.remove(f)
            except OSError as e:
                notes.append((name, f"raport dodano, ale nie udało się usunąć oryginału ({e}) – usuń go ręcznie"))
        times["przeniesienie"] += time.perf_counter() - t0
        _remember(target, res)
        if src_dir == os.path.normcase(os.path.abspath(os.path.join(dst, "_ODRZUCONE"))):
            powod = os.path.splitext(f)[0] + "_POWOD.txt"   # raport wraca z _ODRZUCONE – opis powodu już zbędny
            try:
                if os.path.isfile(powod):
                    os.remove(powod)
            except OSError:
                pass
        added.append((os.path.basename(target), branch))
    return added, rejected, notes


def pending_info(root: str):
    """[(nazwa, oddział lub None)] dla PDF-ów czekających w kolejce."""
    d = os.path.join(root, WRZUC)
    return [(n, inspect(os.path.join(d, n))[0]) for n in pending(root)]


def remove_pending(root: str, name: str) -> None:
    """Usuwa raport z kolejki – z komputera (dodanie do kolejki przeniosło oryginał, więc to jedyna kopia)."""
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
        print(" [TRYB TESTOWY - bez e-maili i bez Dysku Google]")
    print("=" * 64)
    print()
    print("--- Krok 1/3: rozdzielanie raportów ---")   # zakładka pokazuje bieżący krok (KROK_RE)
    licznik, odrzucone_na_wejsciu = roz.rozdziel()

    wyniki = {}
    for i, (klucz, nazwa, sub, silnik_mod, podglad_mod) in enumerate(ODDZIALY, start=2):
        print()
        print(f"--- Krok {i}/3: {BRANCH_NAMES[klucz]} ---")
        folder = os.path.join(root, sub)
        info = {}
        wyniki[klucz] = roz.uruchom_silnik(
            nazwa, folder, lambda f=folder, s=silnik_mod, p=podglad_mod, i_=info: _engine(f, s, p, cfg, ask, i_),
            info)

    summary = roz.podsumowanie(licznik, odrzucone_na_wejsciu, wyniki)
    ok = all(w["status"] == "OK" for w in wyniki.values()) and not odrzucone_na_wejsciu
    return {"ok": ok, "summary": summary, "results": wyniki, "counts": licznik,
            "rejected_input": list(odrzucone_na_wejsciu)}


KROK_RE = r"^--- Krok (\d)/3: (.+?) ---$"   # linia bieżącego kroku (zakładka MARŻA)


def _engine(folder, silnik_mod, podglad_mod, cfg, ask, info=None) -> int:
    """Uruchamia silnik oddziału w procesie. Zwraca kod wyjścia jak proces (0 = OK).
    info (słownik) dostaje podsłuchane dane dla czytelnego przebiegu: reports, podglad, chmura."""
    info = info if info is not None else {}
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
    if key in recips:   # lista z ustawień (także pusta = nikt nie dostaje maila)
        eng.EMAIL_ODBIORCY = list(recips[key])
    # pytanie z konsoli → okno programu
    eng.input = lambda q="": "T" if ask(q.strip()) else "N"
    cap = _listen(eng)   # podsłuch odczytanych raportów i podglądu (bez zmiany obliczeń)
    info.update(cap)
    if SESSION is not None and os.environ.get("LATEX_TRYB_TESTOWY") != "1":
        try:   # cele zmienione w zakładce WYNIKI → kalkulator, PRZED silnikiem; błąd nigdy nie przerywa przebiegu
            info["cele"] = _apply_targets(eng, key, folder)
        except Exception as e:
            print(f"Uwaga: cele z programu nie zostały sprawdzone: {e}")
            info["cele"] = {"krok": False, "uwagi": ["Cele z programu nie zostały sprawdzone – spróbuj "
                                                     "AKTUALIZUJ WSZYSTKO jeszcze raz."]}
    captured = _cloud_hooks(eng, cap) if SESSION is not None else None
    if captured is not None and not eng.EMAIL_NADAWCA:   # nagłówek „Od” – serwer i tak wstawia swój adres
        eng.EMAIL_NADAWCA = SESSION.email
    real_smtplib = sys.modules.get("smtplib")
    if captured is not None:
        sys.modules["smtplib"] = _server_smtplib()   # silnik robi „import smtplib” – maile idą przez serwer
    try:
        eng.main()
        if captured is not None:
            try:   # błąd chmury nie może zepsuć przebiegu – kalkulator jest już zapisany
                info["chmura"] = _cloud_save(eng, key, folder, captured, pod)
            except Exception as e:
                print(f"Uwaga: zapis w chmurze nie powiódł się: {e}")
                info["chmura"] = {"baza": False, "uwagi": ["Zapis w chmurze nie powiódł się – kalkulator jest "
                                                           "zaktualizowany; wyniki online uzupełnią się przy "
                                                           "następnej aktualizacji."]}
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
        if captured is not None:   # przywrócenie prawdziwej biblioteki poczty (albo jej brak)
            if real_smtplib is not None:
                sys.modules["smtplib"] = real_smtplib
            else:
                sys.modules.pop("smtplib", None)


# ---------- chmura: maile przez serwer, wyniki i kopie plików ----------
class _ServerSMTP:
    """Zastępuje smtplib.SMTP w silniku: gotowa wiadomość (HTML z wykresem) idzie przez serwer firmy."""

    def __init__(self, *a, **k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def starttls(self, *a, **k):
        pass

    def login(self, *a, **k):
        pass

    def quit(self):
        pass

    def sendmail(self, frm, to, msg):
        import cloud
        r = SESSION.call("POST", "/functions/v1/send-mail", {"action": "raw", "to": list(to), "raw": msg})
        if isinstance(r, dict) and r.get("error"):
            raise cloud.CloudError(r["error"])
        return {}


def _server_smtplib():
    import types
    m = types.ModuleType("smtplib")
    m.SMTP = m.SMTP_SSL = _ServerSMTP
    return m


def _listen(eng) -> dict:
    """Podsłuch silnika (bez zmiany obliczeń): odczytane raporty i wynik podglądu. Treści PDF-ów nie zbieramy."""
    cap = {"reports": [], "podglad": None}
    o_parse, o_ref = eng.parse_report, eng._refresh_podglad

    def parse(text, name):
        r = o_parse(text, name)
        cap["reports"].append(r)
        return r

    def ref(*a, **k):
        r = o_ref(*a, **k)
        cap["podglad"] = r
        return r
    eng.parse_report, eng._refresh_podglad = parse, ref
    return cap


def _cloud_hooks(eng, cap=None) -> dict:
    """Po zalogowaniu: hasło poczty niepotrzebne (maile idą przez serwer). Zwraca podsłuch (cap)."""
    eng._wczytaj_haslo_email = lambda: "serwer"
    return cap if cap is not None else _listen(eng)


def _cloud_save(eng, key, folder, cap, pod=None):
    """Po udanym przebiegu: kopia kalkulatora w schowku (bez raportów PDF – nie są przechowywane), wyniki do bazy,
    miesiące dla zakładki WYNIKI. Każdy krok ma osobną obsługę błędu – błąd chmury nie psuje przebiegu
    (kalkulator jest już zapisany). Zwraca {"baza": True/False/None, "uwagi": [...]} dla zakładki."""
    out = {"baza": None, "uwagi": []}
    if not cap["reports"] and not cap["podglad"]:
        return out
    if os.environ.get("LATEX_TRYB_TESTOWY") == "1":
        print("[TRYB TESTOWY] Wyniki i kalkulator NIE zostały zapisane w chmurze.")
        return out
    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    base = f"{key}/{stamp[:4]}/{stamp}"
    xlsx = os.path.join(folder, eng.XLSX_NAME)
    try:
        if os.path.isfile(xlsx):
            with open(xlsx, "rb") as f:
                SESSION.upload("marza", f"{base}/{eng.XLSX_NAME}", f.read(),
                               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        print(f"Kopia kalkulatora zapisana w chmurze ({base}).")
    except Exception as e:
        print(f"Uwaga: kopia w chmurze nie powiodła się: {e}")
        out["uwagi"].append("Kopia kalkulatora w chmurze nie zapisała się (kalkulator na komputerze jest "
                            "zaktualizowany).")
        base = None
    try:
        def num(v):
            try:
                return round(float(v), 2)
            except (TypeError, ValueError):
                return None
        label = cel = zrob = None
        if cap["podglad"]:
            label, cel, zrob = (list(cap["podglad"]) + [None, None, None])[:3]
        rows = []
        for r in cap["reports"] or [{"label": label}]:
            same = r.get("label") == label
            rows.append({"branch": key, "month_label": r.get("label"), "period_from": r.get("start_date"),
                         "period_to": r.get("end_date"), "margin": r.get("margin_netto"),
                         "target": num(cel) if same else None,
                         "done": num(zrob) if same else None,
                         "source_pdf": r.get("source"), "files_path": base})
        SESSION.call("POST", "/rest/v1/marza_results", rows, prefer="return=minimal")
        print("Wyniki zapisane w bazie (widoczne w programie na każdym komputerze).")
        out["baza"] = True
    except Exception as e:
        print(f"Uwaga: zapis wyników w bazie nie powiódł się: {e}")
        out["baza"] = False
        out["uwagi"].append("Wyniki nie zapisały się w bazie (Wyniki online) – kalkulator jest zaktualizowany; "
                            "kliknij AKTUALIZUJ WSZYSTKO jeszcze raz, gdy będzie internet.")
    if pod is not None and _save_months(pod, key, xlsx) is False:
        out["baza"] = False
        out["uwagi"].append("Zakładka WYNIKI nie została uzupełniona – szczegóły w „Szczegóły przebiegu”.")
    return out


# ---------- cele zmienione w zakładce WYNIKI (target_pending) → kalkulator Excel ----------
def _find_month_rows(ws):
    """Jak silnik (find_month_rows): {etykieta: wiersz} od nagłówka „Miesiąc”; ten sam miesiąc dwa razy → ostatni."""
    header = None
    for row in ws.iter_rows(min_row=1, max_row=60):
        for cell in row:
            if cell.value == "Miesiąc":
                header = cell.row
                break
        if header:
            break
    if header is None:
        raise ValueError("w kalkulatorze nie ma nagłówka tabeli miesięcy („Miesiąc”)")
    out, r = {}, header + 1
    while True:
        label = ws.cell(row=r, column=2).value
        if label is None or label == "":
            break
        out[label] = r
        r += 1
    return out


def _backup(eng, xlsx, folder):
    """Kopia zapasowa jak silnik (_make_backup: folder „kopie_zapasowe”, ostatnie 10)."""
    mk = getattr(eng, "_make_backup", None)
    if mk is not None:
        mk(xlsx, [])
        return
    d = os.path.join(folder, "kopie_zapasowe")
    os.makedirs(d, exist_ok=True)
    base, ext = os.path.splitext(os.path.basename(xlsx))
    dst = os.path.join(d, f"{base}_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}{ext}")
    shutil.copy2(xlsx, dst)
    print(f"Kopia zapasowa: {dst}")


def _apply_targets(eng, key, folder):
    """Cele czekające na Excel (marza_months.target_pending) → kolumna celu (C) kalkulatora oddziału.
    Zwraca {"krok": True/False/None, "uwagi": [...]} – None = nic nie czekało (albo stara baza bez kolumny).
    Miesiąc, którego nie ma w kalkulatorze, albo plik otwarty w Excelu → pending zostaje + uwaga na karcie."""
    out = {"krok": None, "uwagi": []}
    try:
        rows = SESSION.call("GET", f"/rest/v1/marza_months?branch=eq.{key}&target_pending=eq.true"
                                   "&select=year,month,target")
    except Exception:
        return out   # stara baza (brak kolumny target_pending) albo brak połączenia – pomijamy bez uwagi
    rows = [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []
    todo = []
    for r in rows:
        try:
            y, m, t = int(r["year"]), int(r["month"]), float(r["target"])
        except (KeyError, TypeError, ValueError):
            continue
        if 1 <= m <= 12:
            todo.append((y, m, round(t, 2)))
    if not todo:
        return out
    nazwy = ", ".join(f"{MONTHS_PL[m - 1]} {y}" for y, m, _ in sorted(todo))
    xlsx = os.path.join(folder, eng.XLSX_NAME)
    import openpyxl
    try:
        wb = openpyxl.load_workbook(xlsx)
        ws = wb["Kalkulator marży"]
        month_rows = {}
        for label, r in _find_month_rows(ws).items():
            ym = _label_ym(label)
            if ym is not None:
                month_rows[ym] = r   # ostatni wiersz wygrywa – tak jak silnik
    except Exception as e:
        print(f"Uwaga: cele z programu ({nazwy}) nie trafiły do kalkulatora: {e}")
        out["krok"] = False
        out["uwagi"].append(f"Cel na {nazwy} z programu nie trafił do kalkulatora – nie da się otworzyć pliku "
                            f"{eng.XLSX_NAME}. Zamknij Excel i kliknij AKTUALIZUJ WSZYSTKO jeszcze raz.")
        return out
    wpisane, brak = [], []
    for y, m, t in sorted(todo):
        r = month_rows.get((y, m))
        if r is None:
            brak.append(f"{MONTHS_PL[m - 1]} {y}")
            continue
        c = ws.cell(row=r, column=3)   # kolumna celu – ta sama, z której czyta podgląd i silnik
        old = c.value
        c.value = int(t) if t == int(t) else t   # tylko wartość – format komórki zostaje
        wpisane.append((y, m, old, t))
    for b in brak:
        print(f"Uwaga: cel na {b} z programu nie trafił do kalkulatora – brak takiego miesiąca w tabeli.")
        out["uwagi"].append(f"Cel na {b} z programu nie trafił do kalkulatora – brak miesiąca w kalkulatorze. "
                            f"Dopisz wiersz „{b}” w Excelu albo zgłoś to administratorowi.")
    if wpisane:
        _backup(eng, xlsx, folder)
        wb.calculation.calcMode = "auto"   # jak silnik – Excel przeliczy formuły po otwarciu
        wb.calculation.fullCalcOnLoad = True
        wb.calculation.calcOnSave = True
        tmp = xlsx + ".tmp"
        try:   # zapis atomowy: najpierw plik obok, potem podmiana (otwarty w Excelu → PermissionError)
            wb.save(tmp)
            os.replace(tmp, xlsx)
        except OSError as e:
            with contextlib.suppress(OSError):
                os.remove(tmp)
            nz = ", ".join(f"{MONTHS_PL[m - 1]} {y}" for y, m, _, _ in wpisane)
            print(f"Uwaga: cele z programu ({nz}) nie zostały zapisane w kalkulatorze: {e}")
            out["krok"] = False
            out["uwagi"].append(f"Cel na {nz} z programu nie trafił do kalkulatora – zamknij Excel i kliknij "
                                f"AKTUALIZUJ WSZYSTKO jeszcze raz.")
            return out
        for y, m, old, t in wpisane:
            print(f"Cel z programu wpisany do kalkulatora: {MONTHS_PL[m - 1]} {y}: {old} -> {t} zł")
            try:
                if _target_written(key, y, m, t) is False:
                    print(f"Uwaga: cel na {MONTHS_PL[m - 1]} {y} zmieniono w trakcie – zostanie wpisany przy "
                          f"następnej aktualizacji.")
            except Exception as e:   # cel jest w Excelu; przy następnym przebiegu wpisze się jeszcze raz (ta sama kwota)
                print(f"Uwaga: nie udało się oznaczyć celu {MONTHS_PL[m - 1]} {y} jako wpisanego: {e}")
    out["krok"] = not brak
    return out


def _target_written(key, y, m, t):
    """Zdejmuje „czeka na Excel”. Nowa baza: 4 argumenty, False = admin zmienił cel w międzyczasie (pending zostaje).
    Stara baza (brak funkcji 4-argumentowej) → wersja 3-argumentowa."""
    path = "/rest/v1/rpc/marza_target_written"
    try:
        r = SESSION.call("POST", path, {"p_branch": key, "p_year": y, "p_month": m, "p_target": t})
    except Exception as e:
        txt = str(e)
        if "marza_target_written" not in txt and "PGRST202" not in txt and "function" not in txt.lower():
            raise
        SESSION.call("POST", path, {"p_branch": key, "p_year": y, "p_month": m})
        return None
    return False if r is False else True


# ---------- zakładka WYNIKI: tabela miesięcy z kalkulatora → baza (marza_months) ----------
MONTHS_PL = ["Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec",
             "Lipiec", "Sierpień", "Wrzesień", "Październik", "Listopad", "Grudzień"]   # jak w silnikach
_MONTHS_LOWER = [m.lower() for m in MONTHS_PL]


def _label_ym(label):
    """„Październik 2026” → (2026, 10). Etykieta, której nie da się odczytać (np. „Razem”) → None."""
    if not isinstance(label, str):
        return None
    parts = label.split()
    if len(parts) != 2 or parts[0].lower() not in _MONTHS_LOWER or not (parts[1].isascii() and parts[1].isdecimal()):
        return None
    year = int(parts[1])
    if not 2000 <= year <= 2100:
        return None
    return year, _MONTHS_LOWER.index(parts[0].lower()) + 1


def _liczba(v):
    """Wartość komórki → float (2 miejsca po przecinku). Puste, tekst, formuła bez wyniku → None (nigdy 0)."""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, str):
        v = v.strip().replace("\xa0", "").replace(" ", "").replace(",", ".")
        if not v or v.startswith("="):
            return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f != f or f in (float("inf"), float("-inf")):   # NaN / nieskończoność – baza ich nie przyjmie
        return None
    return round(f, 2)


def _stored_values(xlsx):
    """{etykieta: (cel, aktualna)} – wartości ZAPISANE w pliku (openpyxl data_only=True): liczby wpisane ręcznie
    i wyniki formuł z ostatniego zapisu w Excelu. openpyxl nie przelicza formuł, a zapis pliku przez silnik
    kasuje ich zapisane wyniki – wtedy formuła daje None."""
    import openpyxl
    wb = openpyxl.load_workbook(xlsx, data_only=True)
    ws = wb["Kalkulator marży"]
    header = None
    for row in ws.iter_rows(min_row=1, max_row=60):   # ten sam nagłówek, którego szuka silnik i podgląd
        for cell in row:
            if cell.value == "Miesiąc":
                header = cell.row
                break
        if header:
            break
    out = {}
    if header is None:
        return out
    r = header + 1
    while True:
        label = ws.cell(row=r, column=2).value
        if label is None or label == "":
            break
        out[label] = (ws.cell(row=r, column=3).value, ws.cell(row=r, column=4).value)
        r += 1
    return out


def _holiday_dates(holidays):
    out = set()
    for d in holidays or ():
        if isinstance(d, datetime.datetime):
            d = d.date()
        elif isinstance(d, str):
            try:
                d = datetime.date.fromisoformat(d.strip()[:10])
            except ValueError:
                continue
        if isinstance(d, datetime.date):
            out.add(d)
    return out


def _months_rows(pod, key, xlsx, now=None):
    """Wiersze tabeli marza_months dla oddziału. Zwraca (wiersze, ile pól to formuły bez zapisanego wyniku).

    Miesiące i święta – z podglądu dla handlowców (pod._read_source_months), żeby WYNIKI miały te same miesiące
    co podgląd. Liczby – z wartości zapisanych w pliku (_stored_values): liczba → float, puste → None,
    formuła z wynikiem zapisanym przez Excel → ten wynik, formuła bez wyniku → None."""
    months, holidays = pod._read_source_months(xlsx)
    stored = _stored_values(xlsx)
    days = _holiday_dates(holidays)
    now = now or datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    rows, no_value = {}, 0
    for label, cel, aktualna in months:
        ym = _label_ym(label)
        if ym is None:
            continue
        year, month = ym
        s_cel, s_akt = stored.get(label, (None, None))
        target, done = _liczba(s_cel), _liczba(s_akt)
        for raw, val in ((cel, target), (aktualna, done)):
            if isinstance(raw, str) and raw.startswith("=") and val is None:
                no_value += 1
        # ten sam miesiąc dwa razy w tabeli → ostatni wiersz (tak jak silnik: find_month_rows)
        rows[(year, month)] = {
            "branch": key, "year": year, "month": month, "label": f"{MONTHS_PL[month - 1]} {year}",
            "target": target, "done": done,
            "holidays": sorted(d.isoformat() for d in days if (d.year, d.month) == (year, month)),
            "updated_at": now,
        }
    return [rows[k] for k in sorted(rows)], no_value


def _ile_miesiecy(n):
    if n == 1:
        return "1 miesiąc"
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return f"{n} miesiące"
    return f"{n} miesięcy"


def _save_months(pod, key, xlsx):
    """Zakładka WYNIKI: cała tabela miesięcy kalkulatora oddziału → baza (nadpisuje oddział+rok+miesiąc).
    Błąd = tylko linia w dzienniku przebiegu; kalkulator, podgląd i e-mail są już zrobione."""
    if SESSION is None:
        return None
    try:
        if not os.path.isfile(xlsx):
            raise ValueError(f"nie ma pliku {os.path.basename(xlsx)}")
        rows, no_value = _months_rows(pod, key, xlsx)
        if not rows:
            raise ValueError("w kalkulatorze nie ma miesięcy w postaci „Październik 2026”")
        SESSION.call("POST", "/rest/v1/marza_months?on_conflict=branch,year,month", rows,
                     prefer="resolution=merge-duplicates,return=minimal")
        print(f"Zakładka WYNIKI: zapisano {_ile_miesiecy(len(rows))} ({BRANCH_NAMES.get(key, key)}).")
        if no_value:
            print(f"Uwaga: niektóre pola celu/marży w kalkulatorze ({no_value}) to formuły bez wyliczonej "
                  f"wartości – w zakładce WYNIKI zostaną puste.")
        return True
    except Exception as e:
        print(f"Uwaga: wyniki dla zakładki WYNIKI nie zostały zapisane: {e}")
        return False
