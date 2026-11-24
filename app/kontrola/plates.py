"""Wyciąganie i porównywanie polskich numerów rejestracyjnych."""
import re
from datetime import date

# Polskie tablice: 2-3 znaki wyróżnika powiatu + 4-5 znaków (litery/cyfry),
# np. DW 12345, WR 1234A, DWR 1234, PO 12AB3. Dopuszczamy spację/myślnik w środku.
PLATE_RE = re.compile(
    r"(?<![A-Z0-9])([A-Z]{1,3})[\s\-]?([A-Z0-9]{4,5})(?![A-Z0-9])"
)

INTEGRA_ROW_RE = re.compile(
    r"\d+/[A-Z]+/[A-Z0-9]+/\d+\s+\([^)]*\)\s+([A-Z0-9]{2,8})\s+-\s")
# Ten sam wiersz z datą na początku („8.10.2026 3576/Z/…”) – do liczników dziennych (wizyty)
INTEGRA_VISIT_RE = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{4})\s+" + INTEGRA_ROW_RE.pattern)
INTEGRA_RANGE_RE = re.compile(r"Zakres dat:\s*od\s+(\d{4}-\d{2}-\d{2})\s+do\s+(\d{4}-\d{2}-\d{2})")


def extract_integra_plates(text: str) -> tuple[list[str], bool]:
    """Numery z raportu Integry. Zwraca (numery, czy_rozpoznano_układ_raportu).
    Gdy układ nie zostanie rozpoznany – wzorzec ogólny (mniej pewny)."""
    found = []
    for m in INTEGRA_ROW_RE.finditer(text.upper()):
        p = m.group(1)
        if any(c.isdigit() for c in p) and p not in found:
            found.append(p)
    if found:
        return found, True
    return extract_plates(text), False


def extract_integra_visits(text: str) -> list[tuple[str, str]]:
    """Wszystkie wiersze zleceń z pojazdem jako (dzień 'RRRR-MM-DD', numer) – BEZ odduplikowania
    (to samo auto dwa razy = dwie wizyty). Wiersze bez poprawnej daty są pomijane."""
    out = []
    for m in INTEGRA_VISIT_RE.finditer(text.upper()):
        d, mo, y, p = m.groups()
        if not any(c.isdigit() for c in p):
            continue
        try:
            out.append((date(int(y), int(mo), int(d)).isoformat(), p))
        except ValueError:
            pass
    return out


def integra_date_range(text: str):
    """(od, do) jako 'RRRR-MM-DD' z nagłówka raportu albo None."""
    m = INTEGRA_RANGE_RE.search(text)
    return (m.group(1), m.group(2)) if m else None


def normalize(plate: str) -> str:
    """Wielkie litery, bez spacji i myślników."""
    return re.sub(r"[\s\-]", "", plate.upper())


def _plausible(prefix: str, rest: str) -> bool:
    # Reszta musi zawierać co najmniej 2 cyfry (odsiewa zwykłe słowa typu "ZLECENIE")
    return sum(c.isdigit() for c in rest) >= 2 and 2 <= len(prefix) <= 3


def extract_plates(text: str) -> list[str]:
    """Zwraca unikalne, znormalizowane numery rejestracyjne znalezione w tekście."""
    found = []
    for line in text.upper().splitlines():
        for m in PLATE_RE.finditer(line):
            prefix, rest = m.group(1), m.group(2)
            if _plausible(prefix, rest):
                p = prefix + rest
                if p not in found:
                    found.append(p)
    return found
