"""Plik podglądowy dla handlowców – oddział Wrocław. Kod wspólny: _podglad_wspolny.py (zmieniaj tam)."""
import os as _os

PODGLAD_KALKULATOR = "kalkulator_marzy_Wroclaw.xlsx"
PODGLAD_PLIK = "PODGLAD_dla_handlowcow_Wroclaw.xlsx"
PODGLAD_CSV = "PODGLAD_dla_handlowcow_dane.csv"   # inna nazwa dla każdego oddziału – oba narzędzia piszą na ten sam Dysk Google
PODGLAD_NAGLOWEK = "Opony · Felgi · Serwis"
PODGLAD_STOPKA = "LATEX — Opony, Felgi, Serwis"

_KOD = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "_podglad_wspolny.py")
with open(_KOD, encoding="utf-8") as _f:
    exec(compile(_f.read(), _KOD, "exec"))
