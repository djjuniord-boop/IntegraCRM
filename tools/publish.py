"""Narzędzie autora: buduje paczkę aktualizacji (release/) z folderu app/.

Użycie:  python tools/publish.py
Wynik:   release/version.json + release/integra-<wersja>.zip  → wgraj oba pliki do źródła aktualizacji.
"""
import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
import version  # noqa: E402

OUT = ROOT / "release"
OUT.mkdir(exist_ok=True)
pkg_name = f"integra-{version.VERSION}.zip"
pkg = OUT / pkg_name

with zipfile.ZipFile(pkg, "w", zipfile.ZIP_DEFLATED) as z:
    for f in sorted((ROOT / "app").rglob("*")):
        if f.is_file() and "__pycache__" not in f.parts:
            z.write(f, Path("app") / f.relative_to(ROOT / "app"))

# opcjonalnie: python tools/publish.py <adres_paczki>  (np. link bezposredniego pobrania z Dysku Google)
package_ref = sys.argv[1] if len(sys.argv) > 1 else pkg_name

manifest = {
    "version": version.VERSION,
    "released": version.RELEASED,
    "notes": version.CHANGELOG[0]["changes"],
    "package": package_ref,
    "sha256": hashlib.sha256(pkg.read_bytes()).hexdigest(),
}
(OUT / "version.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"Gotowe: {pkg}  ({pkg.stat().st_size} B)\n        {OUT / 'version.json'}")
