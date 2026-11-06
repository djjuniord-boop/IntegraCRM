"""Synchronizacja pliku ofertowego xPartner (CSV) -> tabela xp_oferta w Supabase.

Uruchamia GitHub Actions (.github/workflows/xp_oferta.yml) co 30 min w godzinach pracy.
Zmienne środowiska (sekrety repozytorium – nigdy w kodzie ani w logach):
  XPARTNER_OFERTA_URL        link z xPartner (Pobierz → Pobieranie oferty; CSV, UTF-8, OPONY, wszystkie kolumny)
  SUPABASE_SERVICE_ROLE_KEY  klucz serwisowy (zapis do tabeli; zwykłe konta mogą ją tylko czytać)
Repozytorium jest publiczne – skrypt wypisuje wyłącznie liczby, nigdy linku, nazw ani cen.

Tryb testowy (bez sieci): python tools/xp_oferta_sync.py --plik oferta.csv --tylko-odczyt
"""
import argparse
import csv
import datetime
import hashlib
import io
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

SB_URL = "https://nlrwulrtaocuemfmlfav.supabase.co"
TABELA = "xp_oferta"
# kolumny pliku, które nie są cechami produktu (reszta = „cechy” jak w API: Producent, Sezon, Klasa, Opory toczenia…)
STALE = {"LP", "Indeks", "Kod produktu", "Nazwa", "Ilość", "Cena katalogowa netto[pln]", "Cena katalogowa brutto[pln]",
         "Cena zakupu netto[pln]", "Cena zakupu brutto[pln]", "Waga", "Objętość", "EAN1", "EAN2", "EAN3", "EAN4", "EAN5"}
WYMAGANE = ("Indeks", "Nazwa", "Ilość", "Cena zakupu netto[pln]", "Szerokość", "Profil", "Średnica")
MIN_UDZIAL = 0.5   # plik mniejszy niż połowa obecnej tabeli = podejrzany (np. ucięty) – nic nie usuwamy


class Blad(Exception):
    pass


def _num(v):
    try:
        return float(str(v).replace(",", ".").strip() or 0)
    except ValueError:
        return 0.0


def _int(v):
    m = re.search(r"\d+", str(v or ""))
    return int(m.group(0)) if m else 0


def _rozmiar(v):
    """'R16' -> 16, 'R22,5' -> 22.5, '-15' -> 15, '' -> None."""
    m = re.search(r"(\d+(?:[.,]\d+)?)", str(v or ""))
    return float(m.group(1).replace(",", ".")) if m else None


