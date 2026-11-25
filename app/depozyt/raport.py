"""Raporty przechowalni z Integra 7 (PDF z FastReport) i lista dla magazyniera.

Obsługuje każdy raport przechowalni z Integry, m.in. „Rejestr przechowalni opon” i „Rejestr opon do wydania
wg umówionych terminów”, na dowolny dzień albo okres. Słowa czytane są wg pozycji kolumn z nagłówka każdej
strony, więc zawijane nazwy firm i modeli nie psują wyników.

`przygotuj(raport, spis)` łączy raport ze spisem depozytu: lokalizacja na regale, kolejność obchodu
i uwagi do sprawdzenia (brak w spisie, inna marka, już odhaczone / nieodhaczone, dwie lokalizacje, niski bieżnik).
"""
import datetime
import re

import pdfplumber

from depozyt import szukaj

COLS = ["Indeks", "Nazwa", "Rozmiar", "Producent", "Typ", "Rodzaj", "Felga", "Bieżnik", "DOT", "Lokalizacja"]
RE_NUM = re.compile(r"^\d+/PO/\d+/\d+$")
RE_DATE = re.compile(r"^\d{1,2}\.\d{2}\.\d{4}$")
RE_IDX = re.compile(r"^\d{6}$")


def _col_bounds(words):
    """Granice kolumn z nagłówka drugiego wiersza (Indeks ... Lokalizacja). Nagłówki rozpoznawane po
    początku słowa – polskie litery bywają w PDF zapisane inaczej."""
    hdr = {}
    for w in words:
        for c in COLS:
            if c not in hdr and len(w["text"]) >= 3 and w["text"][:3].lower() == c[:3].lower():
                hdr[c] = w
    if len(hdr) < 8 or "Indeks" not in hdr:
        return None
    return [(c, (hdr[c]["x0"] - 3) if c in hdr else None) for c in COLS], hdr["Indeks"]["top"]


def _col_of(x, bounds):
    cur = None
    for c, lo in bounds:
        if lo is not None and x >= lo:
            cur = c
    return cur


