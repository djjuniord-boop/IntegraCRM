"""Zdjęcia felg w bazie (Supabase) – pracownicy nie logują się do xPartner (decyzja właściciela 2026-11-27).

Administrator, zalogowany w xPartner w programie, pobiera zdjęcia (ukryte okno przeglądarki), zmniejsza je do JPEG
i zapisuje w schowku „felgi-foto” (<indeks>_<n>.jpg, najwyżej 3) z wierszem w tabeli xp_felgi_foto (ile zdjęć, kiedy
sprawdzono; 0 = xPartner nie ma zdjęcia). Pracownicy czytają tylko z bazy. Zasady dostępu pilnuje baza (RLS).

Moduł bez sieci i bez okna: dostęp do bazy przekazuje okno (funkcje w ZdjeciaBaza), tu tylko logika – łatwa do testów.
"""
import base64
import datetime
import re
import threading

MAX_ZDJEC = 3
PONOW_PO_DNIACH = 7       # felgi bez zdjęcia w xPartner – sprawdzane ponownie najwcześniej po tylu dniach
PAMIEC_MAX = 600          # felg w pamięci programu (zdjęcia jako data:)
JPEG = re.compile(r"^data:image/jpeg;base64,([A-Za-z0-9+/=]+)$")
MAX_BAJTOW = 400_000      # limit schowka „felgi-foto”


def jpeg_z_data(u):
    """data:image/jpeg;base64,… -> bajty JPEG (albo None, gdy to nie JPEG albo za duży)."""
    m = JPEG.match(u or "") if isinstance(u, str) else None
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
    """wiersze(ids) -> [{id, pliki, sprawdzono}], pobierz(nazwa) -> bajty, wyslij(nazwa, bajty), zapisz_wiersz(id, pliki)."""

    def __init__(self, wiersze, pobierz, wyslij=None, zapisz_wiersz=None):
        self.wiersze, self.pobierz, self.wyslij, self.zapisz_wiersz = wiersze, pobierz, wyslij, zapisz_wiersz
        self._pamiec = {}
        self._lock = threading.Lock()

    def _zapamietaj(self, i, lista):
        with self._lock:
            self._pamiec[i] = lista
            while len(self._pamiec) > PAMIEC_MAX:
                self._pamiec.pop(next(iter(self._pamiec)))

    def z_bazy(self, ids):
        """({id: [data:…]}, brak) – brak: indeksy, których jeszcze nikt nie sprawdził (zdjęcie „wkrótce”).
        Felga sprawdzona bez zdjęcia w xPartner -> pusta lista."""
        ids = [int(x) for x in ids]
        with self._lock:
            out = {i: self._pamiec[i] for i in ids if i in self._pamiec}
        reszta = [i for i in ids if i not in out]
        if not reszta:
            return out, []
        znane = {int(w["id"]): int(w.get("pliki") or 0) for w in self.wiersze(reszta) or []}
        from concurrent.futures import ThreadPoolExecutor

        def jedna(i):
            lista = []
            for n in range(1, min(znane[i], MAX_ZDJEC) + 1):
                try:
                    b = self.pobierz("%d_%d.jpg" % (i, n))
                except Exception:
                    b = None
                if b and b[:3] == b"\xff\xd8\xff":
                    lista.append(data_z_jpeg(b))
            return i, lista
        with ThreadPoolExecutor(6) as ex:
            for i, lista in ex.map(jedna, [i for i in reszta if i in znane]):
                out[i] = lista
                if lista or not znane[i]:
                    self._zapamietaj(i, lista)
        return out, [i for i in reszta if i not in znane]

    def zapisz(self, i, obrazy):
        """Administrator: zmniejszone zdjęcia felgi (data:image/jpeg) -> schowek + wiersz. Zwraca zapisane data:."""
        i = int(i)
        dobre = [b for b in (jpeg_z_data(u) for u in obrazy or []) if b][:MAX_ZDJEC]
        for n, b in enumerate(dobre, 1):
            self.wyslij("%d_%d.jpg" % (i, n), b)
        self.zapisz_wiersz(i, len(dobre))
        lista = [data_z_jpeg(b) for b in dobre]
        self._zapamietaj(i, lista)
        return lista
