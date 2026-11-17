-- HISTORIA OFERT: usunięcie duplikatów powstałych przez „Otwórz i odśwież” (przed wersją 1.0.4).
-- Duplikat = ta sama osoba, ten sam klient, te same pojazdy/rozmiary i te same wybrane opony.
-- Z każdej grupy zostaje JEDNA oferta: najpierw ze statusem innym niż „Nowa”, potem z uwagami, potem najnowsza.
-- Wymaga zgody właściciela. Najpierw podgląd (SELECT), potem usunięcie (DELETE).

-- 1) PODGLĄD – ile zostanie usuniętych
with g as (select id, owner, status, uwagi, updated_at,
                  md5(owner || coalesce(klient,'') || coalesce((dane->'pojazdy')::text,'') || coalesce((dane->'wybor')::text,'')) k
             from public.oferty),
     r as (select id, row_number() over (partition by k order by (status is not null and status <> 'nowa') desc,
                                                          (uwagi <> '') desc, updated_at desc) rn
             from g)
select count(*) as do_usuniecia from r where rn > 1;

-- 2) USUNIĘCIE
with g as (select id, owner, status, uwagi, updated_at,
                  md5(owner || coalesce(klient,'') || coalesce((dane->'pojazdy')::text,'') || coalesce((dane->'wybor')::text,'')) k
             from public.oferty),
     r as (select id, row_number() over (partition by k order by (status is not null and status <> 'nowa') desc,
                                                          (uwagi <> '') desc, updated_at desc) rn
             from g)
delete from public.oferty where id in (select id from r where rn > 1);
