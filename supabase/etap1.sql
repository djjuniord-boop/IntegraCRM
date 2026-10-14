-- IntegraCRM – etap 1: użytkownicy, moduły, oddziały
-- Wklej w Supabase → projekt latex-serwis-qr → SQL Editor → Run

create table public.app_users (
  email text primary key,
  user_id uuid unique references auth.users(id) on delete set null,
  name text,
  role text not null default 'user' check (role in ('admin','user')),
  modules text[] not null default '{}',   -- crm, marza, serwis
  branches text[] not null default '{}',  -- Latex Wrocław, Latex Opole, Stangum Opole
  active boolean not null default true,
  last_seen timestamptz,
  app_version text,
  created_at timestamptz not null default now()
);
alter table public.app_users enable row level security;
insert into public.app_users(email, name, role, modules, branches)
values ('djjuniord@gmail.com', 'Daniel', 'admin', '{crm,marza,serwis}', '{Latex Wrocław,Latex Opole,Stangum Opole}');
insert into public.app_users(email, modules, branches)
select lower(s.email), '{serwis}', '{Latex Wrocław}' from public.staff s
where lower(s.email) <> 'djjuniord@gmail.com' on conflict do nothing;

create or replace function public.me() returns public.app_users
language sql stable security definer set search_path = '' as $$
  select u.* from public.app_users u
  where lower(u.email) = lower(auth.jwt() ->> 'email') and u.active;
$$;
create or replace function public.is_admin() returns boolean
language sql stable security definer set search_path = '' as $$
  select coalesce((select role = 'admin' from public.me()), false);
$$;
create or replace function public.has_module(m text) returns boolean
language sql stable security definer set search_path = '' as $$
  select coalesce((select role = 'admin' or m = any(modules) from public.me()), false);
$$;
create or replace function public.has_branch(b text) returns boolean
language sql stable security definer set search_path = '' as $$
  select coalesce((select role = 'admin' or b = any(branches) from public.me()), false);
$$;

create policy self_or_admin on public.app_users for select to authenticated
  using (lower(email) = lower(auth.jwt() ->> 'email') or public.is_admin());

create or replace function public.app_login(p_version text) returns public.app_users
language plpgsql security definer set search_path = '' as $$
declare r public.app_users;
begin
  update public.app_users set last_seen = now(), app_version = left(p_version, 20),
         user_id = coalesce(user_id, auth.uid())
   where lower(email) = lower(auth.jwt() ->> 'email') and active
  returning * into r;
  return r;
end $$;

create or replace function public.admin_set_user(p_email text, p_name text, p_role text,
  p_modules text[], p_branches text[], p_active boolean) returns void
language plpgsql security definer set search_path = '' as $$
begin
  if not public.is_admin() then raise exception 'Brak uprawnień administratora'; end if;
  if lower(p_email) = lower(auth.jwt() ->> 'email') and (p_role <> 'admin' or not p_active) then
    raise exception 'Nie możesz odebrać sobie uprawnień administratora';
  end if;
  insert into public.app_users(email, name, role, modules, branches, active)
  values (lower(trim(p_email)), p_name, p_role, p_modules, p_branches, p_active)
  on conflict (email) do update set name = excluded.name, role = excluded.role,
    modules = excluded.modules, branches = excluded.branches, active = excluded.active;
end $$;

alter table public.cars add column branch text not null default 'Latex Wrocław';
drop policy staff_all on public.cars;
drop policy staff_all on public.services;
drop policy staff_all on public.settings;
create policy staff_all on public.cars for all to authenticated
  using (public.has_module('serwis') and public.has_branch(branch))
  with check (public.has_module('serwis') and public.has_branch(branch));
create policy staff_all on public.services for all to authenticated
  using (exists (select 1 from public.cars c where c.id = car_id
                 and public.has_module('serwis') and public.has_branch(c.branch)))
  with check (exists (select 1 from public.cars c where c.id = car_id
                 and public.has_module('serwis') and public.has_branch(c.branch)));
create policy staff_read on public.settings for select to authenticated using (public.has_module('serwis'));
create policy admin_write on public.settings for all to authenticated using (public.is_admin()) with check (public.is_admin());

create table public.app_config (key text primary key, value jsonb not null);
alter table public.app_config enable row level security;
create policy read_all on public.app_config for select to authenticated using (true);
create policy admin_write on public.app_config for all to authenticated using (public.is_admin()) with check (public.is_admin());
insert into public.app_config values ('min_version', '"0.14.0"');

revoke all on function public.me(), public.is_admin(), public.has_module(text), public.has_branch(text),
  public.app_login(text), public.admin_set_user(text,text,text,text[],text[],boolean) from public, anon;
grant execute on function public.me(), public.is_admin(), public.has_module(text), public.has_branch(text),
  public.app_login(text), public.admin_set_user(text,text,text,text[],text[],boolean) to authenticated;

drop function public.is_staff();
drop table public.staff;
