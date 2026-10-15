-- Etap: poprawki z audytu bezpieczeństwa R1 (2026-10-15) – SEC-004, SEC-005, SEC-006
-- Do wklejenia w SQL Editor (zawiera DROP POLICY – zastąpienie starych zasad nowymi).

-- SEC-004: MARŻA – zapis celów i wyników tylko dla oddziału, do którego konto ma dostęp
create or replace function public.can_write_marza(b text)
returns boolean language sql stable security definer set search_path to '' as $$
  select public.has_module('marza')
     and public.has_branch(case b when 'wroclaw' then 'Latex Wrocław' when 'opole' then 'Latex Opole' end);
$$;
revoke all on function public.can_write_marza(text) from public, anon;
grant execute on function public.can_write_marza(text) to authenticated;

drop policy if exists marza_insert on public.marza_months;
drop policy if exists marza_update on public.marza_months;
create policy marza_insert on public.marza_months for insert to authenticated
  with check ((select public.can_write_marza(branch)));
create policy marza_update on public.marza_months for update to authenticated
  using ((select public.can_write_marza(branch))) with check ((select public.can_write_marza(branch)));

drop policy if exists marza_insert on public.marza_results;
create policy marza_insert on public.marza_results for insert to authenticated
  with check ((select public.can_write_marza(branch))
              and user_email = lower((select auth.jwt()) ->> 'email'));

-- SEC-005: HISTORIA – autor może dopisać tylko informację o wysłanym e-mailu, nie zmienia wyniku sprawdzenia
create or replace function public.checks_guard()
returns trigger language plpgsql security definer set search_path to '' as $$
begin
  if public.is_admin() then return new; end if;
  if (new.id, new.created_at, new.user_email, new.branches, new.pdf_name, new.n_integra, new.n_crm,
      new.missing, new.uncertain, new.imported)
     is distinct from
     (old.id, old.created_at, old.user_email, old.branches, old.pdf_name, old.n_integra, old.n_crm,
      old.missing, old.uncertain, old.imported) then
    raise exception 'Sprawdzenia nie można zmienić – można tylko zapisać wysłanie e-maila' using errcode = '42501';
  end if;
  return new;
end $$;
drop trigger if exists checks_guard on public.checks;
create trigger checks_guard before update on public.checks for each row execute function public.checks_guard();

-- SEC-006: statystyki zapisuje wyłącznie funkcja save_visit_stats (z limitami); bez zapisu bezpośredniego
drop policy if exists stats_insert on public.visit_stats;
drop policy if exists stats_update on public.visit_stats;
