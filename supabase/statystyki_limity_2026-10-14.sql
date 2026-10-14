-- Etap: realne liczby w statystykach (visit_stats) – 2026-10-14
-- Funkcja zapisu pomija dni spoza rozsądnego zakresu (bez błędu – reszta dni z raportu zapisuje się normalnie),
-- a tabela nie przyjmie nierealnych liczb także przy zapisie bezpośrednim.
-- Limity: dzień od 400 dni wstecz do jutra; do 2000 zleceń i 4000 list na oddział dziennie; braki ≤ zleceń.

create or replace function public.save_visit_stats(p_branch text, p_day date, p_visits integer, p_lists integer,
                                                   p_missing integer, p_check_id bigint default null)
returns void language plpgsql security definer set search_path to '' as $function$
begin
  if (select u.email from public.me() u) is null
     or not public.has_module('crm') or not public.has_branch(p_branch) then
    raise exception 'Brak uprawnień do zapisu statystyk oddziału %', p_branch using errcode = '42501';
  end if;
  if p_day is null or p_day > current_date + 1 or p_day < current_date - 400
     or p_visits is null or p_visits < 0 or p_visits > 2000
     or p_lists is null or p_lists < 0 or p_lists > 4000
     or p_missing is null or p_missing < 0 or p_missing > p_visits then
    return;   -- nierealny wiersz (np. zła data w raporcie) – pomijamy
  end if;
  insert into public.visit_stats(branch, day, visits, lists, missing, check_id)
  values (p_branch, p_day, p_visits, p_lists, p_missing, p_check_id)
  on conflict (branch, day) do update set visits = excluded.visits, lists = excluded.lists,
    missing = excluded.missing, check_id = excluded.check_id;
end $function$;

alter table public.visit_stats drop constraint if exists visit_stats_realne;
alter table public.visit_stats add constraint visit_stats_realne check (
  visits between 0 and 2000 and lists between 0 and 4000 and missing between 0 and visits
  and day >= date '2025-01-01');
