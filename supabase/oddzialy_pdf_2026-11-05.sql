-- 2026-11-05 · Dane oddziałów na PDF oferty opon (OFERTY OPON – Panel i aplikacja Android).
-- Klucz app_config 'oddzialy': {nazwa oddziału z konta → dane do nagłówka PDF}. To publiczne dane firmy (adres, telefon).
-- Czytać może każde aktywne konto (zasada read_all), zmieniać tylko administrator (zasada admin_write) – bez zmian w zasadach.
-- PDF bierze oddział z konta pracownika (app_users.branches), więc pracownik Opola nie zrobi oferty z danymi Wrocławia.
-- Zmiana danych później: Panel → OFERTY OPON → Ustawienia → „Dane oddziałów na PDF” (administrator).
-- Bez usuwania: wstawia klucz albo – gdy już jest – nadpisuje go tymi danymi.
insert into public.app_config (key, value) values ('oddzialy', $json$
{
  "Latex Wrocław": {"nazwa": "LATEX SERWIS WROCŁAW", "adres": "ul. Krakowska 54a, 50-425 Wrocław", "tel": "71 341 30 60",
                    "www": "wroclaw.latex.net.pl", "email": "wroclaw@latexserwis.pl"},
  "Latex Opole":   {"nazwa": "LATEX SERWIS OPOLE", "adres": "ul. Krapkowicka 18A, 45-732 Opole", "tel": "77 474 80 89",
                    "www": "opole.latex.net.pl", "email": "opole@latexserwis.pl"}
}
$json$::jsonb)
on conflict (key) do update set value = excluded.value;

-- sprawdzenie
select key, jsonb_pretty(value) from public.app_config where key = 'oddzialy';
