# Aplikacja Android – Oferty opon i Wyniki

Moduł OFERTY OPON z Panelu na telefonie (bez szablonu Excel i pliku XLSX – ofertę wysyła się tekstem przez „Wyślij ofertę”).
Te same konta, ustawienia cen i historia ofert co w Panelu (tabele `oferty_konta`, `oferty`; zasady RLS w bazie).

| Plik | Co robi |
|---|---|
| `www/silnik.js` | port `app/oferty/silnik.py` (wyszukiwanie, ceny, oferta, e-mail) – **zmiana w silniku Panelu = ta sama zmiana tutaj** |
| `www/wyniki.js` | port `app/wyniki/dane.py` – zakładka WYNIKI tylko do podglądu (bez zmiany celów); **zmiana wzorów w Panelu = ta sama zmiana tutaj** |
| `www/app.js` | logowanie Supabase, baza, most do Androida (`Native`), sprawdzanie aktualizacji |
| `www/ui.js`, `index.html`, `styl.css` | ekran telefonu (od 320 px) |
| `www/pdf_wzor.js` | kopia `app/oferty/pdf_wzor.html` – generuje `python3 mobile/zrob_wzor.py` |
| `android/` | okno WebView + most `Native.http/share/openUrl/version/pdf` (PDF: ukryty WebView → `android.print.PdfZapis` → cache/pdf → „Udostępnij” przez `Pliki` – ContentProvider tylko do odczytu, bez eksportu) (HTTP natywnie – xPartner nie pozwala na CORS) |
| `build_apk.sh` | budowa APK bez Gradle (aapt2, javac, d8, apksigner; build-tools 35) |
| `VERSION` | wersja aplikacji – podnieś przy każdej zmianie, inaczej telefony nie zobaczą aktualizacji |

Zakładki wg uprawnień jak w Panelu: Oferta/Historia – moduł `oferty`; Wyniki – `wyniki` albo `marza` (oddziały: admin i MARŻA oba, handlowiec – z konta). Dane pilnuje baza (RLS, `can_see_marza`).

Sprawdzanie: `python3 mobile/test/zgodnosc.py`, `TZ=Europe/Warsaw python3 mobile/test/zgodnosc_wyniki.py` (Python ↔ JS dają te same wyniki), `python3 mobile/test/ekran.py <katalog>` (ekran 360/412 px, cała ścieżka na danych testowych).

Wydanie: push na `main` (workflow `mobile.yml`) → wydanie `aplikacja-android` z `LatexOferty.apk` i `aplikacja.json`. Na `beta` tylko artefakt do pobrania z Actions.
Podpis: sekrety `ANDROID_KEYSTORE_B64`, `ANDROID_KEYSTORE_PASS` – **ten sam klucz zawsze**; zgubiony klucz = każdy musi odinstalować i zainstalować aplikację od nowa.
