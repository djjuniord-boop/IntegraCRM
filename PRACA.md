# Kto teraz nad czym pracuje

Plik wspólny dla wszystkich rozmów (czatów) z Claude pracujących nad programem. **Każda rozmowa przed rozpoczęciem
zmian czyta ten plik (po `git pull`), wpisuje swój wiersz, robi commit i push (z `[skip ci]`), a po skończeniu
(wydanie albo rezygnacja) usuwa swój wiersz.** Jeśli moduł jest zajęty przez inną rozmowę – nie zmieniaj go,
powiedz właścicielowi.

| Od kiedy | Rozmowa (temat) | Gałąź robocza | Moduły / pliki |
|---|---|---|---|
| 2026-11-27 | Zdjęcia felg z bazy (bez logowania pracowników) | praca/zdjecia-felg | app/oferty/okno.py, silnik.py, index.html; supabase (xp_felgi_foto, bucket felgi-foto) |
