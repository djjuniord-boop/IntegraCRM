-- Test uprawnień: marza_months, marza_results, can_see_marza (2026-10-14, wersja 0.20.0 – zakładka WYNIKI).
-- NIC NIE ZOSTAJE W BAZIE: blok kończy się celowym błędem „WYNIK TESTU …”, więc Postgres cofa wszystko
-- (konta testowe t-…@test.pl, wiersze testowe z rokiem 2099 / user_email 'test-seed', wpisy audit_log).
-- Każdy zapis w pętli jest dodatkowo cofany od razu (sqlstate U0001), więc kolejne konta widzą te same dane.
-- Uruchamiać jako postgres (SQL Editor / execute_sql). Wynik czyta się z treści błędu.
--
-- Dane testowe: marza_months 2 wiersze Wrocław + 2 Opole (rok 2099),
--               marza_results 3 wiersze Wrocław + 2 Opole (user_email 'test-seed').
-- Kolumny: widzi = can_see_marza('wroclaw')/('opole'); miesiące, wyniki = ile wierszy widzi (Wrocław/Opole);
--   upsert = POST jak program (json_to_recordset + ON CONFLICT DO UPDATE wszystkich wysłanych kolumn, jak
--   PostgREST przy Prefer: resolution=merge-duplicates): 1 istniejący wiersz Wrocławia + 1 nowy Opola;
--   PATCH = update wszystkich testowych miesięcy; zapis wyników = insert do marza_results.
--
-- Oczekiwany wynik (sprawdzone 2026-10-14):
--   admin, pracownik MARŻA  → widzi T/T, miesiące 2/2, wyniki 3/2, upsert TAK (2), PATCH 4, zapis wyników TAK
--   handlowiec Wrocław      → T/n, 2/0, 3/0, upsert odmowa (RLS), PATCH 0, zapis wyników odmowa (RLS)
--   handlowiec Opole        → n/T, 0/2, 0/2, odmowa, 0, odmowa
--   Stangum, zablokowany, konto crm, obce konto Auth → n/n, 0/0, 0/0, odmowa, 0, odmowa
--   anon → can_see_marza, marza_months (odczyt, upsert, PATCH): brak prawa (brak GRANT);
--          marza_results 0/0, zapis wyników odmowa (RLS)
--   updated_by po upsercie = zapisujący (podrobiony updated_by i stary updated_at z klienta odrzucone).
do $$
declare
  out text := '';
  notes text := '';
  personas text[][] := array[
    ['admin',                   't-admin@test.pl'],
    ['handlowiec Wroclaw',      't-hwroc@test.pl'],
    ['handlowiec Opole',        't-hopole@test.pl'],
    ['pracownik MARZA',         't-marza@test.pl'],
    ['Stangum (wyniki)',        't-stangum@test.pl'],
    ['zablokowany handl. Wroc', 't-blok@test.pl'],
    ['konto crm (bez wyniki)',  't-crm@test.pl'],
    ['obce konto Auth',         'obcy@example.com'],
    ['anon',                    '']];
  -- jak program: wiele wierszy naraz, z updated_at od klienta; tu dodatkowo podrobiony updated_by
  -- i drugi wiersz BEZ klucza holidays (PostgREST wstawi null → wyzwalacz zamienia na {})
  payload json := '[
    {"branch":"wroclaw","year":2099,"month":10,"label":"Październik 2099","target":150000.5,"done":99000,
     "holidays":["2099-10-12"],"updated_at":"2000-01-01T00:00:00Z","updated_by":"podrobiony@example.com"},
    {"branch":"opole","year":2099,"month":11,"label":"Listopad 2099","target":80000,"done":0,
     "updated_at":"2000-01-01T00:00:00Z"}]';
  i int; e text; n int; nw int; nop int;
  r_see text; r_mon text; r_res text; r_ups text; r_patch text; r_rins text;
  ub text; ua timestamptz; tg numeric; hol date[]; hol2 date[];
  chain text;
