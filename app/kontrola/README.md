# Moduł KONTROLA CRM (+ HISTORIA)

**Co robi:** porównuje zakończone zlecenia z raportu Integry 7 (PDF) z raportem z CRM (`.xlsx/.csv` z „Listy
kontrolne”) po numerach rejestracyjnych, pokazuje braki i przygotowuje mail do handlowców. Każde sprawdzenie
trafia do wspólnej historii w bazie, a liczniki dzienne (wizyty / listy kontrolne / braki) do `visit_stats`
(zakładka STATYSTYKI). Od 0.21.0 **bez wycinka ekranu (OCR)** – upuszczony obraz → komunikat „pobierz .xlsx”.
OCR (Tesseract) zostaje tylko dla skanów PDF z Integry. Uprawnienie: moduł `crm` + oddziały.

## Pliki

| Plik | Rola |
|---|---|
| `zakladka.py` | `KontrolaMixin` – zakładka KONTROLA: wybór plików, oddziały, „Sprawdź” (wątek), wynik, mail |
| `historia_zakladka.py` | `HistoriaMixin` – zakładka HISTORIA (z bazy, w tle) i eksport do Excela |
| `analyze.py` | cała analiza: PDF → numery, raport CRM → numery, porównanie dokładne, ostrzeżenia (zły oddział/okres), `daily_stats` |
| `plates.py` | wzorce numerów (Integra, w tym `extract_integra_visits` – wiersze z datą), normalizacja; funkcje OCR (`ocr_equal`, `compare`) zostały, ale analiza ich już nie używa |
| `crm_report.py` | odczyt raportu CRM `.xlsx/.csv` (kolumny Data, Rejestracja, Oddział), wybór oddziałów |
| `extract.py` | tekst z PDF (pdfplumber, skan → Tesseract); funkcje OCR obrazu nieużywane od 0.21.0 |
| `mailer.py` | treść maila, wysyłka przez serwer (`send_server`) albo awaryjnie Gmail z komputera |
| `history.py` | historia sprawdzeń i rejestr „zgłoszony już” – w bazie po zalogowaniu, lokalnie bez sesji (testy); `save_visit_stats` |

## Dane w bazie

- `checks` – sprawdzenia (kto, oddziały, liczby, braki, komu wysłano mail). Pracownik widzi swoje i swoich oddziałów.
- `reported` + funkcja `report_plates()` – numery już zgłoszone (wspólne dla oddziałów, wygasają po 60 dniach).
- `visit_stats` przez `rpc/save_visit_stats` – po każdym sprawdzeniu, w wątku, po `add_check`, dla każdego dnia
  z zakresu raportu Integry: `visits` = wiersze zleceń z pojazdem tego dnia (**bez odduplikowania**: to samo auto
  2× = 2 wizyty), `lists` = wiersze raportu CRM tego dnia dla oddziału (bez odduplikowania), `missing` = wizyty,
  których numeru nie ma w CRM **tego samego dnia**. Zapis tylko gdy zaznaczony jest dokładnie jeden serwis
  (PDF z Integry = jeden serwis) i dane pasują (`no_overlap` → bez zapisu); bez sesji – nic. Błąd zapisu =
  linia w „Szczegółach”, sprawdzenie działa dalej.
- `app_config['crm']` – odbiorcy (`recipients`, `by_branch`), nadawca (`sender_name`); zmienia tylko admin.
- Funkcja serwerowa `send-mail` – wysyła tylko do adresów z `app_config['crm']`.

## Zasady, których nie wolno złamać

- **Raport `.xlsx` porównujemy dokładnie** – bez tolerancji na błędy OCR (`ocr_equal`, `_dist_le1`). Inaczej podobny numer innego auta ukryje prawdziwy brak (błąd z audytu 0.13.8).
- Gdy dane z CRM prawie nie pokrywają się z Integrą (`no_overlap`) – ostrzeżenie i **brak gotowego maila**.
- Do rejestru „zgłoszony już” trafiają tylko pewne braki, nie „do weryfikacji”.
- `_check_work` działa w wątku – nie czyta pól okna (dostaje `pdf`, `src` jako argumenty).

## Testy

- `app/selftest.py` – pełna ścieżka na danych z `tools/make_fixtures.py` (`integra.pdf` + `crm.xlsx`; oczekiwane
  braki `DW3M448`, `PO9AB12`; wiersze innego oddziału nie ukrywają braku), liczniki dzienne (`daily_ok`: auto
  powtórzone = 2 wizyty), dokładne porównanie (`xlsx_exact`), historia i rejestr zgłoszeń.
- `tests/test_kontrola.py` – szybkie testy logiki (bez okna): `python tests/run_tests.py kontrola`.
- `tests/ui_smoke.py` – zakładki KONTROLA/HISTORIA dla admina i pracownika z Opola (tylko jego oddział).
