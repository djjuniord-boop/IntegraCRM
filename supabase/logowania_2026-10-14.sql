-- Etap: skąd zalogował się użytkownik (komputer + IP) – 2026-10-14
-- Nowa wersja app_login(p_version, p_device) obok starej (stare programy wołają app_login(p_version) i działają dalej).
-- IP: pierwszy adres z nagłówka x-forwarded-for (informacyjnie – kto pisze własne zapytania, może go podać),
-- nazwę komputera podaje program. Wpis „logowanie” w Dzienniku zmian robi istniejący wyzwalacz audit_trg –
-- dopisujemy do niego komputer i IP (bez drugiego wpisu).

alter table public.app_users add column if not exists last_device text, add column if not exists last_ip text;

create or replace function public.app_login(p_version text, p_device text)
returns public.app_users language plpgsql security definer set search_path to '' as $$
declare r public.app_users; v_ip text;
begin
  v_ip := split_part(coalesce((current_setting('request.headers', true))::json ->> 'x-forwarded-for', ''), ',', 1);
  update public.app_users set last_seen = now(), app_version = left(p_version, 20),
         last_device = left(nullif(trim(p_device), ''), 80), last_ip = left(nullif(trim(v_ip), ''), 45),
         user_id = coalesce(user_id, auth.uid())
   where lower(email) = lower(auth.jwt() ->> 'email') and active
  returning * into r;
  return r;
end $$;

revoke all on function public.app_login(text, text) from public, anon;
grant execute on function public.app_login(text, text) to authenticated;

-- Dziennik zmian: przy logowaniu także komputer i IP (reszta funkcji bez zmian)
create or replace function public.audit_trg()
returns trigger language plpgsql security definer set search_path to '' as $function$
declare
  who text := lower(coalesce(auth.jwt() ->> 'email', 'system'));
  act text := case tg_op when 'INSERT' then 'dodanie' when 'UPDATE' then 'zmiana' else 'usunięcie' end;
  rec jsonb := to_jsonb(coalesce(new, old));
  ent text; lbl text; det jsonb;
begin
  if tg_table_name = 'checks' and tg_op = 'INSERT' then
    if coalesce((rec ->> 'imported')::boolean, false) then return null; end if;
  end if;
  if tg_table_name = 'cars' then
    ent := 'auto'; lbl := rec ->> 'plate';
    det := jsonb_build_object('oddział', rec ->> 'branch', 'model', rec ->> 'model');
  elsif tg_table_name = 'services' then
    ent := 'wpis serwisowy';
    select c.plate into lbl from public.cars c where c.id = (rec ->> 'car_id')::uuid;
    det := jsonb_build_object('data', rec ->> 'date', 'km', rec ->> 'km', 'rodzaj', rec ->> 'type',
                              'zdjęcia', jsonb_array_length(coalesce(rec -> 'photos', '[]'::jsonb)));
  elsif tg_table_name = 'checks' then
    ent := 'sprawdzenie'; lbl := rec ->> 'pdf_name';
    if tg_op = 'UPDATE' and (rec ->> 'mail_to') is distinct from (to_jsonb(old) ->> 'mail_to') then
      act := 'mail'; det := jsonb_build_object('do', rec ->> 'mail_to', 'braki', rec -> 'missing');
    else
      det := jsonb_build_object('oddziały', rec -> 'branches', 'integra', rec -> 'n_integra',
                                'crm', rec -> 'n_crm', 'braki', rec -> 'missing');
    end if;
  elsif tg_table_name = 'app_users' then
    if tg_op = 'UPDATE' and new.last_seen is distinct from old.last_seen
       and (new.role, new.modules, new.branches, new.active, new.name)
           is not distinct from (old.role, old.modules, old.branches, old.active, old.name) then
      act := 'logowanie'; ent := 'użytkownik'; lbl := new.email;
      det := jsonb_build_object('wersja', new.app_version, 'komputer', rec ->> 'last_device', 'ip', rec ->> 'last_ip');
    else
      ent := 'użytkownik'; lbl := rec ->> 'email'; if tg_op = 'UPDATE' then act := 'uprawnienia'; end if;
      det := jsonb_build_object('rola', rec ->> 'role', 'moduły', rec -> 'modules',
                                'oddziały', rec -> 'branches', 'aktywne', rec -> 'active');
    end if;
  elsif tg_table_name = 'marza_results' then
    act := 'aktualizacja'; ent := 'MARŻA'; lbl := (rec ->> 'branch') || ' – ' || coalesce(rec ->> 'month_label', '');
    det := jsonb_build_object('marża', rec -> 'margin', 'cel', rec -> 'target', 'zrobione', rec -> 'done',
                              'raport', rec ->> 'source_pdf');
  elsif tg_table_name in ('app_config', 'settings') then
    ent := 'ustawienia'; lbl := coalesce(rec ->> 'key', 'naklejki SERWIS QR');
  end if;
  insert into public.audit_log(email, action, entity, label, detail) values (who, act, ent, lbl, det);
  return null;
end $function$;
