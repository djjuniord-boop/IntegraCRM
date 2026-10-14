"""WYNIKI – obliczenia bez okna (te same wzory co wykres w mailu MARŻY, silnik_*._generuj_wykres_png).

Dni sprzedażowe: wszystkie dni miesiąca poza niedzielami i świętami z kalkulatora (arkusz „Święta PL”).
Dzień dzisiejszy liczy się jako jeszcze do zrobienia (jak w kalkulatorze i mailu).
"""
import calendar
import datetime

ODDZIALY = [("wroclaw", "Wrocław"), ("opole", "Opole")]
# oddział w uprawnieniach konta → klucz oddziału w wynikach marży (Stangum Opole nie ma wyników)
ODDZIAL_KONTA = {"Latex Wrocław": "wroclaw", "Latex Opole": "opole"}


def zl(v) -> str:
    """Kwota jak w mailu: „128 450 zł”; brak wartości → „—”."""
    if v is None:
        return "—"
    return f"{float(v):,.0f} zł".replace(",", " ")


def _data(v):
    if isinstance(v, datetime.date):
        return v
    try:
        return datetime.date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def dni_sprzedazowe(year: int, month: int, holidays) -> list:
    """Lista dat dni sprzedażowych miesiąca (bez niedziel i świąt)."""
    swieta = {d for d in (_data(h) for h in holidays or []) if d}
    n = calendar.monthrange(year, month)[1]
    out = []
    for day in range(1, n + 1):
        d = datetime.date(year, month, day)
        if d.weekday() != 6 and d not in swieta:
            out.append(d)
    return out


def podsumowanie(row: dict, today: datetime.date | None = None) -> dict:
    """Wszystko, co pokazuje zakładka dla jednego miesiąca oddziału (wiersz tabeli marza_months)."""
    today = today or datetime.date.today()
    year, month = int(row["year"]), int(row["month"])
    cel = float(row["target"]) if row.get("target") is not None else None
    zrob = float(row["done"]) if row.get("done") is not None else None
    dni = dni_sprzedazowe(year, month, row.get("holidays"))
    dni_all = len(dni)
    biezacy = (year, month) == (today.year, today.month)
    if biezacy:
        dni_min = sum(1 for d in dni if d < today)
    elif (year, month) < (today.year, today.month):
        dni_min = dni_all          # miesiąc zamknięty
    else:
        dni_min = 0                # miesiąc przyszły
    dni_zost = dni_all - dni_min
    r = {"label": row.get("label") or f"{month:02d}.{year}", "year": year, "month": month, "cel": cel,
         "zrobione": zrob, "biezacy": biezacy, "dni_all": dni_all, "dni_minelo": dni_min, "dni_zostalo": dni_zost,
         "pct": None, "plan_dzis": None, "tempo": None, "prognoza": None, "brakuje": None,
         "potrzeba_dziennie": None, "srednio_dziennie": None, "updated_at": row.get("updated_at")}
    if cel and cel > 0 and zrob is not None:
        r["pct"] = zrob / cel * 100
        r["brakuje"] = max(cel - zrob, 0.0)
    if cel and cel > 0 and dni_all:
        r["plan_dzis"] = cel * dni_min / dni_all
        if zrob is not None and dni_min:
            r["tempo"] = zrob / r["plan_dzis"] * 100
    if zrob is not None and dni_min:
        r["srednio_dziennie"] = zrob / dni_min
        if dni_all:
            r["prognoza"] = zrob / dni_min * dni_all
    if r["brakuje"] is not None and dni_zost:
        r["potrzeba_dziennie"] = r["brakuje"] / dni_zost
    return r


def wybierz_miesiac(rows: list, today: datetime.date | None = None):
    """Wiersz bieżącego miesiąca; gdy go brak – ostatni miesiąc z wykonaniem."""
    today = today or datetime.date.today()
    for r in rows:
        if (int(r["year"]), int(r["month"])) == (today.year, today.month):
            return r
    past = [r for r in rows if r.get("done") is not None and (int(r["year"]), int(r["month"])) <= (today.year, today.month)]
    return max(past, key=lambda r: (int(r["year"]), int(r["month"]))) if past else None


def poprzednie(rows: list, biezacy: dict | None, n: int = 6) -> list:
    """Ostatnie zamknięte miesiące (z celem albo wykonaniem), najnowsze pierwsze."""
    if biezacy is None:
        return []
    key = (int(biezacy["year"]), int(biezacy["month"]))
    out = [r for r in rows if (int(r["year"]), int(r["month"])) < key
           and (r.get("target") is not None or r.get("done") is not None)]
    out.sort(key=lambda r: (int(r["year"]), int(r["month"])), reverse=True)
    return out[:n]


def punkty_wykresu(row: dict, runs: list, today: datetime.date | None = None) -> list:
    """Wykonanie narastająco z kolejnych aktualizacji MARŻY w tym miesiącu: [(nr dnia sprzedażowego, kwota)].
    Z jednego dnia bierzemy ostatnią aktualizację; ostatni punkt = stan z kalkulatora."""
    today = today or datetime.date.today()
    year, month = int(row["year"]), int(row["month"])
    dni = dni_sprzedazowe(year, month, row.get("holidays"))
    if not dni:
        return []

    def idx(d):   # ile dni sprzedażowych upłynęło do końca dnia d
        return sum(1 for x in dni if x <= d)
    per_day = {}
    for r in sorted(runs, key=lambda r: str(r.get("run_at") or "")):
        if r.get("done") is None:
            continue
        d = _data(r.get("run_at"))
        if d is None or (d.year, d.month) != (year, month):
            continue
        per_day[idx(d)] = float(r["done"])
    if row.get("done") is not None and (year, month) == (today.year, today.month):
        per_day[max(idx(today), max(per_day, default=0))] = float(row["done"])
    return sorted(per_day.items())
