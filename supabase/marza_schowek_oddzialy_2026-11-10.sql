-- Schowek „marza” (kopie wyników) – dostęp tylko do folderu własnego oddziału (2026-11-10, audyt B-09).
-- Dotąd: każdy z modułem MARŻA widział i zapisywał pliki obu oddziałów (dziś moduł ma tylko administrator,
-- więc nic się nie zmienia w praktyce – to zabezpieczenie na przyszłość). Pliki leżą w folderach wroclaw/, opole/.
-- Zawiera DROP POLICY (podmiana zasad) – do wklejenia w SQL Editor przez właściciela. Danych nie usuwa.
drop policy if exists marza_files_read on storage.objects;
drop policy if exists marza_files_write on storage.objects;
create policy marza_files_read on storage.objects for select to authenticated
  using (bucket_id = 'marza' and (select public.can_write_marza(split_part(name, '/', 1))));
create policy marza_files_write on storage.objects for insert to authenticated
  with check (bucket_id = 'marza' and (select public.can_write_marza(split_part(name, '/', 1))));
-- Uwaga: rejestr „zgłaszany już” (tabela reported) jest celowo wspólny dla wszystkich oddziałów (README KONTROLI).
