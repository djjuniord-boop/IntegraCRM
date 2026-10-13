-- Porządki po wersji 0.19 – wklej w Supabase → latex-serwis-qr → SQL Editor → Run.
-- (Polecenia usuwające wymagają zatwierdzenia, którego narzędzie nie może dać samo.)

-- 1. zbędna funkcja po wcześniejszym podejściu do importu historii (ostrzeżenie bezpieczeństwa doradcy)
drop function if exists public.audit_trg_skip_import();

-- 2. auto testowe z testu strony klienta (DW 1TEST) – razem z jego wpisem serwisowym
delete from public.cars where token = 'TESTqr2026x';
