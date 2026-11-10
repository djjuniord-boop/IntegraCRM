-- Etap 2 pośrednika xPartner (2026-11-10): hasło B2B przestaje być dostępne dla programu na komputerze.
-- WKLEIĆ DOPIERO, gdy wszyscy mają Panel 0.26.0 lub nowszy (minimalna wersja podnosi się sama przy wydaniu).
-- Skutek uboczny: aplikacja na telefon (zawieszona) przestanie wczytywać oferty – używa tej funkcji.
-- Nic nie usuwa (funkcja zostaje w bazie, tylko bez prawa wywołania przez użytkowników).
revoke execute on function public.oferty_moje_haslo() from public, anon, authenticated;
-- Po wklejeniu: zmień hasła obu kont API w xPartner i wpisz nowe w Panelu (UŻYTKOWNICY → konto → xPartner).
