-- Etap: uprawnienia anonima (2026-11-10, audyt B-04). Nic nie usuwa (ani tabel, ani danych).
-- Dotąd rola anon (klucz publiczny z repozytorium) miała SELECT/INSERT/UPDATE/DELETE na tabelach public,
-- a każda NOWA tabela dostawała to automatycznie – chroniło tylko RLS. Teraz anon może tylko czytać
-- ustawienia naklejek (settings – strona QR); funkcje dla klientów (get_car, oferta_link_*) działają dalej.
-- Sprawdzone w transakcji z rollback: anon – tylko settings:SELECT, nowa tabela bez dostępu anon,
-- authenticated bez zmian, get_car dalej wykonywalne przez anon.
revoke all on all tables in schema public from anon;
grant select on public.settings to anon;
alter default privileges for role postgres in schema public revoke all on tables from anon;
alter default privileges for role postgres in schema public revoke all on sequences from anon;
