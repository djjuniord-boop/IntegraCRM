# Decyzje właściciela – czytaj przed każdą zmianą

Stałe ustalenia Daniela (właściciel). Zmiana, która je łamie, wymaga jego wyraźnej zgody. Nowa decyzja → dopisz
wiersz z datą (w tym samym commicie co zmiana). Szczegóły techniczne – w README modułów; tu tylko „co i dlaczego”.

## Jak pracujemy
- **Wydanie tylko przez `tools/wydaj.sh`** (testy → beta + main → czekanie na budowę tej zmiany → sprawdzenie wydania).
  Nigdy ręczne `git push` na beta/main. „Wydane” mówimy dopiero, gdy skrypt skończył się ✅. (2026-11-24)
- **Od 2026-11-25: po skończonej i przetestowanej zmianie od razu wydanie na kanał beta** (bez pytania); wydanie
  oficjalne dopiero na „wydaj official”. (zastępuje zasadę z 2026-11-09)
- (2026-11-09, zastąpione) Po skończonej zmianie od razu wydanie oficjalne, chyba że właściciel powie „najpierw beta”; kilka poprawek w jednym
  wydaniu zamiast wielu małych. (2026-11-09)
- **Najpierw propozycja / makieta, potem wdrażanie** – przy nowych funkcjach i zmianach wyglądu.
- Zanim opiszesz właścicielowi, jak coś działa – sprawdź w kodzie, że to jest naprawdę używane (nie martwy kod).
- Poprawiając regułę (np. „stan 50 = 50+”), znajdź **wszystkie** miejsca, które z niej korzystają.
- Zanim zmienisz logikę opartą na danych z zewnątrz (xPartner, baza) – najpierw sprawdź, czy te dane w ogóle istnieją.
- Martwy kod usuwamy od razu (nie „zostaje na później”). (2026-11-24)
- Baza: `drop` / `delete` tylko jako plik SQL do wklejenia przez właściciela.
- Hasła wpisuje właściciel sam; prawdziwe zamówienia w xPartner składa sam (to wydatki firmy).

## Program ogólnie
- Zawsze online, minimalna wersja podnosi się sama przy każdym wydaniu oficjalnym. (2026-10-17)
- **Aplikacja Android (`mobile/`) zawieszona** – nie przenosimy zmian. (2026-11-09)
- **SERWIS QR wygaszony w programie** (zakładka, kafel, pomoc ukryte); strona z kodów QR działa. (2026-11-16)
- Jedno okno programu – drugie uruchomienie podnosi już otwarte. (2026-11)

## OFERTY OPON
- **Żadnych plików Excel z ofertą** – oferta to PDF + historia w bazie. (2026-11-09) Szablon zapytania .xlsx
  (wczytywanie listy aut) zostaje.
- Marża i **ceny usług (wymiana, TPMS, przechowalnia) w Latex Wrocław wspólne – zmienia tylko administrator**.
  (marża 2026-11-12, usługi 2026-11-24)
- TPMS w ofercie = **usługa** (dopłata za wymianę opony na feldze z czujnikiem), nie sprzedaż czujnika. (2026-11-24)
- Wszystkie stany widoczne; za mało na potrzebę = ostrzeżenie „tylko N szt.”. (2026-11-12)
- Opon nie zaznaczamy automatycznie – wybiera użytkownik. (2026-11-16)
- Każde szybkie polecenie = nowa oferta (poprzednia zostaje w Historii). (2026-11-18)
- Niepełny rozmiar („20555”, „R20”, sama marka/sezon) szukany w kopii pliku xPartner. (2026-11-17)
- Handlowcy z jednego oddziału widzą i współdzielą oferty (wariant „b”). (2026-11-17)
- PDF do schowka + WhatsApp. (2026-11-18)
- Rozmiar bez „C” pokazuje też wersję dostawczą (R16 + R16C), opony C ze znaczkiem „C”. (2026-11-26)
- Czujniki TPMS (zakładka 📡): samo wyszukiwanie i koszyk, bez ofert. (2026-11-17)

