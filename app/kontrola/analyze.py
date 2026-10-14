"""Cała analiza w jednym miejscu (używana przez okno programu i test automatyczny).

Dane z CRM pochodzą wyłącznie z raportu .xlsx/.csv („Listy kontrolne”) – porównanie dokładne, bez OCR.
OCR zostaje tylko dla skanów PDF z Integry (extract.text_from_pdf)."""
from datetime import date, timedelta

from kontrola import extract
from kontrola import plates


def _days(rng):
    a, b = (date.fromisoformat(x) for x in rng)
    return [a + timedelta(days=i) for i in range((b - a).days + 1)] if b >= a else []


def daily_stats(visits, rows, rng=None) -> list[dict]:
    """Liczniki dzienne do statystyk „listy kontrolne na wizyty”.

    visits – [(dzień 'RRRR-MM-DD', numer)] z Integry, bez odduplikowania (to samo auto 2× = 2 wizyty);
    rows   – wiersze raportu CRM (już wybrane oddziały), bez odduplikowania;
    rng    – zakres raportu Integry ('od', 'do'); liczymy tylko dni z tego zakresu
             (bez zakresu – dni, w których są wizyty).
    missing = wizyty, których numeru nie ma w CRM na liście z tego samego dnia."""
    if rng:
        days = [d.isoformat() for d in _days(rng)]
    else:
        days = sorted({d for d, _ in visits})
    crm_by_day = {}
    for x in rows:
        if x.get("date"):
            crm_by_day.setdefault(x["date"].isoformat(), []).append(plates.normalize(x["plate"]))
    out = []
    for d in days:
        v = [plates.normalize(p) for dd, p in visits if dd == d]
        lists = crm_by_day.get(d, [])
        have = set(lists)
        out.append({"day": d, "visits": len(v), "lists": len(lists),
                    "missing": sum(1 for p in v if p not in have)})
    return out


def run(pdf_path, crm, tesseract_cmd=None, log=lambda s: None) -> dict:
    """crm = {"rows": wiersze raportu CRM dla wybranych oddziałów, "branches": [...]}"""
    if not isinstance(crm, dict):
        raise ValueError("Dane z CRM wczytuje się tylko z raportu .xlsx/.csv z „Listy kontrolne”.")
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

    rows = crm["rows"]
    log(f"Raport z CRM (plik), oddziały: {', '.join(crm.get('branches', [])) or '—'}")
    crm_main = []
    for x in rows:
        if x["plate"] not in crm_main:
            crm_main.append(x["plate"])
    dates = {x["date"] for x in rows if x["date"]}
    r.update(crm=list(crm_main), crm_main=crm_main, crm_source="report")
    log(f"  {len(crm_main)}: {', '.join(crm_main) or '—'}")

    # Zakres dat: czy raport z CRM obejmuje wszystkie dni raportu z Integry
    r["crm_dates"] = sorted(d.isoformat() for d in dates)
    if r["range"] and dates:
        lacking = [d for d in _days(r["range"]) if d not in dates]
        if lacking:
            txt = ", ".join(d.strftime("%d.%m") for d in lacking[:5])
            r["warnings"].append(f"W raporcie z CRM (wybrane oddziały) nie ma wierszy z dnia: {txt}. Jeśli tego "
                                 "dnia były importy, pobierz raport za pełny zakres – inaczej wynik pokaże "
                                 "fałszywe braki.")

    exact = {plates.normalize(p) for p in crm_main}
    common = sum(1 for p in integra if plates.normalize(p) in exact)
    r["n_common"] = common
    r["no_overlap"] = bool(integra) and bool(crm_main) and (
        common == 0 or (len(integra) > 5 and common / len(integra) < 0.3))
    if r["no_overlap"]:
        r["warnings"].insert(0, f"Tylko {common} z {len(integra)} numerów z Integry jest w raporcie z CRM – "
                                "prawdopodobnie wybrano zły oddział albo raport za inny okres. "
                                "Sprawdź dane przed wysłaniem maila.")

    # Raport .xlsx to dokładne dane – żadnego „rozmytego” dopasowania,
    # inaczej inny samochód o podobnym numerze ukryłby prawdziwy brak.
    r.update(missing=[plates.normalize(p) for p in integra if plates.normalize(p) not in exact],
             uncertain=[], autofix=[])
    r["daily"] = daily_stats(plates.extract_integra_visits(pdf_text), rows, r["range"])
    return r
