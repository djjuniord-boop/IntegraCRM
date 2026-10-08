"""Wyciąganie i porównywanie polskich numerów rejestracyjnych."""
import re

# Polskie tablice: 2-3 znaki wyróżnika powiatu + 4-5 znaków (litery/cyfry),
# np. DW 12345, WR 1234A, DWR 1234, PO 12AB3. Dopuszczamy spację/myślnik w środku.
PLATE_RE = re.compile(
    r"(?<![A-Z0-9])([A-Z]{1,3})[\s\-]?([A-Z0-9]{4,5})(?![A-Z0-9])"
)

# Typowe pomyłki OCR (sprowadzamy do wspólnej postaci tylko przy porównaniu "rozmytym")
OCR_FOLD = str.maketrans({"O": "0", "Q": "0", "D": "0", "9": "0", "I": "1", "L": "1",
                          "T": "1", "B": "8", "S": "5", "Z": "2", "G": "6"})

# Wiersz historii importów w CRM: "8.10.2026, 15:20  KT2277E  Latex Wrocław ..."
# Numer rejestracyjny to pierwszy token po godzinie (data bywa przekręcona przez OCR,
# godzina HH:MM – prawie nigdy).
CRM_ROW_RE = re.compile(r"\b\d{1,2}:\d{2}\s+([A-Za-z0-9]{3,8})(?![A-Za-z0-9])")


def extract_crm_plates(text: str) -> list[str]:
    """Numery z tabeli CRM (po godzinie w wierszu). Obsługuje też tablice indywidualne
    typu D4DDY. Gdy układ tabeli nie zostanie rozpoznany – wraca do wzorca ogólnego."""
    found = []
    for line in text.splitlines():
        m = CRM_ROW_RE.search(line)
        if m:
            p = m.group(1).upper()
            if any(c.isdigit() for c in p) and p not in found:
                found.append(p)
    return found or extract_plates(text)


def normalize(plate: str) -> str:
    """Wielkie litery, bez spacji i myślników."""
    return re.sub(r"[\s\-]", "", plate.upper())


def fold(plate: str) -> str:
    """Postać do porównań odpornych na błędy OCR (tylko część po wyróżniku)."""
    p = normalize(plate)
    return p[:2] + p[2:].translate(OCR_FOLD)


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


def compare(integra: list[str], crm: list[str]):
    """Zwraca (brakujące, niepewne).

    brakujące – na pewno nie ma ich w CRM
    niepewne  – nie ma dokładnego trafienia, ale jest podobny numer (możliwy błąd OCR)
    """
    crm_exact = {normalize(p) for p in crm}
    crm_fold = {fold(p): normalize(p) for p in crm}
    missing, uncertain = [], []
    for p in integra:
        n = normalize(p)
        if n in crm_exact:
            continue
        f = fold(n)
        if f in crm_fold:
            uncertain.append((n, crm_fold[f]))
            continue
        # jeden błędny / dodatkowy / brakujący znak – typowy błąd OCR
        close = next((orig for cf, orig in crm_fold.items()
                      if len(f) >= 6 and _dist_le1(f, cf)), None)
        if close:
            uncertain.append((n, close))
        else:
            missing.append(n)
    return missing, uncertain


def _dist_le1(a: str, b: str) -> bool:
    """True, jeśli a i b różnią się co najwyżej jednym znakiem (zamiana/wstawienie/usunięcie)."""
    if a == b:
        return True
    la, lb = len(a), len(b)
    if abs(la - lb) > 1:
        return False
    if la == lb:
        return sum(x != y for x, y in zip(a, b)) == 1
    s, l = (a, b) if la < lb else (b, a)
    i = 0
    while i < len(s) and s[i] == l[i]:
        i += 1
    return s[i:] == l[i + 1:]
