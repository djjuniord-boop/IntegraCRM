# Kto teraz nad czym pracuje

Plik wspólny dla wszystkich rozmów (czatów) z Claude pracujących nad programem. **Każda rozmowa przed rozpoczęciem
zmian czyta ten plik (po `git pull`), wpisuje swój wiersz, robi commit i push (z `[skip ci]`), a po skończeniu
(wydanie albo rezygnacja) usuwa swój wiersz.** Jeśli moduł jest zajęty przez inną rozmowę – nie zmieniaj go,
powiedz właścicielowi.

| Od kiedy | Rozmowa (temat) | Gałąź robocza | Moduły / pliki |
|---|---|---|---|
| 2026-11-25 | DEPOZYT OPON (spis przechowalni + lista do przygotowania z raportu Integry) | praca/depozyt | app/depozyt/ (nowy), supabase/depozyt_*, app/gui.py, app/cloud.py (MODULES), app/dzis (kafel), tests |
