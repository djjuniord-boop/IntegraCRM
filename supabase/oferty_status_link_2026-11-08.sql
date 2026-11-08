-- 0.25.0 (beta) – OFERTY OPON: status oferty, przypomnienia, link dla klienta z akceptacją
-- Tylko dodaje kolumny i funkcje (nic nie usuwa). Zasady dostępu tabeli oferty bez zmian:
-- właściciel czyta i zmienia swoje, administrator czyta wszystkie.
-- Klient (bez logowania, rola anon) NIE ma dostępu do tabeli – tylko przez dwie funkcje niżej, po losowym tokenie (uuid),
-- i widzi wyłącznie migawkę przygotowaną dla niego (strony PDF, bez cen zakupu), ważną 30 dni.

alter table public.oferty
  add column if not exists status text not null default 'nowa',
  add column if not exists status_at timestamptz,
  add column if not exists link_token uuid,
  add column if not exists link_dane jsonb,
  add column if not exists link_at timestamptz,
  add column if not exists link_otwarta timestamptz,
  add column if not exists klient_odp jsonb;

do $$ begin
  alter table public.oferty add constraint oferty_status_ok
    check (status in ('nowa', 'wyslana', 'przyjeta', 'odrzucona', 'zamowiona'));
exception when duplicate_object then null; end $$;
create unique index if not exists oferty_link_token on public.oferty (link_token) where link_token is not null;

-- właściciel: utwórz/odśwież link (token zostaje ten sam), status „wysłana” jeśli była „nowa”
create or replace function public.oferty_link(p_oid text, p_dane jsonb)
returns uuid language plpgsql security definer set search_path = '' as $$
declare e text := lower((select auth.jwt() ->> 'email')); t uuid;
begin
  if e is null or not public.has_module('oferty') then raise exception 'Brak dostępu' using errcode = '42501'; end if;
  if octet_length(p_dane::text) > 2000000 then raise exception 'Oferta za duża na link' using errcode = '22023'; end if;
  update public.oferty set link_token = coalesce(link_token, gen_random_uuid()), link_dane = p_dane, link_at = now(),
         status = case when status = 'nowa' then 'wyslana' else status end,
         status_at = case when status = 'nowa' then now() else status_at end
   where owner = e and oid = p_oid
  returning link_token into t;
  if t is null then raise exception 'Najpierw zapisz ofertę (przelicz ją)' using errcode = 'P0002'; end if;
  return t;
end $$;

-- klient (anon): pobierz ofertę po tokenie; pierwsze otwarcie zapisuje czas
create or replace function public.oferta_link_pobierz(p_token uuid)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare r public.oferty;
begin
  select * into r from public.oferty where link_token = p_token and link_at > now() - interval '30 days';
  if r.id is null then return null; end if;
  if r.link_otwarta is null then update public.oferty set link_otwarta = now() where id = r.id; end if;
  return jsonb_build_object('dane', r.link_dane, 'odp', r.klient_odp, 'wazna_do', (r.link_at + interval '30 days'));
end $$;

-- klient (anon): wybór modelu + telefon/uwagi -> status „przyjęta” (można zmienić zdanie, dopóki link ważny)
create or replace function public.oferta_link_akceptuj(p_token uuid, p_wybor text, p_tel text, p_uwagi text)
returns boolean language plpgsql security definer set search_path = '' as $$
declare r public.oferty;
begin
  select * into r from public.oferty where link_token = p_token and link_at > now() - interval '30 days';
  if r.id is null then return false; end if;
  if r.status in ('zamowiona') then return false; end if;
  update public.oferty set klient_odp = jsonb_build_object(
           'wybor', left(coalesce(p_wybor, ''), 300), 'tel', left(regexp_replace(coalesce(p_tel, ''), '[^0-9 +]', '', 'g'), 20),
           'uwagi', left(coalesce(p_uwagi, ''), 500), 'at', now()),
         status = 'przyjeta', status_at = now()
   where id = r.id;
  return true;
end $$;

-- właściciel: zmiana statusu ręcznie
create or replace function public.oferty_status(p_oid text, p_status text)
returns void language plpgsql security definer set search_path = '' as $$
declare e text := lower((select auth.jwt() ->> 'email'));
begin
  if e is null or not public.has_module('oferty') then raise exception 'Brak dostępu' using errcode = '42501'; end if;
  if p_status not in ('nowa', 'wyslana', 'przyjeta', 'odrzucona', 'zamowiona') then raise exception 'Zły status' using errcode = '22023'; end if;
  update public.oferty set status = p_status, status_at = now() where owner = e and oid = p_oid;
end $$;

revoke all on function public.oferty_link(text, jsonb) from public, anon;
revoke all on function public.oferty_status(text, text) from public, anon;
revoke all on function public.oferta_link_pobierz(uuid) from public;
revoke all on function public.oferta_link_akceptuj(uuid, text, text, text) from public;
grant execute on function public.oferty_link(text, jsonb) to authenticated;
grant execute on function public.oferty_status(text, text) to authenticated;
grant execute on function public.oferta_link_pobierz(uuid) to anon, authenticated;
grant execute on function public.oferta_link_akceptuj(uuid, text, text, text) to anon, authenticated;
