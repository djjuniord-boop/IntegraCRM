# Integra 7 ↔ CRM – kontrola eksportu zleceń (wersja przenośna)

Cały program jest w jednym folderze – można go skopiować na inny komputer albo na pendrive.

## Pierwsze uruchomienie (raz na komputer / folder)
1. Rozpakuj folder gdziekolwiek (najlepiej ścieżka bez spacji, np. `C:\IntegraCRM`).
2. Uruchom `Przygotuj.bat` (potrzebny internet). Pobiera Pythona i Tesseracta **do podfolderu `runtime`** –
   nic nie instaluje w systemie. Jeśli Tesseract jest już w `C:\Program Files\Tesseract-OCR`, kopiuje go stamtąd.
3. Uruchom `Start.bat`. Przy pierwszym starcie otworzą się Ustawienia – wpisz hasło aplikacji Google.

## Struktura
- `app\` – kod programu (podmieniany przy aktualizacji)
- `data\` – ustawienia (`config.json`), kopia poprzedniej wersji, log błędów – aktualizacja tego nie rusza
- `runtime\` – Python i Tesseract (tworzone przez `Przygotuj.bat`)

## Aktualizacje
Przy starcie program sprawdza źródło aktualizacji (Ustawienia → „Źródło aktualizacji”: adres do
`version.json` albo folder). Jeśli jest nowsza wersja – pobiera ją, robi kopię obecnej i uruchamia się
ponownie. Zakładka **Pomoc** pokazuje wersję i listę zmian, ma przyciski „Sprawdź aktualizacje”
i „Przywróć poprzednią wersję”. Gdyby program po aktualizacji nie chciał się uruchomić, użyj
`Przywroc-poprzednia.bat`.

## Dla autora: wydanie nowej wersji
1. Zmień `VERSION`, `RELEASED` i dopisz wpis na górze `CHANGELOG` w `app\version.py`.
2. `python tools\publish.py` → powstaje `release\version.json` i `release\integra-<wersja>.zip`.
3. Wgraj oba pliki do źródła aktualizacji (nadpisz poprzednie).

## Obsługa
1. Wybierz PDF z Integra 7.
2. W CRM zrób wycinek ekranu (Win+Shift+S), wróć do programu i naciśnij Ctrl+V.
3. „Sprawdź” – wynik i (gdy czegoś brakuje) gotowy mail. „Wyślij maila” wysyła go po potwierdzeniu.

## Źródło aktualizacji na Dysku Google (instrukcja dla autora)
1. `python tools\publish.py` → `release\integra-<wersja>.zip` i `release\version.json`.
2. Wgraj `integra-<wersja>.zip` na Dysk, ustaw udostępnianie „Każdy mający link – Przeglądający”. Z linku weź ID pliku.
3. `python tools\publish.py "https://drive.google.com/uc?export=download&id=<ID_ZIP>"` – wpisze ten adres do `version.json`.
4. Wgraj `version.json` na Dysk (też „Każdy mający link”). Adres do Ustawień → „Źródło aktualizacji”:
   `https://drive.google.com/uc?export=download&id=<ID_VERSION_JSON>`
5. Kolejne wydania: w Dysku wgraj nowe pliki o tych samych nazwach jako „Zarządzaj wersjami” (ID i linki się nie zmieniają).
