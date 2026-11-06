"""OFERTY OPON: PDF oferty przez Edge na prawdziwym Windows (GitHub Actions). Sprawdza, że powstaje 1-stronicowy PDF A4.
Uruchom: python tests/pdf_edge.py"""
import os, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app")); sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_oferty as T
T._setup()
from oferty import silnik as S, okno
S.OUT_DIR = tempfile.mkdtemp(prefix="oferty_pdf_test_")
S.KONTO.update(oddzialy=["Latex Opole"], kto="Test", oddzialy_dane={"Latex Opole": {"nazwa": "LATEX SERWIS OPOLE", "adres": "ul. Krapkowicka 18A, 45-732 Opole", "tel": "77 474 80 89"}})
okno._open_path = lambda p: None
okno.wczytaj_konto = lambda: None
S.KONTO["zapisz"] = lambda d: None
assert S.handle("/api/offer", {"oid": "20261105_120000", "rabat": "5", "pojazdy": [{"rozmiar": "205/55 R16", "ilosc": 4, "nowe": True, "wymiana": True, "tpms": 4}],
                                "wybor": {"205/55 R16": {"wszystkie": [1]}}})[0] == 200
print("przeglądarka:", okno._przegladarka() or "BRAK")
import time
for proba in (1, 2):   # 1 = pierwszy start Edge (nowy profil), 2 = kolejny PDF (stały profil)
    t = time.time()
    r = okno.Api().call("/api/pdf", {"id": 1, "nazwa": "Oferta test Bridgestone"})
    print("PDF nr %d: %.1f s" % (proba, time.time() - t), r["body"].get("pdf"))
assert r["code"] == 200 and r["body"]["pdf"], "Edge nie utworzył PDF"
from pypdf import PdfReader
pdf = PdfReader(r["body"]["plik"])
w, h = float(pdf.pages[0].mediabox.width), float(pdf.pages[0].mediabox.height)
tekst = pdf.pages[0].extract_text()
print("stron:", len(pdf.pages), "rozmiar:", round(w), "x", round(h))
assert len(pdf.pages) == 1 and abs(w - 595) < 3 and abs(h - 842) < 3, "PDF ma być jedną stroną A4"
assert "OPOLE" in tekst and "BRUTTO" in tekst, tekst[:300]
print("PDF oferty przez Edge: OK")
