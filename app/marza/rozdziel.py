# -*- coding: utf-8 -*-
"""
AKTUALIZUJ WSZYSTKO - rozdziela raporty i aktualizuje oba kalkulatory (LATEX)
=============================================================================

Uruchamiany przyciskiem "AKTUALIZUJ WSZYSTKO" (na Pulpicie).

Co robi, po kolei:
  1. Bierze wszystkie PDF-y z folderu "1. WRZUC RAPORTY TUTAJ".
  2. Rozpoznaje oddzial po TRESCI raportu (Integra wpisuje "Serwis Wrocław"
     albo "Serwis Opole" w naglowku) i przenosi plik do folderu oddzialu.
  3. Uruchamia silnik Wroclawia, potem silnik Opola (kazdy: kopia zapasowa,
     wpis do kalkulatora, podglad + CSV na Dysk Google, e-mail).
  4. Kazdy PDF, ktorego nie udalo sie przetworzyc, wraca do
     "1. WRZUC RAPORTY TUTAJ\\_ODRZUCONE" razem z plikiem *_POWOD.txt.
  5. Na koncu wypisuje jedno podsumowanie (i dopisuje je do
     _system\\log_rozdzielania.txt).

Wszystkie sciezki sa liczone wzgledem folderu "LATEX Wyniki" - folder
mozna przeniesc w inne miejsce w calosci i dalej bedzie dzialal.

Zmienne srodowiskowe (do testow):
  LATEX_TRYB_TESTOWY=1  -> silniki NIE wysylaja maili i NIE kopiuja na Dysk.
"""

import os
import sys
import shutil
import datetime
import subprocess

sys.dont_write_bytecode = True

# IntegraCRM: ścieżki ustawiane przez configure() (folder „LATEX Wyniki” wybrany w programie)
SYSTEM_DIR = ROOT_DIR = WRZUC_DIR = ODRZUCONE_DIR = LOG_PATH = ""
ODDZIALY = []
_linie_podsumowania = []


def configure(root):
    global SYSTEM_DIR, ROOT_DIR, WRZUC_DIR, ODRZUCONE_DIR, LOG_PATH, ODDZIALY, _linie_podsumowania
    ROOT_DIR = root
    SYSTEM_DIR = os.path.join(root, "_system")
    os.makedirs(SYSTEM_DIR, exist_ok=True)
    WRZUC_DIR = os.path.join(ROOT_DIR, "1. WRZUC RAPORTY TUTAJ")
    ODRZUCONE_DIR = os.path.join(WRZUC_DIR, "_ODRZUCONE")
    LOG_PATH = os.path.join(SYSTEM_DIR, "log_rozdzielania.txt")
    ODDZIALY = [
        ("wroclaw", "WROCŁAW", os.path.join(ROOT_DIR, "Wrocław")),
        ("opole", "OPOLE", os.path.join(ROOT_DIR, "Opole")),
    ]
    _linie_podsumowania = []


def log(msg=""):
    print(msg, flush=True)


def wykryj_serwis(pdf_path):
    """Zwraca ('wroclaw'|'opole'|None, opis_problemu)."""
    try:
        import pypdf
    except ImportError:
        return None, "brak biblioteki pypdf (zainstaluj: py -m pip install pypdf)"
    try:
        reader = pypdf.PdfReader(pdf_path)
        if not reader.pages:
            return None, "PDF nie ma zadnej strony"
        text = reader.pages[0].extract_text() or ""
    except Exception as e:
        return None, f"nie udalo sie odczytac PDF ({e})"

    t = text.lower()
    ma_wroclaw = "serwis wrocław" in t or "serwis wroclaw" in t
    ma_opole = "serwis opole" in t
    if ma_wroclaw and not ma_opole:
        return "wroclaw", ""
    if ma_opole and not ma_wroclaw:
        return "opole", ""
    return None, ("w naglowku nie ma ani 'Serwis Wrocław', ani 'Serwis Opole' "
                  "(to chyba nie jest raport sprzedazy z Integry)")


def _wolna_sciezka(folder, nazwa):
    cel = os.path.join(folder, nazwa)
    if not os.path.exists(cel):
        return cel
    base, ext = os.path.splitext(nazwa)
    i = 2
    while os.path.exists(os.path.join(folder, f"{base}_{i}{ext}")):
        i += 1
    return os.path.join(folder, f"{base}_{i}{ext}")


