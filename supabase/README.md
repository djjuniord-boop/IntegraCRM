# Baza i serwer (Supabase)

Projekt `latex-serwis-qr` (id `nlrwulrtaocuemfmlfav`, Frankfurt, plan darmowy). Adres:
`https://nlrwulrtaocuemfmlfav.supabase.co`. Klucz „anon” w `app/cloud.py` jest publiczny – dane chroni RLS.

## Tabele

| Tabela | Moduł | Kto widzi / zmienia |
|---|---|---|
| `app_users` | rdzeń/Użytkownicy | każdy swój wiersz, admin wszystkie; zmiany tylko `admin_set_user()` |
| `app_config` | rdzeń | odczyt: tylko aktywne konto programu (`me()`; nie zablokowani, nie obce konta Auth); zapis: admin. Klucze: `min_version`, `crm` (odbiorcy, nadawca, `marza`) |
| `audit_log` | Użytkownicy | odczyt: admin; zapis: wyzwalacz `audit_trg`, funkcja `log_event()` |
| `checks` | Kontrola | moduł `crm`: swoje + swoich oddziałów; admin wszystko; zapis tylko jako siebie |
| `reported` | Kontrola | moduł `crm` (odczyt); zapis przez `report_plates()` |
| `marza_results` | MARŻA | moduł `marza` |
| `cars`, `services` | SERWIS QR | moduł `serwis` + oddział auta (`cars.branch`) |
| `settings` | SERWIS QR | odczyt: anon (strona klienta) i moduł `serwis`; zapis: admin |
| Storage `marza` | MARŻA | moduł `marza` (odczyt, dodawanie) |

## Funkcje

`me`, `is_admin`, `has_module`, `has_branch` (uprawnienia) · `app_login` (profil + ostatnie logowanie) ·
`admin_set_user` · `report_plates` · `log_event` · `get_car` (strona klienta, anon) · `audit_trg` (wyzwalacz).

Funkcje serwerowe (Edge Functions, kod w `supabase/functions/`):
- `admin-users` – zakładanie kont, hasła, usuwanie (tylko admin; używa `service_role` po stronie serwera),
- `send-mail` – mail z brakami (Kontrola) i mail z wykresem (MARŻA, akcja `raw`); sekrety `GMAIL_USER`,
  `GMAIL_APP_PASSWORD` ustawia właściciel w panelu Supabase. Najpierw sprawdza konto, potem konfigurację.

## Zmiany w bazie

- Nowe tabele/funkcje: `apply_migration` (nazwa po angielsku w snake_case) + zapis treści w `supabase/*.sql`.
- `drop` / `delete` wymagają zatwierdzenia właściciela – plik `.sql` do wklejenia w SQL Editor.
- Po każdej zmianie: doradcy Supabase (`get_advisors` security + performance). Ostrzeżenia
  „SECURITY DEFINER function executable” dla funkcji z listy wyżej są **zamierzone** (z nich korzystają zasady).
- Zasady z `auth.jwt()` / funkcjami pisz jako `(select auth.jwt())`, `(select public.has_module('x'))`.
- „Aktywne konto programu” w zasadzie: `(select u.email from public.me() u) is not null`. **Nie**
  `(select public.me()) is not null` – `wiersz IS NOT NULL` wymaga wszystkich pól, a `name`, `user_id`,
  `last_seen`, `app_version` bywają puste (zwykły pracownik straciłby dostęp).

## Wzór testu uprawnień (w transakcji, nic nie zostaje)

```sql
begin;
insert into public.app_users(email,modules,branches) values ('opole@test.pl','{crm}','{Latex Opole}');
set local role authenticated;
select set_config('request.jwt.claims','{"email":"opole@test.pl"}',true);
select count(*) from public.checks;          -- tylko sprawdzenia Opola
select set_config('request.jwt.claims','{"email":"obcy@example.com"}',true);
select count(*) from public.cars;            -- 0
rollback;
```

Pełniejszy wzór (wszystkie rodzaje kont, `app_login` jak w programie, porównanie wariantów zasady, wynik jako
tabela w treści celowego błędu – więc wszystko się cofa): `test_app_config_2026-10-14.sql`.

## Kopie zapasowe

Plan darmowy **nie ma** automatycznych kopii (dokumentacja Supabase zaleca własny eksport). Do zrobienia:
regularny eksport bazy i schowka plików poza Supabase.

## Historia zmian schematu

`etap1.sql` (użytkownicy, moduły, oddziały) · etap2 (checks, reported, ustawienia firmowe) · etap3 (audit_log) ·
etap4 (log_event, import historii) · etap5 (marza_results, schowek `marza`) · `perf_rls_initplan` (0.19) ·
`porzadki_0.19.sql` (do zatwierdzenia przez właściciela) · `app_config_odczyt_2026-10-14.sql`
(migracja `app_config_read_active_only`: `app_config` czytają tylko aktywne konta programu; test:
`test_app_config_2026-10-14.sql`).
