"""DEPOZYT: wyszukiwanie z literówkami, raport przechowalni z Integry (PDF w układzie FastReport, dane zmyślone)
i lista dla magazyniera."""
import datetime
import tempfile
from pathlib import Path

from _wspolne import temp_data  # noqa: F401 – ustawia ścieżkę do app/

SPIS = [
    {"id": 1, "nr": "DX9M934", "lok": "K5.1", "marka": "HANKOOK", "uwagi": "DX9M935", "przywiezione": False},
    {"id": 2, "nr": "DX8L367", "lok": "K1.2", "marka": "YOKOHAMA", "uwagi": "", "przywiezione": False},
    {"id": 3, "nr": "DX10001", "lok": "M2.1", "marka": "NOKIAN", "uwagi": "", "przywiezione": False},
    {"id": 4, "nr": "DX20002", "lok": "K12.3", "marka": "PIRELLI", "uwagi": "", "przywiezione": True},
    {"id": 5, "nr": "DX30003", "lok": "KPOK", "marka": "MICHELIN", "uwagi": "", "przywiezione": False,
     "komentarz": "felgi w worku"},
    {"id": 6, "nr": "DX30003", "lok": "K40.1", "marka": "MICHELIN", "uwagi": "", "przywiezione": False},
]


def test_szukanie_z_literowkami():
    from depozyt import szukaj
    nr = lambda q: [p["nr"] for p, _, _ in szukaj.szukaj(SPIS, q)]   # noqa: E731
    assert nr("DX9M934")[0] == "DX9M934"
    assert nr("dx 9m9")[0] == "DX9M934"                     # fragment, spacje, małe litery
    assert nr("DX9M93A")[0] == "DX9M934"                     # jedna zła litera
    assert nr("DXBL367")[0] == "DX8L367"                     # B zamiast 8
    assert nr("K12.3") == ["DX20002"]                        # lokalizacja
    assert nr("worku") == ["DX30003"]                        # komentarz
    assert nr("ZZ") == []
    p, pkt, fz = szukaj.szukaj(SPIS, "DX9M93A")[0]
    assert fz and pkt < szukaj.FRAGMENT
    assert szukaj.szukaj(SPIS, "DX9M934")[0][2] is False


def test_kolejnosc_obchodu():
    from depozyt import szukaj
    lok = ["MAGOPIS", "M8/10", "K12.3", "K1.4", "KPOK", "K2.1", "M2.1"]
    assert sorted(lok, key=szukaj.klucz_lokalizacji) == ["K1.4", "K2.1", "K12.3", "M2.1", "M8/10", "KPOK", "MAGOPIS"]


def _raport_pdf(path, pozycje, od="2026-11-26", do="2026-11-26"):
    """PDF w układzie raportu Integry: te same kolumny (pozycje x jak w prawdziwym wydruku), zawijana nazwa firmy."""
    from reportlab.pdfgen import canvas
    c = canvas.Canvas(str(path), pagesize=(595, 842))

    def t(x, top, s, size=7):
        c.setFont("Helvetica", size)
        c.drawString(x, 842 - top - size, s)
    t(59, 31, "LATEX SERWIS Sp. z o.o.", 9)
    t(138, 73, "Rejestr opon do wydania wg umówionych terminów".encode("latin-1", "replace").decode("latin-1"), 11)
    t(217, 96, f"Zakres dat: od {od} do {do}", 9)
    for x, s in ((62, "Lp."), (85, "Numer"), (144, "Kontrahent"), (283, "Nr"), (294, "rej."), (337, "Status"),
                 (456, "Data"), (475, "przyjecia"), (513, "Data"), (532, "wydania")):
        t(x, 135, s)
    for x, s in ((73, "Indeks"), (119, "Nazwa"), (218, "Rozmiar"), (266, "Producent"), (317, "Typ"), (357, "Rodzaj"),
                 (394, "Felga"), (437, "Bieżnik"), (477, "DOT"), (506, "Lokalizacja")):
        t(x, 147, s)
    top = 161
    for i, p in enumerate(pozycje, 1):
        t(59, top, f"{i}.")
        t(85, top, f"{100 + i}/PO/11/26")
        t(144, top, p["klient"])
        t(283, top, p["nr"])
        t(337, top, "Przyjeto do przechowalni")
        t(456, top, p["przyj"])
        t(513, top, p["wyd"])
        for k in range(p.get("ilosc", 4)):
            top += 11
            t(73, top, str(300000 + i * 10 + k))
            t(119, top, p["model"])
            if k == 0:
                t(150, top + 6, "ODPOWIEDZIALNOSCIA")      # zawinięta nazwa klienta – nie może trafić do modelu
            t(218, top, p["rozmiar"])
            t(266, top, p["producent"])
            t(317, top, "1.osobowe")
            t(357, top, p["rodzaj"])
            t(394, top, "brak felgi")
            t(437, top, f"{p['bieznik']} mm")
            t(477, top, "2524")
            t(506, top, "Wrocław".encode("latin-1", "replace").decode("latin-1"))
        top += 16
    t(250, 800, "Strona 1 z 1")
    c.save()


