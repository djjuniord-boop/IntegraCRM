-- 2026-10-14 · migracja `app_config_read_active_only` (zgłoszenie recenzenta po 0.19.0)
--
-- Było: zasada read_all na public.app_config miała `using (true)` – ustawienia firmowe (klucz `crm`
-- z adresami e-mail pracowników) mogło czytać każde konto z ważnym tokenem Supabase Auth, także
-- ZABLOKOWANE (app_users.active = false) i konto Auth, którego nie ma w app_users.
--
-- Jest: czytać może tylko aktywne konto programu (to samo, co zwraca public.me()). Zapis bez zmian
-- (zasada admin_write – tylko administrator).
--
-- Dlaczego nie `(select public.me()) is not null` (propozycja z recenzji): me() zwraca cały wiersz
-- app_users, a w Postgresie `wiersz IS NOT NULL` jest prawdą tylko, gdy WSZYSTKIE pola są wypełnione.
-- name, user_id, last_seen, app_version mogą być puste → zwykły pracownik nie widziałby ustawień
-- (send-mail: „Adres spoza listy odbiorców”, sprawdzenie min_version po cichu wyłączone).
-- Sprawdzamy więc pole email (NOT NULL w tabeli) – jak has_module/has_branch (`from public.me()`).
-- `(select …)` → Postgres liczy to raz na zapytanie (initPlan), nie dla każdego wiersza.
--
-- Bez drop: ALTER POLICY zmienia tylko warunek istniejącej zasady (nazwa zostaje read_all).
-- Test uprawnień: supabase/test_app_config_2026-10-14.sql (kończy się cofnięciem, nic nie zostaje).

alter policy read_all on public.app_config
  using ((select u.email from public.me() u) is not null);
