"""Odczyt starego formatu Excela (.xls, BIFF8) bez dodatkowych bibliotek – tylko pierwszy arkusz, wartości komórek.

Integra eksportuje harmonogram wizyt jako .xls; w paczce programu nie ma biblioteki xlrd (CLAUDE.md, zasada 2),
więc czytamy plik sami: kontener OLE2 (Compound File) → strumień „Workbook” → rekordy BIFF8 (SST, LABELSST,
LABEL, NUMBER, RK, MULRK). Pliki .xlsx czyta openpyxl (`wiersze()`).
"""
import struct

_KONIEC = (0xFFFFFFFE, 0xFFFFFFFF)   # ENDOFCHAIN, FREESECT


class XlsError(ValueError):
    pass


def _strumien_ole(dane: bytes, nazwy=("Workbook", "Book")) -> bytes:
    if dane[:8] != b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        raise XlsError("To nie jest plik Excel (.xls).")
    sekt = 1 << struct.unpack_from("<H", dane, 30)[0]
    mini_sekt = 1 << struct.unpack_from("<H", dane, 32)[0]
    n_fat, kat_start, mini_cutoff, mini_fat_start, n_mini_fat, difat_start, n_difat = struct.unpack_from(
        "<I I 4x I I I I I", dane, 44)

    def sektor(i):
        o = 512 + i * sekt
        return dane[o:o + sekt]

    difat = list(struct.unpack_from("<109I", dane, 76))
    s = difat_start
    for _ in range(n_difat):
        if s in _KONIEC:
            break
        blok = struct.unpack(f"<{sekt // 4}I", sektor(s))
        difat += blok[:-1]
        s = blok[-1]
    fat = []
    for f in difat[:n_fat]:
        if f not in _KONIEC:
            fat += struct.unpack(f"<{sekt // 4}I", sektor(f))

    def lancuch(start, tablica, czytaj):
        out, s, ile = [], start, 0
        while s not in _KONIEC and s < len(tablica) and ile < len(tablica) + 1:
            out.append(czytaj(s))
            s, ile = tablica[s], ile + 1
        return b"".join(out)

    katalog = lancuch(kat_start, fat, sektor)
    wpisy = []
    for o in range(0, len(katalog) - 127, 128):
        dl = struct.unpack_from("<H", katalog, o + 64)[0]
        nazwa = katalog[o:o + max(dl - 2, 0)].decode("utf-16-le", "replace")
        typ = katalog[o + 66]
        start, rozmiar = struct.unpack_from("<I I", katalog, o + 116)
        wpisy.append((nazwa, typ, start, rozmiar))
    root = next((w for w in wpisy if w[1] == 5), None)
    wpis = next((w for w in wpisy if w[0] in nazwy and w[1] == 2), None)
    if wpis is None:
        raise XlsError("W pliku nie ma arkusza Excela.")
    _, _, start, rozmiar = wpis
    if rozmiar >= mini_cutoff or root is None:
        return lancuch(start, fat, sektor)[:rozmiar]
    mini_strumien = lancuch(root[2], fat, sektor)
    mini_fat = []
    if n_mini_fat:
        b = lancuch(mini_fat_start, fat, sektor)
        mini_fat = list(struct.unpack(f"<{len(b) // 4}I", b))
    return lancuch(start, mini_fat, lambda i: mini_strumien[i * mini_sekt:(i + 1) * mini_sekt])[:rozmiar]


def _rk(v: int) -> float:
    if v & 2:
        x = float(v >> 2) if not v & 0x80000000 else float((v >> 2) - (1 << 30))
    else:
        x = struct.unpack("<d", struct.pack("<Q", (v & 0xFFFFFFFC) << 32))[0]
    return x / 100 if v & 1 else x


def _napis(buf: bytes, o: int, dl_bajty=2):
    """Napis BIFF8 (LABEL): długość, flagi, znaki. Zwraca (tekst, nowe przesunięcie)."""
    n = struct.unpack_from("<H" if dl_bajty == 2 else "<B", buf, o)[0]
    o += dl_bajty
    fl = buf[o]
    o += 1
    runs = ext = 0
    if fl & 8:
        runs = struct.unpack_from("<H", buf, o)[0]
        o += 2
    if fl & 4:
        ext = struct.unpack_from("<I", buf, o)[0]
        o += 4
    if fl & 1:
        t = buf[o:o + 2 * n].decode("utf-16-le", "replace")
        o += 2 * n
    else:
        t = buf[o:o + n].decode("latin-1")
        o += n
    return t, o + 4 * runs + ext


