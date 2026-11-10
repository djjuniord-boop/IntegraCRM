# Kto teraz nad czym pracuje

Plik wspólny dla wszystkich rozmów (czatów) z Claude pracujących nad programem. **Każda rozmowa przed rozpoczęciem
zmian czyta ten plik (po `git pull`), wpisuje swój wiersz, robi commit i push (z `[skip ci]`), a po skończeniu
(wydanie albo rezygnacja) usuwa swój wiersz.** Jeśli moduł jest zajęty przez inną rozmowę – nie zmieniaj go,
powiedz właścicielowi.

| Od kiedy | Rozmowa (temat) | Gałąź robocza | Moduły / pliki |
|---|---|---|---|
| 2026-11-10 | Audyt – ETAP 3 (KONTROLA kreator, ekran DZIŚ, limit maili, MFA) | praca/etap3 | app/kontrola/, app/gui.py, app/dzis/ (nowy), supabase/, tests/ |
