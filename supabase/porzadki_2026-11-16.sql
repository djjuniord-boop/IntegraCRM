-- PORZĄDKI przed wersją finalną (2026-11-16). Wymaga zgody właściciela – wklej w SQL Editor.
-- 1) Link dla klienta i akceptacja przez klienta – usunięte z programu w 0.25.3; funkcje były dostępne bez logowania (anon).
drop function if exists public.oferta_link_pobierz(uuid);
drop function if exists public.oferta_link_akceptuj(uuid, text, text, text);
drop function if exists public.oferty_link(text, jsonb);
-- 2) STATYSTYKI – moduł usunięty w 0.27.9 (zebrane dane liczników dziennych zostaną skasowane).
drop function if exists public.save_visit_stats(text, date, integer, integer, integer, bigint);
drop table if exists public.visit_stats;
