"""Wersja programu i lista zmian (wyświetlana w zakładce Pomoc)."""

VERSION = "0.8.4"
RELEASED = "2026-10-08"

# Domyślne źródło aktualizacji (adres do version.json albo folder). Można je nadpisać
# w Ustawieniach (data/config.json -> update_source). Puste = aktualizacje wyłączone.
DEFAULT_UPDATE_SOURCE = "https://github.com/djjuniord-boop/IntegraCRM/releases/latest/download/version.json"

CHANGELOG = [
    {
        "version": "0.8.4",
        "date": "2026-10-08",
        "changes": [
            "Stary adres aktualizacji (Dysk Google) usuwany z ustawień – pole puste oznacza GitHub",
        ],
    },
    {
        "version": "0.8.3",
        "date": "2026-10-08",
        "changes": [
            "Aktualizacje pobierane automatycznie z GitHuba (bez ręcznego podmieniania plików na Dysku)",
        ],
    },
    {
        "version": "0.8.2",
        "date": "2026-10-08",
        "changes": [
            "Naprawa: program nie uruchamiał się w pierwszej kompilacji IntegraCRM.exe 0.8.0 (brak modułu tkinter.font)",
        ],
    },
    {
        "version": "0.8.1",
        "date": "2026-10-08",
        "changes": [
            "Szybsze sprawdzanie – odczyt wycinka z CRM wykonywany równolegle (kilka razy krócej)",
        ],
    },
    {
        "version": "0.8.0",
        "date": "2026-10-08",
        "changes": [
            "Wersja IntegraCRM.exe – nie wymaga instalowania Pythona ani uprawnień administratora",
            "Tesseract OCR dołączony do paczki .exe (folder tesseract)",
            "Przygotuj.bat najpierw sprawdza, co jest już zainstalowane",
            "Paczka startowa bez danych autora – każdy wpisuje własny e-mail i odbiorców",
            "Nowy wygląd w barwach Latex Serwis: logo, czerwono-czarne przyciski, karty kroków, "
            "wyraźny wynik i lista brakujących numerów",
        ],
    },
    {
        "version": "0.7.0",
        "date": "2026-10-08",
        "changes": [
            "Numer wersji w tytule okna i nowa zakładka Pomoc z listą zmian",
            "Automatyczna aktualizacja przy starcie (z jednego wspólnego źródła)",
            "Przycisk „Przywróć poprzednią wersję” oraz plik Przywroc-poprzednia.bat",
            "Układ przenośny: program, ustawienia i środowisko w jednym folderze",
            "Przygotuj.bat – jednorazowe przygotowanie środowiska (Python i Tesseract w folderze)",
            "Błędy zapisywane do data/error.log",
        ],
    },
    {
        "version": "0.6.0",
        "date": "2026-10-08",
        "changes": [
            "Ostrzeżenie, gdy w PDF z Integry albo na wycinku nie znaleziono numerów "
            "(wcześniej program pisał „jest dobrze”)",
            "Kilka przebiegów OCR wycinka – mniej błędnie odczytanych numerów",
            "Porównanie toleruje jeden błędny znak (trafia do „do weryfikacji”)",
        ],
    },
    {
        "version": "0.5.0",
        "date": "2026-10-08",
        "changes": [
            "uruchom.bat samo wyszukuje Pythona, dodany instaluj.bat",
            "OCR po angielsku – nie wymaga polskiego pakietu Tesseracta",
        ],
    },
    {
        "version": "0.4.0",
        "date": "2026-10-08",
        "changes": [
            "Odczyt numerów z tabeli „Historia importów” w CRM (także tablice indywidualne, np. D4DDY)",
            "Pomijanie statusu i pozostałych kolumn – liczy się tylko numer rejestracyjny",
        ],
    },
    {
        "version": "0.3.0",
        "date": "2026-10-08",
        "changes": [
            "Okno Ustawienia: konto Gmail, hasło aplikacji, odbiorcy, ścieżka do Tesseracta",
            "Przycisk „Wyślij test”",
        ],
    },
    {
        "version": "0.2.0",
        "date": "2026-10-08",
        "changes": [
            "Wklejanie wycinka ekranu z CRM ze schowka (Ctrl+V)",
            "Dwa przyciski: „Sprawdź” i „Wyślij maila”, edytowalna treść maila",
        ],
    },
    {
        "version": "0.1.0",
        "date": "2026-10-08",
        "changes": [
            "Pierwsza wersja: porównanie numerów rejestracyjnych z PDF z Integry 7 "
            "z raportem CRM i mail do handlowców z brakującymi numerami",
        ],
    },
]
