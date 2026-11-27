-- 2026-11-27: porządki – stara wersja licznika wheel-size bez parametru (zastąpiona ws_licznik_dodaj(p_email),
-- prawo wywołania odebrane w uprawnienia_ofert_2_2026-11-27.sql). Zawiera DROP – wkleja właściciel w SQL Editor.
drop function if exists public.ws_licznik_dodaj();