def czytaj_csv(dane: bytes):
    """CSV xPartner -> lista produktów w tym samym kształcie co silnik.parse_products (API)."""
    tekst = dane.decode("utf-8-sig", errors="replace")
    r = csv.DictReader(io.StringIO(tekst, newline=""), delimiter=";")
    brak = [k for k in WYMAGANE if k not in (r.fieldnames or [])]
    if brak:
        raise Blad("Plik nie ma wymaganych kolumn (%d) – sprawdź konfigurację linku w xPartner (CSV, wszystkie kolumny)." % len(brak))
    magazyny = [k for k in r.fieldnames if k.startswith("Ilość ")]
    out = []
    for w in r:
        pid = _int(w.get("Indeks"))
        netto = _num(w.get("Cena zakupu netto[pln]"))
        if not pid or netto <= 0:          # cena 0 = niedostępne do zamówienia (jak w API)
            continue
        attrs = {k: (w.get(k) or "").strip() for k in r.fieldnames if k not in STALE and not k.startswith("Ilość ") and (w.get(k) or "").strip()}
        p = {
            "id": pid, "kod": (w.get("Kod produktu") or "").strip(), "ean": (w.get("EAN1") or "").strip(), "foto": "",
            "pola": ["plik"], "nazwa": (w.get("Nazwa") or "").strip(), "ilosc": _int(w.get("Ilość")),
            "netto": netto, "brutto_zak": _num(w.get("Cena zakupu brutto[pln]")), "netto_kat": _num(w.get("Cena katalogowa netto[pln]")),
            "attrs": attrs, "magazyny": {k[6:]: _int(w.get(k)) for k in magazyny},
        }
        out.append({"id": pid, "szer": _int(w.get("Szerokość")) or None, "profil": _rozmiar(w.get("Profil")),
                    "sred": _rozmiar(w.get("Średnica")), "ilosc": p["ilosc"], "dane": p,
                    "h": hashlib.sha1(json.dumps(p, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]})
    return out


def _http(method, path, key, body=None, prefer=None, timeout=120):
    h = {"apikey": key, "Authorization": "Bearer " + key, "Content-Type": "application/json"}
    if prefer:
        h["Prefer"] = prefer
    req = urllib.request.Request(SB_URL + path, method=method, headers=h,
                                 data=None if body is None else json.dumps(body, ensure_ascii=False).encode())
    for proba in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                t = r.read()
                return json.loads(t) if t else None
        except urllib.error.HTTPError as e:
            if e.code < 500 or proba == 2:
                raise Blad("Baza odpowiedziała błędem %d (%s)" % (e.code, path.split("?")[0]))
        except OSError:
            if proba == 2:
                raise Blad("Brak połączenia z bazą (%s)" % path.split("?")[0])
        time.sleep(3 * (proba + 1))


def pobierz_plik(url):
    if not url.startswith("https://"):
        raise Blad("XPARTNER_OFERTA_URL musi zaczynać się od https://")
    req = urllib.request.Request(url, headers={"User-Agent": "PanelLatexSerwis-OfertaSync"})
    for proba in range(3):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                return r.read()
        except Exception as e:   # bez treści błędu – mogłaby zawierać link
            if proba == 2:
                raise Blad("Nie udało się pobrać pliku z xPartner (%s)" % e.__class__.__name__)
            time.sleep(10 * (proba + 1))


def synchronizuj(rows, key):
    teraz = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    stare = {}
    od = 0
    while True:   # obecne wpisy: id -> skrót (bez danych)
        part = _http("GET", "/rest/v1/%s?select=id,h&order=id&limit=1000&offset=%d" % (TABELA, od), key) or []
        stare.update({x["id"]: x["h"] for x in part})
        if len(part) < 1000:
            break
        od += 1000
    if stare and len(rows) < MIN_UDZIAL * len(stare):
        raise Blad("Plik ma %d pozycji, a tabela %d – podejrzanie mało, nic nie zmieniam." % (len(rows), len(stare)))
    zmiany = [dict(r, updated_at=teraz) for r in rows if stare.get(r["id"]) != r["h"]]
    for i in range(0, len(zmiany), 500):
        _http("POST", "/rest/v1/%s?on_conflict=id" % TABELA, key, zmiany[i:i + 500], prefer="resolution=merge-duplicates,return=minimal")
    nowe = {r["id"] for r in rows}
    usun = sorted(i for i in stare if i not in nowe)   # zniknęły z oferty xPartner
    for i in range(0, len(usun), 200):
        _http("DELETE", "/rest/v1/%s?id=in.(%s)" % (TABELA, ",".join(map(str, usun[i:i + 200]))), key, prefer="return=minimal")
    stan = {"czas": teraz, "ile": len(rows), "zmienione": len(zmiany), "usuniete": len(usun)}
    _http("POST", "/rest/v1/app_config?on_conflict=key", key, {"key": "xp_oferta_stan", "value": stan},
          prefer="resolution=merge-duplicates,return=minimal")
    return stan


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plik", help="lokalny CSV zamiast pobierania (testy)")
    ap.add_argument("--tylko-odczyt", action="store_true", help="tylko odczytaj plik i pokaż liczby")
    a = ap.parse_args()
    try:
        dane = open(a.plik, "rb").read() if a.plik else pobierz_plik(os.environ.get("XPARTNER_OFERTA_URL", "").strip())
        rows = czytaj_csv(dane)
        print("Plik: %d opon z ceną" % len(rows))
        if a.tylko_odczyt:
            return 0
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        if not key:
            raise Blad("Brak SUPABASE_SERVICE_ROLE_KEY")
        s = synchronizuj(rows, key)
        print("Tabela: %(ile)d opon, zmienione %(zmienione)d, usunięte %(usuniete)d" % s)
        return 0
    except Blad as e:
        print("BŁĄD: %s" % e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
