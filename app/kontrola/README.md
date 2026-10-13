# Moduł KONTROLA CRM (+ HISTORIA)

**Co robi:** porównuje zakończone zlecenia z raportu Integry 7 (PDF) z danymi z CRM (raport `.xlsx` z „Listy
kontrolne” albo wycinek ekranu przez OCR) po numerach rejestracyjnych, pokazuje braki i przygotowuje mail do
handlowców. Każde sprawdzenie trafia do wspólnej historii w bazie. Uprawnienie: moduł `crm` + oddziały.

## Pliki

| Plik | Rola |
|---|---|
| `zakladka.py` | `KontrolaMixin` – zakładka KONTROLA: wybór plików, oddziały, „Sprawdź” (wątek), wynik, mail |
| `historia_zakladka.py` | `HistoriaMixin` – zakładka HISTORIA (z bazy, w tle) i eksport do Excela |
| `analyze.py` | cała analiza: PDF → numery, CRM → numery, porównanie, ostrzeżenia (zły oddział/okres) |
| `plates.py` | wzorce numerów (Integra, CRM), normalizacja, porównania odporne na błędy OCR |
| `crm_report.py` | odczyt raportu CRM `.xlsx/.csv` (kolumny Data, Rejestracja, Oddział), wybór oddziałów |
| `extract.py` | tekst z PDF (pdfplumber) i OCR wycinka (Tesseract, kilka przebiegów równolegle) |
| `mailer.py` | treść maila, wysyłka przez serwer (`send_server`) albo awaryjnie Gmail z komputera |
| `history.py` | historia sprawdzeń i rejestr „zgłaszany już” – w bazie po zalogowaniu, lokalnie bez sesji (testy) |

## Dane w bazie

- `checks` – sprawdzenia (kto, oddziały, liczby, braki, komu wysłano mail). Pracownik widzi swoje i swoich oddziałów.
- `reported` + funkcja `report_plates()` – numery już zgłoszone (wspólne dla oddziałów, wygasają po 60 dniach).
- `app_config['crm']` – odbiorcy (`recipients`, `by_branch`), nadawca (`sender_name`); zmienia tylko admin.
- Funkcja serwerowa `send-mail` – wysyła tylko do adresów z `app_config['crm']`.

## Zasady, których nie wolno złamać

- **Raport `.xlsx` porównujemy dokładnie** – tolerancja na błędy OCR (`ocr_equal`, `_dist_le1`) tylko dla wycinka
  ekranu. Inaczej podobny numer innego auta ukryje prawdziwy brak (błąd z audytu 0.13.8).
- Gdy dane z CRM prawie nie pokrywają się z Integrą (`no_overlap`) – ostrzeżenie i **brak gotowego maila**.
- Do rejestru „zgłaszany już” trafiają tylko pewne braki, nie „do weryfikacji”.
- `_check_work` działa w wątku – nie czyta pól okna (dostaje `pdf`, `src` jako argumenty).

## Testy

- `app/selftest.py` – pełna ścieżka na danych z `tools/make_fixtures.py` (oczekiwane braki `DW3M448`, `PO9AB12`,
  autopoprawka `WE9LF81`), dokładne porównanie `.xlsx` (`xlsx_exact`), historia i rejestr zgłoszeń.
- `tests/test_kontrola.py` – szybkie testy logiki (bez okna): `python tests/run_tests.py kontrola`.
- `tests/ui_smoke.py` – zakładki KONTROLA/HISTORIA dla admina i pracownika z Opola (tylko jego oddział).