POZ = [
    {"nr": "DX10001", "klient": "FIRMA A SPOLKA Z", "przyj": "8.05.2026", "wyd": "26.11.2026", "model": "Snowproof 2",
     "rozmiar": "215/65R17", "producent": "Nokian", "rodzaj": "zimowa", "bieznik": 7},
    {"nr": "DX20002", "klient": "Jan Testowy", "przyj": "8.04.2026", "wyd": "26.11.2026", "model": "Winter 2",
     "rozmiar": "225 45 18", "producent": "Pirelli", "rodzaj": "zimowa", "bieznik": 4},
    {"nr": "DX9M93A", "klient": "Anna Testowa", "przyj": "3.04.2026", "wyd": "26.11.2026", "model": "Icept",
     "rozmiar": "205/55r16", "producent": "Continental", "rodzaj": "zimowa", "bieznik": 6},
    {"nr": "PO99999", "klient": "Brak W Spisie", "przyj": "3.04.2026", "wyd": "26.11.2026", "model": "Alpin 6",
     "rozmiar": "205/55R16", "producent": "Michelin", "rodzaj": "zimowa", "bieznik": 6, "ilosc": 2},
    {"nr": "DX30003", "klient": "Dwa Miejsca", "przyj": "3.11.2025", "wyd": "26.11.2026", "model": "Pilot Sport",
     "rozmiar": "235/35ZR19", "producent": "Michelin", "rodzaj": "letnia", "bieznik": 5},
]


def test_raport_integry_i_lista_dla_magazyniera():
    from depozyt import raport
    pdf = Path(tempfile.mkdtemp()) / "raport.pdf"
    _raport_pdf(pdf, POZ)
    r = raport.parse(pdf)
    assert (r["od"], r["do"]) == ("2026-11-26", "2026-11-26")
    assert [p["nr_rej"] for p in r["pozycje"]] == [p["nr"] for p in POZ]
    p0 = r["pozycje"][0]
    assert p0["ilosc"] == 4 and p0["rodzaj"] == "zimowa" and p0["bieznik_min"] == 7
    assert p0["data_przyjecia"] == "8.05.2026" and p0["data_wydania"] == "26.11.2026"
    assert p0["opony"][0]["rozmiar"] == "215/65 R17" and r["pozycje"][1]["opony"][0]["rozmiar"] == "225/45 R18"
    assert r["pozycje"][4]["opony"][0]["rozmiar"] == "235/35 R19"
    assert r["pozycje"][3]["ilosc"] == 2

    dzis = datetime.date(2026, 11, 25)
    assert raport.tryb(r, dzis) == "przygotowanie"
    assert raport.tryb(r, datetime.date(2026, 11, 27)) == "kontrola"
    w = raport.przygotuj(r, SPIS, dzis)
    po_nr = {x["raport"]["nr_rej"]: x for x in w}
    assert [x["lok"] for x in w][:3] == ["K5.1", "K12.3", "M2.1"]          # trasa po regałach, brak na końcu
    assert w[-1]["raport"]["nr_rej"] == "PO99999" and "BRAK W SPISIE" in w[-1]["uwagi"]
    assert po_nr["DX10001"]["uwagi"] == [] and "ODPOWIEDZIALNO" not in po_nr["DX10001"]["opis"]
    assert "Snowproof 2" in po_nr["DX10001"]["opis"]
    u = po_nr["DX20002"]["uwagi"]
    assert "w spisie już odhaczone" in u and any("bieżnik 4 mm" in x for x in u)
    u = po_nr["DX9M93A"]["uwagi"]
    assert any("literówka" in x for x in u) and any("inna marka" in x for x in u)
    assert po_nr["DX30003"]["lok"] == "KPOK, K40.1" and "LETNIE do wydania" in po_nr["DX30003"]["uwagi"]
    assert "kilka lokalizacji" in po_nr["DX30003"]["uwagi"]


