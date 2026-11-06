# Moduł OFERTY OPON (beta)

**Co robi:** wyszukuje opony w hurtowni xPartner (Latex) na żywo przez XML API (`productsList`) i robi ofertę dla
klienta: karty wariantów, e-mail do skopiowania, plik XLSX (Dokumenty\Oferty opon), ulotki PDF z xPartner,
historię ofert. Uprawnienie: moduł `oferty`. Każdy użytkownik ma **własne** konto API xPartner – login i hasło
wpisuje administrator w oknie użytkownika (UŻYTKOWNICY).

## Pliki

| Plik | Rola |
|---|---|
| `silnik.py` | cała logika bez okna: rozpoznawanie zapytań (rozmiar w dowolnym zapisie, rejestracje, usługi), API xPartner, oferta, XLSX, e-mail; `handle(ścieżka, dane)` – polecenia strony |
| `index.html` | interfejs (jeden plik HTML/JS); polecenia przez `window.pywebview.api.call(ścieżka, dane)` |
| `okno.py` | proces okna (`start.py --oferty`): pywebview/Edge WebView2, `Api.call` → `silnik.handle`, konto i historia z bazy |
| `zakladka.py` | `OfertyMixin` – osadzenie okna w zakładce (jak SERWIS QR; używa `serwis/embed_win.py`) |

## Wyszukiwanie z pliku ofertowego xPartner

- xPartner zaleca: oferta z **pliku** (co 30–60 min), API tylko do sprawdzenia wybranych produktów. Automat
  `.github/workflows/xp_oferta.yml` → `tools/xp_oferta_sync.py` (sekrety `XPARTNER_OFERTA_URL`, `SUPABASE_SERVICE_ROLE_KEY`)
  ładuje CSV (CSV, UTF-8, OPONY, wszystkie kolumny) do tabeli `xp_oferta` (`supabase/xp_oferta_2026-11-06.sql`): tylko zmiany,
  plik < 50% tabeli = stop, w logach tylko liczby; stan w `app_config` `xp_oferta_stan`.
- `search_size` pyta najpierw `KONTO["katalog"]` (Panel: `okno.Katalog`, aplikacja: `app.js`); kopia starsza niż 3 h / brak → API.
  Ceny w kopii są z konta, które wygenerowało link; oferta (`build_offer`) i tak odświeża produkty przez API z konta pracownika.
- Cechy tylko z pliku (EPREL, śnieg, lód) trzyma `CECHY` (API ich nie ma); PDF: oficjalna etykieta EPREL (obrazek z rejestru UE,
  gdy się nie wczyta – rysowana), znaczki 3PMSF/lód.

## PDF oferty (jeden model opony)

- Przycisk przy każdej oponie w sekcji 4 → `/api/pdf` → `pdf_dane` + `wypelnij(pdf_wzor.html)` → HTML → **Edge headless**
  (`--print-to-pdf`, jest w każdym Windows 10/11) zapisuje PDF w `Dokumenty\Oferty opon` i otwiera go. Brak Edge/Chrome → HTML do „Drukuj → PDF”.
- Pozycje osobno: opona, wymiana (per średnica/typ auta), TPMS, depozyt; rabat tylko na opony (jak w silniku), netto/VAT/brutto.
  Puste pola (klient, pojazd, rabat, usługi) znikają. Zdjęcie – tylko gdy API poda adres https (`_foto`), etykieta UE z cech API.
- **Oddział na PDF z konta** (`app_users.branches`, admin – wszystkie z danymi); strona może wybrać tylko spośród nich (`oddzial_oferty`).
  Dane oddziałów: `app_config` klucz `oddzialy` (SQL `supabase/oddzialy_pdf_2026-11-05.sql`), edycja: Ustawienia → „Dane oddziałów na PDF” (admin).
- Wzór wspólny z aplikacją Android: po zmianie `pdf_wzor.html` uruchom `python3 mobile/zrob_wzor.py` (test zgodności tego pilnuje).
- Test na prawdziwym Windows/Edge: `tests/pdf_edge.py` (krok CI).

## Zamówienia xPartner (beta)

`zamowienia.py` (aplikacja: `mobile/www/zamowienia.js`, zgodność: `mobile/test/zamowienia_zgodnosc.py`) – tylko odczyt
z konta xPartner pracownika: `getOpenOrders` (zamówione opony), `getInvoices`/`getInvoice` (faktury KSeF, od 2026-02-01).
Dostęp: moduł `zamowienia` (UŻYTKOWNICY) albo administrator; faktury – tylko administrator (to porządek, nie
zabezpieczenie – pracownik widzi faktury na stronie xPartner). „Wysłane opony” (listy przewozowe) wymagają tokenu
głównego konta xPartner – na razie brak.

## Dane w bazie

- `oferty_konta` – `xp_login`, hasło w **Vault** (`xp_haslo_id`; odczyt tylko własnego: rpc `oferty_moje_haslo()`, admin: `oferty_ma_haslo(email)`; jawna kolumna `xp_haslo` pusta po etapie 2 – SQL `oferty_haslo_vault_etap1/2_2026-11-06.sql`), `ustawienia` (marża, VAT, cenniki wymiany osobowe/SUV/dostawcze, TPMS,
  przechowalnia, marki premium/średnie/budżet, podpis). Odczyt: swój wiersz albo admin. Zapis: `oferty_admin_set_konto`
  (admin, puste hasło = bez zmiany), `oferty_zapisz_ustawienia` (właściciel, bez loginu i hasła).
- `oferty` – historia (`owner`, `oid`, `klient`, `dane` jsonb, `szukaj`): każdy widzi swoje, administrator wszystkie (kolumna „Kto”, podsumowanie); zmieniać można tylko swoje.

## Uwagi

- Logowanie: okno używa tokenu programu (`serwis_qr.write_token`, odświeżany co 30 min w `gui._keep_session`).
- Ulotki PDF generuje strona xPartner (`m=getPDF`) – otwierają się w przeglądarce zalogowanej do xPartner.
- Pozycje z ceną 0 w xPartner (niedostępne dla konta) są pomijane.
- Testy: `tests/test_oferty.py` (bez sieci; API xPartner podstawiane).
