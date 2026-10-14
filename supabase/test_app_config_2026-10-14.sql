-- Test uprawnień do app_config (2026-10-14). NIC NIE ZOSTAJE W BAZIE:
-- blok kończy się celowym błędem „WYNIK TESTU …”, więc Postgres cofa wszystko (konta testowe, zmiany zasad).
-- Wynik czyta się z treści tego błędu (tabela: konto | min_version | crm | send-mail crm | send-mail marza | zapis).
-- Konta testowe (t-…@test.pl, obcy@example.com) powstają na chwilę w auth.users i app_users – też cofane.
-- Uruchamiać jako postgres (SQL Editor / execute_sql).
--
-- Oczekiwany wynik dla stanu „obecny” (= wariant C, sprawdzone 2026-10-14):
--   admin, pracownik Opole/Wrocław, pracownik bez imienia, konto bez modułu → min_version 1, crm 1
--   konto zablokowane, obce konto Auth, anon                              → min_version 0, crm 0
--   send-mail crm: TAK dla kont z modułem crm; marza: TAK dla kont z modułem marza; zapis: tylko admin.
-- Wariant B daje „pracownik bez imienia → 0 / NIE (pusta lista!)” – dlatego nie został wdrożony.
--
-- Sprawdza trzy warianty zasady read_all (każdy w tej samej transakcji, potem cofnięty):
--   A  using (true)                                   – stan przed poprawką
--   B  using ((select public.me()) is not null)       – propozycja z recenzji
--   C  using ((select u.email from public.me() u) is not null) – wariant wdrożony
-- oraz stan „obecny” (to, co jest w bazie w chwili uruchomienia).
--
-- send-mail (supabase/functions/send-mail) działa tokenem użytkownika: rpc me → has_module → select app_config.
-- Kolumny „send-mail …” = czy funkcja przepuści konto I zobaczy listę odbiorców (recipients / marza).
do $$
declare
  out text := '';
  variants text[] := array['obecny', 'A|true', 'B|(select public.me()) is not null',
                           'C|(select u.email from public.me() u) is not null'];
  personas text[][] := array[
    ['admin',                 't-admin@test.pl'],
    ['pracownik Opole',       't-opole@test.pl'],
    ['pracownik Wroclaw',     't-wroc@test.pl'],
    ['pracownik bez imienia', 't-noname@test.pl'],
    ['konto bez modulu',      't-bezmod@test.pl'],
    ['konto zablokowane',     't-blok@test.pl'],
    ['obce konto Auth',       'obcy@example.com'],
    ['anon',                  '']];
  v text; expr text; i int;
  n_min int; n_crm int; me_ok boolean; crm_ok boolean; mz_ok boolean; recip boolean; mzl boolean; n_upd int;
  r_crm text; r_mz text; r_wr text; uid uuid;
begin
  -- konta Auth (jak po założeniu przez admin-users); obcy@example.com jest w Auth, ale nie w app_users
  insert into auth.users(id, email, aud, role)
  select gen_random_uuid(), e, 'authenticated', 'authenticated'
    from unnest(array['t-admin@test.pl', 't-opole@test.pl', 't-wroc@test.pl', 't-noname@test.pl',
                      't-bezmod@test.pl', 't-blok@test.pl', 'obcy@example.com']) e;
  insert into public.app_users(email, name, role, modules, branches, active) values
    ('t-admin@test.pl',  'Test admin',      'admin', '{}',          '{}',              true),
    ('t-opole@test.pl',  'Test Opole',      'user',  '{crm,marza}', '{Latex Opole}',   true),
    ('t-wroc@test.pl',   'Test Wroclaw',    'user',  '{crm}',       '{Latex Wrocław}', true),
    ('t-noname@test.pl', null,              'user',  '{crm,marza}', '{Latex Opole}',   true),
    ('t-bezmod@test.pl', 'Test bez modulu', 'user',  '{}',          '{Latex Opole}',   true),
    ('t-blok@test.pl',   'Test blok',       'user',  '{crm,marza}', '{Latex Opole}',   false);

  foreach v in array variants loop
    reset role;
    if v <> 'obecny' then
      expr := split_part(v, '|', 2);
      execute format('alter policy read_all on public.app_config using (%s)', expr);
      v := split_part(v, '|', 1);
    end if;
    select qual into expr from pg_policies
     where schemaname = 'public' and tablename = 'app_config' and policyname = 'read_all';
    out := out || E'\n== wariant ' || v || ': using (' || expr || E')\n'
               || E'konto                 | min_version | crm | send-mail crm       | send-mail marza     | zapis\n';

    for i in 1 .. array_length(personas, 1) loop
      reset role;
      select id into uid from auth.users where email = personas[i][2];
      if personas[i][2] = '' then
        execute 'set local role anon';
        perform set_config('request.jwt.claims', '{"role":"anon"}', true);
      else
        execute 'set local role authenticated';
        perform set_config('request.jwt.claims',
          json_build_object('email', personas[i][2], 'role', 'authenticated',
                            'sub', uid)::text, true);
        -- jak program: najpierw app_login (uzupełnia user_id, last_seen, app_version), potem min_version
        perform public.app_login('0.19.0');
      end if;

      begin
        select count(*) into n_min from public.app_config where key = 'min_version';
        select count(*) into n_crm from public.app_config where key = 'crm';
        select coalesce(bool_or(value ? 'recipients' or value ? 'by_branch'), false),
               coalesce(bool_or(value ? 'marza'), false)
          into recip, mzl from public.app_config where key = 'crm';
      exception when insufficient_privilege then
        n_min := -1; n_crm := -1; recip := false; mzl := false;
      end;

      begin
        select (select u.email from public.me() u) is not null into me_ok;
        crm_ok := public.has_module('crm');
        mz_ok := public.has_module('marza');
      exception when insufficient_privilege then
        me_ok := false; crm_ok := false; mz_ok := false;
      end;
      r_crm := case when not me_ok then 'odmowa 401' when not crm_ok then 'odmowa 403'
                    when recip then 'TAK' else 'NIE (pusta lista!)' end;
      r_mz  := case when not me_ok then 'odmowa 401' when not mz_ok then 'odmowa 403'
                    when mzl then 'TAK' else 'NIE (pusta lista!)' end;

      begin
        update public.app_config set value = value where key = 'min_version';
        get diagnostics n_upd = row_count;
        r_wr := case when n_upd > 0 then 'TAK' else 'nie' end;
      exception when insufficient_privilege then
        r_wr := 'nie (brak prawa)';
      end;

      out := out || rpad(personas[i][1], 22) || '| '
                 || rpad(case n_min when -1 then 'brak prawa' else n_min::text end, 12) || '| '
                 || rpad(case n_crm when -1 then '-' else n_crm::text end, 4) || '| '
                 || rpad(r_crm, 19) || '| ' || rpad(r_mz, 19) || '| ' || r_wr || E'\n';
    end loop;
  end loop;

  reset role;
  raise exception 'WYNIK TESTU (wszystko cofniete):%', out;
end $$;
