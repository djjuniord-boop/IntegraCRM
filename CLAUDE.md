# IntegraCRM – mapa programu i zasady pracy

Program desktopowy (Windows, Python + Tkinter) dla Latex Serwis: kontrola eksportu zleceń Integra 7 → CRM,
kalkulator MARŻY, SERWIS QR (historia serwisowa z naklejkami QR), konta i uprawnienia. Dane wspólne
w Supabase (projekt `latex-serwis-qr`, id `nlrwulrtaocuemfmlfav`). Właściciel i administrator: Daniel
(djjuniord@gmail.com). Interfejs i komunikaty: **po polsku**, prostym językiem dla pracowników serwisu.

## Mapa

| Część | Gdzie | Opis |
|---|---|---|
| Rdzeń okna | `app/gui.py` | start, układ, zakładki wg uprawnień, aktualizacje, obsługa błędów |
| Wygląd | `app/ui.py` | kolory Latex, czcionki, `FlatButton`, `card` – wspólne dla modułów |
| Ustawienia | `app/konfig.py`, `app/ustawienia.py` | lokalne `data/config.json` + firmowe z bazy (`COMPANY`) |
| Logowanie | `app/logowanie.py`, `app/cloud.py` | Supabase Auth przez `urllib` (bez dodatkowych bibliotek), profil, uprawnienia |
| Aktualizacje | `app/updater.py`, `app/version.py` | paczka `app/` z GitHub Releases (kanał `kanal-beta`) |
| **Kontrola CRM** | `app/kontrola/` | → [`app/kontrola/README.md`](app/kontrola/README.md) |
| **MARŻA** | `app/marza/` | → [`app/marza/README.md`](app/marza/README.md) |
| **WYNIKI** | `app/wyniki/` | → [`app/wyniki/README.md`](app/wyniki/README.md) – wyniki marży dla handlowców |
| **STATYSTYKI** | `app/statystyki/` | → [`app/statystyki/README.md`](app/statystyki/README.md) – listy kontrolne na 10 zleceń, prognoza |
| **SERWIS QR** | `app/serwis/` | → [`app/serwis/README.md`](app/serwis/README.md) |
| **Użytkownicy** | `app/uzytkownicy/` | → [`app/uzytkownicy/README.md`](app/uzytkownicy/README.md) |
| Baza i serwer | `supabase/` | → [`supabase/README.md`](supabase/README.md) |
| Testy | `tests/`, `app/selftest.py` | → sekcja „Sprawdzanie” niżej |

Zakładki modułów to klasy `*Mixin` (np. `KontrolaMixin`) łączone w `class App(...)` w `gui.py`.
Metody mixinów korzystają z pól okna (`self.session`, `self.fonts`, `self.pages`…).

## Twarde ograniczenia (złamanie = program nie wystartuje u użytkowników)

1. **`app/start.py` i `app/version.py` nie mogą zmienić miejsca** – stary updater szuka `app/version.py`
   (z linią `VERSION = "x.y.z"`), a `IntegraCRM.exe` uruchamia `app/start.py`.
2. **Tylko biblioteki dołączone do .exe.** Kod z `app/` wczytuje się z folderu, ale biblioteki pochodzą z paczki
   `IntegraCRM.exe` (lista w `launcher.py`). Nowy import spoza tej listy (także ze standardowej biblioteki!)
   wymaga nowej paczki .exe – wtedy dopisz go w `launcher.py` i powiedz właścicielowi, że trzeba pobrać nową paczkę.
3. **Wątki nie dotykają okna.** Praca w tle (`threading.Thread`) → wynik do okna tylko przez `self.after(0, …)`
   / `self.ui(…)`. Dane z okna (`StringVar`, `BooleanVar`) odczytuj przed startem wątku.
4. **`data/` należy do użytkownika** – aktualizacja go nie rusza; nie zapisuj tam niczego bez potrzeby, zapis
   atomowy (`.tmp` + `os.replace`).
5. **Uprawnienia sprawdza baza (RLS), nie program.** Ukrycie zakładki to porządek, nie zabezpieczenie. Wszystko,
   co ma być chronione, musi mieć zasadę dostępu w bazie.
6. **Zawsze online.** Bez logowania program się nie otwiera. Minimalną wersję ustawia `app_config.min_version` –
   decyzja właściciela (2026-10-17): **każde wydanie oficjalne (main) od razu podnosi ją automatycznie** (krok CI
   „Minimalna wersja = wydana”, sekret `SUPABASE_SERVICE_ROLE_KEY`), po sprawdzeniu, że wersja jest do pobrania.
   Dlatego na main idzie tylko wersja sprawdzona na becie – przywrócenie poprzedniej wersji wymaga obniżenia
   `min_version` ręcznie (SQL).
