-- Limit wysyłek e-mail z serwera (2026-11-10, audyt B-07): najwyżej 60 wiadomości na konto w ciągu 24 godzin.
-- Chroni firmowego Gmaila (limit ok. 500/dzień) przed zapętleniem albo nadużyciem. Nic nie usuwa.
create table if not exists public.mail_wysylki (
  id bigint generated always as identity primary key,
  email text not null,
  at timestamptz not null default now(),
  rodzaj text not null default ''
);
alter table public.mail_wysylki enable row level security;   -- brak zasad = brak dostępu przez API
revoke all on public.mail_wysylki from anon, authenticated;
create index if not exists mail_wysylki_email_at on public.mail_wysylki (email, at);

-- Zwraca true i zapisuje wysyłkę, gdy limit nie jest przekroczony (wywołuje funkcja send-mail tokenem użytkownika).
create or replace function public.mail_limit_ok(p_rodzaj text default '')
returns boolean language plpgsql security definer set search_path = '' as $$
declare e text := lower((select u.email from public.me() u)); n int;
begin
  if e is null then return false; end if;
  select count(*) into n from public.mail_wysylki where email = e and at > now() - interval '24 hours';
  if n >= 60 then return false; end if;
  insert into public.mail_wysylki(email, rodzaj) values (e, left(coalesce(p_rodzaj, ''), 20));
  delete from public.mail_wysylki where at < now() - interval '30 days';   -- sprzątanie starych wpisów
  return true;
end $$;
revoke all on function public.mail_limit_ok(text) from public, anon;
grant execute on function public.mail_limit_ok(text) to authenticated;
