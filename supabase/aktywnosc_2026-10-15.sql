-- Etap: ostatnia aktywność programu (2026-10-15)
-- Program co 30 minut woła app_ping – zapis do osobnej tabeli (bez wpisów w Dzienniku zmian co 30 min).
-- Czyta tylko administrator. Nic nie usuwa.

create table if not exists public.app_activity (
  email       text primary key,
  last_active timestamptz not null default now(),
  app_version text
);
alter table public.app_activity enable row level security;
revoke all on public.app_activity from anon, authenticated;   -- także TRUNCATE (omija RLS)
grant select on public.app_activity to authenticated;            -- zapis tylko przez app_ping

drop policy if exists activity_admin_read on public.app_activity;
create policy activity_admin_read on public.app_activity for select to authenticated
  using ((select public.is_admin()));

create or replace function public.app_ping(p_version text)
returns void language plpgsql security definer set search_path to '' as $$
declare v_email text := lower(auth.jwt() ->> 'email');
begin
  if (select u.email from public.me() u) is null then return; end if;   -- tylko aktywne konta programu
  insert into public.app_activity(email, last_active, app_version)
  values (v_email, now(), left(p_version, 20))
  on conflict (email) do update set last_active = now(), app_version = excluded.app_version;
end $$;
revoke all on function public.app_ping(text) from public, anon;
grant execute on function public.app_ping(text) to authenticated;

-- Utwardzenie (z recenzji 0.21.5): domyślne prawa Supabase dają rolom anon i authenticated TRUNCATE, REFERENCES
-- i TRIGGER na tabelach. Przez API (PostgREST) nie da się ich użyć, ale nie są potrzebne – odbieramy je wszędzie.
revoke truncate, references, trigger on all tables in schema public from anon, authenticated;
alter default privileges in schema public revoke truncate, references, trigger on tables from anon, authenticated;
