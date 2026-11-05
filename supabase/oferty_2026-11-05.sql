-- 0.23.0 – moduł OFERTY OPON (migracja oferty_opon_modul)
-- oferty_konta: dane logowania API xPartner (każdy użytkownik swoje; wpisuje administrator) + ustawienia oferty
--   odczyt: swój wiersz (program potrzebuje loginu do zapytań) albo administrator; zapis tylko przez funkcje niżej
-- oferty: historia ofert – każdy widzi i zmienia tylko swoje (także administrator)

create table if not exists public.oferty_konta (
  email text primary key references public.app_users(email) on update cascade on delete cascade,
  xp_login text not null default '',
  xp_haslo text not null default '',
  ustawienia jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now(),
  updated_by text
);
alter table public.oferty_konta enable row level security;
revoke all on public.oferty_konta from anon, authenticated;
grant select on public.oferty_konta to authenticated;
create policy oferty_konta_read on public.oferty_konta for select to authenticated
  using (lower(email) = lower((select (u.email) from public.me() u)) or (select public.is_admin()));

create table if not exists public.oferty (
  id bigint generated always as identity primary key,
  owner text not null default lower((auth.jwt() ->> 'email')),
  oid text not null,
  klient text not null default '',
  dane jsonb not null default '{}'::jsonb,
  szukaj text not null default '',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (owner, oid)
);
alter table public.oferty enable row level security;
revoke all on public.oferty from anon, authenticated;
grant select, insert, update, delete on public.oferty to authenticated;
create policy oferty_own on public.oferty for all to authenticated
  using (owner = lower((select auth.jwt() ->> 'email')) and (select public.has_module('oferty')))
  with check (owner = lower((select auth.jwt() ->> 'email')) and (select public.has_module('oferty')));
create index if not exists oferty_owner_upd on public.oferty (owner, updated_at desc);

-- administrator: login i hasło API xPartner dla wybranego konta (puste hasło = bez zmiany)
create or replace function public.oferty_admin_set_konto(p_email text, p_login text, p_haslo text)
returns void language plpgsql security definer set search_path = '' as $$
begin
  if not public.is_admin() then raise exception 'Tylko administrator' using errcode = '42501'; end if;
  insert into public.oferty_konta(email, xp_login, xp_haslo, updated_by)
  values (lower(trim(p_email)), coalesce(trim(p_login), ''), coalesce(p_haslo, ''), (select u.email from public.me() u))
  on conflict (email) do update set xp_login = excluded.xp_login,
    xp_haslo = case when coalesce(p_haslo, '') = '' then public.oferty_konta.xp_haslo else excluded.xp_haslo end,
    updated_at = now(), updated_by = excluded.updated_by;
end $$;

-- użytkownik z modułem oferty: własne ustawienia (marża, cennik wymiany, usługi…) – bez loginu i hasła
create or replace function public.oferty_zapisz_ustawienia(p jsonb)
returns void language plpgsql security definer set search_path = '' as $$
declare e text := (select u.email from public.me() u);
begin
  if e is null or not public.has_module('oferty') then raise exception 'Brak dostępu' using errcode = '42501'; end if;
  insert into public.oferty_konta(email, ustawienia, updated_by) values (lower(e), coalesce(p, '{}'::jsonb), e)
  on conflict (email) do update set ustawienia = excluded.ustawienia, updated_at = now(), updated_by = e;
end $$;

revoke all on function public.oferty_admin_set_konto(text,text,text), public.oferty_zapisz_ustawienia(jsonb) from public, anon;
grant execute on function public.oferty_admin_set_konto(text,text,text), public.oferty_zapisz_ustawienia(jsonb) to authenticated;
