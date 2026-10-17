-- Etap: ręczne wylogowanie użytkownika przez administratora (2026-10-17)
-- Usuwa sesje (i tokeny odświeżania) wskazanego konta w Supabase Auth – program przy najbliższym
-- odświeżeniu logowania (najpóźniej po 30 min, a przy starcie od razu) prosi o hasło. Konto zostaje.
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
