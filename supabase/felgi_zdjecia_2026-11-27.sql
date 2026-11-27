-- 2026-11-27 (1.2.29): zdjęcia felg w bazie – pracownicy nie logują się do xPartner (decyzja właściciela 2026-11-27).
-- Administrator (zalogowany w xPartner w programie) pobiera zdjęcia i zapisuje pomniejszone kopie JPEG w schowku
-- „felgi-foto” (<indeks>_<n>.jpg) oraz wiersz w xp_felgi_foto (ile zdjęć, kiedy sprawdzono; 0 = xPartner nie ma zdjęcia).
-- Czyta każdy z modułem „felgi”, zapisuje tylko administrator (RLS).
create table if not exists public.xp_felgi_foto (
  id         bigint primary key,
  pliki      smallint not null default 0 check (pliki between 0 and 3),
  sprawdzono timestamptz not null default now()
);
alter table public.xp_felgi_foto enable row level security;
drop policy if exists xp_felgi_foto_czyt on public.xp_felgi_foto;
create policy xp_felgi_foto_czyt on public.xp_felgi_foto for select to authenticated using ((select public.has_module('felgi')));
drop policy if exists xp_felgi_foto_admin on public.xp_felgi_foto;
create policy xp_felgi_foto_admin on public.xp_felgi_foto for all to authenticated
  using ((select public.is_admin())) with check ((select public.is_admin()));
grant select, insert, update on public.xp_felgi_foto to authenticated;

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('felgi-foto', 'felgi-foto', false, 400000, array['image/jpeg'])
on conflict (id) do update set public = false, file_size_limit = 400000, allowed_mime_types = array['image/jpeg'];

drop policy if exists felgi_foto_czyt on storage.objects;
create policy felgi_foto_czyt on storage.objects for select to authenticated
  using (bucket_id = 'felgi-foto' and (select public.has_module('felgi')));
drop policy if exists felgi_foto_dodaj on storage.objects;
create policy felgi_foto_dodaj on storage.objects for insert to authenticated
  with check (bucket_id = 'felgi-foto' and (select public.is_admin()));
drop policy if exists felgi_foto_zmien on storage.objects;
create policy felgi_foto_zmien on storage.objects for update to authenticated
  using (bucket_id = 'felgi-foto' and (select public.is_admin())) with check (bucket_id = 'felgi-foto' and (select public.is_admin()));
