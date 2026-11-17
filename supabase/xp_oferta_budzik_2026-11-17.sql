-- Kopia pliku ofertowego xPartner: budzik w bazie (decyzja właściciela 2026-11-17).
-- Harmonogram GitHub odpala automat „Oferta xPartner -> baza” nieregularnie (2–3 razy dziennie), więc baza sama
-- co 30 min (pn–sob, 6:00–20:30 czasu polskiego zimą) prosi GitHub o uruchomienie synchronizacji.
-- Klucz GitHub (fine-grained, tylko repozytorium IntegraCRM, Actions: read and write) leży w sejfie bazy (Vault),
-- nie w kodzie. Wklej go w miejsce WKLEJ_TUTAJ_KLUCZ_GITHUB. Nic nie jest usuwane.

create extension if not exists pg_cron;
create extension if not exists pg_net;

select vault.create_secret('WKLEJ_TUTAJ_KLUCZ_GITHUB', 'github_xp_oferta',
                           'Klucz GitHub: tylko uruchamianie automatu xp_oferta w IntegraCRM');

create or replace function public.xp_oferta_budzik()
returns void language plpgsql security definer set search_path = '' as $$
declare k text;
begin
  select decrypted_secret into k from vault.decrypted_secrets where name = 'github_xp_oferta';
  if k is null or k = '' then
    return;
  end if;
  perform net.http_post(
    url := 'https://api.github.com/repos/djjuniord-boop/IntegraCRM/actions/workflows/xp_oferta.yml/dispatches',
    body := jsonb_build_object('ref', 'main'),
    headers := jsonb_build_object('Authorization', 'Bearer ' || k, 'Accept', 'application/vnd.github+json',
                                  'X-GitHub-Api-Version', '2022-11-28', 'User-Agent', 'PanelLatexSerwis',
                                  'Content-Type', 'application/json'));
end $$;
revoke all on function public.xp_oferta_budzik() from public, anon, authenticated;

-- czas UTC: 7 i 37 minuta, godz. 5–19 UTC, pn–sob
select cron.schedule('xp-oferta-co-30-min', '7,37 5-19 * * 1-6', 'select public.xp_oferta_budzik()');

-- od razu jedna próba (wynik sprawdzi Claude: net._http_response, kod 204 = GitHub przyjął)
select public.xp_oferta_budzik();
