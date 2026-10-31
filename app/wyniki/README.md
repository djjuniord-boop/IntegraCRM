# Moduł WYNIKI (wyniki marży dla handlowców)

**Co robi:** zakładka WYNIKI pokazuje wynik marży oddziału w bieżącym miesiącu – zrobione, cel, % realizacji celu,
plan na dziś, tempo, prognozę, ile trzeba dziennie, wykres narastająco i poprzednie miesiące. Tylko odczyt z bazy,
bez Excela i bez sieci poza dwoma zapytaniami (szybkie). Odświeża się co 5 min, gdy zakładka jest otwarta.

Kto co widzi (pilnuje baza, funkcja `can_see_marza`): handlowiec z modułem `wyniki` – tylko oddziały z konta
(Latex Wrocław → `wroclaw`, Latex Opole → `opole`); moduł `marza` i admin – oba. Stangum Opole nie ma wyników.

## Edycja przez administratora (tylko `session.is_admin`; inni nie widzą przycisków)

- **Zmiana celu**: „✎ Zmień cel…” przy celu bieżącego miesiąca albo dwuklik wiersza w „Poprzednie miesiące” →
  okno z nowym celem (kwota po polsku: spacje, przecinek; > 0). Miesiąc z kalkulatora dostaje `target_pending`
  – cel trafi do Excela przy najbliższej aktualizacji MARŻY (oznaczenie „✎”, w kaflu „czeka na Excel”).
- **„+ Dodaj miesiąc…”**: brakujący zamknięty miesiąc (np. sprzed kalkulatora) – oddział, miesiąc, rok, cel
  i zrobione (wymagane). Istniejący miesiąc → propozycja zmiany celu. Ręczne miesiące (`manual`) – dopisek
  „(ręcznie)”, w ich edycji można zmienić też „zrobione”. Liczą się w tabeli/% celu/kolorach jak pozostałe.
- Zapis: RPC `admin_set_month(p_branch, p_year, p_month, p_target, p_done)` w wątku, wynik przez `after`,
  potem odświeżenie. Baza: `supabase/wyniki_cele_2026-10-31.sql` (tylko administrator – sprawdza baza).
- Tabela pokazuje do 12 poprzednich miesięcy (z przewijaniem).

## Pliki

| Plik | Rola |
|---|---|
| `dane.py` | obliczenia bez okna: dni sprzedażowe, podsumowanie miesiąca, wybór miesiąca, punkty wykresu, kwoty po polsku, parametry RPC, oznaczenia |
| `zakladka.py` | `WynikiMixin` – układ zakładki, wczytanie w tle, rysowanie paska i wykresu (Tk Canvas, bez matplotlib) |

## Wzory (takie same jak wykres w mailu MARŻY – `silnik_*._generuj_wykres_png`)

- dni sprzedażowe: dni miesiąca bez niedziel i świąt (`holidays` z kalkulatora); dziś liczy się jako „do zrobienia”,
- plan na dziś = cel × dni_minęło / dni_wszystkie; **tempo** = zrobione / plan na dziś,
- **prognoza** = zrobione / dni_minęło × dni_wszystkie; potrzeba dziennie = brakuje / dni_zostało.
- `target`/`done` mogą być puste (komórka pusta albo formuła bez wyliczonej wartości) → „—”, nigdy dzielenie przez None.

## Dane w bazie

- `marza_months` (oddział, rok, miesiąc, etykieta, cel, zrobione, święta, kiedy) – zapisuje MARŻA po każdej
  aktualizacji (`marza/runner.py → _save_months`), cała tabela miesięcy z kalkulatora.
- `marza_results` – kolejne aktualizacje (punkty wykresu narastająco w bieżącym miesiącu).

## Testy

`tests/test_wyniki.py` (wzory, puste wartości, wybór miesiąca, wykres, oddziały konta, kwota po polsku, wywołanie `admin_set_month`, brak edycji dla nie-admina, oznaczenia „(ręcznie)”/„✎”) i `tests/ui_smoke.py`
(role: admin – oba oddziały, handlowiec Wrocław – tylko WYNIKI i Wrocław, Stangum – brak wyników; okna zmiany celu i dodania miesiąca u admina, brak przycisków edycji u innych).
