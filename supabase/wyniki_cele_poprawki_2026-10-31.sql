-- Etap: poprawki z recenzji – cele w WYNIKACH (2026-10-31)
-- 1) flag manual / target_pending nie da się zmienić z pominięciem funkcji administratora,
-- 2) zdjęcie „czeka na Excel” tylko dla kwoty, która faktycznie trafiła do Excela (wyścig ze zmianą celu),
-- 3) „zrobione” ręcznego miesiąca nie jest kasowane przy zmianie samego celu, cel musi być > 0.
-- Zawiera DROP FUNCTION (stara wersja marza_target_written bez kwoty) – do wklejenia w SQL Editor.

create or replace function public.marza_months_keep_admin()
returns trigger language plpgsql set search_path = '' as $$
begin
  if coalesce(current_setting('app.admin_edit', true), '') = '1' then
    return new;                                     -- zmiana przez funkcję administratora / MARŻY
  end if;
  if tg_op = 'INSERT' then
    new.manual := false;                            -- nowy wiersz z kalkulatora nigdy nie jest „ręczny”
    new.target_pending := false;
    return new;
  end if;
  if old.manual then
    return old;                                     -- ręczny miesiąc zmienia tylko administrator
  end if;
  new.manual := old.manual;                         -- flag nie da się przestawić bezpośrednio
  new.target_pending := old.target_pending;
  if old.target_pending then
    new.target := old.target;                       -- cel z programu wygrywa, dopóki nie trafi do Excela
  end if;
  return new;
end $$;
revoke execute on function public.marza_months_keep_admin() from public, anon, authenticated;
drop trigger if exists keep_admin on public.marza_months;
create trigger keep_admin before insert or update on public.marza_months
  for each row execute function public.marza_months_keep_admin();

create or replace function public.admin_set_month(p_branch text, p_year int, p_month int,
                                                  p_target numeric, p_done numeric default null)
returns void language plpgsql security definer set search_path = '' as $$
declare v_label text; v_exists boolean;
begin
  if not public.is_admin() then
    raise exception 'Tylko administrator może zmieniać cele' using errcode = '42501';
  end if;
  if p_branch not in ('wroclaw', 'opole') or p_month not between 1 and 12 or p_year not between 2020 and 2100 then
    raise exception 'Nieprawidłowy oddział lub miesiąc';
  end if;
  if p_target is null or p_target <= 0 or p_target > 100000000 or (p_done is not null and (p_done < 0 or p_done > 100000000)) then
    raise exception 'Nieprawidłowa kwota';
  end if;
  v_label := (array['Styczeń','Luty','Marzec','Kwiecień','Maj','Czerwiec','Lipiec','Sierpień','Wrzesień',
                    'Październik','Listopad','Grudzień'])[p_month] || ' ' || p_year;
  select true into v_exists from public.marza_months where branch = p_branch and year = p_year and month = p_month;
  perform set_config('app.admin_edit', '1', true);
  if coalesce(v_exists, false) then
    update public.marza_months
       set target = round(p_target, 2),
           target_pending = not manual,
           done = case when manual then coalesce(round(p_done, 2), done) else done end
     where branch = p_branch and year = p_year and month = p_month;
  else
    if p_done is null then
      perform set_config('app.admin_edit', '', true);
      raise exception 'Podaj kwotę „zrobione” dla nowego miesiąca';
    end if;
    insert into public.marza_months(branch, year, month, label, target, done, manual)
    values (p_branch, p_year, p_month, v_label, round(p_target, 2), round(p_done, 2), true);
  end if;
  perform set_config('app.admin_edit', '', true);
  insert into public.audit_log(email, action, entity, label, detail)
  values (lower(auth.jwt() ->> 'email'), case when coalesce(v_exists, false) then 'zmiana' else 'dodanie' end,
          'cel marży', p_branch || ' – ' || v_label, jsonb_build_object('cel', p_target, 'zrobione', p_done));
end $$;
revoke all on function public.admin_set_month(text, int, int, numeric, numeric) from public, anon;
grant execute on function public.admin_set_month(text, int, int, numeric, numeric) to authenticated;

drop function if exists public.marza_target_written(text, int, int);
create or replace function public.marza_target_written(p_branch text, p_year int, p_month int, p_target numeric)
returns boolean language plpgsql security definer set search_path = '' as $$
declare n int;
begin
  if not public.can_write_marza(p_branch) then
    raise exception 'Brak dostępu' using errcode = '42501';
  end if;
  perform set_config('app.admin_edit', '1', true);
  update public.marza_months set target_pending = false
   where branch = p_branch and year = p_year and month = p_month
     and target_pending and target = round(p_target, 2);   -- cel zmieniony w międzyczasie zostaje „czeka na Excel”
  get diagnostics n = row_count;
  perform set_config('app.admin_edit', '', true);
  return n > 0;
end $$;
revoke all on function public.marza_target_written(text, int, int, numeric) from public, anon;
grant execute on function public.marza_target_written(text, int, int, numeric) to authenticated;