7. **Wydania tylko na wyraźne polecenie właściciela** – także na kanał beta (push na `beta` buduje i wydaje paczkę).

## Jak pracujemy (kontroler + agenci)

Sesja, z którą rozmawia właściciel, jest **kontrolerem**. Kolejność przy każdej zmianie:

1. **Ustal moduł** z mapy wyżej. Czytaj tylko `CLAUDE.md` + README tego modułu + jego pliki.
   Zmiana w jednym module → agent tego modułu (`.claude/agents/agent-<moduł>.md`).
   Zmiana w kilku modułach albo w rdzeniu → kontroler sam, po kolei, z agentami jako pomocą.
2. **Agent modułu** zmienia tylko swoje pliki (lista w jego definicji), uruchamia testy i zwraca raport:
   co zmienił, czym sprawdził, czego nie mógł sprawdzić.
3. **Kontroler sprawdza raport agenta** (przegląda zmiany `git diff`, uruchamia testy sam) – nigdy nie
   przyjmuje „zrobione” bez dowodu.
4. **Recenzent** (`.claude/agents/recenzent.md`) – przed każdym wydaniem. Nie widział, jak powstawała zmiana:
   uruchamia program jak nowy użytkownik (zrzuty wszystkich zakładek i okien), przegląda kod i bazę,
   zgłasza problemy. Kontroler poprawia, recenzent sprawdza poprawki.
5. **Wydanie**: podnieś `VERSION`, dopisz `CHANGELOG` (po polsku, z punktu widzenia użytkownika), commit na `beta`,
   push → GitHub Actions buduje paczkę, testuje na Windows, wydaje na kanał beta i publikuje stronę SERWIS QR.
   Sprawdź wynik (`gh run list -R djjuniord-boop/IntegraCRM -L 1`).
6. **Audyt końcowy**: doradcy Supabase (bezpieczeństwo, wydajność), stan bazy, porównanie zrzutów przed/po,
   krótkie podsumowanie dla właściciela: co działa, co sprawdzić u siebie, co zostało.

## Sprawdzanie (obowiązkowe przy każdej zmianie)

Środowisko testowe (Linux): systemowy `python3.12` z `python3-tk` (Tk 8.6 jak w .exe; Tk 9 z `uv` nie obsługuje
wywołań z wątków, a Tk 8.6 z `uv` pada na obrazkach PNG pod Xvfb) + `xvfb-run`:

```bash
apt-get install -y python3-tk             # raz
python3.12 -m venv /tmp/venv && /tmp/venv/bin/pip install pdfplumber pytesseract Pillow openpyxl pypdf matplotlib pyflakes reportlab
/tmp/venv/bin/python -m pyflakes app                      # brakujące nazwy, literówki
/tmp/venv/bin/python tests/check_imports.py               # każdy import wskazuje istniejący moduł
/tmp/venv/bin/python tests/run_tests.py [kontrola|marza|wyniki|statystyki|serwis|rdzen]   # testy modułów (bez okna)
/tmp/venv/bin/python tools/make_fixtures.py /tmp/fx      # dane testowe (bez prawdziwych danych firmy)
INTEGRA_SELFTEST=/tmp/fx xvfb-run -a /tmp/venv/bin/python app/start.py   # ścieżka PDF→OCR→porównanie→mail
xvfb-run -a -s "-screen 0 1600x1000x24" /tmp/venv/bin/python tests/ui_smoke.py . /tmp/zrzuty  # okno jak nowy użytkownik
```

`selftest` na Linuksie: `serwis_window: false` jest oczekiwane (okno panelu działa tylko na Windows).
GitHub Actions (Windows) uruchamia testy modułów i importów, a na prawdziwym .exe `selftest`, test okna panelu SERWIS QR i zrzuty ekranu.
Zmiany w bazie: testuj zasady dostępu w transakcji z `set local role authenticated` +
`set_config('request.jwt.claims', '{"email": "…"}', true)` i `rollback` – wzory w `supabase/README.md`.

## Repozytorium i wydania

- `beta` – kanał testowy (właściciel tu pracuje); `main` – stabilny (stara wersja 0.13). Gałąź `gh-pages` –
  strona dla klientów z kodów QR, **budowana automatycznie** z `app/serwis/` (`tools/build_pages.py`).
- Repozytorium jest **publiczne** (aktualizacje pobierają się bez logowania): żadnych haseł, adresów e-mail
  pracowników ani danych klientów w kodzie. Klucz „anon” Supabase w `cloud.py` jest publiczny z założenia.
- Commity po polsku, opis co i dlaczego. Zmiany w bazie zapisuj w `supabase/` (plik `.sql` z datą/etapem).
- Polecenia usuwające w bazie (`drop`, `delete`) wymagają zatwierdzenia właściciela – przygotuj plik `.sql`
  do wklejenia w SQL Editor i powiedz o tym wprost.
