-- 2026-11-27: indeksy kopii pliku xPartner – felgi i czujniki (filtr po Asortyment) oraz szukanie po kodzie / EAN.
-- Powód: „canceling statement due to statement timeout” przy szukaniu felg (pełne przeszukanie ok. 32 tys. wierszy jsonb).
-- Po zmianie: strona 1000 felg ok. 7 ms zamiast ~4 s. Zastosowane w bazie (migracje xp_oferta_indeks_*_2026_11_27).
create index if not exists xp_oferta_asortyment on public.xp_oferta ((dane->'attrs'->>'Asortyment'), id);
create index if not exists xp_oferta_kod on public.xp_oferta ((dane->>'kod'));
create index if not exists xp_oferta_ean on public.xp_oferta ((dane->>'ean'));
analyze public.xp_oferta;
