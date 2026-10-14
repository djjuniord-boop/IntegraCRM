-- Test uprawnień: visit_stats, checks (crm/historia) – 2026-10-14, wersja 0.21.0.
-- NIC NIE ZOSTAJE: blok kończy się celowym błędem „WYNIK TESTU …” (wszystko cofnięte).
-- Dane: visit_stats 2099-01-01..02: Wrocław 2 wiersze, Opole 1, Stangum 1; checks 'test-seed' Wrocław 2, Opole 1.
-- Kolumny: stats W/O/S – ile wierszy visit_stats widzi; rpc W / rpc O – save_visit_stats dnia 2099-01-01
-- (istniejący wiersz) dla Wrocławia / Opola; upsert W – bezpośredni upsert jak PostgREST (merge-duplicates);
-- checks W/O – ile sprawdzeń widzi.
do $$
declare
  out text := ''; notes text := '';
  personas text[][] := array[
    ['admin',                    't-admin@test.pl'],
    ['handl. statystyki Wroc',   't-stat@test.pl'],
    ['crm Wroc (bez statyst.)',  't-crm@test.pl'],
    ['historia Wroc (bez crm)',  't-hist@test.pl'],
    ['zablokowany (wszystko)',   't-blok@test.pl'],
    ['obce konto Auth',          'obcy@example.com'],
    ['anon',                     '']];
  i int; e text; n int; a int; b int; c int;
  r_st text; r_rw text; r_ro text; r_uw text; r_uo text; r_ch text;
begin
  perform set_config('request.jwt.claims', '', true);
  insert into public.app_users(email, name, role, modules, branches, active) values
    ('t-admin@test.pl','T admin','admin','{}','{}',true),
    ('t-stat@test.pl','T stat','user','{statystyki}','{Latex Wrocław}',true),
    ('t-crm@test.pl','T crm','user','{crm}','{Latex Wrocław}',true),
    ('t-hist@test.pl','T hist','user','{historia}','{Latex Wrocław}',true),
    ('t-blok@test.pl','T blok','user','{crm,historia,statystyki}','{Latex Wrocław,Latex Opole,Stangum Opole}',false);
  insert into public.visit_stats(branch, day, visits, lists, missing) values
    ('Latex Wrocław','2099-01-01',10,8,2), ('Latex Wrocław','2099-01-02',5,5,0),
    ('Latex Opole','2099-01-01',7,6,1), ('Stangum Opole','2099-01-01',3,3,0);
  insert into public.checks(user_email, branches, pdf_name) values
    ('test-seed','{Latex Wrocław}','T'), ('test-seed','{Latex Wrocław}','T'), ('test-seed','{Latex Opole}','T');

  out := E'\nprawa: authenticated DELETE=' || has_table_privilege('authenticated','public.visit_stats','DELETE')
      || ', anon SELECT=' || has_table_privilege('anon','public.visit_stats','SELECT') || E'\n\n'
      || E'konto                    | stats W/O/S | rpc W            | rpc O            | upsert W         | checks W/O\n';

  for i in 1 .. array_length(personas, 1) loop
    reset role; e := personas[i][2];
    if e = '' then execute 'set local role anon';
      perform set_config('request.jwt.claims','{"role":"anon"}',true);
    else execute 'set local role authenticated';
      perform set_config('request.jwt.claims', json_build_object('email',e,'role','authenticated')::text, true);
    end if;

    begin
      select count(*) filter (where branch='Latex Wrocław'), count(*) filter (where branch='Latex Opole'),
             count(*) filter (where branch='Stangum Opole') into a,b,c from public.visit_stats where day >= '2099-01-01';
      r_st := a||'/'||b||'/'||c;
    exception when insufficient_privilege then r_st := 'brak prawa'; end;

    begin
      execute $q$select public.save_visit_stats('Latex Wrocław','2099-01-01',20,15,5,null)$q$;
      r_rw := 'TAK'; raise sqlstate 'U0001';
    exception when sqlstate 'U0001' then null;
      when insufficient_privilege then r_rw := case when sqlerrm like 'Brak%' then 'odmowa' else 'brak prawa' end;
      when others then r_rw := 'BLAD '||sqlstate; end;

    begin
      execute $q$select public.save_visit_stats('Latex Opole','2099-01-01',1,1,0,null)$q$;
      r_ro := 'TAK'; raise sqlstate 'U0001';
    exception when sqlstate 'U0001' then null;
      when insufficient_privilege then r_ro := case when sqlerrm like 'Brak%' then 'odmowa' else 'brak prawa' end;
      when others then r_ro := 'BLAD '||sqlstate; end;

    begin
      insert into public.visit_stats(branch, day, visits, lists, missing, updated_by)
      select * from json_to_recordset('[{"branch":"Latex Wrocław","day":"2099-01-01","visits":20,"lists":15,"missing":5,"updated_by":"podrobiony"}]')
        as x(branch text, day date, visits int, lists int, missing int, updated_by text)
      on conflict (branch, day) do update set visits=excluded.visits, lists=excluded.lists,
        missing=excluded.missing, updated_by=excluded.updated_by;
      get diagnostics n = row_count; r_uw := 'TAK ('||n||')';
      raise sqlstate 'U0001';
    exception when sqlstate 'U0001' then null;
      when insufficient_privilege then r_uw := case when sqlerrm like '%row-level%' then 'odmowa (RLS)' else 'brak prawa' end;
      when others then r_uw := 'BLAD '||sqlstate; end;

    begin
      select count(*) filter (where 'Latex Wrocław' = any(branches)), count(*) filter (where 'Latex Opole' = any(branches))
        into a,b from public.checks where user_email='test-seed';
      r_ch := a||'/'||b;
    exception when insufficient_privilege then r_ch := 'brak prawa'; end;

    out := out || rpad(personas[i][1],25) || '| ' || rpad(r_st,12) || '| ' || rpad(r_rw,17) || '| '
               || rpad(r_ro,17) || '| ' || rpad(r_uw,17) || '| ' || r_ch || E'\n';
  end loop;

  -- dwa zapisy RPC tego samego (branch, day) przez konto crm → 1 wiersz z nowymi liczbami
  reset role; execute 'set local role authenticated';
  perform set_config('request.jwt.claims','{"email":"t-crm@test.pl","role":"authenticated"}',true);
  for i in 1..2 loop
    perform public.save_visit_stats('Latex Wrocław','2099-02-01',100*i,90*i,10*i,null);
  end loop;
  reset role;
  select notes || 'podwojny upsert 2099-02-01: wierszy=' || count(*) || ', ' || string_agg(visits||'/'||lists||'/'||missing||' by '||updated_by, ',')
    into notes from public.visit_stats where branch='Latex Wrocław' and day='2099-02-01';
  select notes || E'\nkonta z crm bez historia po migracji: ' || count(*) into notes
    from public.app_users where 'crm' = any(modules) and not 'historia' = any(modules);
  raise exception 'WYNIK TESTU (wszystko cofniete):%', out || E'\n' || notes;
end $$;
