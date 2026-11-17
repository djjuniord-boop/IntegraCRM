-- OFERTY OPON: handlowcy z tego samego oddziału widzą i współdzielą oferty (decyzja właściciela 2026-11-17, wariant „b”):
-- podgląd, „Otwórz i odśwież” (aktualizuje ten sam wpis), status i uwagi. Oddział = przypisanie użytkowników (app_users.branches).
-- Usuwać ofertę może dalej tylko jej autor. Nic nie jest usuwane.

-- 1) Czy zalogowany może pracować z ofertą tej osoby: autor, administrator albo wspólny oddział
create or replace function public.oferty_wspolna(p_owner text)
returns boolean language sql stable security definer set search_path = '' as $$
  select coalesce(
    (select m.email = lower(p_owner) or m.role = 'admin'
            or exists (select 1 from public.app_users u where u.email = lower(p_owner) and u.branches && m.branches)
       from public.me() m where m.active), false);
$$;
revoke all on function public.oferty_wspolna(text) from public, anon;
grant execute on function public.oferty_wspolna(text) to authenticated;

-- 2) Zasady dostępu do tabeli oferty: odczyt i zmiana – wspólny oddział
drop policy if exists oferty_read on public.oferty;
create policy oferty_read on public.oferty for select to authenticated
  using ((select public.has_module('oferty')) and public.oferty_wspolna(owner));
drop policy if exists oferty_update on public.oferty;
create policy oferty_update on public.oferty for update to authenticated
  using ((select public.has_module('oferty')) and public.oferty_wspolna(owner))
  with check ((select public.has_module('oferty')) and public.oferty_wspolna(owner));

-- 3) Status oferty kolegi (stara funkcja oferty_status – tylko własne – zostaje dla starszych wersji programu)
create or replace function public.oferty_status_o(p_owner text, p_oid text, p_status text)
returns void language plpgsql security definer set search_path = '' as $$
begin
  if not public.has_module('oferty') or not public.oferty_wspolna(p_owner) then raise exception 'Brak dostępu' using errcode = '42501'; end if;
  if p_status not in ('nowa', 'wyslana', 'przyjeta', 'odrzucona', 'zamowiona') then raise exception 'Zły status' using errcode = '22023'; end if;
  update public.oferty set status = p_status, status_at = now() where owner = lower(p_owner) and oid = p_oid;
  if not found then raise exception 'Nie znaleziono oferty' using errcode = 'P0002'; end if;
end $$;
revoke all on function public.oferty_status_o(text, text, text) from public, anon;
grant execute on function public.oferty_status_o(text, text, text) to authenticated;

-- 4) Uwagi – także kolega z oddziału
create or replace function public.oferty_uwagi(p_id bigint, p_uwagi text)
returns void language plpgsql security definer set search_path = '' as $$
declare e text := lower((select auth.jwt() ->> 'email'));
begin
  if e is null or not public.has_module('oferty') then raise exception 'Brak dostępu' using errcode = '42501'; end if;
  update public.oferty set uwagi = left(coalesce(p_uwagi, ''), 1000), uwagi_at = now(), uwagi_kto = e
   where id = p_id and public.oferty_wspolna(owner);
  if not found then raise exception 'Nie znaleziono oferty (albo jest z innego oddziału)' using errcode = 'P0002'; end if;
end $$;
