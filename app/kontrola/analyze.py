"""Cała analiza w jednym miejscu (używana przez okno programu i test automatyczny).

Dane z CRM pochodzą wyłącznie z raportu .xlsx/.csv („Listy kontrolne”) – porównanie dokładne, bez OCR.
OCR zostaje tylko dla skanów PDF z Integry (extract.text_from_pdf)."""
import re
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
    if crm_by_day:   # tylko dni objęte raportem CRM – krótszy raport nie nadpisze innych dni zerami
        lo, hi = min(crm_by_day), max(crm_by_day)
        days = [d for d in days if lo <= d <= hi]
    else:
        days = []
    out = []
    for d in days:
        v = [plates.normalize(p) for dd, p in visits if dd == d]
        lists = crm_by_day.get(d, [])
        have = set(lists)
        out.append({"day": d, "visits": len(v), "lists": len(lists),
                    "missing": sum(1 for p in v if p not in have)})
    return out


_ZNAKI = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")


def _bez_ogonkow(t: str) -> str:
    return " ".join(str(t or "").translate(_ZNAKI).lower().split())


_SERWIS = re.compile(r"\bserwis (wroclaw|opole|stangum)\b")
_ODDZIAL = {"wroclaw": "Latex Wrocław", "opole": "Latex Opole", "stangum": "Stangum Opole"}


def serwis_z_naglowka(pdf_text: str) -> str | None:
    """Serwis z nagłówka raportu Integry („Serwis Wrocław/Opole/Stangum”) jako nazwa oddziału z CRM.
    Każda linia osobno; kilka różnych serwisów albo brak – None (wtedy nic nie podpowiadamy)."""
    found = {_ODDZIAL[m] for line in pdf_text.splitlines()[:15]
             for m in _SERWIS.findall(_bez_ogonkow(line))}
    return found.pop() if len(found) == 1 else None


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
    r["pdf_branch"] = pdf_br = serwis_z_naglowka(pdf_text)
    chosen = {_bez_ogonkow(b) for b in crm.get("branches", [])}
    r["branch_mismatch"] = bool(pdf_br) and _bez_ogonkow(pdf_br) not in chosen
    # pokrycie numerów – pojedynczy brak (np. raport z 1 samochodem) to zwykły brak, nie „zły serwis”
    r["no_overlap"] = len(integra) >= 2 and bool(crm_main) and (
        common == 0 or (len(integra) > 5 and common / len(integra) < 0.3))
    if r["no_overlap"]:
        if r["branch_mismatch"]:
            txt = (f"Raport z Integry jest z serwisu {pdf_br}, a zaznaczono: {', '.join(crm.get('branches', []))}. "
                   f"Zaznacz {pdf_br} i kliknij „Sprawdź” ponownie.")
        else:
            txt = (f"Tylko {common} z {len(integra)} numerów z Integry jest w raporcie z CRM – "
                   "prawdopodobnie wybrano zły serwis albo raport za inny okres. Sprawdź dane przed wysłaniem e-maila.")
        r["warnings"].insert(0, txt)
    elif r["branch_mismatch"]:
        r["warnings"].insert(0, f"Nagłówek raportu z Integry wskazuje serwis {pdf_br}, a zaznaczono inny – "
                                "numery jednak się zgadzają, sprawdź przed wysłaniem e-maila.")

    # Raport .xlsx to dokładne dane – żadnego „rozmytego” dopasowania,
    # inaczej inny samochód o podobnym numerze ukryłby prawdziwy brak.
    r.update(missing=[plates.normalize(p) for p in integra if plates.normalize(p) not in exact],
             uncertain=[], autofix=[])
    r["daily"] = daily_stats(plates.extract_integra_visits(pdf_text), rows, r["range"])
    return r
