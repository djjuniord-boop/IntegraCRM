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
