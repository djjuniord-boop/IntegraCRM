-- Etap: ręczne wylogowanie użytkownika przez administratora (2026-10-17)
-- Usuwa sesje (i tokeny odświeżania) wskazanego konta w Supabase Auth – program przy najbliższym
-- sprawdzeniu sesji (co 20 s, funkcja session_ok niżej) zamyka się i prosi o hasło. Konto zostaje.
-- Do wklejenia w SQL Editor (zawiera DELETE na sesjach).
create or replace function public.admin_logout_user(p_email text)
returns integer language plpgsql security definer set search_path to '' as $$
declare v_id uuid; v_n integer;
begin
  if not public.is_admin() then
    raise exception 'Tylko administrator może wylogować użytkownika' using errcode = '42501';
  end if;
  select id into v_id from auth.users where lower(email) = lower(trim(p_email));
  if v_id is null then raise exception 'Nie ma takiego konta'; end if;
  delete from auth.sessions where user_id = v_id;   -- tokeny odświeżania usuwają się kaskadowo
  get diagnostics v_n = row_count;
  insert into public.audit_log(email, action, entity, label, detail)
  values (lower(auth.jwt() ->> 'email'), 'wylogowanie', 'użytkownik', lower(trim(p_email)), jsonb_build_object('sesje', v_n));
  return v_n;
end $$;
revoke all on function public.admin_logout_user(text) from public, anon;
grant execute on function public.admin_logout_user(text) to authenticated;

-- Czy sesja, z której pochodzi token, nadal istnieje (program sprawdza co 20 sekund – wylogowanie działa od razu).
create or replace function public.session_ok()
returns boolean language sql stable security definer set search_path to '' as $$
  -- brak identyfikatora sesji w tokenie → null (program wtedy nikogo nie wylogowuje)
  select case when coalesce(auth.jwt() ->> 'session_id', '') = '' then null
              else exists (select 1 from auth.sessions s where s.id = (auth.jwt() ->> 'session_id')::uuid) end;
$$;
revoke all on function public.session_ok() from public, anon;
grant execute on function public.session_ok() to authenticated;
