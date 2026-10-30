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
  4. Każdy PDF, którego nie udało się przetworzyć, wraca do
     "1. WRZUC RAPORTY TUTAJ\\_ODRZUCONE" razem z plikiem *_POWOD.txt.
  5. Na koncu wypisuje jedno podsumowanie (i dopisuje je do
     _system\\log_rozdzielania.txt).

Wszystkie sciezki sa liczone wzgledem folderu "LATEX Wyniki" - folder
można przenieść w inne miejsce w całości i dalej będzie działał.

Zmienne srodowiskowe (do testow):
  LATEX_TRYB_TESTOWY=1  -> silniki NIE wysylaja e-maili i NIE kopiuja na Dysk.
"""

import os
import sys
import shutil
import datetime

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
            return None, "PDF nie ma żadnej strony"
        text = reader.pages[0].extract_text() or ""
    except Exception as e:
        return None, f"nie udało się odczytać PDF ({e})"

    t = text.lower()
    ma_wroclaw = "serwis wrocław" in t or "serwis wroclaw" in t
    ma_opole = "serwis opole" in t
    if ma_wroclaw and not ma_opole:
        return "wroclaw", ""
    if ma_opole and not ma_wroclaw:
        return "opole", ""
    return None, ("w nagłówku nie ma ani „Serwis Wrocław”, ani „Serwis Opole” "
                  "(to chyba nie jest raport sprzedaży z Integry)")


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
        f.write(f"Oddział: {oddzial_nazwa}\n\nPowód:\n")
        for linia in powod_linie:
            f.write(f"  {linia.strip()}\n")
        f.write("\nCo zrobić: popraw albo wygeneruj raport ponownie w Integrze, dodaj go w zakładce MARŻA\n"
                "i kliknij AKTUALIZUJ WSZYSTKO. Ten plik i PDF obok można potem usunąć.\n")
    return cel


def rozdziel():
    os.makedirs(WRZUC_DIR, exist_ok=True)
    pdfy = sorted(f for f in os.listdir(WRZUC_DIR) if f.lower().endswith(".pdf"))
    if not pdfy:
        log("Brak nowych raportów PDF w folderze \"1. WRZUC RAPORTY TUTAJ\".")
    else:
        n = len(pdfy)
        log(f"Znaleziono {n} " + ("raport" if n == 1 else "raporty" if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14) else "raportów") + " PDF.")
    licznik = {"wroclaw": 0, "opole": 0}
    odrzucone = []
    foldery = {k: d for k, _, d in ODDZIALY}
    for nazwa in pdfy:
        sciezka = os.path.join(WRZUC_DIR, nazwa)
        serwis, problem = wykryj_serwis(sciezka)
        if serwis is None:
            cel = odrzuc(sciezka, "nierozpoznany", [problem])
            odrzucone.append((nazwa, problem))
            log(f"  - {nazwa}: NIEROZPOZNANY → _ODRZUCONE")
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


def kwota(v, znak=False):
    """154186.54 → „154 186,54 zł” (znak=True → „+34 186,04 zł”). Brak liczby → „—”."""
    try:
        t = f"{float(v):{'+' if znak else ''},.2f}"
    except (TypeError, ValueError):
        return "—"
    return t.replace(",", " ").replace(".", ",") + " zł"   # minus: zwykły „-” (tak samo jak _zl w silnikach)


def odmiana(n, jeden, kilka, wiele):
    n = abs(int(n))
    if n == 1:
        return jeden
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return kilka
    return wiele


def _na_liczbe(t):
    """„154 186,54” / „154186.54” → 154186.54; „None”, „—” → None."""
    t = (t or "").replace("zł", "").replace("\xa0", "").replace(" ", "").replace("−", "-").strip()
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


# fragmenty dziennika silnika, po których program rozpoznaje przebieg (te same teksty wypisują silniki)
T_ZMIANY = "Zaktualizowano w Excelu:"
T_PODGLAD_LINIA = "  Miesiąc: "
T_PODGLAD_OK = "Odświeżono plik podglądowy"
T_PODGLAD_BLAD = "nie udało się wygenerować pliku podglądowego"
T_DYSK_OK = "Skopiowano na Dysk Google"
T_DYSK_BLAD = ("folder Dysku Google nie znaleziony", "nie udało się skopiować pliku na Dysk")
T_WYSLANO = "Wysłano "
T_MAIL_BLAD = ("nie udało się wysłać e-maila", "NIE zostało wysłane")
T_MAIL_BRAK_ODBIORCOW = "brak zaznaczonych odbiorców"
T_BRAK_PDF = "Brak nowych plików PDF"
T_ODCZYT_BLAD = ("Żaden plik PDF nie został poprawnie odczytany", "Błędy odczytu")
T_POMINIETO = "POMINIĘTO"
T_BLAD = "BŁĄD:"
T_TESTOWY = "[TRYB TESTOWY]"


def _parsuj_zmiane(l):
    """„  Październik 2026: 120000.5 -> 154186.54 zł  (z pliku r.pdf)” → słownik (None, gdy to nie ta linia)."""
    import re
    m = re.match(r"^\s+(.+?): (.+?) -> (.+?) zł(?:\s+\(z pliku (.+)\))?\s*$", l)
    if not m:
        return None
    return {"miesiac": m.group(1), "bylo": _na_liczbe(m.group(2)), "jest": _na_liczbe(m.group(3)),
            "plik": m.group(4) or ""}


def _parsuj_podglad(l):
    """„  Miesiąc: Październik 2026 | Cel: 300 000,00 zł | Zrobione: 154 186,54 zł” → (miesiąc, cel, zrobione)."""
    if not l.startswith(T_PODGLAD_LINIA) or "| Cel:" not in l:
        return None
    try:
        mies, cel, zrob = [c.split(":", 1)[1].strip() for c in l.split("|")]
    except ValueError:
        return None
    return mies, _na_liczbe(cel), _na_liczbe(zrob)


def uruchom_silnik(nazwa, folder, run_engine, info=None):
    """Uruchamia silnik oddziału (w procesie programu) i zwraca słownik z wynikiem.

    info – to, co program podsłuchał w silniku (runner._engine): {"reports": [...], "podglad": (...),
    "chmura": {...}}. Z niego i z dziennika silnika powstają dane do czytelnego przebiegu w zakładce
    (miesiąc, było → jest, cel, kroki ✔/✖). Brak danej = None (zakładka pokazuje „—”)."""
    info = info if info is not None else {}
    log_silnika = os.path.join(folder, "silnik", "log_aktualizacji.txt")
    wynik = {"status": "OK", "uwagi": [], "zmiany": [], "odrzucone": [], "odrzucone_powody": {}, "w_kolejce": [], "info": [],
             "miesiac": None, "cel": None, "zrobione": None, "bylo": None, "jest": None, "zmiana": None,
             "procent": None, "emaile": None, "odjete": None, "raporty": [],
             "kroki": {"raport": None, "kalkulator": None, "podglad": None, "dysk": None, "email": None,
                       "baza": None}}

    def uwaga(tekst, status="UWAGA"):
        if status == "BŁĄD":
            wynik["status"] = "BŁĄD"
        elif wynik["status"] == "OK":
            wynik["status"] = "UWAGA"
        if tekst not in wynik["uwagi"]:
            wynik["uwagi"].append(tekst)

    rozmiar_przed = os.path.getsize(log_silnika) if os.path.exists(log_silnika) else 0
    proc = _Proc(run_engine())

    nowy_log = ""
    if os.path.exists(log_silnika):
        with open(log_silnika, "rb") as f:
            f.seek(rozmiar_przed)
            nowy_log = f.read().decode("utf-8", errors="replace")
    linie = nowy_log.splitlines()
    tekst = nowy_log
    kroki = wynik["kroki"]

    if proc.returncode != 0:
        uwaga("Silnik zakończył się błędem – szczegóły w „Szczegóły przebiegu”. Zgłoś to administratorowi.", "BŁĄD")

    # zmiany w kalkulatorze („Zaktualizowano w Excelu:” + linie „  miesiąc: stara -> nowa zł (z pliku …)”)
    w_sekcji = False
    for l in linie:
        if l.startswith(T_ZMIANY):
            w_sekcji = True
            continue
        if w_sekcji:
            z = _parsuj_zmiane(l) if l.startswith("  ") and "->" in l else None
            if z:
                wynik["zmiany"].append(z)
            else:
                w_sekcji = False
        p_ = _parsuj_podglad(l)
        if p_:
            wynik["miesiac"], wynik["cel"], wynik["zrobione"] = p_
        if l.startswith(T_WYSLANO):
            try:
                wynik["emaile"] = int(l.split()[1])
            except (IndexError, ValueError):
                pass
            wynik["info"].append(l.strip())
        elif l.startswith(T_TESTOWY):
            wynik["info"].append(l.strip())

    # podsłuchane raporty (kwota z raportu, odjęte kategorie w Opolu)
    for r in info.get("reports") or []:
        wynik["raporty"].append({"plik": r.get("source"), "miesiac": r.get("label"),
                                 "marza": r.get("margin_netto"), "z_raportu": r.get("margin_raw"),
                                 "odjeto": r.get("deduction"),
                                 "odjete": [(n, v, brak) for n, v, brak in (r.get("deduction_details") or [])]})
    pod = info.get("podglad")
    if pod and wynik["miesiac"] is None:
        try:
            wynik["miesiac"], wynik["cel"], wynik["zrobione"] = (list(pod) + [None] * 3)[:3]
            wynik["cel"], wynik["zrobione"] = _na_liczbe(str(wynik["cel"])), _na_liczbe(str(wynik["zrobione"]))
        except Exception:
            pass

    # było → jest dla miesiąca z podglądu (gdy go nie ma – ostatnia zmiana)
    if wynik["zmiany"]:
        z = next((z for z in reversed(wynik["zmiany"]) if z["miesiac"] == wynik["miesiac"]), wynik["zmiany"][-1])
        wynik["bylo"], wynik["jest"] = z["bylo"], z["jest"]
        if wynik["miesiac"] is None:
            wynik["miesiac"] = z["miesiac"]
        if z["jest"] is not None:
            wynik["zmiana"] = round(z["jest"] - (z["bylo"] or 0), 2)
        rap = next((r for r in wynik["raporty"] if r["plik"] == z["plik"]), None)
        if rap and rap["odjete"]:
            wynik["odjete"] = {"z_raportu": rap["z_raportu"], "odjeto": rap["odjeto"], "pozycje": rap["odjete"]}
    try:
        if wynik["cel"]:
            wynik["procent"] = round(100 * float(wynik["zrobione"]) / float(wynik["cel"]))
    except (TypeError, ValueError, ZeroDivisionError):
        pass

    # kroki ✔ (True) / ✖ (False) / — (None = nie dotyczy)
    if T_BRAK_PDF in tekst:
        wynik["info"].append("Brak nowego raportu – odświeżono tylko podgląd dla handlowców.")
    elif wynik["raporty"] or "Odczytane raporty:" in tekst:
        kroki["raport"] = bool(wynik["raporty"]) or not any(t in tekst for t in T_ODCZYT_BLAD)
    if any(t in tekst for t in T_ODCZYT_BLAD):
        if not wynik["raporty"]:
            kroki["raport"] = False
        uwaga("Co najmniej jeden raport nie dał się odczytać – nie został zapisany i leży w „_ODRZUCONE”. "
              "Wygeneruj go ponownie w Integrze i dodaj jeszcze raz.")
    if wynik["zmiany"]:
        kroki["kalkulator"] = True
    elif kroki["raport"]:
        kroki["kalkulator"] = False
    if T_POMINIETO in tekst:
        uwaga("Co najmniej jeden raport został pominięty (zły zakres dat albo brak miesiąca w kalkulatorze) – "
              "leży w „_ODRZUCONE”. Popraw go i dodaj ponownie.")
    if T_BLAD in tekst:
        kroki["kalkulator"] = False
        for l in linie:
            if T_BLAD in l:
                uwaga(l.strip().replace("BŁĄD: ", "Błąd: ", 1), "BŁĄD")
        if "nie mogę zapisać" in tekst:
            uwaga("Kalkulator był otwarty w Excelu – zamknij go i kliknij AKTUALIZUJ WSZYSTKO jeszcze raz.", "BŁĄD")
    if T_PODGLAD_OK in tekst:
        kroki["podglad"] = True
    if T_PODGLAD_BLAD in tekst.lower():
        kroki["podglad"] = False
        uwaga("Nie udało się odświeżyć podglądu dla handlowców – szczegóły w „Szczegóły przebiegu”.")
    if T_DYSK_OK in tekst:
        kroki["dysk"] = True
    if any(t in tekst for t in T_DYSK_BLAD):
        kroki["dysk"] = False
        uwaga("Dysk Google niedostępny – podgląd dla handlowców NIE trafił na Dysk. Sprawdź, czy Dysk Google "
              "działa na tym komputerze, i kliknij AKTUALIZUJ WSZYSTKO jeszcze raz.")
    if wynik["emaile"]:
        kroki["email"] = True
    if any(t in tekst for t in T_MAIL_BLAD):
        kroki["email"] = False
        uwaga("E-mail NIE został wysłany – sprawdź internet i ustawienia poczty, potem kliknij "
              "AKTUALIZUJ WSZYSTKO jeszcze raz.")
    if T_MAIL_BRAK_ODBIORCOW in tekst:
        wynik["emaile"] = 0
        wynik["info"].append("E-mail nie został wysłany – brak zaznaczonych odbiorców (MARŻA → „Odbiorcy e-maili”).")

    ch = info.get("chmura")
    if ch:
        if ch.get("baza") is not None:
            kroki["baza"] = bool(ch["baza"])
        for t in ch.get("uwagi") or []:
            uwaga(t)

    # PDF-y, które zostały w folderze oddziału = nieprzetworzone → _ODRZUCONE
    zapisane = {z["plik"] for z in wynik["zmiany"]}
    for nazwa_pdf in sorted(os.listdir(folder)):
        if not nazwa_pdf.lower().endswith(".pdf"):
            continue
        sciezka = os.path.join(folder, nazwa_pdf)
        if nazwa_pdf in zapisane:   # zapisany w kalkulatorze, ale silnik nie zdołał go usunąć
            try:
                os.remove(sciezka)
            except OSError:
                uwaga(f"Raport {nazwa_pdf} jest już zapisany w kalkulatorze, ale nie dało się go usunąć "
                      f"z folderu „{os.path.basename(folder)}” – usuń go ręcznie.")
            continue
        powod = [l for l in linie if nazwa_pdf in l and "->" not in l]
        if not powod and T_BLAD in tekst:
            # przyczyna przejściowa zgłoszona przez silnik (kalkulator otwarty w Excelu, brak pliku) – raport nie jest
            # winny: wraca do KOLEJKI, żeby „AKTUALIZUJ WSZYSTKO jeszcze raz” go zapisało
            try:
                os.makedirs(WRZUC_DIR, exist_ok=True)
                shutil.move(sciezka, _wolna_sciezka(WRZUC_DIR, nazwa_pdf))
                wynik["w_kolejce"].append(nazwa_pdf)
                uwaga(f"Raport {nazwa_pdf} NIE został zapisany i wrócił do kolejki – usuń przyczynę "
                      "i kliknij AKTUALIZUJ WSZYSTKO jeszcze raz. Jeśli się powtarza – zgłoś administratorowi.")
                continue
            except OSError:
                pass
        if not powod and proc.returncode != 0:
            # nieoczekiwany błąd silnika powtórzyłby się przy każdej próbie – raport do _ODRZUCONE z treścią błędu
            powod = [l for l in linie if l.startswith("NIEOCZEKIWANY BŁĄD:")] or \
                    ["silnik zakończył się błędem"]
            powod.append("jeśli raport jest poprawny, zgłoś to administratorowi")
        if not powod:
            powod = ["silnik nie przetworzył tego pliku"]
        wynik["odrzucone_powody"][nazwa_pdf] = powod[0].strip().replace(nazwa_pdf, "", 1).strip(" :—-") or powod[0].strip()
        powod.append("szczegóły w logu: " + os.path.relpath(log_silnika, ROOT_DIR))
        odrzuc(sciezka, nazwa, powod)
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
        p(f" [{znak}] {nazwa}: nowych raportów {licznik[klucz]}")
        for z in w["zmiany"]:
            p(f"           {z['miesiac']}: {kwota(z['bylo'])} → {kwota(z['jest'])}"
              + (f"  (z pliku {z['plik']})" if z["plik"] else ""))
        for u in w["info"]:
            p(f"           - {u}")
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
    p(" WSZYSTKO W PORZĄDKU." if wszystko_ok else
      " SĄ UWAGI – przeczytaj powyżej. Odrzucone pliki leżą w:\n"
      "   1. WRZUC RAPORTY TUTAJ\\_ODRZUCONE")
    p("=" * 64)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write("\n".join(_linie_podsumowania) + "\n\n")
    except Exception:
        pass
    return list(_linie_podsumowania)
