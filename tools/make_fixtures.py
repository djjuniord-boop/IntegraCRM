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

INTEGRA = ["DW12345", "DWR6372L", "WE7A071", "KT2277E", "DX7806F", "D4DDY", "DW3M448", "PO9AB12"]
MISSING = ["DW3M448", "PO9AB12"]           # są w Integrze, nie ma ich w CRM
CRM = [p for p in INTEGRA if p not in MISSING] + ["DW77777", "WR4567A"]

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)

# PDF z „Integry” – z typowym szumem (daty, NIP, faktury), który nie może dać fałszywych braków
c = canvas.Canvas(str(out / "integra.pdf"), pagesize=A4)
y = 800
c.setFont("Helvetica", 10)
c.drawString(40, y, "Raport zakonczonych zlecen   08.10.2026   Oddzial Wroclaw")
y -= 24
for i, p in enumerate(INTEGRA, 1):
    c.drawString(40, y, f"{i}.  Zlecenie 2026/{1000 + i}   Nr rej.: {p}   Wymiana opon   Kwota 240,00")
    y -= 18
c.drawString(40, y - 10, "Razem: 8 zlecen")
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

(out / "expected.json").write_text(json.dumps({"missing": MISSING}), encoding="utf-8")
print("Dane testowe:", out)
