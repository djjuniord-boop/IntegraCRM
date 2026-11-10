"""Plik podglądowy dla handlowców – oddział Opole. Kod wspólny: _podglad_wspolny.py (zmieniaj tam)."""
import os as _os

PODGLAD_KALKULATOR = "kalkulator_marzy_Opole.xlsx"
PODGLAD_PLIK = "PODGLAD_dla_handlowcow_Opole.xlsx"
PODGLAD_CSV = "PODGLAD_dla_handlowcow_dane_Opole.csv"   # inna nazwa dla każdego oddziału – oba narzędzia piszą na ten sam Dysk Google
PODGLAD_NAGLOWEK = "Serwis Opole"
PODGLAD_STOPKA = "LATEX — Serwis Opole"

_KOD = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "_podglad_wspolny.py")
with open(_KOD, encoding="utf-8") as _f:
    exec(compile(_f.read(), _KOD, "exec"))
