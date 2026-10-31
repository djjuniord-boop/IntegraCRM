# Moduł MARŻA

**Co robi:** kalkulator marży Wrocław + Opole – odpowiednik „AKTUALIZUJ WSZYSTKO”. Raporty „Raport sprzedaży towarów
i usług” (PDF z Integry) trafiają do kolejki, silniki wpisują kwotę „Marża towary + sprzedaż usług netto” do
kalkulatorów Excel w folderze użytkownika „LATEX Wyniki”, odświeżają podgląd dla handlowców na Dysku Google
i wysyłają mail z wykresem. Po zalogowaniu: mail przez serwer, wyniki do bazy, kopia kalkulatora w chmurze.

**Raporty PDF nie są przechowywane:** dodanie do kolejki (`runner.add_reports`) plik **przenosi** (gdy się nie da –
kopiuje i próbuje usunąć oryginał; błąd usunięcia = tylko uwaga), a po udanym zapisie w kalkulatorze silnik PDF
**usuwa** (dawniej folder „przetworzone”). Raporty pominięte/odrzucone trafiają do
„1. WRZUC RAPORTY TUTAJ\_ODRZUCONE” (+ `*_POWOD.txt`) – do poprawienia i ponownego dodania. „Usuń” w kolejce
kasuje plik z komputera (z pytaniem). Do chmury idzie tylko kalkulator (`_cloud_save`), nazwa raportu zostaje
w `marza_results.source_pdf`.

**Dodawanie do kolejki (w tle):** `zakladka.marza_add` uruchamia `runner.add_reports` + `pending_info` w wątku
(pasek „Dodaję raport…” z kołem postępu); pytanie o zastąpienie raportu (`_marza_ui_call`) i komunikaty idą
z wątku okna. `runner.inspect` pamięta wynik wg (ścieżka, rozmiar, czas zmiany) – odświeżenie kolejki nie czyta
PDF-ów ponownie; po przeniesieniu wynik jest przypisany do pliku w kolejce. Czytana tylko 1. strona
(`PdfReader(..., strict=False)`). Czas dodania: linia „Dodano raport w 0,4 s (odczyt …, przeniesienie …, kolejka …)”
w dzienniku przebiegu + zdarzenie `log_event` (`pomiar` / „MARŻA dodanie”, sekundy w `p_detail`) – w tle, błąd pomijany.

**Koło postępu:** `ui.WheelProgress` (wspólny widżet: felga z pierścieniem, `start/set/done/reset`) obok paska stanu
w czasie aktualizacji i dodawania. Procent z linii dziennika – `zakladka.marza_step_fraction` (krok 1 = 3%,
Wrocław 8–52%, Opole 54–98%: odczyt, kalkulator, podgląd, e-maile, baza); koniec = `done('ok'|'warn'|'bad')` → ✔/⚠/✖,
bez zaplanowanych klatek; po `WHEEL_HIDE_MS` (4 s) koło znika, żeby karty miały miejsce na małym ekranie.

**Czytelny przebieg:** w trakcie pasek pokazuje bieżący krok (`zakladka.marza_step_text` – linie
`--- Krok N/3: … ---` z `runner._run` + fragmenty dziennika silnika). Po zakończeniu karta na oddział: status ✔/⚠/✖,
miesiąc, było → jest, zmiana, cel, zrobione, % wykonania, liczba e-maili, kroki ✔/✖/— (raport, kalkulator, podgląd,
Dysk Google, e-maile, baza/WYNIKI), w Opolu rozwijane odjęte kategorie, uwagi prostym językiem „co zrobić”.
Pełny dziennik – przycisk „Szczegóły przebiegu (pełny dziennik)…” (osobne okno). Dane kart: `rozdziel.uruchom_silnik`
(dziennik silnika + podsłuch `runner._listen` + wynik `_cloud_save`) → `run_all()["results"]`; brak danej = `None` → „—”.
Uprawnienie: moduł `marza`.

## Pliki

| Plik | Rola |
|---|---|
| `zakladka.py` | `MarzaMixin` – zakładka MARŻA: folder, kolejka raportów, „AKTUALIZUJ WSZYSTKO” (wątek), dziennik przebiegu |
| `okna.py` | okna: Odbiorcy maili (zapis firmowy); Wyniki online i Kopie w chmurze – przyciski usunięte z zakładki; klasy zostają, bo importuje je `gui.py` i sprawdza `ui_smoke` |
| `runner.py` | uruchamia silniki w procesie programu, podmienia ścieżki/pocztę, **podsłuch do chmury** (`_cloud_hooks`, `_cloud_save`), miesiące dla zakładki WYNIKI (`_save_months`) |
| `rozdziel.py` | rozdziela raporty na oddziały, **rozpoznaje przebieg z dziennika silnika** (stałe `T_*` – te same teksty co w silnikach; zmieniasz tekst w silniku → zmień stałą i test), dane kart, podsumowanie; `kwota()` = „154 186,54 zł” |
| `silnik_wroclaw.py`, `silnik_opole.py` | **oryginalne skrypty kalkulatorów** (Excel, wykres, mail) |
| `podglad_wroclaw.py`, `podglad_opole.py` | podgląd dla handlowców (`PODGLAD_dla_handlowcow.xlsx`, kopia na Dysk Google) |

