# DEPOZYT – spis opon w przechowalni

Wspólny spis opon klientów z lokalizacją na regale (dawniej `SPIS_ZIMA_….xlsx`), widoczny na żywo dla wszystkich
w oddziale. Moduł uprawnień `depozyt` (UŻYTKOWNICY), oddział konta = oddział spisu.

- `zakladka.py` – `DepozytMixin` (część `App` w `gui.py`): tabela spisu, odhaczanie „przywiezione” (dwuklik / spacja /
  Enter przy jednym wyniku; data, godzina i kto zapisują się w bazie), komentarz, „do wyjaśnienia”, zmiana
  lokalizacji/numeru/marki, historia zmian, duplikaty, eksport do Excela (czerwone/pomarańczowe wiersze jak w starym
  pliku), „Dodaj pozycję”. Gdy zakładka jest otwarta: co 10 s pobiera tylko pozycje zmienione od ostatniego razu (kolumna `zmieniono`), co 10 min – całość. `PrzygotowanieOkno` – lista z raportu Integry.
- `szukaj.py` – wyszukiwanie odporne na literówki (znaki mylone O/0/D, I/1, B/8…, 1–2 inne znaki, numery w uwagach),
  `klucz_lokalizacji` – kolejność obchodu magazynu: regały K, potem M, potem pozostałe (KPOK, KWEJ, MAGOPIS…).
- `raport.py` – PDF przechowalni z Integry (FastReport; „Rejestr przechowalni opon”, „Rejestr opon do wydania wg
  umówionych terminów”, dowolny dzień lub okres). Czyta słowa wg pozycji kolumn z nagłówka każdej strony.
  `przygotuj()` łączy raport ze spisem i dodaje uwagi; `tryb()`: przyszłość = przygotowanie, przeszłość = kontrola.
  Integra w kolumnie „Lokalizacja” ma zwykle tylko „Wrocław” – miejsce na regale jest wyłącznie w spisie.
- `xls.py` – odczyt starego Excela (.xls, BIFF8) bez xlrd (nie ma go w paczce .exe): kontener OLE2 → rekordy
  komórek; .xlsx przez openpyxl. Sprawdzone na eksporcie z Integry – wynik identyczny jak z xlrd.
  `raport.parse_terminy` / `raport.wczytaj` – harmonogram wizyt z Integry (Termin od, Nr rej., Marka, Model, Kontrahent);
  wpisy techniczne (np. CZK_OPONY) pomijane, auta bez opon w spisie – „brak opon w depozycie” (bez alarmu).
- Ostatnio wczytany raport zapisuje się w `data/depozyt_ostatni_raport.json` (przycisk „↺ Ostatnia lista”).
- `dane.py` – zapytania (stronicowanie po 1000 wierszy; zapis tylko funkcjami `depozyt_zmien`, `depozyt_dodaj`).

Baza: `supabase/depozyt_2026-11-25.sql` (tabele `depozyt`, `depozyt_historia`, RLS, funkcje). Import spisu z Excela –
jednorazowy plik SQL poza repozytorium (dane klientów).

Testy: `tests/test_depozyt.py` (szukanie, raport w układzie Integry na zmyślonych danych, lista, filtry) i kontrola
`depozyt_spis_i_szukanie` w `tests/ui_smoke.py`.

Arkusz Google: `tools/arkusz_depozyt.gs` (Apps Script) – synchronizacja dwustronna; baza powiadamia arkusz od razu
(wyzwalacz `depozyt_do_arkusza` + pg_net, konfiguracja w `depozyt_arkusz_cfg`), zapas – co minutę.
