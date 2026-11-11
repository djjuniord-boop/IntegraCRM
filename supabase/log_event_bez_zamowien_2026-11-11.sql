-- Dziennik: wpis „zamówienie” robi już tylko serwer (funkcja xpartner) – pracownik nie może go dopisać sam
-- (2026-11-11, audyt B-06). Wkleić PO wdrożeniu nowej wersji funkcji xpartner. Nic nie usuwa.
create or replace function public.log_event(p_action text, p_entity text, p_label text, p_detail jsonb)
returns void language plpgsql security definer set search_path = '' as $$
begin
  if public.me() is null then return; end if;
  if p_action not in ('błąd', 'start', 'import') then raise exception 'Niedozwolone zdarzenie'; end if;
  insert into public.audit_log(email, action, entity, label, detail)
  values (lower(auth.jwt() ->> 'email'), p_action, left(p_entity, 60), left(p_label, 200),
          case when pg_column_size(p_detail) < 4000 then p_detail else null end);
end $$;
