-- OFERTY OPON: wewnętrzne uwagi do oferty (np. dla kogo zamówienie). Nie trafiają do PDF ani do klienta.
-- Zapis: autor oferty albo administrator (funkcja oferty_uwagi). Nic nie jest usuwane.
alter table public.oferty add column if not exists uwagi text not null default '';
alter table public.oferty add column if not exists uwagi_at timestamptz;
alter table public.oferty add column if not exists uwagi_kto text;

create or replace function public.oferty_uwagi(p_id bigint, p_uwagi text)
returns void language plpgsql security definer set search_path = '' as $$
declare e text := lower((select auth.jwt() ->> 'email'));
begin
  if e is null or not public.has_module('oferty') then raise exception 'Brak dostępu' using errcode = '42501'; end if;
  update public.oferty set uwagi = left(coalesce(p_uwagi, ''), 1000), uwagi_at = now(), uwagi_kto = e
   where id = p_id and (owner = e or public.is_admin());
  if not found then raise exception 'Nie znaleziono oferty (albo nie jest Twoja)' using errcode = 'P0002'; end if;
end $$;

revoke all on function public.oferty_uwagi(bigint, text) from public, anon;
grant execute on function public.oferty_uwagi(bigint, text) to authenticated;