def parse(path):
    out = {"tytul": "", "od": "", "do": "", "pozycje": []}
    cur = None
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            words = page.extract_words(keep_blank_chars=False, use_text_flow=False)
            txt = " ".join(w["text"] for w in words[:40])
            if not out["tytul"]:
                m = re.search(r"(Rejestr .*?)\s+Zakres dat: od (\S+) do (\S+)", txt)
                if m:
                    out["tytul"], out["od"], out["do"] = m.group(1), m.group(2), m.group(3)
            cb = _col_bounds(words)
            if not cb:
                continue
            bounds, hdr_top = cb
            head = {w["text"]: w["x0"] for w in words if w["top"] < hdr_top and w["text"] in ("Kontrahent", "Nr", "Status")}
            x_kontr, x_nr, x_stat = head.get("Kontrahent", 140), head.get("Nr", 280), head.get("Status", 335)
            foot = min([w["top"] for w in words if w["text"] in ("Strona", "Wydrukowano")] or [page.height])
            rows = {}
            for w in words:
                if w["top"] >= foot - 3:
                    continue
                if w["top"] <= hdr_top + 5 or w["text"].startswith(("Strona", "Wydrukowano")):
                    continue
                rows.setdefault(round(w["top"]), []).append(w)
            tyre = None
            for top in sorted(rows):
                ws = sorted(rows[top], key=lambda w: w["x0"])
                if any(w["text"].startswith(("Wydrukowano", "Strona")) or w["text"] in ("czas", "czas:") for w in ws):
                    continue
                numw = next((w for w in ws if RE_NUM.match(w["text"])), None)
                if numw:  # nagłówek pozycji
                    plate = " ".join(w["text"] for w in ws if x_nr - 10 <= w["x0"] < x_stat - 5)
                    kontr = " ".join(w["text"] for w in ws if x_kontr - 5 <= w["x0"] < x_nr - 10)
                    stat = " ".join(w["text"] for w in ws if w["x0"] >= x_stat - 5 and not RE_DATE.match(w["text"]))
                    dates = [w for w in ws if RE_DATE.match(w["text"])]
                    cur = {"numer": numw["text"], "kontrahent": kontr, "nr_rej": plate.replace(" ", "").upper(),
                           "status": stat, "data_przyjecia": "", "data_wydania": "", "opony": [], "uwagi": ""}
                    # data przyjęcia jest bliżej lewej, wydania bliżej prawej
                    if dates:
                        mid = (x_stat + page.width) / 2 + 40
                        for d in dates:
                            key = "data_przyjecia" if d["x0"] < mid else "data_wydania"
                            cur[key] = d["text"]
                        if len(dates) == 2:
                            cur["data_przyjecia"], cur["data_wydania"] = dates[0]["text"], dates[1]["text"]
                    out["pozycje"].append(cur)
                    tyre = None
                    continue
                if cur is None:
                    continue
                line = " ".join(w["text"] for w in ws)
                if line.startswith("Uwagi"):
                    cur["uwagi"] = line
                    continue
                idx = next((w for w in ws if RE_IDX.match(w["text"]) and _col_of(w["x0"], bounds) == "Indeks"), None)
                if idx:
                    tyre = {c: "" for c in COLS}
                    tyre["Indeks"] = idx["text"]
                    cur["opony"].append(tyre)
                    ws = [w for w in ws if w is not idx]
                target = tyre
                if target is None:
                    # kontynuacja nazwy kontrahenta nad pierwszą oponą
                    continue
                for w in ws:
                    c = _col_of(w["x0"], bounds)
                    if c and c != "Indeks":
                        target[c] = (target[c] + " " + w["text"]).strip()
    for p in out["pozycje"]:
        for t in p["opony"]:
            # porządkowanie: Typ zawija się jako "1.osobow" + "e"
            t["Typ"] = t["Typ"].replace(" ", "")
            t["Felga"] = re.sub(r"aluminiow\s*a", "aluminiowa", re.sub(r"\s+", " ", t["Felga"])).strip()
            m = re.search(r"(\d+(?:,\d+)?)", t["Bieżnik"])
            t["bieznik_mm"] = float(m.group(1).replace(",", ".")) if m else None
            r = t["Rodzaj"].lower()
            t["rodzaj"] = "zimowa" if "zim" in r else "letnia" if "let" in r else "całoroczna" if "cał" in r else r
            t["rozmiar"] = _find_size(t["Rozmiar"].replace(" ", "")) or _find_size(t["Rozmiar"]) or _find_size(t["Nazwa"])
            t["Nazwa"] = re.sub(r"(?<=\w) (?=\w(\s|$))", "", t["Nazwa"]) if re.search(r"(\b\w ){3,}", t["Nazwa"]) else t["Nazwa"]
            if t["Lokalizacja"]:
                t["Lokalizacja"] = " ".join(x for x in t["Lokalizacja"].split() if not re.match(r"^\d\d:\d\d(:\d\d)?$|^\d{1,2}\.\d{2}\.\d{4}$", x))
        sizes = [t["rozmiar"] for t in p["opony"] if t["rozmiar"]]
        for t in p["opony"]:
            if not t["rozmiar"] and sizes:
                t["rozmiar"] = max(set(sizes), key=sizes.count)
        rodz = sorted({t["rodzaj"] for t in p["opony"] if t["rodzaj"]})
        p["rodzaj"] = "/".join(rodz)
        b = [t["bieznik_mm"] for t in p["opony"] if t["bieznik_mm"] is not None]
        p["bieznik_min"] = min(b) if b else None
        p["ilosc"] = len(p["opony"])
        lok = sorted({t["Lokalizacja"] for t in p["opony"] if t["Lokalizacja"] and t["Lokalizacja"] != "Wrocław"})
        p["lokalizacja_integra"] = ", ".join(lok)
    return out


RE_SIZE = re.compile(r"(\d{3})\s*[/ ]\s*(\d{2})\s*/*\s*[Zz]?[Rr]?\s*(\d{2})")


def _find_size(s):
    m = RE_SIZE.search(s or "")
    return f"{m.group(1)}/{m.group(2)} R{m.group(3)}" if m else ""


def _norm_size(s):
    return _find_size(s)


BIEZNIK_NISKI = 4.0   # mm – przy tylu i mniej pokazujemy „do oferty”
_PL = str.maketrans("ĄĆĘŁŃÓŚŹŻ", "ACELNOSZZ")


def _marka(s) -> str:
    return str(s or "").upper().translate(_PL)[:4]


def _data(s):
    """'2026-11-26' albo '26.11.2026' → date (None, gdy brak)."""
    s = str(s or "").strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def tryb(raport: dict, dzis=None) -> str:
    """'przygotowanie' – raport na dzisiaj lub do przodu, 'kontrola' – dni, które minęły,
    'okres' – zakres obejmujący przeszłość i przyszłość."""
    dzis = dzis or datetime.date.today()
    od, do = _data(raport.get("od")), _data(raport.get("do"))
    if od and od >= dzis:
        return "przygotowanie"
    if do and do < dzis:
        return "kontrola"
    return "okres"