## USTAWIENIA OFERT (2026-11-26)
- Okno Ustawień w zakładkach: Ogólne · Oferty opon · Felgi · Koszyk i zamówienia · PDF i oddziały. **Co się da – ustawiane
  w programie, nie w kodzie.** Ceny i reguły (marże, progi, zaokrąglanie, limity rabatów, limit felg, reguła średnicy,
  bezpiecznik koszyka) – w oddziale ze wspólnymi cenami (Latex Wrocław) zmienia administrator; w pozostałych oddziałach
  każdy u siebie (jak dotąd marża opon). Wygoda (stan, ilość wyników, DEMO, domyślne) – osobiste.
- Oferta felg trafia do Historii dopiero po PDF / WhatsApp / uwagach; opony i czujniki w ofercie felg zawsze z ceną z xPartner.
- Zapis ustawień osobistych w bazie scala (nie zastępuje) – stary telefon nie kasuje nowych ustawień z Panelu.
- Felgi mają **własne ustawienia cen** (marża % albo progi kwotowe, **osobna marża na czujniki TPMS**, zaokrąglanie, rabat
  max) – **bez własnego cennika usług**: montaż, TPMS i przechowalnia z cennika „Oferty opon”.
- Zaokrąglanie ceny (1 / 5 / 10 zł) – dla opon i dla felg (każde osobno).
- **Teksty PDF osobno dla każdego oddziału** (warunki, napisy w ramce kontaktu, napisy w porównaniach) – admin; puste = domyślne.
- Aplikacja Android nie dostaje tych ustawień (decyzja: wydanie bez telefonu) – przy zaokrągleniu innym niż 1 zł albo
  własnych tekstach PDF ceny / PDF w telefonie mogą się różnić od Panelu.

## OFERTY NA FELGI (decyzje 2026-11-26)
- Nowa część OFERT: felgi z pliku oferty xPartner (asortyment FELGA), **zdjęcia z usługi zdjęć xPartner po indeksie**
  (`konfigurator-api.xpartner.net.pl/xpartner-product-images/<indeks>`) – właściciel ma zgodę xPartner.
- **Marża na felgi 13%**, ustawia tylko administrator (jak marża opon).
- Oferta na **same felgi albo komplet**: felgi + opony (z naszej oferty opon) + czujniki TPMS (jako część, z xPartner)
  + montaż + depozyt (przechowalnia).
- Wyniki jako **kafelki ze zdjęciem**.
- **Bez aplikacji Android** (tylko Panel).
- Oferta felg wygląda i działa jak oferta opon: uwagi wewnętrzne, rabat osobno na felgi / opony / montaż, własne ceny,
  ilości i usługi, karty propozycji z sumą, PDF, „Zamów w xPartner”, folder, WhatsApp, zapis w Historii ofert ze znaczkiem
  „felgi”. **Do 3 felg w jednej ofercie** – każda to osobna propozycja (własny PDF) + PDF „porównanie” (wszystkie na jednej
  stronie, klient wybiera). Opony, czujniki i usługi wspólne dla wszystkich felg; opony o innej średnicy niż felga =
  czerwony komunikat i blokada PDF tej propozycji i porównania (albo tylko ostrzeżenie – Ustawienia → Felgi). (2026-11-26)

## DOBÓR PO AUCIE (wheel-size.com, decyzje 2026-11-27)
- Dane aut z API wheel-size.com przez funkcję serwera `wheel-size` – **klucz tylko w sekrecie Supabase** (`WHEELSIZE_API_KEY`),
  nigdy w programie ani w repozytorium. Nie budujemy własnej bazy z ich danych (regulamin) – tylko krótka pamięć w programie.