def odrzuc(sciezka_pdf, oddzial_nazwa, powod_linie):
    """Przenosi PDF do _ODRZUCONE i zapisuje obok plik z powodem."""
    os.makedirs(ODRZUCONE_DIR, exist_ok=True)
    cel = _wolna_sciezka(ODRZUCONE_DIR, os.path.basename(sciezka_pdf))
    shutil.move(sciezka_pdf, cel)
    teraz = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(os.path.splitext(cel)[0] + "_POWOD.txt", "w", encoding="utf-8") as f:
        f.write(f"Plik: {os.path.basename(cel)}\n")
        f.write(f"Odrzucony: {teraz}\n")
        f.write(f"Oddzial: {oddzial_nazwa}\n\nPowod:\n")
        for linia in powod_linie:
            f.write(f"  {linia.strip()}\n")
        f.write("\nCo zrobic: popraw/wygeneruj raport ponownie w Integrze, wrzuc go do\n"
                "folderu \"1. WRZUC RAPORTY TUTAJ\" i kliknij AKTUALIZUJ WSZYSTKO.\n"
                "Ten plik i PDF obok mozna potem usunac.\n")
    return cel


def rozdziel():
    os.makedirs(WRZUC_DIR, exist_ok=True)
    pdfy = sorted(f for f in os.listdir(WRZUC_DIR) if f.lower().endswith(".pdf"))
    if not pdfy:
        log("Brak nowych raportow PDF w folderze \"1. WRZUC RAPORTY TUTAJ\".")
    else:
        log(f"Znaleziono {len(pdfy)} raport(ow) PDF.")
    licznik = {"wroclaw": 0, "opole": 0}
    odrzucone = []
    foldery = {k: d for k, _, d in ODDZIALY}
    for nazwa in pdfy:
        sciezka = os.path.join(WRZUC_DIR, nazwa)
        serwis, problem = wykryj_serwis(sciezka)
        if serwis is None:
            cel = odrzuc(sciezka, "nierozpoznany", [problem])
            odrzucone.append((nazwa, problem))
            log(f"  - {nazwa}: NIEROZPOZNANY -> _ODRZUCONE")
            continue
        folder = foldery[serwis]
        cel = _wolna_sciezka(folder, nazwa)
        shutil.move(sciezka, cel)
        licznik[serwis] += 1
        log(f"  - {nazwa}: {'WROCŁAW' if serwis == 'wroclaw' else 'OPOLE'}")
    return licznik, odrzucone


class _Proc:
    def __init__(self, code):
        self.returncode = code


