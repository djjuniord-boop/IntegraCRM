# Kto teraz nad czym pracuje

Plik wspólny dla wszystkich rozmów (czatów) z Claude pracujących nad programem. **Każda rozmowa przed rozpoczęciem
zmian czyta ten plik (po `git pull`), wpisuje swój wiersz, robi commit i push (z `[skip ci]`), a po skończeniu
(wydanie albo rezygnacja) usuwa swój wiersz.** Jeśli moduł jest zajęty przez inną rozmowę – nie zmieniaj go,
powiedz właścicielowi.

| Od kiedy | Rozmowa (temat) | Gałąź robocza | Moduły / pliki |
|---|---|---|---|
| 2026-11-11 | Drobne poprawki z audytu (odbiorcy, Powiększ, kolejka MARŻY, dziennik zamówień, czytelność WYNIKÓW/STAT, porządki CI) | praca/drobne | app/kontrola/zakladka.py, app/gui.py, app/marza/zakladka.py, app/oferty/, app/wyniki/, app/statystyki/, app/ui.py, supabase/, .github/workflows/ |
