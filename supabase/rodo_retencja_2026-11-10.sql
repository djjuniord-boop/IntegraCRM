-- RODO: okresy przechowywania danych (2026-11-10, audyt B-05). PROPOZYCJA – do decyzji właściciela.
-- Uruchamiać ręcznie w SQL Editor raz na kwartał (w projekcie nie ma pg_cron). Usuwa / czyści tylko dane
-- starsze niż podane okresy; dziś (listopad 2026) nie obejmuje jeszcze żadnego wiersza.
-- Zmień okresy przed pierwszym użyciem, jeśli zdecydujesz inaczej.
-- Całość w jednej transakcji z wyłączonymi wyzwalaczami (checks_guard blokuje zmianę sprawdzeń poza administratorem
-- programu, a audit dopisałby wpis za każdy wiersz) – tylko na czas tego skryptu.
begin;
set local session_replication_role = replica;

-- 1. Dziennik zmian (logowania z adresem IP i nazwą komputera, zmiany uprawnień, e-maile): 12 miesięcy
delete from public.audit_log where at < now() - interval '12 months';

-- 2. Numery „zgłaszane już” (rejestracje aut): nieaktywne od 12 miesięcy
delete from public.reported where last_at < now() - interval '12 months';

-- 3. Sprawdzenia KONTROLI: po 12 miesiącach bez numerów rejestracyjnych (liczby zostają dla STATYSTYK)
update public.checks set missing = '{}', uncertain = '{}'
 where created_at < now() - interval '12 months' and (cardinality(missing) > 0 or cardinality(uncertain) > 0);

-- 4. Oferty: odpowiedź klienta z linku (telefon, uwagi) – 120 dni od wysłania linku (link ważny 30 dni)
update public.oferty set klient_odp = null
 where coalesce(link_at, created_at) < now() - interval '120 days' and klient_odp is not null;

commit;
