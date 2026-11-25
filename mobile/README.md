# Aplikacja Android – Latex Serwis (Oferty opon, Wyniki, Depozyt)

> **Wznowiona (decyzja właściciela 2026-11-25)** – zmiany silnika ofert, wzorów WYNIKÓW i wyszukiwania DEPOZYTU w Panelu
> przenosimy tutaj (testy zgodności Python ↔ JS niżej).

Zakładki wg modułów konta, jak w Panelu (dane i tak pilnuje baza – RLS; ukrycie zakładki to tylko porządek):

| Zakładka | Moduł | Co robi |
|---|---|---|
| 🛞 Oferta, 🕘 Historia | `oferty` | oferty opon z xPartner, PDF dla klienta (bez Excela i bez treści e-maila – jak Panel), wspólna historia ofert oddziału |
| 📈 Wyniki | `wyniki` albo `marza` | wyniki marży tylko do podglądu (oddziały: admin i MARŻA oba, handlowiec – z konta) |
| 📦 Depozyt | `depozyt` | spis opon w przechowalni: szukanie numeru (odporne na literówki), „✓ Przywiezione”, komentarz, zmiana lokalizacji |
| ⚙ Ustawienia | każdy | ustawienia ofert (gdy moduł `oferty`), konto, aktualizacja, wylogowanie |

Magazynier z samym modułem `depozyt` widzi tylko Depozyt i Ustawienia. Zamówienia xPartner są tylko w Panelu.

| Plik | Co robi |
|---|---|
| `www/silnik.js` | port `app/oferty/silnik.py` (szybkie polecenie – też po indeksie/kodzie/EAN, wyszukiwanie, homologacja, ceny, oferta, PDF) – **zmiana w silniku Panelu = ta sama zmiana tutaj** |
| `www/wyniki.js` | port `app/wyniki/dane.py` – **zmiana wzorów w Panelu = ta sama zmiana tutaj** |
| `www/depozyt.js` | port `app/depozyt/szukaj.py` (norm, kanon, lev, szukaj) + liczniki i opis „przywiezione” jak `zakladka.py` – **zmiana wyszukiwania w Panelu = ta sama zmiana tutaj** |
| `www/app.js` | logowanie Supabase, baza (oferty, `oferty_ceny`, `xp_oferta`, `depozyt`), most do Androida (`Native`), sprawdzanie aktualizacji |
| `www/ui.js`, `index.html`, `styl.css` | ekran telefonu (od 320 px) |
| `www/pdf_wzor.js` | kopia `app/oferty/pdf_wzor.html` – generuje `python3 mobile/zrob_wzor.py` |
| `android/` | okno WebView + most `Native.http/share/openUrl/version/pdf` (PDF: ukryty WebView → `android.print.PdfZapis` → cache/pdf → „Udostępnij” przez `Pliki` – ContentProvider tylko do odczytu, bez eksportu) (HTTP natywnie – xPartner nie pozwala na CORS) |
| `build_apk.sh` | budowa APK bez Gradle (aapt2, javac, d8, apksigner; build-tools 35) |
| `VERSION` | wersja aplikacji – podnieś przy każdej zmianie, inaczej telefony nie zobaczą aktualizacji |

**Ceny w ofercie:** marża i ceny usług (wymiana, obsługa TPMS, przechowalnia) dla oddziału z listy `ODDZ_CEN`
(Latex Wrocław) są wspólne – z `app_config.oferty_ceny`, zmienia je tylko administrator (u pracownika pola zablokowane).
TPMS w ofercie = obsługa czujnika przy wymianie (za koło), nie sprzedaż czujnika.

**Depozyt:** odczyt tabeli `depozyt` (stronicowanie po 1000, oddział z konta; admin – wybór oddziału), ustawienia
`depozyt_ustawienia` (sezon na start, ukryte sezony; brak wiersza = domyślne). Zapis **tylko** funkcją bazy
`depozyt_zmien(p_id, p_pole, p_wartosc)` (pola: `przywiezione` 1/0, `komentarz`, `lok`); odmowę bazy (np. cofnięcie
„przywiezione” przez nie-administratora) aplikacja pokazuje słowami bazy. Gdy zakładka jest widoczna – co 10 s pobiera
tylko zmienione pozycje (`zmieniono=gt.<najnowszy znany>`) i podmienia je po `id`. Bez wyszukania – najwyżej 50 kart
(nieprzywiezione albo z filtra) i „Pokaż więcej”. Przycisk „Lista do przygotowania” jest na razie ukryty (`#dLista`).
Bez oznaczenia „do wyjaśnienia” (wycofane w Panelu).

Sprawdzanie (wszystkie muszą przejść):

```bash
python3 mobile/test/zgodnosc.py                          # silnik ofert Python ↔ JS (+ homologacja, kod/EAN, ceny oddziału)
TZ=Europe/Warsaw python3 mobile/test/zgodnosc_wyniki.py  # WYNIKI Python ↔ JS
python3 mobile/test/zgodnosc_depozyt.py                  # wyszukiwanie DEPOZYTU Python ↔ JS (zmyślone numery)
python3 mobile/test/ekran.py <katalog>                   # ekran 360/412 px: oferta, historia, wyniki, depozyt (admin, handlowiec, magazynier)
```

Niepełny rozmiar w szybkim poleceniu („20555”, „R20”, sama marka/sezon – Panel 1.0.7) nie jest jeszcze przeniesiony
do telefonu (wymaga szukania wzorca w kopii `xp_oferta`).

Wydanie: push na `main` (workflow `mobile.yml`) → wydanie `aplikacja-android` z `LatexOferty.apk` i `aplikacja.json`. Na `beta` tylko artefakt do pobrania z Actions.
Podpis: sekrety `ANDROID_KEYSTORE_B64`, `ANDROID_KEYSTORE_PASS` – **ten sam klucz zawsze**; zgubiony klucz = każdy musi odinstalować i zainstalować aplikację od nowa.
