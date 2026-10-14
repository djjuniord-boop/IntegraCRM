"""Tworzy syntetyczne dane testowe (bez prawdziwych danych firmy):
integra.pdf – raport z numerami, crm.xlsx – raport „Listy kontrolne” z CRM, expected.json.

Użycie: python tools/make_fixtures.py <folder>
"""
import json
import sys
from datetime import date
from pathlib import Path

from openpyxl import Workbook
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

INTEGRA = ["DW12345", "DWR6372L", "WE7A071", "KT2277E", "DX7806F", "D4DDY", "DW3M448", "PO9AB12", "WE9LF81"]
REPEAT = "DW12345"                         # to samo auto drugi raz tego dnia = druga wizyta
MISSING = ["DW3M448", "PO9AB12"]           # są w Integrze, nie ma ich w CRM
BRANCH = "Latex Wrocław"
CRM = [p for p in INTEGRA if p not in MISSING] + ["DW77777", "WR4567A"]
OTHER = [("Latex Opole", "OP11111"), ("Latex Opole", "DW3M448")]   # inny oddział – nie może ukryć braku
DAY = "2026-10-08"
# liczniki dzienne dla oddziału BRANCH: wizyty bez odduplikowania, listy = wiersze CRM tego dnia
DAILY = [{"day": DAY, "visits": len(INTEGRA) + 1, "lists": len(CRM), "missing": len(MISSING)}]

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
for i, p in enumerate(INTEGRA + [REPEAT], 1):
    c.drawString(30, y, f"8.10.2026 {3570 + i}/Z/SP51/26 (Zak.) {p} - SKODA FABIA IV (PJ3) 1.0 TSI 4x4 eDrive40 "
                        f"0,80 0,80 (0 rbh, 8 oper) 229,59")
    y -= 16
c.drawString(30, y - 8, "Podsumowanie raportu: 7,70 7,70 4724,82 2196,01   Strona 1 z 1")
c.save()

# Raport z CRM „Listy kontrolne” (.xlsx): kolumny Data, Rejestracja, Oddział
wb = Workbook()
ws = wb.active
ws.title = "Listy kontrolne"
ws.append(["Data", "Rejestracja", "Oddział", "Status"])
for p in CRM:
    ws.append([date.fromisoformat(DAY), p, BRANCH, "Zaimportowano"])
for b, p in OTHER:
    ws.append([date.fromisoformat(DAY), p, b, "Zaimportowano"])
wb.save(out / "crm.xlsx")

(out / "expected.json").write_text(json.dumps({"missing": MISSING, "integra": INTEGRA, "branch": BRANCH, "daily": DAILY},
                                                ensure_ascii=False), encoding="utf-8")
print("Dane testowe:", out)
