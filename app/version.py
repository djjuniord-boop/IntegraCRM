"""Wersja programu i lista zmian (wyświetlana w zakładce Pomoc)."""

VERSION = "0.15.1"
RELEASED = "2026-10-13"

# Domyślne źródło aktualizacji (adres do version.json albo folder). Można je nadpisać
# w Ustawieniach (data/config.json -> update_source). Puste = aktualizacje wyłączone.
DEFAULT_UPDATE_SOURCE = "https://github.com/djjuniord-boop/IntegraCRM/releases/latest/download/version.json"

# Adres odbioru anonimowych statystyk (Google Apps Script). Puste = zdarzenia czekają w kolejce.
STATS_URL = "https://script.google.com/macros/s/AKfycby7Du6o7t6jtA9jDKrAXQsONfz33y1Aga1V4OGrHlBYmrcFo5WV184ttB66bPJOtgqy/exec"

CHANGELOG = [
    {"version": "0.15.1", "date": "2026-10-13",
     "changes": ["Naprawiony zapis ustawień firmowych (odbiorcy, nadawca) przez administratora"]},
    {
        "version": "0.15.0",
        "date": "2026-10-13",
        "changes": [
            "Historia sprawdzeń wspólna dla wszystkich komputerów (w bazie) – z informacją kto i dla którego oddziału",
            "Rejestr „zgłaszany już” wspólny dla oddziałów – ten sam numer nie jest zgłaszany dwa razy; "
            "dotychczasowy rejestr z tego komputera przenosi się automatycznie",
            "Ustawienia firmowe (administrator): nadawca, odbiorcy domyślni i osobni odbiorcy dla każdego oddziału",
            "Mail z brakami trafia do odbiorców oddziałów zaznaczonych przy sprawdzaniu",
        ],
    },
    {
        "version": "0.14.0",
        "date": "2026-10-13",
        "changes": [
            "Logowanie przy starcie (konto zakłada administrator), opcja „Zapamiętaj mnie na tym komputerze”",
            "Zakładki według uprawnień konta: Kontrola CRM, MARŻA, SERWIS QR",
            "Oddziały w kontroli CRM ograniczone do przydzielonych użytkownikowi",
            "Zakładka UŻYTKOWNICY dla administratora: dodawanie kont, moduły, oddziały, blokowanie, zmiana hasła, "
            "ostatnie logowanie i wersja programu",
            "SERWIS QR: auta przypisane do oddziałów – pracownik widzi tylko swoje",
            "Program wymaga internetu; zbyt stara wersja sama się aktualizuje",
        ],
    },
    {
        "version": "0.13.9",
        "date": "2026-10-13",
        "changes": [
            "Raport .xlsx z CRM: porównanie dokładne – podobny numer innego auta nie ukrywa już prawdziwego braku",
            "Ostrzeżenie, gdy dane z CRM prawie nie pasują do Integry (zły oddział lub okres) – mail nie jest wtedy przygotowywany",
            "Wysyłka maila w tle, z limitem czasu – okno nie zamarza przy słabym internecie",
            "Statystyki nie blokują już okna, gdy brak internetu",
            "Rejestr „zgłaszany już”: tylko pewne braki, wpisy wygasają po 60 dniach",
            "Bezpieczny zapis ustawień i historii (przerwanie nie psuje plików), poprawki raportów CSV i tematu maila",
            "SERWIS QR: zdjęcia ostatniej wizyty widoczne od razu na stronie klienta",
        ],
    },
    {
        "version": "0.13.8",
        "date": "2026-10-13",
        "changes": [
            "Krok 2: można wczytać raport .xlsx z „Listy kontrolne” w CRM (przycisk albo przeciągnięcie) – "
            "bez OCR, bez błędów odczytu",
            "Wybór serwisów do sprawdzenia: Latex Wrocław, Latex Opole, Stangum Opole (zapamiętywany)",
            "Ostrzeżenie, gdy raport z CRM nie obejmuje wszystkich dni z raportu Integry",
            "Wklejanie wycinka ekranu (Ctrl+V) działa jak dotąd",
        ],
    },
    {
        "version": "0.13.7",
        "date": "2026-10-13",
        "changes": [
            "SERWIS QR: po „Uruchom ponownie” panel nie zostaje już porzucony poza ekranem "
            "(znikają „martwe” pozycje na pasku zadań i fałszywy komunikat „Panel został zamknięty”).",
            "SERWIS QR: okno panelu czekające na osadzenie nie pokazuje się na pasku zadań; zamykanie panelu "
            "kończy też procesy Edge WebView2.",
            "SERWIS QR: pewniejsze wyszukiwanie okna panelu i dziennik kroków osadzania w data\\serwis.log.",
        ],
    },
    {
        "version": "0.13.6",
        "date": "2026-10-13",
        "changes": [
            "SERWIS QR: panel działa wewnątrz zakładki programu (jedno okno) – uruchamia się sam przy wejściu "
            "w zakładkę, chowa przy przejściu na inną i zamyka razem z programem.",
            "SERWIS QR: ustawienia panelu pod przyciskiem „Ustawienia panelu”, przycisk „Uruchom ponownie”.",
        ],
    },
    {
        "version": "0.13.5",
        "date": "2026-10-13",
        "changes": [
            "SERWIS QR: naprawiony błąd „Failed to resolve Python.Runtime.Loader.Initialize” – program sam zdejmuje "
            "z bibliotek okna znacznik Windows „pobrano z internetu”.",
        ],
    },
    {
        "version": "0.13.4",
        "date": "2026-10-13",
        "changes": [
            "SERWIS QR: naprawione otwieranie okna panelu (błąd biblioteki okna przy funkcjach programu "
            "i blokada przy wysuwaniu okna na wierzch). Panel działa wyłącznie w oknie programu.",
        ],
    },
    {
        "version": "0.13.3",
        "date": "2026-10-13",
        "changes": [
            "SERWIS QR: program śledzi uruchamianie okna panelu (etapy, czas) zamiast od razu pisać „otwarty”; "
            "przy problemie pokazuje przyczynę z dziennika data\\serwis.log i proponuje przeglądarkę.",
            "SERWIS QR: okno panelu wysuwa się na wierzch po otwarciu.",
        ],
    },
    {
        "version": "0.13.2",
        "date": "2026-10-13",
        "changes": [
            "SERWIS QR: poprawny opis trybu lokalnego w oknie programu; ikona Latex w oknie panelu i na pasku zadań.",
        ],
    },
    {
        "version": "0.13.1",
        "date": "2026-10-13",
        "changes": [
            "BETA SERWIS QR: panel otwiera się jako okno programu (bez przeglądarki). Wymaga nowej paczki .exe.",
            "SERWIS QR: dane panelu zapisywane w folderze programu (data\\serwis_webview), kopia zapasowa przez okno „Zapisz jako”.",
        ],
    },
    {
        "version": "0.13.0",
        "date": "2026-10-13",
        "changes": [
            "BETA (kanał testowy): zakładka SERWIS QR – historia wymian oleju i innych prac, naklejka z kodem QR "
            "pod maskę, strona historii dla klienta. Włączana w Ustawieniach.",
            "SERWIS QR: tryb lokalny (dane w przeglądarce) z kopią zapasową albo baza Supabase.",
        ],
    },
    {
        "version": "0.12.3",
        "date": "2026-10-09",
        "changes": [
            "MARŻA: po „Wyczyść kolejkę” lub „✕ Usuń” komunikat pokazuje aktualny stan kolejki (zamiast starego „Dodano…”).",
        ],
    },
    {
        "version": "0.12.2",
        "date": "2026-10-09",
        "changes": [
            "MARŻA: kolejka raportów z przyciskiem „✕ Usuń” przy każdym pliku i „Wyczyść kolejkę”",
            "MARŻA: najwyżej 1 raport na oddział – przy drugim pytanie o podmianę",
            "MARŻA: raport sprawdzany już przy dodawaniu – inne pliki (np. faktura, raport serwisu) są odrzucane z powodem",
        ],
    },
    {
        "version": "0.12.1",
        "date": "2026-10-09",
        "changes": ["MARŻA: program sam szuka folderu „LATEX Wyniki” (Pulpit, Dokumenty, Dysk Google); "
                    "przyciski bez wskazanego folderu proponują jego wybór"],
    },
    {
        "version": "0.12.0",
        "date": "2026-10-09",
        "changes": [
            "Nowa zakładka MARŻA (do włączenia w Ustawieniach): kalkulator marży Wrocław + Opole – te same "
            "reguły co „AKTUALIZUJ WSZYSTKO”, przeciąganie raportów, podgląd dla handlowców i e-maile",
        ],
    },
    {
        "version": "0.11.2",
        "date": "2026-10-09",
        "changes": [
            "Automatyczne zgłaszanie błędów do autora: rodzaj błędu, miejsce w programie i miejsce w kodzie "
            "(bez treści komunikatów, numerów, adresów i ścieżek)",
            "Nieoczekiwane błędy w oknie są zapisywane do data/error.log i pokazywane, zamiast cichej awarii",
        ],
    },
    {
        "version": "0.11.1",
        "date": "2026-10-09",
        "changes": ["Włączone wysyłanie anonimowych statystyk do arkusza właściciela programu"],
    },
    {
        "version": "0.11.0",
        "date": "2026-10-09",
        "changes": [
            "Anonimowe statystyki użycia (tylko liczby: uruchomienia, sprawdzenia, maile, błędy) – "
            "bez numerów, adresów e-mail i haseł; do wyłączenia w Ustawieniach",
        ],
    },
    {
        "version": "0.10.3",
        "date": "2026-10-09",
        "changes": [
            "Nazwa nadawcy maila (domyślnie „Kontrola eksportu – Latex Serwis”) – do zmiany w Ustawieniach",
        ],
    },
    {
        "version": "0.10.2",
        "date": "2026-10-09",
        "changes": [
            "Mniej pozycji „do weryfikacji”: numery różniące się tylko znakami typowo mylonymi przez OCR "
            "(9/S, 0/O, 1/I, 5/S, 8/B…) są uznawane za ten sam numer – informacja pod wynikiem",
        ],
    },
    {
        "version": "0.10.1",
        "date": "2026-10-09",
        "changes": [
            "Kliknięcie brakującego numeru kopiuje go do schowka, przycisk „Kopiuj wszystkie”",
            "Szczegóły odczytu w osobnym, dużym oknie",
            "Treść maila: przycisk „Powiększ” – edycja w dużym oknie",
            "Okno programu otwiera się na pełnym ekranie",
        ],
    },
    {
        "version": "0.10.0",
        "date": "2026-10-09",
        "changes": [
            "Odczyt raportu Integry z kolumny „Pojazd” – numer brany dokładnie z pozycji przed „ - marka”",
            "Rozpoznawane tablice indywidualne (np. D4DDY), pomijane wiersze bez pojazdu",
            "Koniec fałszywych numerów z PDF (np. daty „od 2026”, „eDrive40”)",
            "Ostrzeżenie, gdy wycinek z CRM nie obejmuje wszystkich dni z raportu Integry",
            "Dokładniejsza lista „do weryfikacji” (bez przekłamań z dodatkowych przebiegów OCR)",
        ],
    },
    {
        "version": "0.9.0",
        "date": "2026-10-09",
        "changes": [
            "Przeciąganie plików: PDF z Integry i zrzut z CRM można upuścić na okno (przycisk wyboru zostaje)",
            "Nowa zakładka Historia – każde sprawdzenie zapisywane, plik otwiera się w Excelu",
            "Numery zgłoszone wcześniej są oznaczane („zgłoszony …”) na ekranie i w mailu",
            "Kopia (DW) wysyłanego maila do nadawcy – do wyłączenia w Ustawieniach",
            "Hasło aplikacji Google zapisywane w postaci zaszyfrowanej (Windows DPAPI)",
        ],
    },
    {
        "version": "0.8.5",
        "date": "2026-10-09",
        "changes": [
            "Naprawa: odczyt wycinka (OCR) nie działał, gdy nazwa użytkownika Windows ma polskie znaki "
            "(np. C:\\Users\\Użytkownik)",
            "Naprawa: Ctrl+V w temacie i treści maila wkleja tekst (wcześniej próbował wkleić obraz)",
            "Uszkodzony plik ustawień nie blokuje już uruchomienia programu",
            "Każda wersja jest automatycznie testowana na Windows przed publikacją",
        ],
    },
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
