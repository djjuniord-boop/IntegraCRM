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

## Dane w bazie

- `oferty_konta` – `xp_login`, `xp_haslo`, `ustawienia` (marża, VAT, cenniki wymiany osobowe/SUV/dostawcze, TPMS,
  przechowalnia, marki premium/średnie/budżet, podpis). Odczyt: swój wiersz albo admin. Zapis: `oferty_admin_set_konto`
  (admin, puste hasło = bez zmiany), `oferty_zapisz_ustawienia` (właściciel, bez loginu i hasła).
- `oferty` – historia (`owner`, `oid`, `klient`, `dane` jsonb, `szukaj`): każdy widzi swoje, administrator wszystkie (kolumna „Kto”, podsumowanie); zmieniać można tylko swoje.

## Uwagi

- Logowanie: okno używa tokenu programu (`serwis_qr.write_token`, odświeżany co 30 min w `gui._keep_session`).
- Ulotki PDF generuje strona xPartner (`m=getPDF`) – otwierają się w przeglądarce zalogowanej do xPartner.
- Pozycje z ceną 0 w xPartner (niedostępne dla konta) są pomijane.
- Testy: `tests/test_oferty.py` (bez sieci; API xPartner podstawiane).
