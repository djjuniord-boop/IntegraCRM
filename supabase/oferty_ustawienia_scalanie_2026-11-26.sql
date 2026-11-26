-- 2026-11-26 (1.2.21): zapis ustawień ofert SCALA z poprzednimi zamiast je zastępować.
-- Powód: stara aplikacja w telefonie zna mniej ustawień – jej zapis kasował nowe ustawienia z Panelu (felgi, wyniki na stronę…).
-- Zastosowane w bazie (migracja oferty_ustawienia_scalanie_2026_11_26); test w transakcji: dwa zapisy częściowe -> oba klucze zostają.
create or replace function public.oferty_zapisz_ustawienia(p jsonb)
returns void language plpgsql security definer set search_path = '' as $$
declare e text := (select u.email from public.me() u);
begin
  if e is null or not public.has_module('oferty') then raise exception 'Brak dostępu' using errcode = '42501'; end if;
  -- scalanie zamiast zastępowania: stara aplikacja w telefonie (zna mniej ustawień) nie kasuje nowych ustawień z Panelu
  insert into public.oferty_konta as k (email, ustawienia, updated_by) values (lower(e), coalesce(p, '{}'::jsonb), e)
  on conflict (email) do update set ustawienia = coalesce(k.ustawienia, '{}'::jsonb) || excluded.ustawienia, updated_at = now(), updated_by = e;
end $$;
revoke all on function public.oferty_zapisz_ustawienia(jsonb) from public, anon;
grant execute on function public.oferty_zapisz_ustawienia(jsonb) to authenticated;
