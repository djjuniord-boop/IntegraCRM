-- 2026-11-27 (1.2.24): licznik zapytań doboru po aucie (wheel-size.com) – dzienny limit planu API.
-- Funkcja serwera „wheel-size” przed każdym zapytaniem woła ws_licznik_dodaj() tokenem użytkownika: liczy dzień (UTC, jak
-- limit wheel-size), osobę i odmawia po przekroczeniu limitu z app_config 'wheel_size' {"limit": 300} (ustawia admin w Panelu).
-- Raport dla administratora: ws_licznik_raport(dni). Tabela bez dostępu bezpośredniego (tylko przez funkcje).
create table if not exists public.ws_licznik (
  dzien date not null,
  email text not null,
  n integer not null default 0,
  primary key (dzien, email)
);
alter table public.ws_licznik enable row level security;
-- brak zasad = brak dostępu przez REST; odczyt i zapis tylko przez funkcje niżej

insert into public.app_config(key, value) values ('wheel_size', '{"limit": 300}'::jsonb) on conflict (key) do nothing;

create or replace function public.ws_licznik_dodaj()
returns jsonb language plpgsql security definer set search_path = '' as $$
declare
  e text := (select lower(u.email) from public.me() u);
  d date := (now() at time zone 'utc')::date;
  lim integer := coalesce((select (value->>'limit')::integer from public.app_config where key = 'wheel_size'), 300);
  suma integer;
begin
  if e is null or not public.has_module('oferty') then raise exception 'Brak dostępu' using errcode = '42501'; end if;
  perform pg_advisory_xact_lock(hashtext('ws_licznik'));
  select coalesce(sum(n), 0) into suma from public.ws_licznik where dzien = d;
  if suma >= lim then
    return jsonb_build_object('ok', false, 'suma', suma, 'limit', lim);
  end if;
  insert into public.ws_licznik(dzien, email, n) values (d, e, 1)
  on conflict (dzien, email) do update set n = public.ws_licznik.n + 1;
  return jsonb_build_object('ok', true, 'suma', suma + 1, 'limit', lim);
end $$;

create or replace function public.ws_licznik_raport(p_dni integer default 7)
returns jsonb language plpgsql stable security definer set search_path = '' as $$
declare d date := (now() at time zone 'utc')::date;
begin
  if not public.is_admin() then raise exception 'Tylko administrator' using errcode = '42501'; end if;
  return jsonb_build_object(
    'limit', coalesce((select (value->>'limit')::integer from public.app_config where key = 'wheel_size'), 300),
    'dzis', coalesce((select sum(n) from public.ws_licznik where dzien = d), 0),
    'osoby', coalesce((select jsonb_agg(jsonb_build_object('email', l.email, 'imie', coalesce(u.name, ''), 'n', l.n) order by l.n desc)
                       from public.ws_licznik l left join public.app_users u on lower(u.email) = l.email where l.dzien = d), '[]'::jsonb),
    'dni', coalesce((select jsonb_agg(jsonb_build_object('dzien', x.dzien, 'n', x.n) order by x.dzien)
                     from (select dzien, sum(n)::integer n from public.ws_licznik
                           where dzien > d - greatest(1, least(p_dni, 60)) group by dzien) x), '[]'::jsonb));
end $$;

revoke all on function public.ws_licznik_dodaj() from public, anon;
revoke all on function public.ws_licznik_raport(integer) from public, anon;
grant execute on function public.ws_licznik_dodaj() to authenticated;
grant execute on function public.ws_licznik_raport(integer) to authenticated;