begin
  -- dane testowe (jako postgres, bez tokenu → updated_by = 'system')
  perform set_config('request.jwt.claims', '', true);
  insert into public.app_users(email, name, role, modules, branches, active) values
    ('t-admin@test.pl',   'Test admin',       'admin', '{}',       '{}',              true),
    ('t-hwroc@test.pl',   'Test handl. Wroc', 'user',  '{wyniki}', '{Latex Wrocław}', true),
    ('t-hopole@test.pl',  'Test handl. Opole','user',  '{wyniki}', '{Latex Opole}',   true),
    ('t-marza@test.pl',   'Test MARZA',       'user',  '{marza}',  '{Latex Wrocław}', true),
    ('t-stangum@test.pl', 'Test Stangum',     'user',  '{wyniki}', '{Stangum Opole}', true),
    ('t-blok@test.pl',    'Test blok',        'user',  '{wyniki}', '{Latex Wrocław}', false),
    ('t-crm@test.pl',     'Test crm',         'user',  '{crm}',    '{Latex Wrocław}', true);
  insert into public.marza_months(branch, year, month, label, target, done) values
    ('wroclaw', 2099,  9, 'Wrzesień 2099',    100000, 90000),
    ('wroclaw', 2099, 10, 'Październik 2099', 120000, 50000),
    ('opole',   2099,  9, 'Wrzesień 2099',     70000, 60000),
    ('opole',   2099, 10, 'Październik 2099',  75000, 30000);
  insert into public.marza_results(branch, user_email, month_label) values
    ('wroclaw', 'test-seed', 'TEST'), ('wroclaw', 'test-seed', 'TEST'), ('wroclaw', 'test-seed', 'TEST'),
    ('opole',   'test-seed', 'TEST'), ('opole',   'test-seed', 'TEST');

  out := E'\nprawa tabeli marza_months: authenticated DELETE='
      || has_table_privilege('authenticated', 'public.marza_months', 'DELETE')
      || ', anon SELECT=' || has_table_privilege('anon', 'public.marza_months', 'SELECT')
      || ', anon EXECUTE can_see_marza='
      || has_function_privilege('anon', 'public.can_see_marza(text)', 'EXECUTE') || E'\n\n'
      || E'konto                   | widzi W/O  | miesiace W/O | wyniki W/O | upsert miesiecy  | PATCH      | zapis wynikow\n';

  for i in 1 .. array_length(personas, 1) loop
    reset role;
    e := personas[i][2];
    if e = '' then
      execute 'set local role anon';
      perform set_config('request.jwt.claims', '{"role":"anon"}', true);
    else
      execute 'set local role authenticated';
      perform set_config('request.jwt.claims',
        json_build_object('email', e, 'role', 'authenticated')::text, true);
    end if;

    -- przez execute: PL/pgSQL sprawdza prawo EXECUTE do „prostego wyrażenia” tylko raz na transakcję
    -- (dla pierwszego konta), więc bez execute anon dostałby wynik zamiast „brak prawa”
    begin
      execute $q$select case when public.can_see_marza('wroclaw') then 'T' else 'n' end || '/'
                     || case when public.can_see_marza('opole')   then 'T' else 'n' end$q$ into r_see;
    exception when insufficient_privilege then r_see := 'brak prawa';
    end;

    begin
      select count(*) filter (where branch = 'wroclaw'), count(*) filter (where branch = 'opole')
        into nw, nop from public.marza_months where year = 2099;
      r_mon := nw || '/' || nop;
    exception when insufficient_privilege then r_mon := 'brak prawa';
    end;

    begin
      select count(*) filter (where branch = 'wroclaw'), count(*) filter (where branch = 'opole')
        into nw, nop from public.marza_results where user_email = 'test-seed';
      r_res := nw || '/' || nop;
    exception when insufficient_privilege then r_res := 'brak prawa';
    end;

    -- upsert jak PostgREST (merge-duplicates): ON CONFLICT DO UPDATE SET wszystkie wysłane kolumny
    begin
      insert into public.marza_months(branch, year, month, label, target, done, holidays, updated_at, updated_by)
      select * from json_to_recordset(payload)
        as x(branch text, year int, month int, label text, target numeric, done numeric,
             holidays date[], updated_at timestamptz, updated_by text)
      on conflict (branch, year, month) do update set
        branch = excluded.branch, year = excluded.year, month = excluded.month, label = excluded.label,
        target = excluded.target, done = excluded.done, holidays = excluded.holidays,
        updated_at = excluded.updated_at, updated_by = excluded.updated_by;
      get diagnostics n = row_count;
      select updated_by, updated_at, target, holidays into ub, ua, tg, hol
        from public.marza_months where branch = 'wroclaw' and year = 2099 and month = 10;
      select holidays into hol2 from public.marza_months where branch = 'opole' and year = 2099 and month = 11;
      r_ups := 'TAK (' || n || ')';
      notes := notes || '  ' || rpad(personas[i][1], 22) || ': istniejacy wiersz -> updated_by=' || ub
            || ', updated_at=' || case when ua = now() then 'czas serwera' else 'CZAS KLIENTA!' end
            || ', cel=' || tg || ', swieta=' || hol::text || '; nowy wiersz bez holidays -> ' || hol2::text || E'\n';
      raise sqlstate 'U0001';   -- cofnij zapis, następne konto widzi te same dane
    exception
      when sqlstate 'U0001' then null;
      when insufficient_privilege then
        r_ups := case when sqlerrm like '%row-level security%' then 'odmowa (RLS)' else 'brak prawa' end;
      when others then r_ups := 'BLAD ' || sqlstate;
    end;

    begin
      update public.marza_months set done = done + 1 where year = 2099;
      get diagnostics n = row_count;
      r_patch := n::text;
      raise sqlstate 'U0001';
    exception
      when sqlstate 'U0001' then null;
      when insufficient_privilege then r_patch := 'brak prawa';
      when others then r_patch := 'BLAD ' || sqlstate;
    end;

    begin
      insert into public.marza_results(branch, month_label) values ('wroclaw', 'TEST-zapis');
      r_rins := 'TAK';
      raise sqlstate 'U0001';
    exception
      when sqlstate 'U0001' then null;
      when insufficient_privilege then
        r_rins := case when sqlerrm like '%row-level security%' then 'odmowa (RLS)' else 'brak prawa' end;
      when others then r_rins := 'BLAD ' || sqlstate;
    end;

    out := out || rpad(personas[i][1], 24) || '| ' || rpad(r_see, 11) || '| ' || rpad(r_mon, 13) || '| '
               || rpad(r_res, 11) || '| ' || rpad(r_ups, 17) || '| ' || rpad(r_patch, 11) || '| ' || r_rins || E'\n';
  end loop;

  -- Upsert na istniejącym wierszu bez updated_by/updated_at w treści (jak może wysyłać program):
  -- kolejno pracownik MARŻA, potem admin – updated_by przechodzi na zapisującego.
  reset role;
  select 'system(seed)=' || updated_by into chain
    from public.marza_months where branch = 'wroclaw' and year = 2099 and month = 9;
  for i in 1 .. 2 loop
    e := case i when 1 then 't-marza@test.pl' else 't-admin@test.pl' end;
    execute 'set local role authenticated';
    perform set_config('request.jwt.claims', json_build_object('email', e, 'role', 'authenticated')::text, true);
    insert into public.marza_months(branch, year, month, label, target, done, holidays)
    select * from json_to_recordset(json_build_array(json_build_object(
        'branch', 'wroclaw', 'year', 2099, 'month', 9, 'label', 'Wrzesień 2099',
        'target', 100000 + i * 1000, 'done', 90000, 'holidays', array['2099-09-01'])))
      as x(branch text, year int, month int, label text, target numeric, done numeric, holidays date[])
    on conflict (branch, year, month) do update set
      branch = excluded.branch, year = excluded.year, month = excluded.month, label = excluded.label,
      target = excluded.target, done = excluded.done, holidays = excluded.holidays;
    reset role;
    select chain || ' -> po zapisie ' || e || ': updated_by=' || updated_by || ', cel=' || target
      into chain from public.marza_months where branch = 'wroclaw' and year = 2099 and month = 9;
  end loop;

  reset role;
  raise exception 'WYNIK TESTU (wszystko cofniete):%', out
    || E'\nszczegoly udanych upsertow:\n' || notes
    || E'\nupsert na istniejacym wierszu (wroclaw 09.2099), bez updated_by w tresci:\n  ' || chain || E'\n';
end $$;
