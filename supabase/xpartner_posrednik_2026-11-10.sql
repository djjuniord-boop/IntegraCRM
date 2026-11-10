-- Etap: pośrednik xPartner (2026-11-10, audyt B-01). Nic nie usuwa.
-- Funkcja Edge „xpartner” czyta login i hasło B2B tylko po stronie serwera (klucz service_role).
-- Program przestaje pobierać hasło (oferty_moje_haslo) – odebranie tej funkcji: plik *_etap2.
create or replace function public.xpartner_dane(p_email text)
returns table(login text, haslo text)
language sql stable security definer set search_path = '' as $$
  select k.xp_login,
         coalesce((select d.decrypted_secret from vault.decrypted_secrets d where d.id = k.xp_haslo_id),
                  nullif(k.xp_haslo, ''), '')
    from public.oferty_konta k
   where lower(k.email) = lower(trim(p_email));
$$;
revoke all on function public.xpartner_dane(text) from public, anon, authenticated;
grant execute on function public.xpartner_dane(text) to service_role;
