-- DEPOZYT ↔ arkusz Google: znacznik zmian (zmieniono) dla skryptu arkusza, edycja marka2 / rodzaj (kolumny
-- arkusza), indeks do pobierania tylko zmian. Nic nie jest usuwane. Migracja `depozyt_arkusz_sync`.

alter table public.depozyt add column if not exists zmieniono timestamptz not null default now();
create index if not exists depozyt_zmieniono_idx on public.depozyt (branch, sezon, zmieniono);

create or replace function public.depozyt_stamp() returns trigger language plpgsql set search_path = '' as $$
begin
  new.zmieniono := clock_timestamp();
  return new;
end $$;
drop trigger if exists depozyt_stamp on public.depozyt;
create trigger depozyt_stamp before insert or update on public.depozyt
  for each row execute function public.depozyt_stamp();

-- depozyt_zmien: dodatkowo pola marka2 i rodzaj (kolumna „SEZON” spisu); reszta bez zmian
create or replace function public.depozyt_zmien(p_id bigint, p_pole text, p_wartosc text)
returns public.depozyt language plpgsql security definer set search_path = '' as $$
declare
  k text;
  d public.depozyt;
  v text := left(trim(coalesce(p_wartosc, '')), 500);
  tak boolean := v in ('1', 'true', 't');
begin
  select coalesce(nullif(u.name, ''), u.email) into k from public.me() u;
  if k is null or not public.has_module('depozyt') then raise exception 'Brak dostępu' using errcode = '42501'; end if;
  select * into d from public.depozyt where id = p_id for update;
  if not found or not public.has_branch(d.branch) then
    raise exception 'Nie znaleziono pozycji' using errcode = 'P0002';
  end if;
  if p_pole = 'przywiezione' then
    if tak = d.przywiezione then return d; end if;
    update public.depozyt set przywiezione = tak, przywiezione_at = case when tak then now() end,
           przywiezione_kto = case when tak then k end where id = p_id returning * into d;
    insert into public.depozyt_historia(depozyt_id, kto, co)
      values (p_id, k, case when tak then 'PRZYWIEZIONE' else 'cofnięto „przywiezione”' end);
  elsif p_pole = 'wyjasnic' then
    if tak = d.wyjasnic then return d; end if;
    update public.depozyt set wyjasnic = tak where id = p_id returning * into d;
    insert into public.depozyt_historia(depozyt_id, kto, co)
      values (p_id, k, case when tak then 'oznaczono „do wyjaśnienia”' else 'zdjęto „do wyjaśnienia”' end);
  elsif p_pole = 'przygotowane' then
    update public.depozyt set przygotowane_at = case when tak then now() end,
           przygotowane_kto = case when tak then k end where id = p_id returning * into d;
    insert into public.depozyt_historia(depozyt_id, kto, co)
      values (p_id, k, case when tak then 'przygotowane do wydania' else 'cofnięto „przygotowane”' end);
  elsif p_pole = 'komentarz' then
    if v = d.komentarz then return d; end if;
    insert into public.depozyt_historia(depozyt_id, kto, co)
      values (p_id, k, 'komentarz: „' || d.komentarz || '” → „' || v || '”');
    update public.depozyt set komentarz = v, komentarz_at = now(), komentarz_kto = k where id = p_id returning * into d;
  elsif p_pole in ('lok', 'nr', 'marka', 'marka2', 'ilosc', 'rodzaj', 'uwagi') then
    if p_pole in ('lok', 'nr', 'marka', 'marka2') then v := upper(v); end if;
    if p_pole = 'nr' then v := regexp_replace(v, '\s', '', 'g'); end if;
    if p_pole = 'nr' and v = '' then raise exception 'Numer nie może być pusty' using errcode = '22023'; end if;
    if v = coalesce(to_jsonb(d) ->> p_pole, '') then return d; end if;
    insert into public.depozyt_historia(depozyt_id, kto, co)
      select p_id, k, p_pole || ': „' || coalesce(to_jsonb(d) ->> p_pole, '') || '” → „' || v || '”';
    execute format('update public.depozyt set %I = $1 where id = $2 returning *', p_pole) into d using v, p_id;
  else
    raise exception 'Nieznane pole: %', p_pole using errcode = '22023';
  end if;
  return d;
end $$;
revoke all on function public.depozyt_zmien(bigint, text, text) from public, anon;
grant execute on function public.depozyt_zmien(bigint, text, text) to authenticated;

-- ===== Etap 2 (2026-11-25): natychmiastowe powiadomienia program → arkusz =====
-- Migracja `depozyt_arkusz_powiadomienia`. Po każdej zmianie pozycji baza wysyła ją (pg_net) do aplikacji
-- internetowej skryptu arkusza. Zmiany zrobione z konta arkusza są pomijane (bez pętli). Synchronizacja co minutę
-- w skrypcie zostaje jako zapas. Adres i klucz – tabela bez żadnych uprawnień (czyta tylko wyzwalacz).
create table if not exists public.depozyt_arkusz_cfg (
  branch text not null,
  sezon text not null,
  url text not null,
  klucz text not null,
  pomin_email text not null,          -- konto, którym pisze arkusz
  aktywny boolean not null default true,
  primary key (branch, sezon)
);
alter table public.depozyt_arkusz_cfg enable row level security;
revoke all on public.depozyt_arkusz_cfg from public, anon, authenticated;

create or replace function public.depozyt_do_arkusza() returns trigger
language plpgsql security definer set search_path = '' as $$
declare c public.depozyt_arkusz_cfg;
begin
  select * into c from public.depozyt_arkusz_cfg where branch = new.branch and sezon = new.sezon and aktywny;
  if found and lower(coalesce((select auth.jwt() ->> 'email'), '')) <> lower(c.pomin_email) then
    perform net.http_post(url := c.url,
                          body := jsonb_build_object('klucz', c.klucz, 'wiersz', to_jsonb(new)),
                          headers := '{"Content-Type": "application/json"}'::jsonb);
  end if;
  return null;
exception when others then
  return null;   -- powiadomienie nigdy nie blokuje zapisu w programie
end $$;
revoke all on function public.depozyt_do_arkusza() from public, anon, authenticated;
drop trigger if exists depozyt_do_arkusza on public.depozyt;
create trigger depozyt_do_arkusza after insert or update on public.depozyt
  for each row execute function public.depozyt_do_arkusza();