## Zasady, których nie wolno złamać

- **Nie zmieniamy obliczeń w silnikach.** Program je tylko uruchamia i podsłuchuje (`extract_text`, `parse_report`,
  `_refresh_podglad`) – zmiana logiki silnika = zmiana wyników finansowych; tylko na wyraźne życzenie właściciela.
- Silnik robi `import smtplib` w funkcji – po zalogowaniu `runner` na czas przebiegu podstawia `sys.modules["smtplib"]`
  (`_ServerSMTP` → funkcja `send-mail`, akcja `raw`) i **zawsze przywraca** prawdziwą bibliotekę (albo ją usuwa).
- Odbiorcy maili: wyłącznie `app_config['crm'].marza` (zaznaczeni). W kodzie silników `EMAIL_ODBIORCY = []`.
- Silniki mają rok 2026 na sztywno (celowo – na 2027 powstaje nowy plik kalkulatora).
- `import generuj_podglad` w silniku działa, bo `runner` podstawia ten moduł – `tests/check_imports.py` go pomija.

## Dane w bazie

- `marza_results` – wynik każdej aktualizacji (oddział, miesiąc, marża, cel, zrobione, nazwa pliku źródłowego, folder kopii).
- `marza_months` – dane zakładki WYNIKI: cała tabela miesięcy kalkulatora oddziału (`branch`, `year`, `month`, `label`,
  `target`, `done`, `holidays` = święta z arkusza „Święta PL” w tym miesiącu, `updated_at`). Zapis po każdym udanym
  przebiegu silnika (po zalogowaniu, nie w trybie testowym), nadpisuje oddział+rok+miesiąc
  (`on_conflict=branch,year,month`). Błąd zapisu = tylko „Uwaga: …” w dzienniku przebiegu.
  - Miesiące i święta – `podglad_*._read_source_months` (te same co w podglądzie dla handlowców); wiersz z etykietą
    innej postaci niż „Październik 2026” jest pomijany; ten sam miesiąc dwa razy → ostatni wiersz (tam pisze silnik).
  - Liczby – z wartości **zapisanych w pliku** (`openpyxl data_only=True`): liczba → float, pusta komórka → `None`
    (podgląd i mail pokazują wtedy 0). **Formuła** w kolumnie celu/marży daje wynik tylko, jeśli zapisał go Excel –
    openpyxl formuł nie liczy, a zapis kalkulatora przez silnik kasuje zapisane wyniki, więc po imporcie raportu
    formuła = `None` (+ „Uwaga: … formuły bez wyliczonej wartości” w dzienniku). Cele trzeba wpisywać liczbami.
- Schowek plików `marza` (Supabase Storage, prywatny): `<oddział>/<rok>/<data_godzina>/` kalkulator (starsze kopie
  mają też PDF-y raportów – okno „Kopie w chmurze” pobiera je jak każdy plik).

## Dziennik silnika – czego nie ruszać

- Linia `  <miesiąc>: <stara> -> <nowa> zł  (z pliku …)` pod „Zaktualizowano w Excelu:” **zostaje w starym formacie**
  (liczby z kropką) – silnik czyta ją z `log_aktualizacji.txt` do karty „MARZA DZISIAJ” (`_MD_CHANGE_RE`). Zakładka
  pokazuje te kwoty po polsku sama.
- Pozostałe kwoty w dzienniku są po polsku (`_zl` w silnikach), e-maile: „Wysłano 2 powiadomienia e-mail …” (`_odmiana`),
  0 odbiorców: „E-mail nie został wysłany – brak zaznaczonych odbiorców.”

## Testy

- `app/selftest.py` – biblioteki i wykres do maila (`marza_chart_bytes`).
- `tests/test_marza.py` – przeniesienie przy dodaniu (i plik zablokowany), pełny przebieg na prawdziwych silnikach
  w trybie testowym (zapisany PDF usunięty, pominięty w `_ODRZUCONE`, dane kart), rozpoznawanie tekstów dziennika,
  kwoty i odmiana, krok w pasku, brak wysyłki PDF; podsłuch silnika na udawanym silniku i udawanej sesji: wysyłka przez serwer, kopia plików,
  zapis wyniku, przywrócenie `smtplib`; miesiące dla WYNIKÓW na kalkulatorze testowym (formuła z wynikiem Excela
  i bez, święta tylko z danego miesiąca i roku, błąd sesji/odczytu nie przerywa przebiegu, tryb testowy nic nie wysyła).
- `tests/test_marza.py` (cd.) – pamięć `inspect` (bez ponownego czytania PDF), dodanie w wątku nie blokuje okna
  (pętla okna, wynik w kolejce, linia czasu w dzienniku), koło: `set`/`done` nie rzucają, po `done()` brak `after`,
  postęp z linii dziennika (rośnie, nowy przebieg od zera). Testy okna wymagają ekranu (`xvfb-run`), bez niego – pominięte.
- `tests/ui_smoke.py` – zakładka i trzy okna MARŻY.
