-- 2026-10-14 · migracja `marza_months_wyniki` (wersja 0.20.0 – zakładka WYNIKI)
--
-- Cel: handlowcy (nowy moduł uprawnień 'wyniki') widzą wyniki marży SWOJEGO oddziału; pracownicy z modułem
-- 'marza' (i admin) widzą oba oddziały i jako jedyni zapisują.
--
-- 1. public.can_see_marza(b) – czy bieżące konto może czytać wyniki oddziału b ('wroclaw' / 'opole'):
--    moduł 'marza' ALBO (moduł 'wyniki' I oddział 'Latex Wrocław' / 'Latex Opole' na koncie).
--    Admin przechodzi przez has_module/has_branch. Zablokowane i obce konta: me() puste → false.
-- 2. Nowa tabela public.marza_months – cel, wykonanie i święta dla oddziału i miesiąca (klucz: oddział, rok,
--    miesiąc). Program zapisuje upsertem (POST ...?on_conflict=branch,year,month, Prefer: merge-duplicates).
--    Wyzwalacz `stamp` ustawia updated_by (e-mail z tokenu) i updated_at (czas serwera) przy KAŻDYM
--    zapisie, także przy aktualizacji istniejącego wiersza – klient nie może tego podrobić.
-- 3. marza_results: zasada marza_read dostaje ten sam warunek odczytu (ALTER POLICY, bez drop).
--    Zapis do marza_results bez zmian (marza_insert – tylko moduł 'marza').
--
-- Wydajność: warunek odczytu NIE jest pisany jako `using (public.can_see_marza(branch))` – wtedy Postgres
-- woła funkcję dla każdego wiersza (pomiar 2026-10-14 na 5000 wierszach marza_results: 2328 ms dla
-- handlowca). Forma `case branch when 'wroclaw' then (select public.can_see_marza('wroclaw')) ...` liczy
-- funkcję raz na zapytanie dla każdego oddziału (initPlan): 2 ms, ten sam wynik. `else false` – nieznany
-- oddział (nie przejdzie i tak przez check na kolumnie branch) jest niewidoczny.
-- Dodanie oddziału = zmiana w trzech miejscach: check na branch, can_see_marza, oba warunki odczytu.
--
-- Bez wyzwalacza `audit` (audit_trg nie zna tej tabeli – wpisałby pusty `entity`, a ta kolumna jest NOT NULL;
-- ostatnią zmianę pokazują updated_by / updated_at).
-- Test uprawnień: supabase/test_wyniki_2026-10-14.sql (kończy się cofnięciem, nic nie zostaje).

-- 1. Kto widzi wyniki oddziału ------------------------------------------------------------------------------
create function public.can_see_marza(b text)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select public.has_module('marza')
      or (public.has_module('wyniki')
          and public.has_branch(case b when 'wroclaw' then 'Latex Wrocław'
                                       when 'opole'   then 'Latex Opole' end));
$$;
comment on function public.can_see_marza(text) is
  'Czy bieżące konto widzi wyniki marży oddziału (wroclaw/opole): moduł marza albo moduł wyniki + oddział.';
revoke execute on function public.can_see_marza(text) from public, anon;
grant execute on function public.can_see_marza(text) to authenticated;

-- 2. Miesiące marży: cel, wykonanie, święta ------------------------------------------------------------------
create table public.marza_months (
  branch     text          not null check (branch in ('wroclaw', 'opole')),
  year       int           not null,
  month      int           not null check (month between 1 and 12),
  label      text,
  target     numeric(14,2),
  done       numeric(14,2),
  holidays   date[]        not null default '{}',
  updated_at timestamptz   not null default now(),
  updated_by text          default lower(auth.jwt() ->> 'email'),
  primary key (branch, year, month)
);
comment on table public.marza_months is
  'MARŻA/WYNIKI: cel, wykonanie i święta (do liczenia dni sprzedażowych) dla oddziału i miesiąca.';
comment on column public.marza_months.holidays is 'Święta przypadające w tym miesiącu (dni bez sprzedaży).';
comment on column public.marza_months.updated_by is 'Kto ostatnio zapisał wiersz – ustawia wyzwalacz stamp.';

alter table public.marza_months enable row level security;

-- Tylko zalogowani, tylko odczyt/dodanie/zmiana (usuwania program nie potrzebuje). Anon – nic.
revoke all on table public.marza_months from anon, authenticated;
grant select, insert, update on table public.marza_months to authenticated;

-- updated_by / updated_at zawsze z serwera (także przy upsercie na istniejącym wierszu);
-- holidays: null (np. brak klucza w jednym z wierszy upsertu) → pusta lista zamiast błędu NOT NULL.
create function public.marza_months_stamp()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_by := coalesce(lower(auth.jwt() ->> 'email'), 'system');
  new.updated_at := now();
  new.holidays   := coalesce(new.holidays, '{}');
  return new;
end $$;
revoke execute on function public.marza_months_stamp() from public, anon, authenticated;

create trigger stamp
  before insert or update on public.marza_months
  for each row execute function public.marza_months_stamp();

create policy marza_read on public.marza_months
  for select to authenticated
  using (case branch when 'wroclaw' then (select public.can_see_marza('wroclaw'))
                     when 'opole'   then (select public.can_see_marza('opole'))
                     else false end);

create policy marza_insert on public.marza_months
  for insert to authenticated
  with check ((select public.has_module('marza')));

create policy marza_update on public.marza_months
  for update to authenticated
  using ((select public.has_module('marza')))
  with check ((select public.has_module('marza')));

-- 3. marza_results: odczyt także dla handlowców swojego oddziału ---------------------------------------------
alter policy marza_read on public.marza_results
  using (case branch when 'wroclaw' then (select public.can_see_marza('wroclaw'))
                     when 'opole'   then (select public.can_see_marza('opole'))
                     else false end);
