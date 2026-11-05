-- 0.23.1 – OFERTY OPON: administrator widzi historię ofert wszystkich (tylko odczyt cudzych)
drop policy if exists oferty_own on public.oferty;
create policy oferty_read on public.oferty for select to authenticated
  using ((owner = lower((select auth.jwt() ->> 'email')) and (select public.has_module('oferty'))) or (select public.is_admin()));
create policy oferty_insert on public.oferty for insert to authenticated
  with check (owner = lower((select auth.jwt() ->> 'email')) and (select public.has_module('oferty')));
create policy oferty_update on public.oferty for update to authenticated
  using (owner = lower((select auth.jwt() ->> 'email')) and (select public.has_module('oferty')))
  with check (owner = lower((select auth.jwt() ->> 'email')) and (select public.has_module('oferty')));
create policy oferty_delete on public.oferty for delete to authenticated
  using (owner = lower((select auth.jwt() ->> 'email')) and (select public.has_module('oferty')));