def _opona_wzorcowa(opony: list) -> dict:
    """Opis kompletu z opony, której nazwy nie zakłóca zawinięta nazwa klienta (zwykle ostatnia)."""
    if not opony:
        return {}
    czyste = [t for t in opony if not re.search(r"[A-ZĄĆĘŁŃÓŚŹŻ]{6,}", t.get("Nazwa") or "")]
    return (czyste or opony)[-1]


def przygotuj(raport: dict, spis: list, dzis=None) -> list:
    """Wiersze listy: pozycja raportu + dopasowane pozycje spisu + uwagi. Posortowane trasą po regałach
    (dniami, gdy raport obejmuje kilka dni). Pozycje bez lokalizacji na końcu."""
    dzis = dzis or datetime.date.today()
    wynik = []
    for p in raport.get("pozycje", []):
        traf = szukaj.szukaj(spis, p["nr_rej"])
        if traf:
            najlepsze = traf[0][1]
            traf = [t for t in traf if t[1] == najlepsze][:3]
        if traf and traf[0][2] and traf[0][1] < szukaj.LITEROWKA - 10:   # słabe podobieństwo – tylko podpowiedź, bez lokalizacji
            podobne = ", ".join(t[0].get("nr", "") for t in traf)
            traf = []
        else:
            podobne = ""
        spis_poz = [t[0] for t in traf]
        przybl = bool(traf) and traf[0][2]
        opona = _opona_wzorcowa(p["opony"])
        uwagi = []
        if not spis_poz:
            uwagi.append("BRAK W SPISIE" + (f" (podobne: {podobne})" if podobne else ""))
        elif przybl:
            uwagi.append("≈ możliwa literówka – sprawdź numer")
        letnie = p.get("rodzaj") == "letnia"
        wyd, przyj = _data(p.get("data_wydania")), _data(p.get("data_przyjecia"))
        przyw = [s for s in spis_poz if s.get("przywiezione")]
        prod = _marka(opona.get("Producent"))
        if letnie:
            if wyd and przyj and przyj < wyd:
                uwagi.append("LETNIE do wydania")
            elif (wyd or przyj) and (wyd or przyj) <= dzis and spis_poz and not przyw:
                # klient zostawił letnie → zimowe ze spisu powinny być odhaczone
                uwagi.append("NIE odhaczone w spisie")
        else:
            if spis_poz and prod and not any(prod in (_marka(s.get("marka")), _marka(s.get("marka2"))) for s in spis_poz):
                uwagi.append(f"w spisie inna marka: {spis_poz[0].get('marka') or '—'}")
            if wyd and wyd >= dzis and przyw:
                uwagi.append("w spisie już odhaczone")
            if wyd and wyd < dzis and spis_poz and not przyw:
                uwagi.append("NIE odhaczone w spisie")
        if any(s.get("wyjasnic") for s in spis_poz):
            uwagi.append("do wyjaśnienia w spisie")
        if len({s.get("lok") for s in spis_poz}) > 1:
            uwagi.append("kilka lokalizacji")
        if p.get("bieznik_min") is not None and p["bieznik_min"] <= BIEZNIK_NISKI:
            uwagi.append(f"bieżnik {p['bieznik_min']:g} mm – do oferty")
        lok = ", ".join(dict.fromkeys(s.get("lok") or "?" for s in spis_poz))
        wynik.append({
            "raport": p, "spis": spis_poz, "lok": lok, "uwagi": uwagi,
            "dzien": p.get("data_wydania") or p.get("data_przyjecia") or "",
            "opis": f"{p.get('ilosc', 0)}× {(opona.get('Producent') or '').strip()} {(opona.get('Nazwa') or '').strip()}".strip(),
            "szczegoly": " · ".join(x for x in (opona.get("rozmiar"), p.get("rodzaj"), opona.get("Felga") or "bez felgi",
                                                 f"{p['bieznik_min']:g} mm" if p.get("bieznik_min") is not None else "") if x),
        })
    wynik.sort(key=lambda w: (_data(w["dzien"]) or datetime.date.max,
                              szukaj.klucz_lokalizacji(w["spis"][0].get("lok")) if w["spis"] else (10, "", 0, 0)))
    return wynik
