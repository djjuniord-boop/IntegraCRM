-- DEPOZYT OPON (przechowalnia): spis opon klientów z lokalizacją na regale, odhaczanie „przywiezione”
-- z datą i godziną, komentarze, „do wyjaśnienia”, „przygotowane” (lista dla magazyniera) i historia zmian.
-- Migracja `depozyt_opon_modul`. Test uprawnień (w transakcji, cofnięty) – 2026-11-25: konto z modułem i oddziałem
-- widzi i zmienia; inny oddział / brak modułu – nie widzi i nie zmienia; bezpośredni INSERT – odmowa. Nowy moduł uprawnień: `depozyt`.
-- Odczyt: konto z modułem `depozyt` i oddziałem wiersza (admin wszystko). Zapis tylko przez funkcje niżej –
-- każda zmiana trafia do depozyt_historia (kto, kiedy, co). Nic nie jest usuwane.

create table if not exists public.depozyt (
  id bigint generated always as identity primary key,
  branch text not null default 'Latex Wrocław' check (branch in ('Latex Wrocław', 'Latex Opole', 'Stangum Opole')),
  sezon text not null,                       -- np. 'ZIMA 2026/27'
  nr text not null,                          -- numer rejestracyjny (jak w spisie, wielkie litery)
  lok text not null default '',              -- miejsce na regale, np. K1.4, M8/10, KPOK
  marka text not null default '',
  marka2 text not null default '',
  ilosc text not null default '',
  rodzaj text not null default '',           -- kolumna „SEZON” ze spisu (np. LATO)
  uwagi text not null default '',            -- uwagi ze spisu
  komentarz text not null default '',
  komentarz_at timestamptz, komentarz_kto text,
  przywiezione boolean not null default false,
  przywiezione_at timestamptz,               -- null przy przywiezione = true: odhaczone jeszcze w Excelu
  przywiezione_kto text,
  wyjasnic boolean not null default false,
  przygotowane_at timestamptz, przygotowane_kto text,
  utworzono timestamptz not null default now(), utworzyl text
);
create index if not exists depozyt_sezon_idx on public.depozyt (branch, sezon);
create index if not exists depozyt_nr_idx on public.depozyt (nr);

create table if not exists public.depozyt_historia (
  id bigint generated always as identity primary key,
  depozyt_id bigint not null references public.depozyt(id),
  at timestamptz not null default now(),
  kto text not null,
  co text not null
);
create index if not exists depozyt_historia_poz_idx on public.depozyt_historia (depozyt_id, at desc);

alter table public.depozyt enable row level security;
alter table public.depozyt_historia enable row level security;
revoke all on public.depozyt, public.depozyt_historia from anon, authenticated;
grant select on public.depozyt, public.depozyt_historia to authenticated;

-- oddział rozpisany na znane wartości – każda gałąź liczy się raz na zapytanie (supabase/README.md)
create policy depozyt_read on public.depozyt for select to authenticated using (
  (select public.has_module('depozyt')) and case branch
    when 'Latex Wrocław' then (select public.has_branch('Latex Wrocław'))
    when 'Latex Opole' then (select public.has_branch('Latex Opole'))
    when 'Stangum Opole' then (select public.has_branch('Stangum Opole'))
    else false end);
create policy depozyt_historia_read on public.depozyt_historia for select to authenticated using (
  exists (select 1 from public.depozyt d where d.id = depozyt_id));   -- widzi historię pozycji, które widzi

-- Zmiana jednego pola pozycji. p_pole: przywiezione ('1'/'0'), wyjasnic ('1'/'0'), przygotowane ('1'/'0'),
-- komentarz, lok, nr, marka, ilosc, uwagi. Zwraca zmieniony wiersz.
create or replace function public.depozyt_zmien(p_id bigint, p_pole text, p_wartosc text)
returns public.depozyt language plpgsql security definer set search_path = '' as $$
declare
  e text := lower((select auth.jwt() ->> 'email'));
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
    update public.depozyt set wyjasnic = tak where id = p_id returning * into d;
    insert into public.depozyt_historia(depozyt_id, kto, co)
      values (p_id, k, case when tak then 'oznaczono „do wyjaśnienia”' else 'zdjęto „do wyjaśnienia”' end);
  elsif p_pole = 'przygotowane' then
    update public.depozyt set przygotowane_at = case when tak then now() end,
           przygotowane_kto = case when tak then k end where id = p_id returning * into d;
    insert into public.depozyt_historia(depozyt_id, kto, co)
      values (p_id, k, case when tak then 'przygotowane do wydania' else 'cofnięto „przygotowane”' end);
  elsif p_pole = 'komentarz' then
    insert into public.depozyt_historia(depozyt_id, kto, co)
      values (p_id, k, 'komentarz: „' || d.komentarz || '” → „' || v || '”');
    update public.depozyt set komentarz = v, komentarz_at = now(), komentarz_kto = k where id = p_id returning * into d;
  elsif p_pole in ('lok', 'nr', 'marka', 'ilosc', 'uwagi') then
    if p_pole in ('lok', 'nr', 'marka') then v := upper(v); end if;
    if p_pole = 'nr' then v := regexp_replace(v, '\s', '', 'g'); end if;
    if p_pole = 'nr' and v = '' then raise exception 'Numer nie może być pusty' using errcode = '22023'; end if;
    insert into public.depozyt_historia(depozyt_id, kto, co)
      select p_id, k, p_pole || ': „' || coalesce(to_jsonb(d) ->> p_pole, '') || '” → „' || v || '”';
    execute format('update public.depozyt set %I = $1 where id = $2 returning *', p_pole) into d using v, p_id;
  else
    raise exception 'Nieznane pole: %', p_pole using errcode = '22023';
  end if;
  return d;
end $$;

create or replace function public.depozyt_dodaj(p_branch text, p_sezon text, p_nr text, p_lok text,
  p_marka text, p_ilosc text default '', p_rodzaj text default '', p_uwagi text default '')
returns public.depozyt language plpgsql security definer set search_path = '' as $$
declare
  k text;
  d public.depozyt;
begin
  select coalesce(nullif(u.name, ''), u.email) into k from public.me() u;
  if k is null or not public.has_module('depozyt') or not public.has_branch(p_branch) then
    raise exception 'Brak dostępu' using errcode = '42501';
  end if;
  if trim(coalesce(p_nr, '')) = '' then raise exception 'Podaj numer rejestracyjny' using errcode = '22023'; end if;
  insert into public.depozyt(branch, sezon, nr, lok, marka, ilosc, rodzaj, uwagi, utworzyl)
  values (p_branch, p_sezon, upper(regexp_replace(p_nr, '\s', '', 'g')), upper(trim(coalesce(p_lok, ''))), upper(trim(coalesce(p_marka, ''))),
          trim(coalesce(p_ilosc, '')), trim(coalesce(p_rodzaj, '')), trim(coalesce(p_uwagi, '')), k)
  returning * into d;
  insert into public.depozyt_historia(depozyt_id, kto, co) values (d.id, k, 'dodano pozycję');
  return d;
end $$;

revoke all on function public.depozyt_zmien(bigint, text, text) from public, anon;
revoke all on function public.depozyt_dodaj(text, text, text, text, text, text, text, text) from public, anon;
grant execute on function public.depozyt_zmien(bigint, text, text) to authenticated;
grant execute on function public.depozyt_dodaj(text, text, text, text, text, text, text, text) to authenticated;
