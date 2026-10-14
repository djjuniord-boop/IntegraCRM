# Moduł MARŻA

**Co robi:** kalkulator marży Wrocław + Opole – odpowiednik „AKTUALIZUJ WSZYSTKO”. Raporty „Raport sprzedaży towarów
i usług” (PDF z Integry) trafiają do kolejki, silniki wpisują kwotę „Marża towary + sprzedaż usług netto” do
kalkulatorów Excel w folderze użytkownika „LATEX Wyniki”, odświeżają podgląd dla handlowców na Dysku Google
i wysyłają mail z wykresem. Po zalogowaniu: mail przez serwer, wyniki do bazy, kopia plików w chmurze.
Uprawnienie: moduł `marza`.

## Pliki

| Plik | Rola |
|---|---|
| `zakladka.py` | `MarzaMixin` – zakładka MARŻA: folder, kolejka raportów, „AKTUALIZUJ WSZYSTKO” (wątek), dziennik przebiegu |
| `okna.py` | okna: Odbiorcy maili (zapis firmowy), Wyniki online, Kopie w chmurze (pobieranie) |
| `runner.py` | uruchamia silniki w procesie programu, podmienia ścieżki/pocztę, **podsłuch do chmury** (`_cloud_hooks`, `_cloud_save`), miesiące dla zakładki WYNIKI (`_save_months`) |
| `rozdziel.py` | rozdziela raporty na oddziały i podsumowuje przebieg |
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

- `marza_results` – wynik każdej aktualizacji (oddział, miesiąc, marża, cel, zrobione, plik źródłowy, folder kopii).
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
- Schowek plików `marza` (Supabase Storage, prywatny): `<oddział>/<rok>/<data_godzina>/` kalkulator + PDF-y.

## Testy

- `app/selftest.py` – biblioteki i wykres do maila (`marza_chart_bytes`).
- `tests/test_marza.py` – podsłuch silnika na udawanym silniku i udawanej sesji: wysyłka przez serwer, kopia plików,
  zapis wyniku, przywrócenie `smtplib`; miesiące dla WYNIKÓW na kalkulatorze testowym (formuła z wynikiem Excela
  i bez, święta tylko z danego miesiąca i roku, błąd sesji/odczytu nie przerywa przebiegu, tryb testowy nic nie wysyła).
- `tests/ui_smoke.py` – zakładka i trzy okna MARŻY.
