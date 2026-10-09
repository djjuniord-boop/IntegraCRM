"""Cała analiza w jednym miejscu (używana przez okno programu i test automatyczny)."""
import re
from datetime import date, timedelta

import extract
import plates

CRM_DATE_RE = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4}),?\s+\d{1,2}:\d{2}")


def crm_dates(texts) -> set:
    """Daty wierszy z wycinka CRM (z wszystkich przebiegów OCR)."""
    out = set()
    for t in texts:
        for d, m, y in CRM_DATE_RE.findall(t):
            try:
                out.add(date(int(y), int(m), int(d)))
            except ValueError:
                pass
    return out


def _days(rng):
    a, b = (date.fromisoformat(x) for x in rng)
    return [a + timedelta(days=i) for i in range((b - a).days + 1)] if b >= a else []


def run(pdf_path, crm_image, tesseract_cmd=None, log=lambda s: None) -> dict:
    r = {"warnings": []}
    log("PDF z Integry…")
    pdf_text = extract.text_from_pdf(pdf_path, tesseract_cmd)
    integra, layout_ok = plates.extract_integra_plates(pdf_text)
    r.update(integra=integra, layout_ok=layout_ok, range=plates.integra_date_range(pdf_text))
    log(f"  {len(integra)}: {', '.join(integra) or '—'}")
    if r["range"]:
        log(f"  zakres raportu: {r['range'][0]} – {r['range'][1]}")
    if integra and not layout_ok:
        r["warnings"].append("Nie rozpoznano układu raportu Integry – numery wyszukane ogólnie, "
                             "wynik może zawierać błędne pozycje.")

    log("Wycinek z CRM (OCR)…")
    texts = extract.ocr_variants(crm_image, tesseract_cmd)
    crm_main = plates.extract_crm_plates(texts[0])
    crm = list(crm_main)
    for t in texts[1:]:   # dodatkowe przebiegi poprawiają przekręcone znaki
        for p in plates.extract_crm_plates(t):
            if p not in crm:
                crm.append(p)
    r.update(crm=crm, crm_main=crm_main)
    log(f"  {len(crm_main)}: {', '.join(crm_main) or '—'}")

    # Zakres dat: czy wycinek z CRM obejmuje wszystkie dni raportu z Integry
    dates = crm_dates(texts)
    r["crm_dates"] = sorted(d.isoformat() for d in dates)
    if r["range"] and dates:
        lacking = [d for d in _days(r["range"]) if d not in dates]
        if lacking:
            txt = ", ".join(d.strftime("%d.%m") for d in lacking[:5])
            r["warnings"].append(f"Na wycinku z CRM nie widać wierszy z dnia: {txt}. Jeśli tego dnia były "
                                 "importy, zrób dłuższy wycinek – inaczej wynik pokaże fałszywe braki.")

    # Porównanie: dokładne trafienia ze wszystkich przebiegów, „podobne” tylko z głównego
    exact = {plates.normalize(p) for p in crm}
    rest = [p for p in integra if plates.normalize(p) not in exact]
    missing, uncertain = plates.compare(rest, crm_main)
    r.update(missing=missing, uncertain=uncertain)
    return r
