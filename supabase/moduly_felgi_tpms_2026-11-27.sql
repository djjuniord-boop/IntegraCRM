-- 2026-11-27 (1.2.25): nowe moduły kont „felgi” (Oferty – felgi + dobór po aucie) i „tpms” (Oferty – czujniki TPMS).
-- Każdy, kto ma dziś „oferty”, dostaje oba (bez zmiany tego, co widzi); administrator może je odznaczyć w UŻYTKOWNICY.
update public.app_users
   set modules = modules || array(select x from unnest(array['felgi', 'tpms']) x where not x = any(modules))
 where 'oferty' = any(modules);
