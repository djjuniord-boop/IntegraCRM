-- Etap: WYNIKI – edycja celu i dopisywanie starych miesięcy przez administratora (2026-10-31)
-- Nic nie usuwa. Do wklejenia w SQL Editor.
--
-- target_pending = cel zmieniony w programie, czeka na wpisanie do kalkulatora Excel przy najbliższej
--                  aktualizacji MARŻY (do tego czasu zapis z Excela nie nadpisuje celu).
-- manual         = miesiąc dopisany ręcznie (np. sprzed kalkulatora) – wynik wpisany przez administratora.

alter table public.marza_months add column if not exists target_pending boolean not null default false;
alter table public.marza_months add column if not exists manual boolean not null default false;

-- Zapis z kalkulatora (MARŻA) nie nadpisuje celu czekającego na Excel ani miesięcy dopisanych ręcznie.
create or replace function public.marza_months_keep_admin()
returns trigger language plpgsql set search_path = '' as $$
begin
  if tg_op = 'UPDATE' and coalesce(current_setting('app.admin_edit', true), '') <> '1' then
    if old.manual then
      return old;                                   -- ręczny miesiąc zmienia tylko administrator (RPC niżej)
    end if;
    if old.target_pending then
      new.target := old.target;                     -- cel z programu wygrywa, dopóki nie trafi do Excela
      new.target_pending := true;
    end if;
  end if;
  return new;
end $$;
revoke execute on function public.marza_months_keep_admin() from public, anon, authenticated;
drop trigger if exists keep_admin on public.marza_months;
create trigger keep_admin before update on public.marza_months
  for each row execute function public.marza_months_keep_admin();

-- Administrator: cel miesiąca (istniejącego) albo nowy ręczny miesiąc z celem i wynikiem.
create or replace function public.admin_set_month(p_branch text, p_year int, p_month int,
                                                  p_target numeric, p_done numeric default null)
returns void language plpgsql security definer set search_path = '' as $$
declare v_label text; v_exists boolean; v_manual boolean;
begin
  if not public.is_admin() then
    raise exception 'Tylko administrator może zmieniać cele' using errcode = '42501';
  end if;
  if p_branch not in ('wroclaw', 'opole') or p_month not between 1 and 12 or p_year not between 2020 and 2100 then
    raise exception 'Nieprawidłowy oddział lub miesiąc';
  end if;
  if p_target is null or p_target < 0 or p_target > 100000000 or (p_done is not null and (p_done < 0 or p_done > 100000000)) then
    raise exception 'Nieprawidłowa kwota';
  end if;
  v_label := (array['Styczeń','Luty','Marzec','Kwiecień','Maj','Czerwiec','Lipiec','Sierpień','Wrzesień',
                    'Październik','Listopad','Grudzień'])[p_month] || ' ' || p_year;
  select true, manual into v_exists, v_manual from public.marza_months
   where branch = p_branch and year = p_year and month = p_month;
  perform set_config('app.admin_edit', '1', true);
  if coalesce(v_exists, false) then
    update public.marza_months
       set target = round(p_target, 2),
           target_pending = not manual,             -- miesiąc z kalkulatora: cel trafi też do Excela
           done = case when manual then round(p_done, 2) else done end
     where branch = p_branch and year = p_year and month = p_month;
  else
    insert into public.marza_months(branch, year, month, label, target, done, manual)
    values (p_branch, p_year, p_month, v_label, round(p_target, 2), round(p_done, 2), true);
  end if;
  insert into public.audit_log(email, action, entity, label, detail)
  values (lower(auth.jwt() ->> 'email'), case when coalesce(v_exists, false) then 'zmiana' else 'dodanie' end,
          'cel marży', p_branch || ' – ' || v_label,
          jsonb_build_object('cel', p_target, 'zrobione', p_done));
end $$;
revoke all on function public.admin_set_month(text, int, int, numeric, numeric) from public, anon;
grant execute on function public.admin_set_month(text, int, int, numeric, numeric) to authenticated;

-- MARŻA po wpisaniu celu do Excela: zdejmuje znacznik „czeka na Excel”.
create or replace function public.marza_target_written(p_branch text, p_year int, p_month int)
returns void language plpgsql security definer set search_path = '' as $$
begin
  if not public.can_write_marza(p_branch) then
    raise exception 'Brak dostępu' using errcode = '42501';
  end if;
  perform set_config('app.admin_edit', '1', true);
  update public.marza_months set target_pending = false
   where branch = p_branch and year = p_year and month = p_month;
end $$;
revoke all on function public.marza_target_written(text, int, int) from public, anon;
grant execute on function public.marza_target_written(text, int, int) to authenticated;
