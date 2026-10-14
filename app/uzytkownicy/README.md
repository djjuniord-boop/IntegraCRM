# Moduł UŻYTKOWNICY (+ Dziennik zmian)

**Co robi:** administrator zakłada konta, nadaje moduły (`crm`, `marza`, `wyniki`, `serwis`) i oddziały (Latex Wrocław,
Latex Opole, Stangum Opole), blokuje konta, zmienia hasła i przegląda Dziennik zmian. Tylko rola `admin`.

## Pliki

| Plik | Rola |
|---|---|
| `zakladka.py` | `UzytkownicyMixin` – lista kont (z bazy, w tle) |
| `okna.py` | `UserDialog` (nowe konto / edycja / usunięcie), `AuditWindow` (dziennik z wyszukiwaniem) |

Logowanie i profil (rola, moduły, oddziały) są w rdzeniu: `app/cloud.py`, `app/logowanie.py`.

## Dane i funkcje w bazie

- `app_users` – konto programu: e-mail, rola, moduły, oddziały, aktywne, ostatnie logowanie, wersja programu.
- `me()`, `is_admin()`, `has_module(m)`, `has_branch(b)` – używane w zasadach dostępu wszystkich tabel.
- `admin_set_user(...)` – zmiana uprawnień (tylko admin, nie można odebrać sobie roli admina).
- Funkcja serwerowa `admin-users` (klucz `service_role` tylko na serwerze): `create`, `set_password`, `delete`.
- `audit_log` – dziennik (wyzwalacz `audit_trg` na tabelach + `log_event()` dla błędów); czyta tylko admin.

## Zasady

- Konta zakłada tylko admin – samodzielna rejestracja ma być wyłączona w Supabase (Authentication).
- Sprawdzanie uprawnień w programie to tylko wygląd; ochronę daje RLS w bazie.

## Testy

- `tests/ui_smoke.py` – zakładka, okno edycji konta, nowe konto, dziennik (admin); brak zakładki u pracownika.
- Zasady w bazie: wzory w `supabase/README.md` (admin, pracownik oddziału, konto zablokowane, obce, eskalacja).
