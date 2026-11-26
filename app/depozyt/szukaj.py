"""Wyszukiwanie w spisie depozytu odporne na literówki w numerach rejestracyjnych.

Kolejność wyników: numer dokładnie / fragment numeru → lokalizacja, marka, komentarz → „≈ możliwa literówka”
(znaki mylone przy przepisywaniu: O/0/D, I/1/L, Z/2, S/5, B/8, G/6, T/7 albo 1–2 inne znaki).
Numery szukane są też w kolumnie uwag (spis często ma tam poprawiony numer, np. „DX8L367?”).
"""
import re

_MYLONE = str.maketrans({"O": "0", "Q": "0", "D": "0", "I": "1", "L": "1", "J": "1", "Z": "2", "S": "5",
                         "B": "8", "G": "6", "T": "7"})
_NUMER_W_TEKSCIE = re.compile(r"[A-Z0-9]{5,9}")

DOKLADNE, FRAGMENT, INNE_POLE, PODOBNE, LITEROWKA = 100, 90, 85, 75, 60


def norm(s) -> str:
    return re.sub(r"[\s\-_.]", "", str(s or "").upper())


def kanon(s) -> str:
    """Numer bez znaków mylonych przy przepisywaniu (O→0, I→1 …)."""
    return norm(s).translate(_MYLONE)


def lev(a: str, b: str, limit: int) -> int:
    """Odległość edycyjna (z przerwaniem, gdy przekroczy limit – wtedy limit+1)."""
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    prev = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        cur = [i] + [0] * len(b)
        best = i
        for j in range(1, len(b) + 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] != b[j - 1]))
            best = min(best, cur[j])
        if best > limit:
            return limit + 1
        prev = cur
    return prev[-1]


def _lev_fragment(q: str, t: str, limit: int) -> int:
    """Najmniejsza odległość q od dowolnego fragmentu t tej samej długości (wpisano część numeru)."""
    if len(t) <= len(q):
        return lev(q, t, limit)
    best = limit + 1
    for i in range(len(t) - len(q) + 1):
        best = min(best, lev(q, t[i:i + len(q)], limit))
        if best == 0:
            break
    return best


def numery(poz: dict) -> list:
    """Numer pozycji + numery wpisane w uwagach."""
    return [poz.get("nr") or ""] + _NUMER_W_TEKSCIE.findall(str(poz.get("uwagi") or "").upper())


def ocena(poz: dict, zapytanie: str) -> tuple:
    """(punkty, czy_przyblizone). 0 = brak dopasowania."""
    q_raw = str(zapytanie or "").strip().upper()
    qn, qc = norm(q_raw), kanon(q_raw)
    if not qn:
        return 0, False
    best, przybl = 0, False
    for p in numery(poz):
        pn, pc = norm(p), kanon(p)
        if not pn:
            continue
        if pn == qn:
            pkt, fz = DOKLADNE, False
        elif qn in pn:
            pkt, fz = FRAGMENT, False
        elif pc == qc:
            pkt, fz = 80, True
        elif qc in pc:
            pkt, fz = 70, True
        elif len(qn) >= 5 and any(c.isdigit() for c in qn) and any(c.isalpha() for c in qn):
            d = _lev_fragment(qc, pc, 2 if len(qn) >= 7 else 1)
            pkt, fz = (LITEROWKA - d * 10, True) if d <= 2 else (0, False)
        else:
            pkt, fz = 0, False
        if pkt > best:
            best, przybl = pkt, fz
    if best < FRAGMENT:
        tekst = " ".join(str(poz.get(k) or "") for k in ("lok", "marka", "marka2", "uwagi", "komentarz", "rodzaj")).upper()
        if q_raw in tekst:
            best, przybl = max(best, INNE_POLE), False
    return best, przybl and best < FRAGMENT


def szukaj(pozycje: list, zapytanie: str) -> list:
    """[(pozycja, punkty, czy_przyblizone)] od najlepszego dopasowania."""
    out = []
    for p in pozycje:
        pkt, fz = ocena(p, zapytanie)
        if pkt:
            out.append((p, pkt, fz))
    out.sort(key=lambda x: -x[1])
    return out


TRASA: list = []   # kolejność regałów z ustawień depozytu (np. ["K", "KB", "M", "KPOK"]); pusta = K, M, reszta


def regal(lok: str) -> str:
    """Oznaczenie regału z lokalizacji: „K12.3” → „K”, „KPOK” → „KPOK”, „M8/10” → „M”."""
    m = re.match(r"\s*([A-Z]+)", str(lok or "").upper())
    return m.group(1) if m else ""


def trasa_dla(lokalizacje, zapisana=None) -> list:
    """Pełna kolejność regałów: zapisana w ustawieniach + nowe oznaczenia z danych (na końcu, wg kolejności domyślnej)."""
    zapisana = [r for r in (zapisana or []) if r]
    nowe = sorted({regal(x) for x in lokalizacje if regal(x)} - set(zapisana),
                  key=lambda r: ({"K": 0, "M": 1}.get(r, 2), r))
    return zapisana + nowe


def klucz_lokalizacji(lok: str) -> tuple:
    """Kolejność obchodu magazynu: wg TRASA z ustawień, a bez ustawień – regały K, potem M, potem pozostałe
    (KPOK, KWEJ, MAGOPIS…); w obrębie regału numerami rosnąco."""
    m = re.match(r"\s*([A-Z]+)\s*(\d+)?\D*(\d+)?", str(lok or "").upper())
    if not m:
        return (999, "", 0, 0)
    r = m.group(1)
    grupa = TRASA.index(r) if r in TRASA else len(TRASA) + {"K": 0, "M": 1}.get(r, 2)
    return (grupa, r, int(m.group(2) or 0), int(m.group(3) or 0))


def opis_trasy() -> str:
    return " → ".join(TRASA) if TRASA else "K → M → pozostałe"
