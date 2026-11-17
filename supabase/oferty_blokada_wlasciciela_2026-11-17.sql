-- OFERTY OPON: blokada „przejęcia” oferty kolegi (przegląd bezpieczeństwa 2026-11-17).
-- Od 1.0.6 handlowcy z oddziału mogą zmieniać wspólne oferty. Bez tej blokady ktoś, kto pominie program,
-- mógłby przepisać cudzą ofertę na siebie (zmiana owner) i ją usunąć.
-- Zasada (zwykłe konta, rola authenticated):
--   * nikt nie zmienia id, owner, oid ani created_at;
--   * oferta kolegi: tylko treść (klient, dane, szukaj, updated_at) – status i uwagi wyłącznie przez funkcje
--     oferty_status_o / oferty_uwagi (one sprawdzają oddział i poprawny status).
-- Funkcje SECURITY DEFINER i serwer działają jako inna rola, więc ich ta blokada nie dotyczy. Nic nie jest usuwane.

create or replace function public.oferty_straz()
returns trigger language plpgsql set search_path = '' as $$
begin
  if current_user <> 'authenticated' then
    return new;
  end if;
  if new.id is distinct from old.id or new.owner is distinct from old.owner
     or new.oid is distinct from old.oid or new.created_at is distinct from old.created_at then
    raise exception 'Nie można zmienić autora ani numeru oferty' using errcode = '42501';
  end if;
  if old.owner <> lower(coalesce((select auth.jwt() ->> 'email'), ''))
     and (new.status is distinct from old.status or new.status_at is distinct from old.status_at
          or new.uwagi is distinct from old.uwagi or new.uwagi_at is distinct from old.uwagi_at
          or new.uwagi_kto is distinct from old.uwagi_kto) then
    raise exception 'Status i uwagi oferty kolegi zmienia się w programie' using errcode = '42501';
  end if;
  return new;
end $$;
revoke all on function public.oferty_straz() from public, anon, authenticated;

drop trigger if exists oferty_straz on public.oferty;
create trigger oferty_straz before update on public.oferty
  for each row execute function public.oferty_straz();