- „🚗 Dobierz po aucie” **w felgach i w ofercie opon**. Ocena felgi: ET ±5 mm od fabrycznego = pasuje, do ±15 = sprawdź,
  dalej nie pasuje (zakresy w Ustawieniach → Felgi, admin). Inny rozstaw / za mały otwór = nie pasuje; większy otwór = pierścień.
- „Dobrane do: …” na PDF **z przełącznikiem** przy ofercie. Dla mechanika: mocowanie, moment, ciśnienie (tylko w Panelu).
- Plan API: **na razie darmowy (testy, 300 zapytań dziennie)**; do pracy na co dzień – decyzja o Basic po testach.
- Licznik zapytań w bazie (`ws_licznik`, cała firma, doba UTC); administrator widzi zużycie i ustawia limit w Ustawieniach →
  Felgi; 80% = ostrzeżenie dla pracownika, 100% = blokada do następnego dnia. (2026-11-27)

## UPRAWNIENIA OFERT (2026-11-27)
- Moduł „Oferty” dzieli się na: **„oferty”** (opony – podstawa, konto xPartner, dobór po aucie w oponach), **„felgi”** (felgi +
  dobór po aucie) i **„tpms”** (czujniki TPMS). Felgi, TPMS, zamówienia i zamawianie – tylko razem z „Oferty – opony”.
  Kto miał „oferty”, dostał oba nowe (bez zmiany tego, co widzi). Nazwa zakładki: **„Oferty”** (nie „Oferty opon”).
- Ukrycie felg / TPMS w programie to porządek – dane felg i czujników w kopii pliku xPartner czyta każdy z modułem „oferty”.

## Koszyk i ZAMÓWIENIA xPartner
- Dokument: faktura, płatność: przelew – stałe; cen do xPartner nie wysyłamy. (2026-11-09)
- Dostawa tylko na adres oddziału konta.
- Koszyk dzieli zamówienie na części po najwyżej N szt. jednej opony. (2026-11-17)
- Stan „50” z xPartner = „50 lub więcej” – nie blokuje większej ilości. (2026-11-23)
- Magazyn Bydgoszcz oznaczany (dostawa ok. 48 h, czas w Ustawieniach): prognoza w koszyku, pewna informacja po
  zamówieniu i w otwartych. (2026-11-21)
- Kto zamówił przez Panel – zapisywane w bazie. (2026-11-18)
- Oddział faktury („Kod odbiorcy”) **nie jest dostępny w API xPartner** – faktura bez zamówienia widoczna tylko przy
  „wszystkie subkonta”. (2026-11-21)

## DEPOZYT OPON
- Spis przechowalni w programie (moduł `depozyt`) zamiast arkusza; wszyscy w oddziale na żywo, „przywiezione”
  z datą, godziną i nazwiskiem z konta. Pozycje odhaczone w Excelu mają „wg Excela” (bez godziny). (2026-11-25)
- Raport przechowalni z Integry: program daje wynik zależny od raportu – dzień do przodu = lista do przygotowania
  (trasa po regałach K → M → reszta), dni minione = kontrola rozbieżności, okres = jedno i drugie. (2026-11-25)
- Pomarańczowe w starym Excelu = przywiezione bez wymiany, nowa lokalizacja. W programie **bez oznaczenia
  pomarańczowego** – informacja w komentarzu. (2026-11-25)
- Ustawienia depozytu (sezon na start, archiwum sezonów, trasa regałów, uprawnienia cofania/edycji) zmienia
  administrator w programie; domyślnie cofanie „przywiezione” tylko admin, numer/lokalizację – wszyscy. (2026-11-25)
- Aplikacja Android wznowiona: Wyniki, Oferta opon, Depozyt (zakładki wg modułów konta; magazynier – sam Depozyt).
  Zamówień w telefonie nie ma. Lista do przygotowania: wczytywana w Panelu, zapisywana w bazie, otwierana w telefonie. (2026-11-25)
