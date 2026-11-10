# Kto teraz nad czym pracuje

Plik wspólny dla wszystkich rozmów (czatów) z Claude pracujących nad programem. **Każda rozmowa przed rozpoczęciem
zmian czyta ten plik (po `git pull`), wpisuje swój wiersz, robi commit i push (z `[skip ci]`), a po skończeniu
(wydanie albo rezygnacja) usuwa swój wiersz.** Jeśli moduł jest zajęty przez inną rozmowę – nie zmieniaj go,
powiedz właścicielowi.

| Od kiedy | Rozmowa (temat) | Gałąź robocza | Moduły / pliki |
|---|---|---|---|
| 2026-11-10 | Audyt – ETAP 2 (klawiatura i wygląd, MARŻA podgląd, WYNIKI, czuwanie, RODO, komunikaty, martwy kod) | praca/etap2 | app/ui.py, app/gui.py, app/czuwanie.py, app/marza/, app/wyniki/, app/kontrola/, app/uzytkownicy/, app/oferty/silnik.py, supabase/, tests/ |
