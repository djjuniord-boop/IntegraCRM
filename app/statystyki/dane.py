"""Obliczenia statystyk (bez okna – testowane w tests/test_statystyki.py).

Wiersz z bazy (visit_stats): {"branch", "day": "RRRR-MM-DD", "visits", "lists", "missing"}.
Wizyta = zlecenie z pojazdem w raporcie Integry; lista = wiersz raportu „Listy kontrolne” z CRM.
"""
from datetime import date, timedelta

MIESIACE = ["Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec", "Lipiec", "Sierpień",
            "Wrzesień", "Październik", "Listopad", "Grudzień"]
MIN_WIZYT_MIESIAC = 30   # miesiąc z mniejszą liczbą wizyt nie wyznacza widełek prognozy (za mało danych)


def _suma(rows):
    v = sum(int(r.get("visits") or 0) for r in rows)
    l_ = sum(int(r.get("lists") or 0) for r in rows)
    m = sum(int(r.get("missing") or 0) for r in rows)
    return {"visits": v, "lists": l_, "missing": m, "na10": (10 * l_ / v) if v else None,
            "dni": len({r["day"] for r in rows})}


def filtruj(rows, oddzial=None):
    return [r for r in rows if oddzial in (None, "") or r.get("branch") == oddzial]


def miesiace(rows) -> list:
    """[{"klucz": "RRRR-MM", "nazwa": "Październik 2026", visits, lists, missing, na10, dni}] – najnowsze pierwsze."""
    grupy = {}
    for r in rows:
        grupy.setdefault(str(r["day"])[:7], []).append(r)
    out = []
    for k in sorted(grupy, reverse=True):
        y, m = int(k[:4]), int(k[5:7])
        out.append(dict(_suma(grupy[k]), klucz=k, nazwa=f"{MIESIACE[m - 1]} {y}"))
    return out


def okres(rows, dni: int = 90, dzis: date | None = None) -> dict:
    """Suma z ostatnich `dni` dni (domyślnie 90)."""
    od = ((dzis or date.today()) - timedelta(days=dni)).isoformat()
    return _suma([r for r in rows if str(r["day"]) >= od])


def prognoza(zlecen: int, rows, dzis: date | None = None) -> dict | None:
    """Ile list kontrolnych spodziewać się przy `zlecen` zleceniach.
    Środek – wskaźnik z ostatnich 90 dni (gdy brak – ze wszystkich danych); widełki – najniższy i najwyższy
    wskaźnik pełniejszych miesięcy (≥ MIN_WIZYT_MIESIAC wizyt). None, gdy brak danych."""
    if not zlecen or zlecen <= 0:
        return None
    baza, zakres = okres(rows, 90, dzis), "ostatnich 90 dni"
    if not baza["visits"]:
        baza, zakres = _suma(rows), "wszystkich zebranych danych"
    if not baza["visits"]:
        return None
    sr = baza["lists"] / baza["visits"]
    wsk = [m["lists"] / m["visits"] for m in miesiace(rows) if m["visits"] >= MIN_WIZYT_MIESIAC]
    lo, hi = (min(wsk), max(wsk)) if len(wsk) >= 2 else (sr, sr)
    return {"srodek": round(zlecen * sr), "od": round(zlecen * min(lo, sr)), "do": round(zlecen * max(hi, sr)),
            "na10": 10 * sr, "miesiecy": len(wsk), "wizyt_w_bazie": baza["visits"], "zakres": zakres}


def liczba(txt) -> int | None:
    """„1 000”, „1000”, „1.000” → 1000; zła wartość → None."""
    t = "".join(ch for ch in str(txt or "") if ch.isdigit())
    return int(t) if t and len(t) <= 7 else None


def fmt_na10(x) -> str:
    return "—" if x is None else f"{x:.1f}".replace(".", ",")


def fmt_int(n) -> str:
    return f"{int(n):,}".replace(",", " ")
