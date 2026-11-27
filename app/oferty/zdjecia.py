"""Zdjęcia felg w bazie (Supabase) – pracownicy nie logują się do xPartner (decyzja właściciela 2026-11-27).

Administrator, zalogowany w xPartner w programie, pobiera zdjęcia (ukryte okno przeglądarki), zmniejsza je do JPEG
i zapisuje w schowku „felgi-foto”: miniaturę do kafelków (<indeks>_m.jpg, ok. 280 px) i najwyżej 2 zdjęcia do PDF
(<indeks>_<n>.jpg, 640 px), z wierszem w tabeli xp_felgi_foto (pliki = ile zdjęć; 0 = xPartner nie ma zdjęcia).
Pracownicy czytają tylko z bazy. Zasady dostępu pilnuje baza (RLS).

Darmowy plan Supabase ma limit ruchu – dlatego Panel dostaje tylko miniatury (kilkanaście kB), pełne zdjęcia tylko
dla wybranych felg (PDF), a miniatury zostają na dysku komputera (pamięć podręczna, odświeżana po zmianie w bazie).
Moduł bez sieci i bez okna: dostęp do bazy przekazuje okno (funkcje w ZdjeciaBaza), tu tylko logika – łatwa do testów.
"""
import base64
import datetime
import os
import re
import threading
from pathlib import Path

MAX_ZDJEC = 2
PONOW_PO_DNIACH = 7       # felgi bez zdjęcia w xPartner – sprawdzane ponownie najwcześniej po tylu dniach
PAMIEC_MAX = 800          # miniatur w pamięci programu (ok. 15 kB każda)
PELNE_MAX = 30            # felg z pełnymi zdjęciami w pamięci
DYSK_MAX = 4000           # miniatur na dysku
JPEG = re.compile(r"data:image/jpeg;base64,([A-Za-z0-9+/]+={0,2})")
MAX_BAJTOW = 400_000      # limit schowka „felgi-foto”


def jpeg_z_data(u):
    """data:image/jpeg;base64,… -> bajty JPEG (albo None, gdy to nie JPEG albo za duży)."""
    m = JPEG.fullmatch(u) if isinstance(u, str) else None
    if not m:
        return None
    try:
        b = base64.b64decode(m.group(1), validate=True)
    except ValueError:
        return None
    return b if b[:3] == b"\xff\xd8\xff" and len(b) <= MAX_BAJTOW else None


def data_z_jpeg(b):
    return "data:image/jpeg;base64," + base64.b64encode(b).decode("ascii")


def _czas(t):
    try:
        return datetime.datetime.fromisoformat(str(t).replace("Z", "+00:00"))
    except ValueError:
        return datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)


def do_pobrania(wszystkie, wiersze, teraz=None):
    """Indeksy felg do pobrania przez administratora: nowe (bez wiersza) i bez zdjęcia sprawdzone ponad tydzień temu."""
    teraz = teraz or datetime.datetime.now(datetime.timezone.utc)
    znane = {int(w["id"]): w for w in wiersze or []}
    nowe, ponow = [], []
    for i in wszystkie:
        w = znane.get(int(i))
        if w is None:
            nowe.append(int(i))
        elif not int(w.get("pliki") or 0) and (teraz - _czas(w.get("sprawdzono"))).days >= PONOW_PO_DNIACH:
            ponow.append(int(i))
    return nowe + ponow


