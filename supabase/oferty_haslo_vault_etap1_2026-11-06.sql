-- 2026-11-06 · OFERTY OPON – hasła xPartner w zaszyfrowanym sejfie (Supabase Vault). ETAP 1 z 2.
-- Etap 1 tylko DODAJE (kolumna, funkcje, wyzwalacz) – nic nie przenosi ani nie usuwa, stare wersje Panelu działają dalej.
-- Po nim: wydanie Panelu 0.23.9 / aplikacji 1.0.5 (czytają hasło przez oferty_moje_haslo()), potem ETAP 2 (przeniesienie haseł).
--
-- Co daje: hasło nie leży jawnie w tabeli (podgląd tabeli, kopie zapasowe, eksport, błąd w zasadach dostępu nie pokażą go);
-- odszyfrować może tylko funkcja oferty_moje_haslo() i tylko dla zalogowanego właściciela konta – administrator wpisuje
-- hasła pracowników, ale już ich nie odczyta. Czego NIE daje: pracownik nadal zna swoje hasło (program musi go użyć).

alter table public.oferty_konta add column if not exists xp_haslo_id uuid;

-- Własne hasło xPartner (sejf; dopóki etap 2 nie przeniesie – stara kolumna). Tylko konto z modułem „oferty”.
create or replace function public.oferty_moje_haslo()
returns text language plpgsql stable security definer set search_path = '' as $$
declare e text := lower((select u.email from public.me() u)); r record;
begin
  if e is null or not public.has_module('oferty') then raise exception 'Brak dostępu' using errcode = '42501'; end if;
  select k.xp_haslo, k.xp_haslo_id into r from public.oferty_konta k where lower(k.email) = e;
  if not found then return ''; end if;
  if r.xp_haslo_id is not null then
    return coalesce((select d.decrypted_secret from vault.decrypted_secrets d where d.id = r.xp_haslo_id), '');
  end if;
  return coalesce(r.xp_haslo, '');
end $$;

-- Administrator: login i hasło pracownika. Puste hasło = bez zmiany. Nowe hasło trafia od razu do sejfu.
create or replace function public.oferty_admin_set_konto(p_email text, p_login text, p_haslo text)
returns void language plpgsql security definer set search_path = '' as $$
declare e text := lower(trim(p_email)); sid uuid;
begin
  if not public.is_admin() then raise exception 'Tylko administrator' using errcode = '42501'; end if;
  insert into public.oferty_konta(email, xp_login, updated_by)
  values (e, coalesce(trim(p_login), ''), (select u.email from public.me() u))
  on conflict (email) do update set xp_login = excluded.xp_login, updated_at = now(), updated_by = excluded.updated_by;
  if coalesce(p_haslo, '') <> '' then
    select k.xp_haslo_id into sid from public.oferty_konta k where k.email = e;
    if sid is not null and exists (select 1 from vault.secrets s where s.id = sid) then
      perform vault.update_secret(sid, p_haslo);
    else
      sid := vault.create_secret(p_haslo, 'oferty_xp_' || e || '_' || gen_random_uuid(), 'Hasło API xPartner – ' || e);
    end if;
    update public.oferty_konta set xp_haslo_id = sid, xp_haslo = '' where email = e;
  end if;
end $$;

-- Czy konto ma zapisane hasło (dla okna UŻYTKOWNICY) – bez ujawniania hasła.
create or replace function public.oferty_ma_haslo(p_email text)
returns boolean language sql stable security definer set search_path = '' as $$
  select public.is_admin() and exists (select 1 from public.oferty_konta k
    where lower(k.email) = lower(trim(p_email)) and (k.xp_haslo_id is not null or k.xp_haslo <> ''));
$$;

-- Usunięcie konta ofert (np. usunięcie pracownika) usuwa też jego hasło z sejfu.
create or replace function public.oferty_konta_usun_haslo()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
  if old.xp_haslo_id is not null then delete from vault.secrets s where s.id = old.xp_haslo_id; end if;
  return old;
end $$;
drop trigger if exists oferty_konta_usun_haslo on public.oferty_konta;
create trigger oferty_konta_usun_haslo after delete on public.oferty_konta for each row execute function public.oferty_konta_usun_haslo();

revoke all on function public.oferty_moje_haslo(), public.oferty_ma_haslo(text), public.oferty_konta_usun_haslo() from public, anon;
revoke all on function public.oferty_admin_set_konto(text,text,text) from public, anon;
grant execute on function public.oferty_moje_haslo(), public.oferty_ma_haslo(text), public.oferty_admin_set_konto(text,text,text) to authenticated;

-- sprawdzenie
select proname from pg_proc where proname in ('oferty_moje_haslo','oferty_admin_set_konto','oferty_ma_haslo','oferty_konta_usun_haslo') order by 1;
