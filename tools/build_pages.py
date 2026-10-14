"""Buduje stronę SERWIS QR dla GitHub Pages z panelu w programie (app/serwis/) – jedno źródło, bez ręcznych kopii.

Użycie: python tools/build_pages.py <folder_wyjściowy>
Wynik: index.html (konfiguracja z config.js zamiast pliku programu, bez indeksowania), qrcode.min.js, config.js, .nojekyll.
Adres i klucz bazy brane z app/cloud.py (klucz „anon” jest publiczny z założenia – dane chroni RLS w bazie).
"""
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "app" / "serwis"
OUT = Path(sys.argv[1])
BASE = "https://djjuniord-boop.github.io/IntegraCRM/"   # adres strony dla klientów (kody QR na naklejkach)

cloud = (ROOT / "app" / "cloud.py").read_text(encoding="utf-8")
url = re.search(r'^URL = "([^"]+)"', cloud, re.M).group(1)
key = "".join(re.findall(r'"([^"]+)"', re.search(r"^ANON_KEY = \(([^)]*)\)", cloud, re.M | re.S).group(1)))

html = (SRC / "index.html").read_text(encoding="utf-8")
old_cfg = '<script src="../../data/serwis_config.js"></script>'
if old_cfg not in html:
    sys.exit("Nie znaleziono w index.html wczytywania ustawień panelu – sprawdź app/serwis/index.html")
html = html.replace(old_cfg, '<script src="config.js"></script>')
if 'name="robots"' not in html:
    html = html.replace('<meta charset="utf-8">', '<meta charset="utf-8">\n<meta name="robots" content="noindex">', 1)

OUT.mkdir(parents=True, exist_ok=True)
(OUT / "index.html").write_text(html, encoding="utf-8")
shutil.copy2(SRC / "qrcode.min.js", OUT / "qrcode.min.js")
(OUT / "config.js").write_text("window.SERWIS_CFG = " + json.dumps({"url": url, "key": key, "base": BASE}, indent=2)
                               + ";\n", encoding="utf-8")
(OUT / ".nojekyll").write_text("", encoding="utf-8")
print(f"Strona zbudowana w {OUT}")
