-- DEPOZYT: lista do przygotowania zapisywana z Panelu (po wczytaniu raportu z Integry), żeby magazynier
-- otworzył ją w telefonie. Jedna aktualna lista na oddział (nowy raport ją zastępuje). Bez nazw klientów.
-- Migracja `depozyt_listy`. Nic nie jest usuwane.
create table if not exists public.depozyt_listy (
  branch text primary key check (branch in ('Latex Wrocław', 'Latex Opole', 'Stangum Opole')),
  tytul text not null default '',
  od text not null default '',
  "do" text not null default '',
  zrodlo text not null default '',          -- 'terminy' (Excel z wizytami) albo '' (PDF przechowalni)
  wiersze jsonb not null default '[]',      -- [{nr, lok, szt, sezon, dzien, godzina, uwagi, ids}]
  utworzono timestamptz not null default now(),
  kto text
);
alter table public.depozyt_listy enable row level security;
revoke all on public.depozyt_listy from anon, authenticated;
grant select on public.depozyt_listy to authenticated;
drop policy if exists depozyt_listy_read on public.depozyt_listy;
create policy depozyt_listy_read on public.depozyt_listy for select to authenticated using (
  (select public.has_module('depozyt')) and case branch
    when 'Latex Wrocław' then (select public.has_branch('Latex Wrocław'))
    when 'Latex Opole' then (select public.has_branch('Latex Opole'))
    when 'Stangum Opole' then (select public.has_branch('Stangum Opole'))
    else false end);

create or replace function public.depozyt_zapisz_liste(p_branch text, p jsonb)
returns void language plpgsql security definer set search_path = '' as $$
declare k text;
begin
  select coalesce(nullif(u.name, ''), u.email) into k from public.me() u;
  if k is null or not public.has_module('depozyt') or not public.has_branch(p_branch) then
    raise exception 'Brak dostępu' using errcode = '42501';
  end if;
  if jsonb_typeof(p -> 'wiersze') <> 'array' or jsonb_array_length(p -> 'wiersze') > 2000 then
    raise exception 'Nieprawidłowa lista' using errcode = '22023';
  end if;
  insert into public.depozyt_listy(branch, tytul, od, "do", zrodlo, wiersze, utworzono, kto)
  values (p_branch, left(coalesce(p ->> 'tytul', ''), 200), left(coalesce(p ->> 'od', ''), 20),
          left(coalesce(p ->> 'do', ''), 20), left(coalesce(p ->> 'zrodlo', ''), 20), p -> 'wiersze', now(), k)
  on conflict (branch) do update set tytul = excluded.tytul, od = excluded.od, "do" = excluded."do",
    zrodlo = excluded.zrodlo, wiersze = excluded.wiersze, utworzono = now(), kto = k;
end $$;
revoke all on function public.depozyt_zapisz_liste(text, jsonb) from public, anon;
grant execute on function public.depozyt_zapisz_liste(text, jsonb) to authenticated;
