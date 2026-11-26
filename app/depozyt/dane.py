"""DEPOZYT: odczyt i zapis w bazie (tabele depozyt, depozyt_historia; zapis tylko funkcjami depozyt_zmien
i depozyt_dodaj – baza pilnuje modułu `depozyt` i oddziału, zapisuje kto i kiedy)."""
import urllib.parse

STRONA = 1000   # PostgREST oddaje najwyżej 1000 wierszy naraz


def _q(v) -> str:
    return urllib.parse.quote(str(v), safe="")


def pozycje(session, branch: str, sezon: str = "") -> list:
    out, offset = [], 0
    filtr = f"branch=eq.{_q(branch)}" + (f"&sezon=eq.{_q(sezon)}" if sezon else "")
    while True:
        rows = session.call("GET", f"/rest/v1/depozyt?select=*&{filtr}&order=id&limit={STRONA}&offset={offset}") or []
        out += rows
        if len(rows) < STRONA:
            return out
        offset += STRONA


def zmiany(session, branch: str, od: str) -> list:
    """Pozycje oddziału zmienione po chwili `od` (znacznik `zmieniono` z bazy) – małe zapytanie co kilka sekund."""
    return session.call("GET", f"/rest/v1/depozyt?select=*&branch=eq.{_q(branch)}&zmieniono=gt.{_q(od)}"
                               f"&order=zmieniono&limit={STRONA}") or []


def najnowsza_zmiana(rows: list) -> str:
    return max((r.get("zmieniono") or "" for r in rows), default="")


def zmien(session, id_: int, pole: str, wartosc) -> dict:
    if isinstance(wartosc, bool):
        wartosc = "1" if wartosc else "0"
    return session.rpc("depozyt_zmien", p_id=id_, p_pole=pole, p_wartosc=str(wartosc))


def dodaj(session, branch, sezon, nr, lok, marka, ilosc="", rodzaj="", uwagi="") -> dict:
    return session.rpc("depozyt_dodaj", p_branch=branch, p_sezon=sezon, p_nr=nr, p_lok=lok, p_marka=marka,
                       p_ilosc=ilosc, p_rodzaj=rodzaj, p_uwagi=uwagi)


def historia(session, id_: int | None = None, limit: int = 300) -> list:
    """Historia jednej pozycji albo ostatnie zmiany (z numerem i lokalizacją pozycji)."""
    filtr = f"&depozyt_id=eq.{int(id_)}" if id_ else ""
    return session.call("GET", f"/rest/v1/depozyt_historia?select=at,kto,co,depozyt(nr,lok)"
                               f"{filtr}&order=at.desc&limit={limit}") or []


def ustawienia(session, branch: str) -> dict:
    """Ustawienia depozytu oddziału (sezon na start, ukryte sezony, trasa, uprawnienia). Brak tabeli/wiersza = {}."""
    try:
        rows = session.call("GET", f"/rest/v1/depozyt_ustawienia?select=*&branch=eq.{_q(branch)}") or []
    except Exception:
        return {}
    return rows[0] if rows else {}


def zapisz_ustawienia(session, branch: str, u: dict) -> dict:
    r = session.rpc("depozyt_zapisz_ustawienia", p_branch=branch, p=u)
    return (r[0] if isinstance(r, list) and r else r) or {}


def lista_do_bazy(rap: dict, wiersze: list) -> dict:
    """Lista do przygotowania w postaci dla telefonu (bez nazw klientów): lokalizacja, numer, ilość, sezon, uwagi,
    id pozycji spisu (do „Przygotowane”)."""
    return {"tytul": rap.get("tytul", ""), "od": rap.get("od", ""), "do": rap.get("do", ""),
            "zrodlo": rap.get("zrodlo", ""),
            "wiersze": [{"nr": w["raport"].get("nr_rej", ""), "lok": w.get("lok", ""), "szt": w.get("szt", ""),
                         "sezon": w.get("sezon", ""), "dzien": w.get("dzien", ""),
                         "godzina": w["raport"].get("godzina", ""), "uwagi": w.get("uwagi", []),
                         "ids": [s.get("id") for s in w.get("spis", []) if s.get("id")]} for w in wiersze]}


def zapisz_liste(session, branch: str, rap: dict, wiersze: list):
    session.rpc("depozyt_zapisz_liste", p_branch=branch, p=lista_do_bazy(rap, wiersze))