def _sst(czesci: list) -> list:
    """Tablica napisów; napis może przechodzić na kolejny rekord CONTINUE (wtedy nowy bajt flag)."""
    out = []
    ci, buf = 0, czesci[0]
    o = 8

    def dalej():
        nonlocal ci, buf, o
        ci += 1
        buf, o = czesci[ci], 0

    ile = struct.unpack_from("<I", buf, 4)[0]
    while len(out) < ile:
        if o >= len(buf):
            if ci + 1 >= len(czesci):
                break
            dalej()
        n = struct.unpack_from("<H", buf, o)[0]
        fl = buf[o + 2]
        o += 3
        runs = ext = 0
        if fl & 8:
            runs = struct.unpack_from("<H", buf, o)[0]
            o += 2
        if fl & 4:
            ext = struct.unpack_from("<I", buf, o)[0]
            o += 4
        zebrane, szer = "", 2 if fl & 1 else 1
        while len(zebrane) < n:
            if o >= len(buf):
                if ci + 1 >= len(czesci):
                    break
                dalej()
                szer = 2 if buf[o] & 1 else 1
                o += 1
            ile_tu = min(n - len(zebrane), (len(buf) - o) // szer)
            if ile_tu <= 0:
                break
            kawal = buf[o:o + ile_tu * szer]
            zebrane += kawal.decode("utf-16-le", "replace") if szer == 2 else kawal.decode("latin-1")
            o += ile_tu * szer
        out.append(zebrane)
        reszta = 4 * runs + ext
        while reszta > 0:
            tu = min(reszta, len(buf) - o)
            o += tu
            reszta -= tu
            if reszta > 0:
                if ci + 1 >= len(czesci):
                    break
                dalej()
    return out


def czytaj_xls(sciezka) -> list:
    """Pierwszy arkusz jako lista wierszy (lista wartości; puste komórki = '')."""
    with open(sciezka, "rb") as fh:
        wb = _strumien_ole(fh.read())
    o, sst, sst_czesci, w_sst = 0, [], [], False
    komorki, arkusz = {}, 0   # arkusz: 0 – przed, 1 – pierwszy arkusz, 2 – po
    while o + 4 <= len(wb):
        typ, dl = struct.unpack_from("<HH", wb, o)
        rec = wb[o + 4:o + 4 + dl]
        o += 4 + dl
        if typ == 0x00FC:
            sst_czesci, w_sst = [rec], True
            continue
        if typ == 0x003C and w_sst:
            sst_czesci.append(rec)
            continue
        if w_sst:
            sst, w_sst = _sst(sst_czesci), False
        if typ == 0x0809 and len(rec) >= 4:
            if struct.unpack_from("<H", rec, 2)[0] == 0x0010 and arkusz == 0:
                arkusz = 1
            continue
        if typ == 0x000A and arkusz == 1:
            arkusz = 2
            break
        if arkusz != 1:
            continue
        if typ == 0x00FD:
            r, c, _, i = struct.unpack_from("<HHHI", rec)
            komorki[(r, c)] = sst[i] if i < len(sst) else ""
        elif typ == 0x0204:
            r, c, _ = struct.unpack_from("<HHH", rec)
            komorki[(r, c)] = _napis(rec, 6)[0]
        elif typ == 0x0203:
            r, c, _, v = struct.unpack_from("<HHHd", rec)
            komorki[(r, c)] = v
        elif typ == 0x027E:
            r, c, _, v = struct.unpack_from("<HHHI", rec)
            komorki[(r, c)] = _rk(v)
        elif typ == 0x00BD:
            r, c0 = struct.unpack_from("<HH", rec)
            n = (len(rec) - 6) // 6
            for k in range(n):
                _, v = struct.unpack_from("<HI", rec, 4 + 6 * k)
                komorki[(r, c0 + k)] = _rk(v)
    if not komorki:
        return []
    nr, nc = max(r for r, _ in komorki) + 1, max(c for _, c in komorki) + 1
    return [[komorki.get((r, c), "") for c in range(nc)] for r in range(nr)]


def wiersze(sciezka) -> list:
    """.xls lub .xlsx → lista wierszy pierwszego arkusza."""
    with open(sciezka, "rb") as fh:
        poczatek = fh.read(8)
    if poczatek.startswith(b"PK"):
        import openpyxl
        wb = openpyxl.load_workbook(sciezka, read_only=True, data_only=True)
        try:
            return [["" if v is None else v for v in r] for r in wb.worksheets[0].iter_rows(values_only=True)]
        finally:
            wb.close()
    return czytaj_xls(sciezka)
