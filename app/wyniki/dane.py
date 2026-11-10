"""WYNIKI – obliczenia bez okna (te same wzory co wykres w e-mailu MARŻY, silnik_*._generuj_wykres_png).

Dni sprzedażowe: wszystkie dni miesiąca poza niedzielami i świętami z kalkulatora (arkusz „Święta PL”).
Dzień aktualizacji MARŻY liczy się jako miniony (raport z danego dnia), inne dni od dziś – jako do zrobienia;
daty aktualizacji w czasie polskim (_data_lokalna).
"""
import calendar
import datetime

ODDZIALY = [("wroclaw", "Wrocław"), ("opole", "Opole")]
# oddział w uprawnieniach konta → klucz oddziału w wynikach marży (Stangum Opole nie ma wyników)
ODDZIAL_KONTA = {"Latex Wrocław": "wroclaw", "Latex Opole": "opole"}


def zl(v) -> str:
    """Kwota jak w e-mailu: „128 450 zł”; brak wartości → „—”."""
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


def _data_lokalna(v):
    """Znacznik czasu z bazy (UTC) → data w czasie lokalnym (zapis o 0:30 to już nowy dzień)."""
    try:
        t = datetime.datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return t.astimezone().date() if t.tzinfo else t.date()
    except (TypeError, ValueError):
        return _data(v)


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
    dzien_dzis = sum(1 for d in dni if d <= today) if biezacy else None
    if biezacy:
        # Raport z Integry wgrany dziś obejmuje też dzisiejszą sprzedaż – dzisiejszy dzień liczy się wtedy
        # jako miniony (inaczej średnia i prognoza dzielą kwotę z N dni przez N-1 dni).
        upd = _data_lokalna(row.get("updated_at"))
        dni_min = sum(1 for d in dni if (d <= today if upd is not None and upd >= today else d < today))
    elif (year, month) < (today.year, today.month):
        dni_min = dni_all          # miesiąc zamknięty
    else:
        dni_min = 0                # miesiąc przyszły
    dni_zost = dni_all - dni_min
    r = {"label": row.get("label") or f"{month:02d}.{year}", "year": year, "month": month, "cel": cel,
         "zrobione": zrob, "biezacy": biezacy, "dni_all": dni_all, "dni_minelo": dni_min, "dzien_dzis": dzien_dzis, "dni_zostalo": dni_zost,
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


def poprzednie(rows: list, biezacy: dict | None, n: int | None = None) -> list:
    """Zamknięte miesiące (z celem albo wykonaniem), najnowsze pierwsze; domyślnie wszystkie (także ręczne)."""
    if biezacy is None:
        return []
    key = (int(biezacy["year"]), int(biezacy["month"]))
    out = [r for r in rows if (int(r["year"]), int(r["month"])) < key
           and (r.get("target") is not None or r.get("done") is not None)]
    out.sort(key=lambda r: (int(r["year"]), int(r["month"])), reverse=True)
    return out if n is None else out[:n]


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
        d = _data_lokalna(r.get("run_at"))   # aktualizacja o 0:30 czasu polskiego to już nowy dzień
        if d is None or (d.year, d.month) != (year, month):
            continue
        per_day[idx(d)] = float(r["done"])
    if row.get("done") is not None and (year, month) == (today.year, today.month):
        per_day[max(idx(today), max(per_day, default=0))] = float(row["done"])
    return sorted(per_day.items())


# ---------- edycja przez administratora (RPC admin_set_month) ----------
MIESIACE = ["Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec", "Lipiec", "Sierpień", "Wrzesień",
            "Październik", "Listopad", "Grudzień"]
MAX_KWOTA = 100_000_000      # jak w bazie (admin_set_month)


def parsuj_kwote(text) -> float:
    """Kwota wpisana po polsku: „128 450,50”, „128450”, „128.450,5 zł” → 128450.5. Błąd → ValueError z opisem."""
    s = str(text or "").strip().lower().replace("zł", "").replace("zl", "")
    for sp in (" ", " ", " ", "\t"):
        s = s.replace(sp, "")
    if not s:
        raise ValueError("Wpisz kwotę.")
    if "," in s:
        s = s.replace(".", "").replace(",", ".")          # 128.450,50 → 128450.50
    elif s.count(".") > 1 or (s.count(".") == 1 and len(s.split(".")[1]) == 3):
        s = s.replace(".", "")                            # 128.450 → 128450 (kropka jako tysiące)
    try:
        v = float(s)
    except ValueError:
        raise ValueError("To nie jest kwota – wpisz same cyfry, np. 300 000 albo 128 450,50.") from None
    v = round(v, 2) if v == v else v
    if v != v or v <= 0:   # po zaokrągleniu: „0,004” to 0 zł
        raise ValueError("Kwota musi być większa od zera.")
    if v > MAX_KWOTA:
        raise ValueError("Kwota jest za duża.")
    return v


def kwota_do_pola(v) -> str:
    """Kwota do pola edycji: „300 000” albo „128 450,50”."""
    if v is None:
        return ""
    v = float(v)
    txt = f"{v:,.2f}".replace(",", " ").replace(".", ",")
    return txt[:-3] if txt.endswith(",00") else txt


def parametry_rpc(branch: str, year: int, month: int, target: float, done: float | None = None) -> dict:
    """Parametry admin_set_month; p_done tylko przy miesiącu ręcznym (nowy albo edycja ręcznego)."""
    p = {"p_branch": branch, "p_year": int(year), "p_month": int(month), "p_target": target}
    if done is not None:
        p["p_done"] = done
    return p


def znajdz_miesiac(rows: list, year: int, month: int):
    for r in rows:
        if (int(r["year"]), int(r["month"])) == (int(year), int(month)):
            return r
    return None


def oznaczenie(row: dict) -> str:
    """Dopisek przy miesiącu w tabeli: ręcznie dopisany / cel czeka na wpisanie do Excela."""
    parts = []
    if row.get("manual"):
        parts.append("(ręcznie)")
    if row.get("target_pending"):
        parts.append("cel ✎ czeka na Excel")
    return " ".join(parts)


def opis_bledu(e) -> str:
    """Błąd z bazy prostym językiem."""
    t = str(e)
    low = t.lower()
    if "42501" in t or "tylko administrator" in low:
        return "Tylko administrator może zmieniać cele."
    if "admin_set_month" in low and ("function" in low or "not find" in low or "pgrst202" in low):
        return "Baza nie ma jeszcze tej funkcji – administrator musi najpierw wkleić aktualizację bazy (plik SQL)."
    if "kwota" in low:
        return "Baza nie przyjęła kwoty – sprawdź, czy jest większa od zera."
    if "miesiąc" in low or "oddział" in low:
        return "Baza nie przyjęła miesiąca – sprawdź oddział, miesiąc i rok."
    return f"Nie udało się zapisać: {t}"


def wiersz_tabeli(row: dict) -> tuple:
    """Wiersz tabeli „Poprzednie miesiące”: (wartości kolumn, znacznik koloru)."""
    p = podsumowanie(row)
    label = p["label"] + (" (ręcznie)" if row.get("manual") else "")
    cel = zl(p["cel"]) + (" ✎" if row.get("target_pending") else "")
    tag = () if p["pct"] is None else (("ok",) if p["pct"] >= 100 else ("bad",))
    return (label, zl(p["zrobione"]), cel, f"{p['pct']:.0f}%" if p["pct"] is not None else "—"), tag


def domyslny_nowy_miesiac(rows: list, today: datetime.date | None = None) -> tuple:
    """Domyślny miesiąc w oknie „Dodaj miesiąc”: miesiąc przed najstarszym w wynikach (brak wyników – poprzedni)."""
    today = today or datetime.date.today()
    keys = [(int(r["year"]), int(r["month"])) for r in rows]
    y, m = min(keys) if keys else (today.year, today.month)
    y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    return (max(y, 2020), m) if y >= 2020 else (2020, 1)
