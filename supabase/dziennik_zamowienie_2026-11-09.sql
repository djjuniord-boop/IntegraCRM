-- Dziennik: zdarzenie „zamówienie” (koszyk xPartner w Panelu). Wklej w SQL Editor.
CREATE OR REPLACE FUNCTION public.log_event(p_action text, p_entity text, p_label text, p_detail jsonb)
 RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path TO ''
AS $function$
begin
  if public.me() is null then return; end if;
  if p_action not in ('błąd', 'start', 'import', 'zamówienie') then raise exception 'Niedozwolone zdarzenie'; end if;
  insert into public.audit_log(email, action, entity, label, detail)
  values (lower(auth.jwt() ->> 'email'), p_action, left(p_entity, 60), left(p_label, 200),
          case when pg_column_size(p_detail) < 4000 then p_detail else null end);
end $function$;
