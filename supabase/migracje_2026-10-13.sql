-- Migracje bazy z 13.10.2026 w kolejności wykonania (zapis z supabase_migrations.schema_migrations).
-- etap1 (użytkownicy, moduły, oddziały) – osobno w etap1.sql (wklejony ręcznie w SQL Editor).
-- Adresy e-mail pracowników zastąpione opisem [adres …] – repozytorium jest publiczne.

-- ===== 20261013113217 serwis_qr_schema =====
create table public.cars (
  id uuid primary key default gen_random_uuid(),
  token text not null unique check (length(token) >= 10),
  plate text not null,
  model text, year text, vin text, owner text, phone text,
  created_at timestamptz not null default now()
);
create index cars_plate_idx on public.cars (upper(regexp_replace(plate,'[^A-Za-z0-9]','','g')));

create table public.services (
  id uuid primary key default gen_random_uuid(),
  car_id uuid not null references public.cars(id) on delete cascade,
  date date not null,
  km integer,
  oil text, qty text,
  filters text[] not null default '{}',
  next_km integer, next_date date,
  notes text, type text, work text,
  photos text[] not null default '{}',
  created_at timestamptz not null default now()
);
create index services_car_idx on public.services(car_id);

create table public.settings (
  id integer primary key check (id = 1),
  data jsonb not null default '{}'::jsonb
);
insert into public.settings(id) values (1);

alter table public.cars enable row level security;
alter table public.services enable row level security;
alter table public.settings enable row level security;
-- (zasady staff_all z tego etapu zastąpione w etap1.sql zasadami wg modułu i oddziału)
create policy public_read on public.settings for select to anon using (true);

create or replace function public.get_car(p_token text)
returns jsonb language sql stable security definer set search_path = '' as $$
  select jsonb_build_object(
    'plate', c.plate, 'model', c.model, 'year', c.year, 'token', c.token,
    'services', coalesce((select jsonb_agg(jsonb_build_object(
        'id', s.id, 'date', s.date, 'km', s.km, 'oil', s.oil, 'qty', s.qty, 'filters', s.filters,
        'next_km', s.next_km, 'next_date', s.next_date, 'notes', s.notes, 'type', s.type,
        'work', s.work, 'photos', s.photos) order by s.date desc)
      from public.services s where s.car_id = c.id), '[]'::jsonb))
  from public.cars c where c.token = p_token and length(p_token) >= 10;
$$;
revoke all on function public.get_car(text) from public;
grant execute on function public.get_car(text) to anon, authenticated;

-- ===== 20261013125121 etap2_history_reported =====
create table public.checks (
  id bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  user_email text not null default lower(auth.jwt() ->> 'email'),
  branches text[] not null default '{}',
  pdf_name text,
  n_integra int, n_crm int,
  missing text[] not null default '{}',
  uncertain text[] not null default '{}',
  mail_to text,
  mail_at timestamptz
);
create index checks_created_idx on public.checks(created_at desc);
alter table public.checks enable row level security;
create policy crm_read on public.checks for select to authenticated
  using (public.has_module('crm') and (public.is_admin() or user_email = lower(auth.jwt() ->> 'email')
         or exists (select 1 from unnest(branches) b where public.has_branch(b))));
create policy crm_insert on public.checks for insert to authenticated
  with check (public.has_module('crm') and user_email = lower(auth.jwt() ->> 'email'));
create policy crm_update_own on public.checks for update to authenticated
  using (public.has_module('crm') and user_email = lower(auth.jwt() ->> 'email'))
  with check (user_email = lower(auth.jwt() ->> 'email'));

create table public.reported (
  plate text primary key,
  first_at timestamptz not null default now(),
  last_at timestamptz not null default now(),
  times int not null default 1,
  by_email text,
  branch text
);
alter table public.reported enable row level security;
create policy crm_read on public.reported for select to authenticated using (public.has_module('crm'));

create or replace function public.report_plates(p_plates text[], p_branch text) returns void
language plpgsql security definer set search_path = '' as $$
begin
  if not public.has_module('crm') then raise exception 'Brak dostępu do modułu Kontrola CRM'; end if;
  insert into public.reported(plate, by_email, branch)
  select distinct upper(regexp_replace(p, '[^A-Za-z0-9]', '', 'g')), lower(auth.jwt() ->> 'email'), p_branch
  from unnest(p_plates) p where length(p) between 2 and 12
  on conflict (plate) do update set last_at = now(), times = public.reported.times + 1,
    first_at = case when public.reported.last_at < now() - interval '60 days' then now() else public.reported.first_at end;
end $$;
revoke all on function public.report_plates(text[], text) from public, anon;
grant execute on function public.report_plates(text[], text) to authenticated;

insert into public.app_config values ('crm', '{"recipients": ["[adres skrzynki serwisu Wrocław]"], "sender_name": "Kontrola eksportu – Latex Serwis"}')
on conflict (key) do nothing;

