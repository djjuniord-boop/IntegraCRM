-- 2026-11-27 (1.2.25): uprawnienia ofert cz. 2 – po recenzji.
-- 1) Moduły „ceny” (własne ceny i rabaty w ofercie) i „dobor” (dobór po aucie – płatne API): kto ma „oferty”, dostaje oba
--    (bez zmiany tego, co dziś może); administrator odznacza w UŻYTKOWNICY.
-- 2) Najwyższy rabat osoby (app_users.rabat_max, puste = jak w Ustawieniach ofert) – ustawia administrator.
-- 3) Licznik wheel-size: wołany przez funkcję serwera kluczem service_role z e-mailem użytkownika – pracownik nie może
--    sam „wyczerpać” limitu przez REST; wymaga modułu „dobor”.
update public.app_users
   set modules = modules || array(select x from unnest(array['ceny', 'dobor']) x where not x = any(modules))
 where 'oferty' = any(modules);

alter table public.app_users add column if not exists rabat_max numeric
  check (rabat_max is null or (rabat_max >= 0 and rabat_max <= 100));

create or replace function public.admin_set_rabat_max(p_email text, p_rabat numeric)
returns void language plpgsql security definer set search_path = '' as $$
begin
  if not public.is_admin() then raise exception 'Brak uprawnień administratora' using errcode = '42501'; end if;
  if p_rabat is not null and (p_rabat < 0 or p_rabat > 100) then raise exception 'Rabat: od 0 do 100'; end if;
  update public.app_users set rabat_max = p_rabat where lower(email) = lower(trim(p_email));
end $$;
revoke all on function public.admin_set_rabat_max(text, numeric) from public, anon;
grant execute on function public.admin_set_rabat_max(text, numeric) to authenticated;

-- stara wersja bez parametru: tylko odebrane prawo wywołania (usunięcie funkcji = osobny plik do zatwierdzenia przez właściciela)
revoke all on function public.ws_licznik_dodaj() from public, anon, authenticated;
create or replace function public.ws_licznik_dodaj(p_email text)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare
  e text := lower(trim(p_email));
  d date := (now() at time zone 'utc')::date;
  lim integer := coalesce((select (value->>'limit')::integer from public.app_config where key = 'wheel_size'), 300);
  suma integer;
begin
  if not exists (select 1 from public.app_users u where lower(u.email) = e and u.active
                 and (u.role = 'admin' or 'dobor' = any(u.modules))) then
    raise exception 'Brak dostępu' using errcode = '42501';
  end if;
  perform pg_advisory_xact_lock(hashtext('ws_licznik'));
  select coalesce(sum(n), 0) into suma from public.ws_licznik where dzien = d;
  if suma >= lim then
    return jsonb_build_object('ok', false, 'suma', suma, 'limit', lim);
  end if;
  insert into public.ws_licznik(dzien, email, n) values (d, e, 1)
  on conflict (dzien, email) do update set n = public.ws_licznik.n + 1;
  return jsonb_build_object('ok', true, 'suma', suma + 1, 'limit', lim);
end $$;
revoke all on function public.ws_licznik_dodaj(text) from public, anon, authenticated;
grant execute on function public.ws_licznik_dodaj(text) to service_role;
