# Kto teraz nad czym pracuje

Plik wspólny dla wszystkich rozmów (czatów) z Claude pracujących nad programem. **Każda rozmowa przed rozpoczęciem
zmian czyta ten plik (po `git pull`), wpisuje swój wiersz, robi commit i push (z `[skip ci]`), a po skończeniu
(wydanie albo rezygnacja) usuwa swój wiersz.** Jeśli moduł jest zajęty przez inną rozmowę – nie zmieniaj go,
powiedz właścicielowi.

| Od kiedy | Rozmowa (temat) | Gałąź robocza | Moduły / pliki |
|---|---|---|---|
| 2026-11-08 | Oferty 0.25: statusy, link dla klienta, porównanie PDF, zrzuty Edge | praca/oferty-025 | app/oferty/*, mobile/www/*, tests/test_oferty.py, tests/ui_oferty_win.py, tools/build_pages.py, build.yml (krok zrzutów), supabase/oferty_status_link_2026-11-08.sql, tabela oferty |
