-- 2026-10-14 · migracja `visit_stats_statystyki` (wersja 0.21.0 – statystyki list kontrolnych na wizyty)
--
-- 1. Tabela public.visit_stats – licznik dzienny na oddział: wizyty (zlecenia z pojazdem w Integrze),
--    listy kontrolne (wiersze raportu .xlsx z CRM), braki. Klucz (branch, day). Program zapisuje upsertem
--    (POST /rest/v1/visit_stats?on_conflict=branch,day, Prefer: resolution=merge-duplicates) – kolejne
--    sprawdzenie tego samego dnia nadpisuje liczby (bez podwójnego liczenia).
--    updated_by/updated_at ustawia wyzwalacz `stamp` przy każdym zapisie (klient nie podrobi).
--    Bez wyzwalacza audit (dziennik ma już „sprawdzenie”).
-- 2. RLS: odczyt – moduł 'statystyki' + oddział (admin wszystko); zapis – moduł 'crm' + oddział;
--    usuwanie – nikt (brak GRANT DELETE). Anon – brak prawa do tabeli.
-- 3. Nowe moduły: 'historia' (zakładka HISTORIA, dotąd z 'crm') i 'statystyki'. Każde konto z 'crm'
--    dostaje 'historia'. checks.crm_read: crm OR historia (warunek oddziałów bez zmian).
--    reported.crm_read bez zmian (tylko 'crm' – rejestr używa Kontrola).
-- Test: supabase/test_statystyki_2026-10-14.sql

create table public.visit_stats (
  branch     text        not null check (branch in ('Latex Wrocław', 'Latex Opole', 'Stangum Opole')),
  day        date        not null,
  visits     int         not null default 0 check (visits >= 0),
  lists      int         not null default 0 check (lists >= 0),
  missing    int         not null default 0 check (missing >= 0),
  check_id   bigint      references public.checks(id) on delete set null,
  updated_at timestamptz not null default now(),
  updated_by text        default lower(auth.jwt() ->> 'email'),
  primary key (branch, day)
);
comment on table public.visit_stats is
  'Statystyki: dzienny licznik na oddział – wizyty z Integry, listy kontrolne z CRM, braki (upsert, nadpisuje).';
create index visit_stats_check_id on public.visit_stats(check_id);

alter table public.visit_stats enable row level security;
revoke all on table public.visit_stats from anon, authenticated;
grant select, insert, update on table public.visit_stats to authenticated;

create function public.visit_stats_stamp()
returns trigger language plpgsql set search_path = '' as $$
begin
  new.updated_by := coalesce(lower(auth.jwt() ->> 'email'), 'system');
  new.updated_at := now();
  return new;
end $$;
revoke execute on function public.visit_stats_stamp() from public, anon, authenticated;

create trigger stamp before insert or update on public.visit_stats
  for each row execute function public.visit_stats_stamp();

-- branch ma 3 znane wartości → has_branch liczony raz na zapytanie (initPlan), nie dla każdego wiersza
create policy stats_read on public.visit_stats for select to authenticated
  using ((select u.email from public.me() u) is not null
         and (select public.has_module('statystyki'))
         and case branch when 'Latex Wrocław' then (select public.has_branch('Latex Wrocław'))
                         when 'Latex Opole'   then (select public.has_branch('Latex Opole'))
                         when 'Stangum Opole' then (select public.has_branch('Stangum Opole'))
                         else false end);

create policy stats_insert on public.visit_stats for insert to authenticated
  with check ((select public.has_module('crm')) and public.has_branch(branch));
-- (przy insert/update warunek liczy się tylko dla zapisywanych wierszy – kilka dziennie)

create policy stats_update on public.visit_stats for update to authenticated
  using ((select public.has_module('crm')) and public.has_branch(branch))
  with check ((select public.has_module('crm')) and public.has_branch(branch));

-- 3. Moduły historia / statystyki
update public.app_users set modules = array_append(modules, 'historia')
 where 'crm' = any(modules) and not ('historia' = any(modules));

alter policy crm_read on public.checks
  using (((select public.has_module('crm')) or (select public.has_module('historia')))
         and ((select public.is_admin())
              or user_email = lower((select auth.jwt()) ->> 'email')
              or exists (select 1 from unnest(checks.branches) b(b) where public.has_branch(b.b))));

-- 4. (druga migracja `visit_stats_save_rpc`) Zapis przez funkcję.
-- Powód: w Postgresie INSERT ... ON CONFLICT DO UPDATE (upsert PostgREST z merge-duplicates) wymaga, żeby
-- istniejący wiersz przechodził zasadę SELECT. Konto 'crm' bez 'statystyki' nie czyta tabeli, więc drugi
-- zapis tego samego dnia kończył się błędem RLS (sprawdzone testem). Program zapisuje więc przez:
--   POST /rest/v1/rpc/save_visit_stats {"p_branch","p_day","p_visits","p_lists","p_missing","p_check_id"}
-- Funkcja sama sprawdza: aktywne konto, moduł 'crm', oddział. Zwraca nic (void).
create function public.save_visit_stats(p_branch text, p_day date, p_visits int, p_lists int,
                                        p_missing int, p_check_id bigint default null)
returns void language plpgsql security definer set search_path = '' as $$
begin
  if (select u.email from public.me() u) is null
     or not public.has_module('crm') or not public.has_branch(p_branch) then
    raise exception 'Brak uprawnień do zapisu statystyk oddziału %', p_branch using errcode = '42501';
  end if;
  insert into public.visit_stats(branch, day, visits, lists, missing, check_id)
  values (p_branch, p_day, p_visits, p_lists, p_missing, p_check_id)
  on conflict (branch, day) do update set visits = excluded.visits, lists = excluded.lists,
    missing = excluded.missing, check_id = excluded.check_id;
end $$;
revoke execute on function public.save_visit_stats(text, date, int, int, int, bigint) from public, anon;
grant execute on function public.save_visit_stats(text, date, int, int, int, bigint) to authenticated;
