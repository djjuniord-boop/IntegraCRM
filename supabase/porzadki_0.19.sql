-- Porządki po wersji 0.19 – wklej w Supabase → latex-serwis-qr → SQL Editor → Run.
-- (Polecenia usuwające wymagają zatwierdzenia, którego narzędzie nie może dać samo.)

-- 1. zbędna funkcja po wcześniejszym podejściu do importu historii (ostrzeżenie bezpieczeństwa doradcy)
drop function if exists public.audit_trg_skip_import();

-- Auto testowe DW 1TEST (token TESTqr2026x) zostaje celowo – na nim sprawdzamy stronę klienta (?a=TESTqr2026x).
