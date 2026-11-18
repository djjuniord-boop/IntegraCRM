-- Zamówienia xPartner: kto zamówił przez Panel (decyzja właściciela 2026-11-18).
-- Zwraca TYLKO numer zamówienia, e-mail i imię i nazwisko osoby – z Dziennika zmian (wpis „zamówienie” robi serwer).
-- Widoczność jak przy wspólnych ofertach: osoby z Twojego oddziału (administrator – wszyscy). Wymaga modułu „zamowienia”.
-- Nic nie jest usuwane.

create or replace function public.zamowienia_kto(p_nry text[])
returns table(nr text, email text, kto text)
language sql stable security definer set search_path = '' as $$
  select distinct on (n.nr) n.nr, lower(a.email), coalesce(nullif(u.name, ''), lower(a.email))
    from public.audit_log a
    cross join lateral jsonb_array_elements_text(coalesce(a.detail -> 'numery', '[]'::jsonb)) as n(nr)
    left join public.app_users u on u.email = lower(a.email)
   where a.action = 'zamówienie'
     and n.nr = any(p_nry[1:2000])
     and (select public.has_module('zamowienia'))
     and public.oferty_wspolna(a.email)
   order by n.nr, a.at desc;
$$;
revoke all on function public.zamowienia_kto(text[]) from public, anon;
grant execute on function public.zamowienia_kto(text[]) to authenticated;
