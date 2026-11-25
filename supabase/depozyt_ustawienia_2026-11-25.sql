-- DEPOZYT: ustawienia oddziału (administrator w programie) i koniec oznaczenia pomarańczowego.
-- Migracja `depozyt_ustawienia`. Nic nie jest usuwane (kolumna `wyjasnic` zostaje, nieużywana).
--  * depozyt_ustawienia – sezon otwierany na start, ukryte sezony (archiwum), kolejność regałów (trasa),
--    kto może cofać „przywiezione” i zmieniać numer/lokalizację; odczyt: moduł depozyt + oddział, zapis: admin.
--  * depozyt_zmien sprawdza te uprawnienia (pilnuje baza, nie program).
--  * 20 pozycji „do wyjaśnienia” (pomarańczowe w Excelu = przywiezione bez wymiany, nowa lokalizacja):
--    oznaczenie zdjęte, informacja przeniesiona do komentarza, wpis w historii.

create table if not exists public.depozyt_ustawienia (
  branch text primary key check (branch in ('Latex Wrocław', 'Latex Opole', 'Stangum Opole')),
  sezon_domyslny text not null default '',
  ukryte_sezony text[] not null default '{}',
  trasa text[] not null default '{}',
  cofanie_tylko_admin boolean not null default true,
  edycja_tylko_admin boolean not null default false,
  zmieniono timestamptz not null default now(),
  zmienil text
);
alter table public.depozyt_ustawienia enable row level security;
revoke all on public.depozyt_ustawienia from anon, authenticated;
grant select on public.depozyt_ustawienia to authenticated;
drop policy if exists depozyt_ustawienia_read on public.depozyt_ustawienia;
create policy depozyt_ustawienia_read on public.depozyt_ustawienia for select to authenticated using (
  (select public.has_module('depozyt')) and case branch
    when 'Latex Wrocław' then (select public.has_branch('Latex Wrocław'))
    when 'Latex Opole' then (select public.has_branch('Latex Opole'))
    when 'Stangum Opole' then (select public.has_branch('Stangum Opole'))
    else false end);

create or replace function public.depozyt_zapisz_ustawienia(p_branch text, p jsonb)
returns public.depozyt_ustawienia language plpgsql security definer set search_path = '' as $$
declare
  u public.depozyt_ustawienia;
  k text;
begin
  select coalesce(nullif(x.name, ''), x.email) into k from public.me() x;
  if k is null or not public.is_admin() then
    raise exception 'Ustawienia depozytu zmienia tylko administrator' using errcode = '42501';
  end if;
  insert into public.depozyt_ustawienia(branch, sezon_domyslny, ukryte_sezony, trasa, cofanie_tylko_admin,
                                        edycja_tylko_admin, zmieniono, zmienil)
  values (p_branch, coalesce(p ->> 'sezon_domyslny', ''),
          coalesce(array(select jsonb_array_elements_text(p -> 'ukryte_sezony')), '{}'),
          coalesce(array(select upper(jsonb_array_elements_text(p -> 'trasa'))), '{}'),
          coalesce((p ->> 'cofanie_tylko_admin')::boolean, true),
          coalesce((p ->> 'edycja_tylko_admin')::boolean, false), now(), k)
  on conflict (branch) do update set sezon_domyslny = excluded.sezon_domyslny, ukryte_sezony = excluded.ukryte_sezony,
    trasa = excluded.trasa, cofanie_tylko_admin = excluded.cofanie_tylko_admin,
    edycja_tylko_admin = excluded.edycja_tylko_admin, zmieniono = now(), zmienil = k
  returning * into u;
  return u;   -- kto i kiedy: kolumny zmienil / zmieniono
end $$;
revoke all on function public.depozyt_zapisz_ustawienia(text, jsonb) from public, anon;
grant execute on function public.depozyt_zapisz_ustawienia(text, jsonb) to authenticated;

-- depozyt_zmien: uprawnienia z ustawień (cofanie „przywiezione”, zmiana numeru i lokalizacji)
create or replace function public.depozyt_zmien(p_id bigint, p_pole text, p_wartosc text)
returns public.depozyt language plpgsql security definer set search_path = '' as $$
declare
  k text;
  d public.depozyt;
  s public.depozyt_ustawienia;
  v text := left(trim(coalesce(p_wartosc, '')), 500);
  tak boolean := v in ('1', 'true', 't');
begin
  select coalesce(nullif(u.name, ''), u.email) into k from public.me() u;
  if k is null or not public.has_module('depozyt') then raise exception 'Brak dostępu' using errcode = '42501'; end if;
  select * into d from public.depozyt where id = p_id for update;
  if not found or not public.has_branch(d.branch) then
    raise exception 'Nie znaleziono pozycji' using errcode = 'P0002';
  end if;
  select * into s from public.depozyt_ustawienia where branch = d.branch;
  if p_pole = 'przywiezione' then
    if tak = d.przywiezione then return d; end if;
    if not tak and coalesce(s.cofanie_tylko_admin, true) and not public.is_admin() then
      raise exception 'Cofnąć „przywiezione” może tylko administrator' using errcode = '42501';
    end if;
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
    if p_pole in ('nr', 'lok') and coalesce(s.edycja_tylko_admin, false) and not public.is_admin() then
      raise exception 'Numer i lokalizację zmienia tylko administrator' using errcode = '42501';
    end if;
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

-- Domyślne ustawienia Wrocławia (jak dotąd: cofanie tylko admin, edycja wszyscy; TEST ARKUSZ ukryty)
insert into public.depozyt_ustawienia(branch, sezon_domyslny, ukryte_sezony, zmienil)
values ('Latex Wrocław', 'ZIMA 2026/27', '{TEST ARKUSZ}', 'migracja')
on conflict (branch) do nothing;

-- Pomarańczowe → komentarz (raz; drugie uruchomienie nic nie zmienia)
with zm as (
  update public.depozyt
     set wyjasnic = false,
         komentarz = trim(both ' ·' from komentarz || ' · przywiezione bez wymiany – nowa lokalizacja (z Excela)'),
         komentarz_at = now(), komentarz_kto = 'migracja'
   where wyjasnic
  returning id)
insert into public.depozyt_historia(depozyt_id, kto, co)
select id, 'migracja', 'zdjęto „do wyjaśnienia” → komentarz „przywiezione bez wymiany – nowa lokalizacja”' from zm;

select (select count(*) from public.depozyt where wyjasnic) as pomaranczowe_zostalo,
       (select count(*) from public.depozyt where komentarz like '%bez wymiany%') as z_komentarzem;
