# Moduł SERWIS QR

**Co robi:** historia wymian oleju i innych prac + naklejka z kodem QR pod maskę. Klient skanuje QR i widzi
historię auta na stronie (GitHub Pages), bez logowania. Pracownicy pracują w panelu w zakładce programu.
Uprawnienie: moduł `serwis` + oddziały (pracownik widzi auta swoich oddziałów).

## Pliki

| Plik | Rola |
|---|---|
| `index.html` | **cały panel i strona klienta** (jeden plik HTML/JS, supabase-js z CDN); `?a=<token>` = widok klienta |
| `qrcode.min.js` | biblioteka kodów QR (lokalnie) |
| `zakladka.py` | `SerwisMixin` – zakładka: uruchamia panel w osobnym procesie, osadza jego okno, pilnuje go |
| `serwis_window.py` | proces panelu (`start.py --serwis`): okno pywebview/Edge WebView2, `Api.get_token()`, `open_url()` |
| `serwis_qr.py` | ustawienia dla panelu (`data/serwis_config.js`), token logowania (`data/serwis_token.json`) |
| `embed_win.py` | WinAPI: znajdź okno panelu, osadź w zakładce, ukryj z paska zadań |

## Jak działa logowanie panelu

Program zapisuje bieżący token (`serwis_qr.write_token`) i co 30 min go odświeża (`App._keep_session`).
Panel (`CFG.sso`) tworzy klienta Supabase z `accessToken: ssoToken` → `window.pywebview.api.get_token()`.
W przeglądarce (GitHub Pages) panel ma własne logowanie.

## Strona dla klientów (GitHub Pages)

Budowana **automatycznie** z tego folderu przy każdym wydaniu (`tools/build_pages.py`, krok w GitHub Actions)
pod adres `https://djjuniord-boop.github.io/IntegraCRM/`. Nie edytuj gałęzi `gh-pages` ręcznie.
Uwaga: zmiana `index.html` na kanale beta od razu zmienia stronę, którą widzą klienci.

## Dane w bazie

- `cars` (token QR, numer, model, właściciel, telefon, VIN, `branch`), `services` (wpisy, zdjęcia base64 w `photos`),
  `settings` (wygląd naklejki – zmienia admin).
- `get_car(token)` – jedyna droga dla klienta: historia jednego auta **bez** właściciela, telefonu i VIN.

## Auto testowe

`DW 1TEST` (token `TESTqr2026x`, oddział Latex Wrocław) jest w bazie **celowo** – na nim testujemy stronę klienta.
Nie usuwaj go; administrator widzi je w panelu.

## Do zrobienia (znane)

- Zdjęcia jako base64 w bazie – przy setkach wpisów zbliżą się do limitu 500 MB; przenieść do Supabase Storage.

## Testy

- GitHub Actions (Windows): start okna panelu 3×, trwałość danych, osadzenie w zakładce (`serwis_embed.txt`).
- `app/selftest.py` – pliki panelu, zapis ustawień, walidacja adresów.
- Strona klienta: `python tools/build_pages.py /tmp/pages` + przeglądarka (Playwright) na `?a=<token testowy>`.
