-- PORZĄDKI 2 przed wersją 1.0.0 (2026-11-16). Wymaga zgody właściciela – wklej w SQL Editor.
-- UWAGA – KOLEJNOŚĆ: uruchomić dopiero, gdy app_config.min_version = 1.0.0 (wydanie na main gotowe).
-- Wersje < 1.0.0 czytają kolumny link_* i po ich usunięciu pokazałyby historię ofert bez statusów i uwag.
-- Zawieszona aplikacja Android (mobile/www/app.js) też je czyta – jej historia ofert przestanie działać (świadomie).

-- 1) Dane po linku dla klienta (migawki ofert, odpowiedzi klientów z telefonem) – RODO: kasujemy
alter table public.oferty drop column if exists link_token;
alter table public.oferty drop column if exists link_dane;
alter table public.oferty drop column if exists link_at;
alter table public.oferty drop column if exists link_otwarta;
alter table public.oferty drop column if exists klient_odp;

-- 2) Martwe funkcje
drop function if exists public.visit_stats_stamp();          -- wyzwalacz skasowanej tabeli visit_stats
drop function if exists public.oferty_moje_haslo();          -- nikt nie ma prawa jej wykonać
drop function if exists public.app_login(text);              -- stara wersja; program używa app_login(p_version, p_device)

-- 3) Usunięty moduł STATYSTYKI w kontach
update public.app_users set modules = array_remove(modules, 'statystyki') where 'statystyki' = any(modules);
