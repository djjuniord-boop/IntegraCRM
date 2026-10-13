"""Uruchamia testy modułów (bez okna): python tests/run_tests.py [nazwa_modułu …]

Każdy plik tests/test_*.py, każda funkcja test_*. Kod wyjścia 0 = wszystkie przeszły.
"""
import importlib
import sys
import traceback
from pathlib import Path

for _s in (sys.stdout, sys.stderr):   # konsola Windows (cp1252) – polskie znaki nie mogą przerwać testów
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
want = set(sys.argv[1:])
ok = bad = 0
for f in sorted(HERE.glob("test_*.py")):
    if want and f.stem[5:] not in want:
        continue
    mod = importlib.import_module(f.stem)
    for name in sorted(n for n in dir(mod) if n.startswith("test_")):
        try:
            getattr(mod, name)()
            ok += 1
            print(f"  OK    {f.stem}.{name}")
        except Exception:
            bad += 1
            print(f"  BŁĄD  {f.stem}.{name}\n{traceback.format_exc()}")
print(f"\nTesty modułów: {ok} OK, {bad} błędów")
sys.exit(1 if bad else 0)
