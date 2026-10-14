# STATYSTYKI

Zakładka (moduł `statystyki` w uprawnieniach) – ile list kontrolnych w CRM przypada na zlecenia z Integry.

- **Dane:** tabela `visit_stats` (oddział, dzień → wizyty, listy, braki). Zapisuje je KONTROLA przy każdym
  sprawdzeniu (raport .xlsx, dokładnie jeden oddział) przez funkcję `save_visit_stats`; ponowne sprawdzenie
  tego samego dnia nadpisuje liczby. Każde zlecenie z pojazdem = jedna wizyta (to samo auto 2× = 2 wizyty).
- **Odczyt:** baza pokazuje tylko oddziały konta (RLS: moduł `statystyki` + oddział).
- `dane.py` – obliczenia bez okna: `miesiace`, `okres(90 dni)`, `prognoza` (środek = wskaźnik z 90 dni,
  widełki = najsłabszy/najlepszy miesiąc z ≥ 30 zleceniami), `liczba`, formaty.
- `zakladka.py` – `StatystykiMixin`: kafle, prognoza (pole „Jeśli będzie N zleceń”), tabela miesięcy.
- Testy: `tests/test_statystyki.py`, scenariusze w `tests/ui_smoke.py` (`admin_statystyki_oba`,
  `statystyki_tylko_swoje`, `statystyki_prognoza`).