class ZdjeciaBaza:
    """wiersze(ids) -> [{id, pliki, sprawdzono}], pobierz(nazwa) -> bajty, wyslij(nazwa, bajty), zapisz_wiersz(id, pliki);
    dysk – folder na miniatury (pamięć podręczna; None = bez)."""

    def __init__(self, wiersze, pobierz, wyslij=None, zapisz_wiersz=None, dysk=None):
        self.wiersze, self.pobierz, self.wyslij, self.zapisz_wiersz = wiersze, pobierz, wyslij, zapisz_wiersz
        self.dysk = Path(dysk) if dysk else None
        self._mini = {}      # id -> (znacznik, data:) albo (znacznik, "") = brak zdjęcia
        self._pelne = {}     # id -> (znacznik, [data:])
        self._lock = threading.Lock()

    @staticmethod
    def _znacznik(w):
        return "%d_%s" % (int(w.get("pliki") or 0), re.sub(r"\D", "", str(w.get("sprawdzono") or ""))[:14])

    def _wpisz(self, slownik, i, wartosc, limit):
        with self._lock:
            slownik.pop(i, None)
            slownik[i] = wartosc
            while len(slownik) > limit:
                slownik.pop(next(iter(slownik)))

    def _z_dysku(self, i, zn):
        if not self.dysk:
            return None
        try:
            b = (self.dysk / ("%d_%s.jpg" % (i, zn))).read_bytes()
            return b if b[:3] == b"\xff\xd8\xff" else None
        except OSError:
            return None

    def _na_dysk(self, i, zn, b):
        if not self.dysk:
            return
        try:
            self.dysk.mkdir(parents=True, exist_ok=True)
            for stary in self.dysk.glob("%d_*.jpg" % i):
                stary.unlink()
            cel = self.dysk / ("%d_%s.jpg" % (i, zn))
            tmp = cel.with_suffix(".tmp")
            tmp.write_bytes(b)
            os.replace(tmp, cel)
            pliki = list(self.dysk.glob("*.jpg"))
            if len(pliki) > DYSK_MAX:
                for p in sorted(pliki, key=lambda p: p.stat().st_mtime)[:len(pliki) - DYSK_MAX]:
                    p.unlink()
        except OSError:
            pass

    def miniatury(self, ids):
        """({id: data:… albo ""}, wkrotce) – "" = xPartner nie ma zdjęcia; wkrotce = jeszcze nikt nie sprawdził."""
        ids = [int(x) for x in ids]
        if not ids:
            return {}, []
        znane = {int(w["id"]): w for w in self.wiersze(ids) or []}
        out, do_bazy = {}, []
        for i in ids:
            w = znane.get(i)
            if w is None:
                continue
            zn = self._znacznik(w)
            if not int(w.get("pliki") or 0):
                out[i] = ""
                continue
            m = self._mini.get(i)
            if m and m[0] == zn:
                out[i] = m[1]
                continue
            b = self._z_dysku(i, zn)
            if b:
                out[i] = data_z_jpeg(b)
                self._wpisz(self._mini, i, (zn, out[i]), PAMIEC_MAX)
            else:
                do_bazy.append((i, zn))
        if do_bazy:
            from concurrent.futures import ThreadPoolExecutor

            def jedna(x):
                i, zn = x
                try:
                    b = self.pobierz("%d_m.jpg" % i)
                except Exception:
                    b = None
                return i, zn, (b if b and b[:3] == b"\xff\xd8\xff" else None)
            with ThreadPoolExecutor(6) as ex:
                for i, zn, b in ex.map(jedna, do_bazy):
                    if b:
                        out[i] = data_z_jpeg(b)
                        self._wpisz(self._mini, i, (zn, out[i]), PAMIEC_MAX)
                        self._na_dysk(i, zn, b)
        return out, [i for i in ids if i not in znane]

    def pelne(self, ids):
        """{id: [data:…]} – zdjęcia do PDF, tylko dla wybranych felg (najwyżej 3 naraz)."""
        ids = [int(x) for x in ids][:3]
        out = {}
        for w in self.wiersze(ids) or []:
            i, zn = int(w["id"]), self._znacznik(w)
            m = self._pelne.get(i)
            if m and m[0] == zn:
                out[i] = m[1]
                continue
            lista = []
            for n in range(1, min(int(w.get("pliki") or 0), MAX_ZDJEC) + 1):
                try:
                    b = self.pobierz("%d_%d.jpg" % (i, n))
                except Exception:
                    b = None
                if b and b[:3] == b"\xff\xd8\xff":
                    lista.append(data_z_jpeg(b))
            out[i] = lista
            self._wpisz(self._pelne, i, (zn, lista), PELNE_MAX)
        return out

    def zapisz(self, i, obrazy, miniatura=None):
        """Administrator: zmniejszone zdjęcia felgi (data:image/jpeg) i miniatura -> schowek + wiersz.
        Zwraca miniaturę (data:) albo "" (felga bez zdjęcia)."""
        i = int(i)
        dobre = [b for b in (jpeg_z_data(u) for u in obrazy or []) if b][:MAX_ZDJEC]
        mini = jpeg_z_data(miniatura) or (dobre[0] if dobre else None)
        if dobre and mini:
            self.wyslij("%d_m.jpg" % i, mini)
            for n, b in enumerate(dobre, 1):
                self.wyslij("%d_%d.jpg" % (i, n), b)
        else:
            dobre = []
        self.zapisz_wiersz(i, len(dobre))
        with self._lock:
            self._mini.pop(i, None)
            self._pelne.pop(i, None)
        return data_z_jpeg(mini) if dobre else ""
