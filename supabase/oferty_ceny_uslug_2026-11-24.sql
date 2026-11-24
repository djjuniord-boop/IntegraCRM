-- 2026-11-24: ceny usług (wymiana, TPMS, przechowalnia) wspólne dla Latex Wrocław – zmienia tylko administrator
-- (app_config 'oferty_ceny', zapis tylko admin). Wartości startowe skopiowane z ustawień osobistych administratora.
-- Wykonane przez kontroler (dopisanie kluczy, bez usuwania).
update public.app_config c
set value = jsonb_set(c.value, '{Latex Wrocław}', (c.value->'Latex Wrocław') || (
  select jsonb_object_agg(k, a.ustawienia->k)
  from public.oferty_konta a,
       unnest(array['wymiana_kolo','wymiana_suv','wymiana_dost','tpms_cena',
                    'przech_opony_do19','przech_opony_pow19','przech_kola_do19','przech_kola_pow19']) k
  where a.email = '<e-mail administratora>'))
where c.key = 'oferty_ceny';