def test_filtry_i_statystyki_zakladki():
    from depozyt import zakladka
    teraz = datetime.datetime.now(datetime.timezone.utc).isoformat()
    rows = [dict(p) for p in SPIS]
    rows[0].update(przywiezione=True, przywiezione_at=teraz, przywiezione_kto="Jan")
    rows[2]["wyjasnic"] = True
    s = zakladka.statystyki(rows)
    assert (s["wszystkie"], s["przywiezione"], s["zostalo"], s["dzis"], s["wyjasnic"]) == (6, 2, 4, 1, 1)
    assert len(zakladka.filtruj(rows, "", "Nieprzywiezione", "")) == 4
    assert [p["nr"] for p, _ in zakladka.filtruj(rows, "", "Przywiezione dziś", "")] == ["DX9M934"]
    assert len(zakladka.filtruj(rows, "", "Wszystkie", "KPOK")) == 1
    assert zakladka.opis_przywiezienia(rows[3]) == "wg Excela"
    assert zakladka.opis_przywiezienia(rows[0]).endswith("Jan")
    assert zakladka.esc("<a&'>") == "&lt;a&amp;&#39;&gt;"


def test_harmonogram_wizyt_excel():
    """Excel z harmonogramem wizyt (jak eksport z Integry): pomija wpisy techniczne, łączy ze spisem."""
    import openpyxl
    from depozyt import raport
    p = Path(tempfile.mkdtemp()) / "wizyty.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append([""] * 9)
    ws.append(["Termin od", "Termin do", "Nr rej. / Nr seryjny", "Marka / Rodzaj", "Model / Marka", "Wersja / Model",
               "Rok produkcji", "Kontrahent", "Telefon"])
    ws.append(["2026-11-26 17:30", "2026-11-26 18:00", "DX10001", "OPEL", "......................", "", "", "Jan", ""])
    ws.append(["2026-11-26 16:30", "2026-11-26 17:00", "CZK_OPONY", "", "", "", "", "Latex", ""])
    ws.append(["2026-11-26 08:00", "2026-11-26 08:30", "DX 9M934", "KIA", "XCEED", "", "", "Anna", ""])
    ws.append(["2026-11-26 09:00", "2026-11-26 09:30", "PO77777", "FORD", "FOCUS", "", "", "Obcy", ""])
    wb.save(p)
    r = raport.wczytaj(p)
    assert r["zrodlo"] == "terminy" and (r["od"], r["do"]) == ("2026-11-26", "2026-11-26")
    assert [x["nr_rej"] for x in r["pozycje"]] == ["DX10001", "DX9M934", "PO77777"]
    assert r["pozycje"][0]["godzina"] == "17:30" and r["pozycje"][0]["auto"] == "OPEL"
    w = raport.przygotuj(r, SPIS, datetime.date(2026, 11, 25))
    assert [x["lok"] for x in w] == ["K5.1", "M2.1", ""]
    assert w[-1]["uwagi"] == [raport.BRAK_OPON] and "auto: KIA XCEED" in w[0]["opis"]


def test_xls_bledny_plik():
    from depozyt import xls
    p = Path(tempfile.mkdtemp()) / "zly.xls"
    p.write_bytes(b"to nie jest excel")
    try:
        xls.wiersze(p)
        assert False, "powinien być błąd"
    except xls.XlsError:
        pass
