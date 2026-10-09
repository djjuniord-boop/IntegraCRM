"""Tworzy syntetyczne dane testowe (bez prawdziwych danych firmy):
integra.pdf – raport z numerami, crm.png – „wycinek” tabeli CRM, expected.json.

Użycie: python tools/make_fixtures.py <folder>
"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

INTEGRA = ["DW12345", "DWR6372L", "WE7A071", "KT2277E", "DX7806F", "D4DDY", "DW3M448", "PO9AB12", "WE9LF81"]
MISSING = ["DW3M448", "PO9AB12"]           # są w Integrze, nie ma ich w CRM
# WE9LF81 „przekręcony” jak przez OCR (9→S) – program ma go uznać za ten sam numer
CRM = [("WESLF81" if p == "WE9LF81" else p) for p in INTEGRA if p not in MISSING] + ["DW77777", "WR4567A"]

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)

# PDF w układzie Integry 7 („Raport bieżącej pracy serwisu wg pojazdów”) z typowym szumem
c = canvas.Canvas(str(out / "integra.pdf"), pagesize=A4)
y = 800
c.setFont("Helvetica", 9)
for line in ("LATEX SERWIS Sp. z o.o.", "NIP 7543073900 Serwis Wroclaw",
             "Raport biezacej pracy serwisu wg pojazdow",
             "Zakres dat: od 2026-10-08 do 2026-10-08 (OSTATNI DZIEN)",
             "8.10.2026 () 0,00 0,00 (0 rbh, 0 oper) 2219,51 358,91 2219,51 358,91"):
    c.drawString(30, y, line)
    y -= 16
for i, p in enumerate(INTEGRA, 1):
    c.drawString(30, y, f"8.10.2026 {3570 + i}/Z/SP51/26 (Zak.) {p} - SKODA FABIA IV (PJ3) 1.0 TSI 4x4 eDrive40 "
                        f"0,80 0,80 (0 rbh, 8 oper) 229,59")
    y -= 16
c.drawString(30, y - 8, "Podsumowanie raportu: 7,70 7,70 4724,82 2196,01   Strona 1 z 1")
c.save()

# „Wycinek” z CRM – układ jak w Historii importów (data, godzina, numer, oddział, status)
font = None
for name in ("segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"):
    try:
        font = ImageFont.truetype(name, 15)
        break
    except OSError:
        pass
font = font or ImageFont.load_default()
rows = [f"8.10.2026, 1{i % 10}:2{i % 6}    {p}    Latex Wroclaw    Zaimportowano" for i, p in enumerate(CRM)]
img = Image.new("RGB", (760, 40 + 32 * len(rows)), "white")
dr = ImageDraw.Draw(img)
dr.text((12, 10), "Data                     Rejestracja     Oddzial            Status", fill="#555", font=font)
for i, r in enumerate(rows):
    dr.text((12, 40 + 32 * i), r, fill="black", font=font)
img.save(out / "crm.png")

(out / "expected.json").write_text(json.dumps({"missing": MISSING, "integra": INTEGRA}), encoding="utf-8")
print("Dane testowe:", out)
