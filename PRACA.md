# Kto teraz nad czym pracuje

Plik wspólny dla wszystkich rozmów (czatów) z Claude pracujących nad programem. **Każda rozmowa przed rozpoczęciem
zmian czyta ten plik (po `git pull`), wpisuje swój wiersz, robi commit i push (z `[skip ci]`), a po skończeniu
(wydanie albo rezygnacja) usuwa swój wiersz.** Jeśli moduł jest zajęty przez inną rozmowę – nie zmieniaj go,
powiedz właścicielowi.

| Od kiedy | Rozmowa (temat) | Gałąź robocza | Moduły / pliki |
|---|---|---|---|
| 2026-11-10 | Audyt – ETAP 1 (rok 2027 MARŻA, pośrednik xPartner, wycofanie wersji, KONTROLA 1366, rozmiary opon, SQL uprawnień) | praca/etap1 | app/marza/silnik_*, podglad_*, app/oferty/ (okno, silnik, koszyk, zamowienia), app/updater.py, app/logowanie.py, app/kontrola/zakladka.py, tests/ui_smoke.py, supabase/, .github/workflows/xp_oferta.yml |
