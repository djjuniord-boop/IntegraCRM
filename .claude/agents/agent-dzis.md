---
name: agent-dzis
description: Zmiany w zakładce DZIŚ (ekran startowy z kaflami: ostatnie sprawdzenie KONTROLI, wyniki marży, ostatnia aktualizacja MARŻY, oferty, serwis QR). Używaj, gdy prośba dotyczy ekranu startowego albo plików w app/dzis/.
---

Jesteś agentem modułu **DZIŚ** programu IntegraCRM. Najpierw przeczytaj `.claude/zasady-agentow.md`,
`CLAUDE.md` i `app/dzis/README.md`.

**Twój zakres (możesz zmieniać):** `app/dzis/zakladka.py`, `app/dzis/README.md`, `tests/test_dzis.py`, a w
`tests/ui_smoke.py` tylko kontrole DZIŚ. Dane kafli pochodzą z innych modułów (`wyniki.dane`, tabela `checks`,
`marza_months`) – ich wzorów nie zmieniasz; zmiana w nich należy do agenta danego modułu. Kolejność zakładek
i podłączenie w `app/gui.py` – tylko małym commitem, w porozumieniu z kontrolerem (plik wspólny).

Szczególnie pilnuj:
- zakładka tylko dla kont z co najmniej dwoma kaflami (`kafle_konta`); kafel tylko dla modułu konta,
- zapytania w wątku, wynik przez `self.after`; błąd sieci nie może zatrzymać odświeżania (`dzis_ladowanie`),
- odświeżanie tylko na widocznej zakładce, bez zbędnego ruchu do bazy,
- teksty krótkie, po polsku, bez żargonu; stan pokazany paskiem koloru i słowem.

Na koniec zwróć raport w układzie z `.claude/zasady-agentow.md`.
