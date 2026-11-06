-- 2026-11-06 · OFERTY OPON – hasła xPartner w sejfie. ETAP 2 z 2 – uruchom DOPIERO po wydaniu Panelu 0.23.9
-- (oficjalne wydanie samo wymusza aktualizację) i po aktualizacji aplikacji Android do 1.0.5. Starsze wersje po tym
-- etapie nie zobaczą hasła (pokażą błąd logowania do xPartner).
-- Przenosi istniejące jawne hasła do sejfu i czyści jawną kolumnę xp_haslo (kolumna zostaje, pusta – bez DROP).

do $$
declare r record; sid uuid;
begin
  for r in select email, xp_haslo from public.oferty_konta where xp_haslo <> '' and xp_haslo_id is null loop
    sid := vault.create_secret(r.xp_haslo, 'oferty_xp_' || lower(r.email) || '_' || gen_random_uuid(), 'Hasło API xPartner – ' || lower(r.email));
    update public.oferty_konta set xp_haslo_id = sid, xp_haslo = '' where email = r.email;
  end loop;
end $$;

-- Od teraz w jawnej kolumnie nic nie może się pojawić.
alter table public.oferty_konta drop constraint if exists oferty_konta_bez_jawnego_hasla;
alter table public.oferty_konta add constraint oferty_konta_bez_jawnego_hasla check (xp_haslo = '');

-- sprawdzenie: jawnych haseł 0, w sejfie tyle, ile kont z hasłem
select count(*) filter (where xp_haslo <> '') as jawne, count(*) filter (where xp_haslo_id is not null) as w_sejfie from public.oferty_konta;
