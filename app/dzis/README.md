# DZIŚ – ekran startowy

Pierwsza zakładka dla kont z co najmniej dwoma kaflami (`kafle_konta`): Kontrola CRM (ostatnie sprawdzenie),
Wyniki marży (% celu i plan na dziś wg `wyniki.dane`), Marża – aktualizacja (ostatni zapis oddziału, czerwony pasek
po ponad dniu bez aktualizacji), Oferty opon, Serwis QR. Administrator widzi też „Pracuje teraz: N osób”.

- `zakladka.py` – `DzisMixin` (część `App` w `gui.py`); dane w wątku, do okna przez `self.after`; odświeżanie przy
  wejściu na zakładkę i co 5 min. Teksty kafli (`tekst_kontroli`, `tekst_marzy`) bez okna – testy `tests/test_dzis.py`.
- Uprawnienia sprawdza baza (RLS) – kafel pokazuje tylko to, co konto i tak może odczytać.