def uruchom_silnik(nazwa, folder, run_engine):
    """Uruchamia silnik oddzialu (w procesie programu) i zwraca slownik z wynikiem."""
    log_silnika = os.path.join(folder, "silnik", "log_aktualizacji.txt")
    wynik = {"status": "OK", "uwagi": [], "zmiany": [], "odrzucone": []}

    rozmiar_przed = os.path.getsize(log_silnika) if os.path.exists(log_silnika) else 0
    proc = _Proc(run_engine())

    nowy_log = ""
    if os.path.exists(log_silnika):
        with open(log_silnika, "rb") as f:
            f.seek(rozmiar_przed)
            nowy_log = f.read().decode("utf-8", errors="replace")
    linie = nowy_log.splitlines()

    if proc.returncode != 0:
        wynik["status"] = "BŁĄD"
        wynik["uwagi"].append("silnik zakonczyl sie bledem (szczegoly w dzienniku)")

    # zmiany w kalkulatorze
    w_sekcji = False
    for l in linie:
        if l.startswith("Zaktualizowano w Excelu:"):
            w_sekcji = True
            continue
        if w_sekcji:
            if l.startswith("  ") and "->" in l:
                wynik["zmiany"].append(l.strip())
            else:
                w_sekcji = False

    tekst = nowy_log
    if "Brak nowych plików PDF" in tekst:
        wynik["uwagi"].append("brak nowych raportow - odswiezono tylko podglad")
    if "Żaden plik PDF nie został poprawnie odczytany" in tekst or "Błędy odczytu" in tekst:
        if wynik["status"] == "OK":
            wynik["status"] = "UWAGA"
        wynik["uwagi"].append("co najmniej jeden raport zostal odrzucony")
    if "POMINIĘTO" in tekst:
        if wynik["status"] == "OK":
            wynik["status"] = "UWAGA"
        wynik["uwagi"].append("co najmniej jeden raport zostal pominiety")
    if "BŁĄD:" in tekst:
        wynik["status"] = "BŁĄD"
        for l in linie:
            if "BŁĄD:" in l:
                wynik["uwagi"].append(l.strip())
    if "folder Dysku Google nie znaleziony" in tekst or "nie udało się skopiować pliku na Dysk" in tekst:
        if wynik["status"] == "OK":
            wynik["status"] = "UWAGA"
        wynik["uwagi"].append("Dysk Google niedostepny - Arkusz Google NIE zostal zaktualizowany")
    if "nie udalo sie wyslac e-maila" in tekst or "NIE zostalo wyslane" in tekst:
        if wynik["status"] == "OK":
            wynik["status"] = "UWAGA"
        wynik["uwagi"].append("e-mail NIE zostal wyslany")
    if "Nie udało się wygenerować pliku podglądowego" in tekst or "nie udało się wygenerować pliku podglądowego" in tekst:
        if wynik["status"] == "OK":
            wynik["status"] = "UWAGA"
        wynik["uwagi"].append("nie udalo sie wygenerowac podgladu dla handlowcow")
    for l in linie:
        if l.startswith("Wyslano ") or l.startswith("[TRYB TESTOWY]"):
            wynik["uwagi"].append(l.strip())

    # PDF-y, ktore zostaly w folderze oddzialu = nieprzetworzone -> _ODRZUCONE
    for nazwa_pdf in sorted(os.listdir(folder)):
        if not nazwa_pdf.lower().endswith(".pdf"):
            continue
        powod = [l for l in linie if nazwa_pdf in l and "->" not in l]
        if not powod and proc.returncode != 0:
            powod = [l for l in linie if l.startswith("NIEOCZEKIWANY BŁĄD:")] or \
                    ["silnik zakonczyl sie bledem"]
        if not powod:
            powod = ["silnik nie przetworzyl tego pliku"]
        powod.append("szczegoly w logu: " + os.path.relpath(log_silnika, ROOT_DIR))
        odrzuc(os.path.join(folder, nazwa_pdf), nazwa, powod)
        wynik["odrzucone"].append(nazwa_pdf)
    if wynik["odrzucone"] and wynik["status"] == "OK":
        wynik["status"] = "UWAGA"
    return wynik


def p(msg=""):
    _linie_podsumowania.append(msg)
    log(msg)


def podsumowanie(licznik, odrzucone_na_wejsciu, wyniki):
    teraz = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log()
    p("=" * 64)
    p(f" PODSUMOWANIE  ({teraz})")
    p("=" * 64)
    for klucz, nazwa, _ in ODDZIALY:
        w = wyniki[klucz]
        znak = {"OK": "OK   ", "UWAGA": "UWAGA", "BŁĄD": "BŁĄD "}[w["status"]]
        p(f" [{znak}] {nazwa}: nowych raportow {licznik[klucz]}")
        for z in w["zmiany"]:
            p(f"           {z}")
        for u in w["uwagi"]:
            p(f"           - {u}")
        for o in w["odrzucone"]:
            p(f"           - ODRZUCONY: {o}  (patrz _ODRZUCONE)")
    if odrzucone_na_wejsciu:
        p(" [UWAGA] Nierozpoznane pliki (przeniesione do _ODRZUCONE):")
        for n, powod in odrzucone_na_wejsciu:
            p(f"           - {n}: {powod}")
    wszystko_ok = all(w["status"] == "OK" for w in wyniki.values()) and not odrzucone_na_wejsciu
    p("-" * 64)
    p(" WSZYSTKO W PORZADKU." if wszystko_ok else
      " SA UWAGI - przeczytaj powyzej. Odrzucone pliki leza w:\n"
      "   1. WRZUC RAPORTY TUTAJ\\_ODRZUCONE")
    p("=" * 64)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write("\n".join(_linie_podsumowania) + "\n\n")
    except Exception:
        pass
    return list(_linie_podsumowania)
