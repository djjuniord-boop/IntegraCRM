# Wspólne zasady agentów IntegraCRM (czyta każdy agent przed pracą)

1. Przeczytaj `CLAUDE.md` (mapa i twarde ograniczenia) oraz README swojego modułu. Nie czytaj innych modułów,
   chyba że zadanie wprost ich dotyczy – wtedy zgłoś to kontrolerowi zamiast zmieniać cudze pliki.
2. Zmieniaj **tylko pliki ze swojego zakresu**. Zmiana potrzebna gdzie indziej (rdzeń, inny moduł, baza) →
   opisz ją w raporcie jako „potrzebne poza moim zakresem”.
3. Teksty w programie po polsku, prostym językiem dla pracownika serwisu. Bez haseł, adresów e-mail pracowników
   i danych klientów w kodzie (repozytorium jest publiczne).
4. Praca w tle → okno tylko przez `self.after(0, …)`; żadnych nowych bibliotek spoza listy w `launcher.py`.
5. **Sprawdź, zanim zgłosisz „gotowe”** – minimum: `python -m pyflakes app`, `python tests/check_imports.py`,
   testy swojego modułu (lista w README), `tests/ui_smoke.py` gdy zmieniasz okno. Polecenia: `CLAUDE.md` → Sprawdzanie.
6. Nie podnoś wersji, nie rób commitów na `beta`, nie wydawaj – to robi kontroler po recenzji.

## Raport dla kontrolera (zawsze w tym układzie)

- **Zmienione pliki:** lista z jednym zdaniem „co i dlaczego” przy każdym.
- **Sprawdzone:** dokładne polecenia i ich wynik (np. `ui_smoke: ok=true, 24 zrzuty, 0 błędów`).
- **Niesprawdzone:** czego nie dało się sprawdzić tutaj (np. okno panelu WebView2 – tylko Windows) i dlaczego.
- **Potrzebne poza moim zakresem:** zmiany w innych modułach / bazie / rdzeniu.
- **Ryzyka:** co może pójść źle u użytkownika.