-- ===== 20261013131145 etap3_audit_log =====
create table public.audit_log (
  id bigint generated always as identity primary key,
  at timestamptz not null default now(),
  email text,
  action text not null,      -- dodanie / zmiana / usunięcie / mail / logowanie / uprawnienia
  entity text not null,      -- auto, wpis serwisowy, sprawdzenie, użytkownik, ustawienia
  label text,                -- np. numer rejestracyjny, e-mail użytkownika
  detail jsonb
);
create index audit_at_idx on public.audit_log(at desc);
alter table public.audit_log enable row level security;
create policy admin_read on public.audit_log for select to authenticated using (public.is_admin());
-- funkcja audit_trg: aktualna treść niżej (20261013153832)
create trigger audit after insert or update or delete on public.cars for each row execute function public.audit_trg();
create trigger audit after insert or update or delete on public.services for each row execute function public.audit_trg();
create trigger audit after insert or update on public.checks for each row execute function public.audit_trg();
create trigger audit after insert or update or delete on public.app_users for each row execute function public.audit_trg();
create trigger audit after insert or update on public.app_config for each row execute function public.audit_trg();
create trigger audit after insert or update on public.settings for each row execute function public.audit_trg();
revoke all on function public.audit_trg() from public, anon, authenticated;

-- ===== 20261013152233 etap4_log_event_import =====
create or replace function public.log_event(p_action text, p_entity text, p_label text, p_detail jsonb)
returns void language plpgsql security definer set search_path = '' as $$
begin
  if public.me() is null then return; end if;
  if p_action not in ('błąd', 'start', 'import') then raise exception 'Niedozwolone zdarzenie'; end if;
  insert into public.audit_log(email, action, entity, label, detail)
  values (lower(auth.jwt() ->> 'email'), p_action, left(p_entity, 60), left(p_label, 200),
          case when pg_column_size(p_detail) < 4000 then p_detail else null end);
end $$;
revoke all on function public.log_event(text,text,text,jsonb) from public, anon;
grant execute on function public.log_event(text,text,text,jsonb) to authenticated;
alter table public.checks add column imported boolean not null default false;
-- (tu powstała też zbędna funkcja audit_trg_skip_import – do usunięcia: porzadki_0.19.sql)

-- ===== 20261013153832 audit_trg_fix_marza (aktualna treść wyzwalacza dziennika) =====
create or replace function public.audit_trg() returns trigger
language plpgsql security definer set search_path = '' as $$
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
      det := jsonb_build_object('wersja', new.app_version);
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
end $$;

-- ===== 20261013153851 etap5_marza_online =====
create table public.marza_results (
  id bigint generated always as identity primary key,
  run_at timestamptz not null default now(),
  user_email text not null default lower(auth.jwt() ->> 'email'),
  branch text not null check (branch in ('wroclaw','opole')),
  month_label text,
  period_from date, period_to date,
  margin numeric(14,2),
  target numeric(14,2),
  done numeric(14,2),
  source_pdf text,
  files_path text
);
create index marza_results_idx on public.marza_results(branch, run_at desc);
alter table public.marza_results enable row level security;
create policy marza_read on public.marza_results for select to authenticated using (public.has_module('marza'));
create policy marza_insert on public.marza_results for insert to authenticated
  with check (public.has_module('marza') and user_email = lower(auth.jwt() ->> 'email'));
create trigger audit after insert on public.marza_results for each row execute function public.audit_trg();

insert into storage.buckets (id, name, public, file_size_limit)
values ('marza', 'marza', false, 26214400) on conflict (id) do nothing;
create policy marza_files_read on storage.objects for select to authenticated
  using (bucket_id = 'marza' and public.has_module('marza'));
create policy marza_files_write on storage.objects for insert to authenticated
  with check (bucket_id = 'marza' and public.has_module('marza'));
-- + jednorazowe przeniesienie dotychczasowych odbiorców maili MARŻY z kodu do app_config['crm'].marza
--   (adresy pominięte w tym pliku; dziś ustawia je administrator w programie: MARŻA → „Odbiorcy maili”)

-- ===== 20261013163942 perf_rls_initplan (0.19) =====
alter policy self_or_admin on public.app_users
  using (lower(email) = lower((select auth.jwt()) ->> 'email') or (select public.is_admin()));
alter policy crm_read on public.checks
  using ((select public.has_module('crm')) and ((select public.is_admin())
         or user_email = lower((select auth.jwt()) ->> 'email')
         or exists (select 1 from unnest(branches) b where public.has_branch(b))));
alter policy crm_insert on public.checks
  with check ((select public.has_module('crm')) and user_email = lower((select auth.jwt()) ->> 'email'));
alter policy crm_update_own on public.checks
  using ((select public.has_module('crm')) and user_email = lower((select auth.jwt()) ->> 'email'))
  with check (user_email = lower((select auth.jwt()) ->> 'email'));
alter policy marza_insert on public.marza_results
  with check ((select public.has_module('marza')) and user_email = lower((select auth.jwt()) ->> 'email'));
