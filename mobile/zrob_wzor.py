"""Kopiuje wzór PDF oferty z Panelu (app/oferty/pdf_wzor.html) do aplikacji (mobile/www/pdf_wzor.js).
Uruchom po każdej zmianie wzoru: python3 mobile/zrob_wzor.py  (test zgodności sprawdza, czy kopia jest aktualna)."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
def tresc():
    t = (ROOT / "app/oferty/pdf_wzor.html").read_text(encoding="utf-8")
    return "// Wygenerowane z app/oferty/pdf_wzor.html przez mobile/zrob_wzor.py – nie edytuj ręcznie.\nwindow.PDF_WZOR = " + json.dumps(t, ensure_ascii=False) + ";\n"
if __name__ == "__main__":
    (ROOT / "mobile/www/pdf_wzor.js").write_text(tresc(), encoding="utf-8"); print("zapisano mobile/www/pdf_wzor.js")
