-- Etap: poprawka z doradcy bezpieczeństwa Supabase (2026-10-15)
-- checks_guard() to funkcja wyzwalacza – nie powinna być wywoływana przez API (RPC). Nic nie usuwa.
revoke execute on function public.checks_guard() from public, anon, authenticated;
