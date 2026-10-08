"""Wersja programu i lista zmian (wyświetlana w zakładce Pomoc)."""

VERSION = "0.7.0"
RELEASED = "2026-10-08"

# Domyślne źródło aktualizacji (adres do version.json albo folder). Można je nadpisać
# w Ustawieniach (data/config.json -> update_source). Puste = aktualizacje wyłączone.
DEFAULT_UPDATE_SOURCE = ""

CHANGELOG = [
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
