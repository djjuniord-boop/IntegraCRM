-- 2026-11-06 · OFERTY OPON – kopia pliku ofertowego xPartner (wyszukiwanie bez obciążania API xPartner).
-- Tabelę wypełnia automat (GitHub Actions, tools/xp_oferta_sync.py) co 30 min w godzinach pracy kluczem serwisowym.
-- Konta z modułem „oferty” (i administrator) mogą ją tylko CZYTAĆ – zapis/usuwanie wyłącznie przez automat.
-- Stan synchronizacji: app_config klucz 'xp_oferta_stan' {czas, ile, zmienione, usuniete} – programy po nim poznają,
-- czy kopia jest świeża (starsza niż 3 h → wyszukiwanie wraca do API xPartner).
-- Ceny w tabeli pochodzą z konta, które wygenerowało link – oferta i tak odświeża ceny przez API z konta pracownika.

create table if not exists public.xp_oferta (
  id integer primary key,                 -- indeks xPartner (= productId w API)
  szer integer,
  profil numeric,
  sred numeric,
  ilosc integer not null default 0,
  h text not null default '',             -- skrót zawartości (automat wysyła tylko zmiany)
  dane jsonb not null,                    -- produkt w kształcie jak z API (silnik.parse_products)
  updated_at timestamptz not null default now()
);
create index if not exists xp_oferta_rozmiar on public.xp_oferta (szer, profil, sred);

alter table public.xp_oferta enable row level security;
revoke all on public.xp_oferta from anon, authenticated;
grant select on public.xp_oferta to authenticated;
drop policy if exists xp_oferta_read on public.xp_oferta;
create policy xp_oferta_read on public.xp_oferta for select to authenticated
  using ((select public.has_module('oferty')) or (select public.is_admin()));

-- sprawdzenie
select relname, relrowsecurity from pg_class where relname = 'xp_oferta';
