# Moduł WYNIKI (wyniki marży dla handlowców)

**Co robi:** zakładka WYNIKI pokazuje wynik marży oddziału w bieżącym miesiącu – zrobione, cel, % realizacji celu,
plan na dziś, tempo, prognozę, ile trzeba dziennie, wykres narastająco i poprzednie miesiące. Tylko odczyt z bazy,
bez Excela i bez sieci poza dwoma zapytaniami (szybkie). Odświeża się co 5 min, gdy zakładka jest otwarta.

Kto co widzi (pilnuje baza, funkcja `can_see_marza`): handlowiec z modułem `wyniki` – tylko oddziały z konta
(Latex Wrocław → `wroclaw`, Latex Opole → `opole`); moduł `marza` i admin – oba. Stangum Opole nie ma wyników.

## Pliki

| Plik | Rola |
|---|---|
| `dane.py` | obliczenia bez okna: dni sprzedażowe, podsumowanie miesiąca, wybór miesiąca, punkty wykresu |
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

`tests/test_wyniki.py` (wzory, puste wartości, wybór miesiąca, wykres, oddziały konta) i `tests/ui_smoke.py`
(role: admin – oba oddziały, handlowiec Wrocław – tylko WYNIKI i Wrocław, Stangum – brak wyników).
