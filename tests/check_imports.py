"""Sprawdza, czy każdy import w kodzie programu (także wewnątrz funkcji) wskazuje istniejący moduł.

Użycie: python tests/check_imports.py   (z głównego folderu repozytorium). Kod wyjścia 0 = wszystko się znajduje.
Moduły tylko dla Windows (okno panelu WebView2) są pomijane.
"""
import ast
import importlib.util
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app"
sys.path.insert(0, str(APP))
WINDOWS_ONLY = {"webview", "clr", "winreg", "msvcrt", "pythonnet", "clr_loader",
                "generuj_podglad"}   # silniki MARŻY: moduł podstawiany przez marza/runner.py w trakcie przebiegu
bad = []
for f in sorted(APP.rglob("*.py")):
    if "__pycache__" in f.parts:
        continue
    pkg = ".".join(f.relative_to(APP).parent.parts)
    for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
        names = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:   # import względny
                base = pkg.split(".")[: len(pkg.split(".")) - node.level + 1] if pkg else []
                mod = ".".join([*base, node.module] if node.module else base)
            else:
                mod = node.module
            names = [mod] + [f"{mod}.{a.name}" for a in node.names]
        for n in names:
            if n.split(".")[0] in WINDOWS_ONLY:
                continue
            try:
                ok = importlib.util.find_spec(n) is not None
            except (ModuleNotFoundError, ValueError):
                ok = False
            if not ok and isinstance(node, ast.ImportFrom) and n != names[0]:
                continue   # „from moduł import nazwa” – nazwa to funkcja/klasa, nie moduł
            if not ok:
                bad.append(f"{f.relative_to(APP)}:{node.lineno}  {n}")
for b in bad:
    print("BRAK:", b)
print("importy OK" if not bad else f"{len(bad)} brakujących importów")
sys.exit(1 if bad else 0)
