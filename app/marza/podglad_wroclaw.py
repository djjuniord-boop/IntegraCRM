#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GENERUJ PODGLĄD DLA HANDLOWCÓW
================================
Bierze zaktualizowany plik kalkulator_marzy_latex.xlsx (po aktualizacji
danymi z PDF) i tworzy z niego UPROSZCZONY plik podglądowy:
  - panel WYNIK z rozwijaną listą wyboru miesiąca (handlowcy mogą sami
    przełączać, który miesiąc chcą zobaczyć)
  - dane wszystkich miesięcy są w UKRYTYM arkuszu pomocniczym (nie widać
    tabeli do edycji - tylko wynik i lista wyboru)
  - CAŁY arkusz główny zablokowany przed edycją poza samą komórką wyboru
    miesiąca - handlowcy nie mogą zmienić celu, wyniku, ani niczego innego
  - wartości w ukrytej tabeli danych są "zamrożone" (liczby, nie formuły
    odwołujące się do głównego kalkulatora) - plik podglądowy jest w pełni
    samodzielny i nie psuje się, jeśli główny plik zniknie/zmieni nazwę

Wywoływany automatycznie na końcu aktualizuj_kalkulator.py.
"""
import os
import datetime
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side, Protection
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.formatting.rule import FormulaRule

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Skrypt mieszka w podfolderze "silnik". Dane (kalkulator, gotowy podglad)
# leza PIETRO WYZEJ, w glownym folderze roboczym - stad BASE_DIR.
# Przy skrypcie zostaja tylko rzeczy techniczne: logo wklejane w naglowek
# i plik CSV dla Arkusza Google.
BASE_DIR = os.path.dirname(SCRIPT_DIR)
SRC_XLSX = os.path.join(BASE_DIR, "kalkulator_marzy_Wroclaw.xlsx")
OUT_NAME = "PODGLAD_dla_handlowcow_Wroclaw.xlsx"
# CSV dla chronionego Arkusza Google - plik techniczny, wiec lezy
# przy skrypcie, a nie w glownym folderze roboczym.
CSV_NAME = "PODGLAD_dla_handlowcow_dane.csv"

# Kolory oficjalne wg Brandbook_LATEX (znak towarowy nr 267001, rozdz. 3.3):
#   CZARNY   #000000
#   CZERWONY #E30613
#   SZARY 60 #878787
#   SZARY 40 #B2B2B2
#   SZARY 20 #DADADA
# Reszta (jasniejsze odcienie szarosci, zielen/niebieski dla wskaznikow
# stanu) to kolory pomocnicze spoza brandbooka, potrzebne do UI dashboardu
# (tlo strony, obwodki kart, kolor "zrobione"/"realizacja") - brandbook
# zabrania zmiany kolorow SAMEGO ZNAKU (logo), nie ogranicza reszty UI.
BLACK = "000000"      # oficjalny czarny brandbooka
RED = "E30613"         # oficjalny czerwony brandbooka
GRAY70 = "6B7280"       # pomocniczy (etykiety) - poza brandbookiem
GRAY60 = "666666"  # WCAG AA (4.5:1) na bialym i jasnoszarym tle - uzywane w drobnym tekscie
GRAY40 = "B2B2B2"       # = SZARY 40 brandbooka
GRAY20 = "DADADA"       # = SZARY 20 brandbooka
GRAY10 = "E9EAEC"       # pomocniczy (cienkie linie kart) - poza brandbookiem
GRAY05 = "F2F3F5"       # pomocniczy (tlo drugorzedne) - poza brandbookiem
PAGE_BG = "F7F7F8"       # pomocniczy (tlo strony) - poza brandbookiem
WHITE = "FFFFFF"
GREEN = "15803D"         # pomocniczy (wskaznik "cel osiagniety") - poza brandbookiem
GREEN_BG = "DCFCE7"       # pomocniczy - poza brandbookiem
BLUE = "1D4ED8"           # pomocniczy (wskaznik "zrobione") - poza brandbookiem
BLUE_BG = "E8EEFC"         # pomocniczy - poza brandbookiem

LOGO_HEADER_PATH = os.path.join(SCRIPT_DIR, "latex_logo_header.png")  # biale logo (na czarne tlo)

thin = Side(style="thin", color=GRAY10)
CARD_BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)
BORDER_ALL = CARD_BORDER
ACCENT_LEFT = Side(style="thick", color=RED)

MONTHS_PL = ["Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec",
             "Lipiec", "Sierpień", "Wrzesień", "Październik", "Listopad", "Grudzień"]


def _read_source_months(src_path):
    """Czyta z głównego kalkulatora: liste miesiecy (etykieta, cel, aktualna)
    oraz liste swiat PL - potrzebne do policzenia dni sprzedazowych kazdego
    miesiaca od zera (plik podgladowy ma byc samodzielny, wiec dni sprzedazowe
    licza sie tu w Pythonie, tak samo jak w oryginalnym arkuszu pomocniczym)."""
    raw_wb = openpyxl.load_workbook(src_path, data_only=False)
    raw_ws = raw_wb["Kalkulator marży"]

    header_row = None
    for row in raw_ws.iter_rows(min_row=1, max_row=60):
        for cell in row:
            if cell.value == "Miesiąc":
                header_row = cell.row
                break
        if header_row:
            break
    if header_row is None:
        raise ValueError("Nie znaleziono nagłówka tabeli miesięcy w głównym kalkulatorze.")

    months = []
    r = header_row + 1
    while True:
        label = raw_ws.cell(row=r, column=2).value
        if label is None or label == "":
            break
        cel = raw_ws.cell(row=r, column=3).value or 0
        aktualna = raw_ws.cell(row=r, column=4).value or 0
        months.append((label, cel, aktualna))
        r += 1

    hol_ws = raw_wb["Święta PL"]
    holidays = set()
    for hrow in hol_ws.iter_rows(min_row=2):
        d = hrow[0].value
        if d is not None:
            if isinstance(d, datetime.datetime):
                d = d.date()
            holidays.add(d)

    return months, holidays


def _sales_days(year, month, holidays):
    import calendar
    days_in_month = calendar.monthrange(year, month)[1]
    today = datetime.date.today()
    all_days = 0
    remaining_days = 0
    for day in range(1, days_in_month + 1):
        d = datetime.date(year, month, day)
        is_sales_day = d.weekday() != 6 and d not in holidays
        if is_sales_day:
            all_days += 1
            if d >= today:
                remaining_days += 1
    return all_days, remaining_days


def _label_to_year_month(label):
    name, year_str = label.rsplit(" ", 1)
    month = MONTHS_PL.index(name) + 1
    return int(year_str), month


def generate(src_path, out_path, only_year=None):
    """only_year: jesli podane (np. 2026), lista wyboru miesiecy zawiera
    TYLKO miesiace z tego roku (reszta danych zrodlowych jest ignorowana
    przy budowie pliku podgladowego dla handlowcow)."""
    months, holidays = _read_source_months(src_path)
    if not months:
        raise ValueError("Brak miesięcy w głównym kalkulatorze.")

    if only_year is not None:
        months = [m for m in months if _label_to_year_month(m[0])[0] == only_year]
        if not months:
            raise ValueError(f"Brak miesięcy dla roku {only_year} w głównym kalkulatorze.")

    today = datetime.date.today()
    current_label = f"{MONTHS_PL[today.month-1]} {today.year}"
    labels = [m[0] for m in months]
    default_label = current_label if current_label in labels else labels[0]

    # --- Nowy skoroszyt ---
    wb = openpyxl.Workbook()

    # Arkusz z danymi (UKRYTY):
    #   Etykieta | Cel | Aktualna | Dni w mies. | Dni pozostałe | 1. dzień mies.
    # Kolumny D/E zostaja jako zamrozony snapshot (przydatny do podejrzenia
    # "jak bylo w chwili generowania"), ale wynik NIE liczy sie juz z nich -
    # dni sprzedazowe przelicza na zywo arkusz "Kalendarz (ukryte)".
    # Kolumna F (prawdziwa data 1. dnia miesiaca) jest potrzebna, zeby z
    # etykiety tekstowej ("Sierpień 2026") dalo sie zrobic date bez parsowania
    # polskich nazw miesiecy w formule.
    data_ws = wb.active
    data_ws.title = "Dane (ukryte)"
    headers = ["Miesiąc", "Cel marży", "Aktualna marża", "Dni w miesiącu",
               "Dni pozostałe (snapshot)", "Pierwszy dzień"]
    for i, h in enumerate(headers, start=1):
        data_ws.cell(row=1, column=i, value=h)
    for i, (label, cel, aktualna) in enumerate(months, start=2):
        year, month = _label_to_year_month(label)
        all_days, rem_days = _sales_days(year, month, holidays)
        data_ws.cell(row=i, column=1, value=label)
        data_ws.cell(row=i, column=2, value=cel)
        data_ws.cell(row=i, column=3, value=aktualna)
        data_ws.cell(row=i, column=4, value=all_days)
        data_ws.cell(row=i, column=5, value=rem_days)
        c_date = data_ws.cell(row=i, column=6, value=datetime.date(year, month, 1))
        c_date.number_format = "yyyy-mm-dd"
    last_row = len(months) + 1
    data_ws.sheet_state = "hidden"

    DATA = "'Dane (ukryte)'"
    FIRSTDAYS = f"{DATA}!$F$2:$F${last_row}"
    LABELS = f"{DATA}!$A$2:$A${last_row}"
    TARGETS = f"{DATA}!$B$2:$B${last_row}"
    CURRENTS = f"{DATA}!$C$2:$C${last_row}"
    ALLDAYS = f"{DATA}!$D$2:$D${last_row}"
    REMDAYS = f"{DATA}!$E$2:$E${last_row}"

    # --- Arkusz "Kalendarz (ukryte)": dni sprzedazowe liczone NA ZYWO ---
    # Bez tego "dni pozostale" byly zamrazane w chwili generowania pliku:
    # jesli nikt nie uruchomil AKTUALIZUJ.bat przez tydzien, handlowcy dalej
    # widzieli stara liczbe dni, a wyliczona z niej srednia dzienna byla
    # zanizona. Teraz siatka dni przelicza sie sama przy kazdym otwarciu
    # (TODAY()), zarowno w Excelu, jak i w Arkuszach Google.
    cal_ws = wb.create_sheet("Kalendarz (ukryte)")
    cal_ws["A1"] = "Nie edytuj tego arkusza — służy tylko do obliczeń."
    cal_ws["A1"].font = Font(bold=True, color=GRAY60)

    # Lista swiat (kolumna H), przeniesiona z glownego kalkulatora.
    hol_sorted = sorted(holidays)
    cal_ws["H1"] = "Święta PL"
    for i, d in enumerate(hol_sorted, start=2):
        c = cal_ws.cell(row=i, column=8, value=d)
        c.number_format = "yyyy-mm-dd"
    hol_last = len(hol_sorted) + 1
    HOL_RANGE = f"'Kalendarz (ukryte)'!$H$2:$H${max(hol_last, 2)}"

    # B1 = pierwszy dzien wybranego miesiaca (data), wyciagniety z tabeli
    # danych po etykiecie wybranej z listy rozwijanej.
    PICKER_REF = None  # ustawiane nizej, po zbudowaniu arkusza "Wynik"

    # Siatka 31 dni: data | sprzedazowy? | pozostaly? | swieto?
    cal_ws["A3"] = "Dzień#"
    cal_ws["B3"] = "Data"
    cal_ws["C3"] = "Sprzedażowy"
    cal_ws["D3"] = "Pozostały"
    cal_ws["E3"] = "Święto?"
    for i in range(1, 32):
        r = i + 3
        cal_ws.cell(row=r, column=1, value=i)
        cal_ws.cell(row=r, column=2,
                    value=(f'=IF(A{r}<=DAY(EOMONTH($B$1,0)),'
                           f'DATE(YEAR($B$1),MONTH($B$1),A{r}),"")')).number_format = "yyyy-mm-dd"
        # Dzien sprzedazowy = poniedzialek-sobota (WEEKDAY(...,2)<>7) i nie swieto
        cal_ws.cell(row=r, column=3,
                    value=f'=IF(B{r}="",0,IF(AND(WEEKDAY(B{r},2)<>7,E{r}=0),1,0))')
        # Pozostaly = dzien sprzedazowy, ktory jeszcze nie minal (dzis wlicza sie)
        cal_ws.cell(row=r, column=4,
                    value=f'=IF(B{r}="",0,IF(AND(WEEKDAY(B{r},2)<>7,E{r}=0,B{r}>=TODAY()),1,0))')
        cal_ws.cell(row=r, column=5,
                    value=f'=IF(B{r}="",0,IF(COUNTIF({HOL_RANGE},B{r})>0,1,0))')
    cal_ws.sheet_state = "hidden"

    CAL = "'Kalendarz (ukryte)'"
    DNI_ALL_F = f"SUM({CAL}!$C$4:$C$34)"
    DNI_REM_F = f"SUM({CAL}!$D$4:$D$34)"

    # --- Arkusz główny "Wynik" ---
    ws = wb.create_sheet("Wynik")
    wb.active = wb.sheetnames.index("Wynik")
    ws.sheet_view.showGridLines = False
    FIRST_COL_IDX = 2   # B
    LAST_COL_IDX = 7    # G
    LAST_COL = "G"
    ws.column_dimensions["A"].width = 2.5
    ws.column_dimensions["B"].width = 2.5
    for col, width in zip("CDEFG", [15, 15, 6, 15, 15]):
        ws.column_dimensions[col].width = width
    # Kolumna H: margines po PRAWEJ stronie kart, lustrzane odbicie
    # marginesu A+B po lewej (2.5+2.5=5) - taki sam jasnoszary "ramka"
    # efekt z obu stron.
    ws.column_dimensions["H"].width = 5

    def page_bg(row, height=None, upto_col=LAST_COL_IDX):
        for c in range(1, upto_col + 1):
            ws.cell(row=row, column=c).fill = PatternFill("solid", fgColor=PAGE_BG)
        if height:
            ws.row_dimensions[row].height = height

    def card(row_top, row_bottom, col_from="C", col_to="G", accent=None, fill=WHITE):
        """Rysuje "karte" - biale/kolorowe tlo z cienka ramka na obszarze
        col_from:row_top do col_to:row_bottom, opcjonalnie z grubym
        kolorowym akcentem po lewej krawedzi (symulacja nowoczesnej karty
        dashboardu w ograniczeniach formatowania Excela/Arkuszy)."""
        col_from_idx = openpyxl.utils.column_index_from_string(col_from)
        col_to_idx = openpyxl.utils.column_index_from_string(col_to)
        for r in range(row_top, row_bottom + 1):
            for c in range(col_from_idx, col_to_idx + 1):
                cell = ws.cell(row=r, column=c)
                cell.fill = PatternFill("solid", fgColor=fill)
                left = ACCENT_LEFT if (accent and c == col_from_idx) else thin
                top = thin if r == row_top else Side(style=None)
                bottom = thin if r == row_bottom else Side(style=None)
                right = thin if c == col_to_idx else Side(style=None)
                cell.border = Border(left=left, right=right, top=top, bottom=bottom)

    def section_label(row, text, col="C", center=False):
        if center:
            ws.merge_cells(f"C{row}:G{row}")
        cell = ws[f"{col}{row}"]
        cell.value = text.upper()
        cell.font = Font(size=9, bold=True, color=GRAY70)
        cell.alignment = Alignment(horizontal="center", vertical="center") if center \
            else Alignment(vertical="center")
        ws.row_dimensions[row].height = 16

    # Tlo calej widocznej strony na jasnoszaro (dashboard, nie "arkusz").
    for r in range(1, 45):
        page_bg(r)

    # --- Naglowek marki: pelny czarny pasek z PRAWDZIWYM logo LATEX
    # (wariant "OPONY FELGI SERWIS" z Brandbook_LATEX, wersja _inv na
    # ciemne tlo) zamiast tekstu udajacego logo. ---
    header_row = 1
    ws.row_dimensions[header_row].height = 54
    # Czarny pasek naglowka i czerwony akcent pod nim ciagna sie az do
    # kolumny H (margines po prawej), zeby pasowac do reszty ukladu -
    # stad "+2" zamiast "+1" (LAST_COL_IDX=7=G, H=8).
    for c in range(1, LAST_COL_IDX + 2):
        ws.cell(row=header_row, column=c).fill = PatternFill("solid", fgColor=BLACK)

    if os.path.exists(LOGO_HEADER_PATH):
        from openpyxl.drawing.spreadsheet_drawing import TwoCellAnchor, AnchorMarker
        from openpyxl.utils.units import pixels_to_EMU

        img = openpyxl.drawing.image.Image(LOGO_HEADER_PATH)
        # Docelowa wysokosc logo w nagłówku (px) - dobrana pod wysokosc
        # wiersza 54pt (~72px), z marginesem gora/dol. Zachowujemy
        # proporcje oryginalnego pliku (593x183).
        target_h = 40
        scale = target_h / img.height
        img.height = target_h
        img.width = int(img.width * scale)

        # UWAGA: OneCellAnchor z samym rowOff bywa ignorowany przez
        # importer Arkuszy Google (obraz "przykleja sie" do gory wiersza
        # zamiast wyśrodkowac sie wedlug rowOff) - dziala poprawnie w
        # Excelu/LibreOffice, ale nie w Google Sheets. TwoCellAnchor
        # (zakotwiczenie OD gornego-lewego DO dolnego-prawego rogu, oba z
        # jawnym offsetem) jest interpretowany spojnie przez oba silniki.
        row_height_px = 72  # 54pt ~ 72px
        offset_y_px = max(0, (row_height_px - target_h) // 2)

        # Wyśrodkuj POZIOMO logo w calej szerokosci paska naglowka C:G.
        # UWAGA: liczenie offsetu w pikselach od kolumny A zawodzi, bo
        # Excel/LibreOffice i Google Sheets przeliczaja "jednostki
        # szerokosci kolumny" na piksele RÓŻNYMI wzorami - efekt byl
        # widoczny golym okiem w Google Sheets (logo wyraznie przesuniete
        # w lewo mimo poprawnego wyliczenia w LibreOffice), i bledu NIE
        # da sie uniknac probujac zakotwiczyc wzgledem jednej "centralnej"
        # kolumny (E ma tylko 6 jednostek szerokosci - logo w nia nie
        # wchodzi, wiec i tak trzeba cofac sie do sasiedniej kolumny z
        # przeliczeniem px, co ponownie uzaleznia wynik od niepewnego
        # wzoru piksel/jednostka).
        #
        # Zamiast tego liczymy srodek CALEJ szerokosci C:G w JEDNOSTKACH
        # SZEROKOSCI KOLUMN (nie w pikselach - oba silniki zgadzaja sie co
        # do jednostek szerokosci kolumn, tylko roznia sie przelicznikiem
        # na piksele), znajdujemy, w ktorej kolumnie wypada ten srodek, i
        # dopiero WEWNATRZ tej jednej kolumny liczymy maly offset w
        # pikselach. Blad przelicznika px/jednostka (jesli w ogole
        # wystepuje) jest wtedy ograniczony do ulamka szerokosci pojedynczej
        # kolumny zamiast kumulowac sie na sumie 5 kolumn - w praktyce
        # niezauwazalny.
        col_letters = ["C", "D", "E", "F", "G"]
        col_widths_units = [ws.column_dimensions[c].width for c in col_letters]
        total_width_units = sum(col_widths_units)
        # px logo -> jednostki szerokosci kolumny, uzywajac tego samego
        # wzoru co do zamiany jednostek->px (blad w obie strony sie znosi,
        # bo interesuje nas tylko POLOZENIE srodka logo wzgledem srodka
        # paska, a nie bezwzgledna wartosc w px)
        def _px_to_units(px):
            return (px - 5) / 7

        img_width_units = _px_to_units(img.width)
        center_units = total_width_units / 2
        logo_left_units = center_units - (img_width_units / 2)

        # Znajdz kolumne (indeks 0-based wzgledem col_letters), w ktorej
        # wypada lewa krawedz logo, i offset wewnatrz niej w jednostkach.
        cum = 0.0
        col_from_local = 0
        offset_units_in_col = logo_left_units
        for i, w in enumerate(col_widths_units):
            if logo_left_units < cum + w or i == len(col_widths_units) - 1:
                col_from_local = i
                offset_units_in_col = logo_left_units - cum
                break
            cum += w
        offset_units_in_col = max(0.0, offset_units_in_col)

        col_from_x = openpyxl.utils.column_index_from_string("C") - 1 + col_from_local  # 0-based
        off_x_px = round(offset_units_in_col * 7)

        row_from = header_row - 1
        marker_from = AnchorMarker(col=col_from_x, colOff=pixels_to_EMU(off_x_px),
                                    row=row_from, rowOff=pixels_to_EMU(offset_y_px))
        # "to" marker liczony jako from + rozmiar, w tej samej kolumnie bazowej
        marker_to = AnchorMarker(col=col_from_x, colOff=pixels_to_EMU(off_x_px + img.width),
                                  row=row_from, rowOff=pixels_to_EMU(offset_y_px + img.height))
        img.anchor = TwoCellAnchor(editAs="oneCell", _from=marker_from, to=marker_to)
        ws.add_image(img)
    else:
        # Fallback tekstowy, gdyby plik logo nie byl dostepny obok skryptu.
        ws.merge_cells(f"C{header_row}:E{header_row}")
        ws[f"C{header_row}"] = "LATEX"
        ws[f"C{header_row}"].font = Font(name="Calibri", size=20, bold=True, color=WHITE)
        ws[f"C{header_row}"].alignment = Alignment(vertical="center", indent=1)

        ws.merge_cells(f"F{header_row}:G{header_row}")
        ws[f"F{header_row}"] = "Opony · Felgi · Serwis"
        ws[f"F{header_row}"].font = Font(name="Calibri", size=9, color=GRAY40)
        ws[f"F{header_row}"].alignment = Alignment(vertical="center", horizontal="right")

    accent_row = header_row + 1
    ws.row_dimensions[accent_row].height = 4
    for c in range(1, LAST_COL_IDX + 2):  # az do H, patrz komentarz wyzej
        ws.cell(row=accent_row, column=c).fill = PatternFill("solid", fgColor=RED)

    spacer0 = accent_row + 1
    ws.row_dimensions[spacer0].height = 14
    page_bg(spacer0, height=14)

    # --- Karta: wybór miesiąca ---
    # Jeden spójny blok zamiast trzech warstw powtarzajacych to samo
    # (naglowek sekcji + osobna etykieta + wartosc): naglowek na gorze
    # karty, od razu pod nim duza wartosc do wyboru, wszystko
    # wysrodkowane. Cala karta to jeden ciagly prostokat (card()) bez
    # dodatkowych "pustych" wierszy z ramka w srodku, ktore wygladaly
    # jak przypadkowa szara linia.
    row_top = spacer0 + 1
    picker_val_row = row_top + 1
    card(row_top, picker_val_row, accent=True)

    ws.merge_cells(f"C{row_top}:G{row_top}")
    ws[f"C{row_top}"] = "WYBÓR MIESIĄCA"
    ws[f"C{row_top}"].font = Font(size=9, bold=True, color=GRAY70)
    ws[f"C{row_top}"].alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[row_top].height = 20

    ws.merge_cells(f"C{picker_val_row}:G{picker_val_row}")
    picker = ws[f"C{picker_val_row}"]
    picker.value = default_label
    picker.font = Font(bold=True, color=BLACK, size=16)
    picker.alignment = Alignment(horizontal="center", vertical="center")
    picker.protection = Protection(locked=False)  # JEDYNA edytowalna komórka
    # KRYTYCZNE: format tekstowy "@".
    # Bez niego Arkusze Google w polskiej lokalizacji rozpoznaja "Maj 2026"
    # jako DATE i po wybraniu z listy zamieniaja tekst na wartosc daty
    # (2026-05-01, wyswietlane jako "maj 2026"). Wtedy MATCH nie znajduje
    # juz takiej etykiety w tabeli i CALY panel pokazuje zera oraz falszywe
    # "CEL OSIAGNIETY". Format tekstowy blokuje te konwersje.
    picker.number_format = "@"
    ws.row_dimensions[picker_val_row].height = 30

    # UWAGA: formula1 dla type="list" NIE powinno mieć znaku "=" na
    # początku (to nie jest formuła Excela w normalnym sensie, tylko
    # referencja do zakresu). Excel to toleruje i po cichu ignoruje "=",
    # ale importer Arkuszy Google jest bardziej rygorystyczny i przy "="
    # nie rozpoznaje zakresu, przez co cała lista rozwijana znika po
    # konwersji xlsx -> Arkusze Google.
    dv = DataValidation(type="list", formula1=LABELS, allow_blank=False,
                         showDropDown=False)
    dv.errorTitle = "Nieprawidłowy miesiąc"
    dv.error = "Wybierz miesiąc z rozwijanej listy."
    dv.promptTitle = "Wybór miesiąca"
    dv.prompt = "Wybierz miesiąc, dla którego chcesz zobaczyć wynik."
    ws.add_data_validation(dv)
    dv.add(picker)

    # Numer wybranego miesiaca liczymy RAZ, w ukrytym arkuszu, i wszystkie
    # formuly korzystaja juz z gotowego wyniku.
    # Druga warstwa zabezpieczenia przed problemem z data (patrz komentarz
    # przy number_format wyzej): gdyby komorka wyboru mimo wszystko okazala
    # sie data (np. ktos wpisze miesiac recznie zamiast wybrac z listy),
    # dopasowujemy po DACIE zamiast po tekscie, wiec panel dalej liczy
    # poprawnie zamiast pokazywac zera.
    PICKER_REF = f"'Wynik'!$C${picker_val_row}"
    base_year = _label_to_year_month(months[0][0])[0]
    # Gdy komorka wyboru jest data, numer miesiaca liczymy ARYTMETYCZNIE
    # (rok/miesiac), a nie przez MATCH po kolumnie dat. MATCH wymagalby, zeby
    # kolumna dat po imporcie do Arkuszy nadal byla datami, a nie tekstem -
    # arytmetyka nie zalezy od niczego takiego i nie da sie jej zepsuc typem.
    # Tabela zawiera 12 kolejnych miesiecy jednego roku, wiec numer = miesiac.
    idx_z_daty = (f"(YEAR({PICKER_REF})-{base_year})*12+MONTH({PICKER_REF})")
    cal_ws["B2"] = (
        f"=IFERROR(IF(ISNUMBER({PICKER_REF}),{idx_z_daty},"
        f"MATCH({PICKER_REF},{LABELS},0)),1)")
    MATCHF = "'Kalendarz (ukryte)'!$B$2"

    # B1 = pierwszy dzien wybranego miesiaca -> od tego zalezy cala siatka dni.
    cal_ws["B1"] = f"=IFERROR(INDEX({FIRSTDAYS},{MATCHF}),TODAY())"
    cal_ws["B1"].number_format = "yyyy-mm-dd"

    spacer1 = picker_val_row + 1
    ws.row_dimensions[spacer1].height = 18
    page_bg(spacer1, height=18)

    # --- Karty statystyk: siatka 2x2 zamiast waskiej listy wierszy ---
    stats_label_row = spacer1 + 1
    section_label(stats_label_row, "Wynik dla wybranego miesiąca", center=True)

    grid_top = stats_label_row + 1
    page_bg(grid_top, height=6)

    def stat_card(top_row, col_from, col_to, label, formula, fmt, accent_color=None):
        bottom_row = top_row + 3
        card(top_row, bottom_row, col_from=col_from, col_to=col_to,
             accent=True, fill=WHITE)
        # Pasek koloru na lewej krawedzi karty (nadpisuje domyslny czerwony
        # akcent z card(), jesli podano inny kolor dla tej konkretnej karty).
        if accent_color:
            for r in range(top_row, bottom_row + 1):
                cell = ws.cell(row=r, column=openpyxl.utils.column_index_from_string(col_from))
                b = cell.border
                cell.border = Border(left=Side(style="thick", color=accent_color),
                                      right=b.right, top=b.top, bottom=b.bottom)
        lbl = ws.cell(row=top_row + 1, column=openpyxl.utils.column_index_from_string(col_from))
        ws.merge_cells(start_row=top_row + 1, start_column=openpyxl.utils.column_index_from_string(col_from),
                       end_row=top_row + 1, end_column=openpyxl.utils.column_index_from_string(col_to))
        lbl.value = label
        lbl.font = Font(size=9, color=GRAY70)
        lbl.alignment = Alignment(vertical="center", indent=1)

        val = ws.cell(row=top_row + 2, column=openpyxl.utils.column_index_from_string(col_from))
        ws.merge_cells(start_row=top_row + 2, start_column=openpyxl.utils.column_index_from_string(col_from),
                       end_row=top_row + 2, end_column=openpyxl.utils.column_index_from_string(col_to))
        val.value = formula
        val.number_format = fmt
        val.font = Font(name="Consolas", size=17, bold=True, color=BLACK)
        val.alignment = Alignment(vertical="center", indent=1)
        ws.row_dimensions[top_row].height = 6
        ws.row_dimensions[top_row + 1].height = 15
        ws.row_dimensions[top_row + 2].height = 24
        ws.row_dimensions[bottom_row].height = 6
        return f"{col_from}{top_row + 2}"

    CEL_CELL = stat_card(grid_top, "C", "D", "Cel marży",
                          f"=IFERROR(INDEX({TARGETS},{MATCHF}),0)", '#,##0 "zł"')
    ZROB_CELL = stat_card(grid_top, "F", "G", "Zrobione",
                           f"=IFERROR(INDEX({CURRENTS},{MATCHF}),0)", '#,##0 "zł"',
                           accent_color=BLUE)
    CEL, ZROB = CEL_CELL, ZROB_CELL

    grid2_top = grid_top + 4
    POZ_CELL = stat_card(grid2_top, "C", "D", "Pozostało do celu",
                          f"=MAX(0,{CEL}-{ZROB})", '#,##0 "zł"')
    REAL_CELL = stat_card(grid2_top, "F", "G", "Realizacja",
                           f"=IF({CEL}>0,{ZROB}/{CEL},0)", "0.0%",
                           accent_color=GREEN)
    POZ = POZ_CELL

    # --- Trzeci rzad kart: TEMPO i dni pozostale ---
    # Sam procent realizacji w polowie miesiaca wprowadza w blad: porownuje
    # niepelny miesiac z pelnym celem, wiec 20. dnia zawsze wyglada slabo.
    # "Tempo" porownuje zrobione z tym, ile POWINNO byc na dzis wedlug
    # minionych dni sprzedazowych: 100% = dokladnie na kursie.
    grid3_top = grid2_top + 4
    DNI_REM = f"F{grid3_top + 2}"
    DNI_MIN = f"({DNI_ALL_F}-{DNI_REM_F})"

    TEMPO = stat_card(
        grid3_top, "C", "D", "Tempo (gdzie powinieneś być dziś)",
        f'=IF(OR({CEL}<=0,{DNI_ALL_F}<=0,{DNI_MIN}<=0),"—",'
        f'{ZROB}/({CEL}*{DNI_MIN}/{DNI_ALL_F}))',
        "0%", accent_color=GRAY40)
    stat_card(grid3_top, "F", "G", "Dni sprzedażowe pozostałe",
              f"={DNI_REM_F}", "0", accent_color=GRAY40)

    ws.conditional_formatting.add(
        TEMPO, FormulaRule(formula=[f"AND(ISNUMBER({TEMPO}),{TEMPO}>=1)"],
                           font=Font(name="Consolas", size=17, bold=True, color=GREEN)))
    ws.conditional_formatting.add(
        TEMPO, FormulaRule(formula=[f"AND(ISNUMBER({TEMPO}),{TEMPO}<1)"],
                           font=Font(name="Consolas", size=17, bold=True, color=RED)))

    # --- Prognoza na koniec miesiaca ---
    # Ekstrapolacja liniowa po dniach sprzedazowych: srednia dzienna
    # wypracowana do tej pory razy wszystkie dni sprzedazowe miesiaca.
    # Dla miesiaca zamknietego prognoza = faktyczny wynik. Na poczatku
    # miesiaca (zero minietych dni) pokazujemy "—" zamiast dzielic przez zero.
    # Dla miesiaca zamknietego to juz nie jest prognoza, tylko fakt - wiec
    # etykiety same zmieniaja nazwe, zeby nie sugerowac przewidywania tam,
    # gdzie miesiac dawno sie skonczyl.
    grid4_top = grid3_top + 4
    PROGNOZA = stat_card(
        grid4_top, "C", "D",
        f'=IF({DNI_REM_F}=0,"Wynik końcowy miesiąca","Prognoza na koniec miesiąca")',
        f'=IF(OR({DNI_ALL_F}<=0,{DNI_MIN}<=0),"—",{ZROB}/{DNI_MIN}*{DNI_ALL_F})',
        '#,##0 "zł"', accent_color=BLUE)
    PROG_DIFF = stat_card(
        grid4_top, "F", "G",
        f'=IF({DNI_REM_F}=0,"Wynik względem celu","Prognoza względem celu")',
        f'=IF(OR({CEL}<=0,{DNI_ALL_F}<=0,{DNI_MIN}<=0),"—",{PROGNOZA}-{CEL})',
        '+#,##0 "zł";-#,##0 "zł";0 "zł"', accent_color=GRAY40)

    ws.conditional_formatting.add(
        PROG_DIFF, FormulaRule(formula=[f"AND(ISNUMBER({PROG_DIFF}),{PROG_DIFF}>=0)"],
                               font=Font(name="Consolas", size=17, bold=True, color=GREEN)))
    ws.conditional_formatting.add(
        PROG_DIFF, FormulaRule(formula=[f"AND(ISNUMBER({PROG_DIFF}),{PROG_DIFF}<0)"],
                               font=Font(name="Consolas", size=17, bold=True, color=RED)))

    # --- Pasek postepu ---
    # Budowany z REPT(), a nie z "paskow danych" Excela - te ostatnie gina
    # przy konwersji do Arkuszy Google, a zwykly tekst renderuje sie tak samo
    # w obu silnikach.
    bar_gap = grid4_top + 4
    page_bg(bar_gap, height=6)
    bar_row = bar_gap + 1
    card(bar_row, bar_row, accent=True, fill=WHITE)
    ws.merge_cells(f"C{bar_row}:G{bar_row}")
    bar = ws[f"C{bar_row}"]
    # Kropki, a nie znaki blokow. Arkusze Google nie maja Consolas i
    # podstawiaja wlasny font, w ktorym "█" renderuje sie z przerwami -
    # pasek wygladal jak kod kreskowy. Kropki maja odstepy z natury, wiec
    # wygladaja tak samo dobrze w kazdym foncie i w obu silnikach.
    # 10 kropek = dzialka co 10%.
    n_blocks = f"MAX(0,MIN(10,ROUND({REAL_CELL}*10,0)))"
    bar.value = f'=REPT("●",{n_blocks})&REPT("○",10-{n_blocks})'
    bar.font = Font(name="Consolas", size=14, bold=True, color=BLACK)
    bar.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[bar_row].height = 24
    ws.conditional_formatting.add(
        f"C{bar_row}", FormulaRule(formula=[f"${POZ}<=0"],
                                   font=Font(name="Consolas", size=12,
                                             bold=True, color=GREEN)))

    spacer2 = bar_row + 1
    ws.row_dimensions[spacer2].height = 14
    page_bg(spacer2, height=14)

    # --- Karta "hero": duzy czarny blok z kluczowa liczba, z czerwonym
    # akcentem u gory - ten sam motyw co czerwona linia pod logo w
    # naglowku, zeby wizualnie spiac gore i dol dashboardu. ---
    hero_accent_row = spacer2 + 1
    ws.row_dimensions[hero_accent_row].height = 4
    for c in range(3, LAST_COL_IDX + 1):
        ws.cell(row=hero_accent_row, column=c).fill = PatternFill("solid", fgColor=RED)

    hero_label_row = hero_accent_row + 1
    ws.merge_cells(f"C{hero_label_row}:G{hero_label_row}")
    # Etykieta bloku jest FORMULĄ, bo dla miesiąca zamkniętego "średnia
    # dzienna do celu" nie ma sensu - nie ma już dni, na które można by tę
    # kwotę rozłożyć. Wtedy pod spodem widnieje cała brakująca kwota i
    # blok sam sobie przeczył ("średnia dzienna" + "brak pozostałych dni").
    ws[f"C{hero_label_row}"] = (
        f'=IF(AND({POZ}>0,{DNI_REM}=0),"ZABRAKŁO DO CELU",'
        f'"ŚREDNIA DZIENNA MARŻA DO CELU")')
    ws[f"C{hero_label_row}"].font = Font(bold=True, size=10, color=WHITE)
    ws[f"C{hero_label_row}"].alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[hero_label_row].height = 24

    hero_val_row = hero_label_row + 1
    ws.merge_cells(f"C{hero_val_row}:G{hero_val_row}")
    ws[f"C{hero_val_row}"] = (f'=IF({POZ}<=0,"CEL OSIĄGNIĘTY",'
                 f'IF({DNI_REM}>0,{POZ}/{DNI_REM},{POZ}))')
    ws[f"C{hero_val_row}"].number_format = '#,##0 "zł";;@'
    ws[f"C{hero_val_row}"].font = Font(name="Consolas", bold=True, size=26, color=WHITE)
    ws[f"C{hero_val_row}"].alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[hero_val_row].height = 42

    hero_msg_row = hero_val_row + 1
    ws.merge_cells(f"C{hero_msg_row}:G{hero_msg_row}")
    ws[f"C{hero_msg_row}"] = (f'=IF({POZ}<=0,"Cel zrealizowany — każda kolejna złotówka to nadwyżka.",'
                 f'IF({DNI_REM}=0,"Brak pozostałych dni sprzedażowych w tym miesiącu.",'
                 f'"Do celu brakuje "&TEXT({POZ},"#,##0")&" zł przez "&{DNI_REM}&" dni."))')
    ws[f"C{hero_msg_row}"].font = Font(italic=True, size=10, color=GRAY20)
    ws[f"C{hero_msg_row}"].alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[hero_msg_row].height = 20

    for r in range(hero_label_row, hero_msg_row + 1):
        for c in range(3, LAST_COL_IDX + 1):  # od C - kolumna B zostaje jako margines (tło strony)
            ws.cell(row=r, column=c).fill = PatternFill("solid", fgColor=BLACK)

    # Formatowanie warunkowe: zielone tło + ciemnozielony tekst, gdy cel
    # osiągnięty (patrz komentarz w głównym build_v4.py o tym samym błędzie -
    # trzeba nadpisać OBA: fill i font, inaczej biały tekst zostaje nieczytelny).
    ws.conditional_formatting.add(
        f"C{hero_label_row}", FormulaRule(formula=[f"${POZ}<=0"],
                           fill=PatternFill("solid", fgColor=GREEN_BG),
                           font=Font(bold=True, size=10, color=GREEN)))
    ws.conditional_formatting.add(
        f"C{hero_val_row}", FormulaRule(formula=[f"${POZ}<=0"],
                           fill=PatternFill("solid", fgColor=GREEN_BG),
                           font=Font(name="Consolas", bold=True, size=26, color=GREEN)))
    ws.conditional_formatting.add(
        f"C{hero_msg_row}", FormulaRule(formula=[f"${POZ}<=0"],
                           fill=PatternFill("solid", fgColor=GREEN_BG),
                           font=Font(italic=True, size=10, color=GREEN)))
    ws.conditional_formatting.add(
        f"D{hero_label_row}:{LAST_COL}{hero_msg_row}",
        FormulaRule(formula=[f"${POZ}<=0"], fill=PatternFill("solid", fgColor=GREEN_BG)))

    spacer3 = hero_msg_row + 1
    ws.row_dimensions[spacer3].height = 16
    page_bg(spacer3, height=16)

    stamp_row = spacer3 + 1
    ws.merge_cells(f"C{stamp_row}:G{stamp_row}")
    now_str = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
    ws[f"C{stamp_row}"] = f"Dane zaktualizowane: {now_str}"
    ws[f"C{stamp_row}"].font = Font(size=8, italic=True, color=GRAY60)
    ws[f"C{stamp_row}"].alignment = Alignment(horizontal="center")

    ws.merge_cells(f"C{stamp_row+1}:G{stamp_row+1}")
    ws[f"C{stamp_row+1}"] = "LATEX — Opony, Felgi, Serwis"
    ws[f"C{stamp_row+1}"].font = Font(size=8, color=GRAY40, italic=True)
    ws[f"C{stamp_row+1}"].alignment = Alignment(horizontal="center")

    # Kolumna H: margines po prawej stronie kart, lustrzane odbicie
    # marginesu A+B po lewej - to samo jasnoszare tlo PAGE_BG, od wiersza
    # 3 (naglowek/akcent w wierszach 1-2 zostaja bez zmian) do 32.
    # Malujemy na samym koncu, zeby zadna karta budowana wczesniej
    # (ktora dotyka tylko kolumn C:G) przypadkiem tego nie nadpisala.
    for r in range(3, 45):
        ws.cell(row=r, column=8).fill = PatternFill("solid", fgColor=PAGE_BG)  # H

    # Bez freeze_panes: caly arkusz miesci sie na jednym ekranie, a
    # zamrozenie tuz nad karta "WYBOR MIESIACA" tworzylo widoczna,
    # mylaca szara linie podzialu miedzy wierszami 3 i 4.

    # Ochrona: caly arkusz zablokowany poza polem wyboru miesiaca.
    ws.protection.sheet = True
    ws.protection.selectLockedCells = False
    ws.protection.selectUnlockedCells = False
    ws.protection.formatCells = False
    ws.protection.formatColumns = False
    ws.protection.formatRows = False
    ws.sheet_view.zoomScale = 100

    wb.calculation.calcMode = "auto"
    wb.calculation.fullCalcOnLoad = True
    wb.calculation.calcOnSave = True

    wb.save(out_path)

    # --- Maly plik CSV obok xlsx: zrodlo dla chronionego Arkusza Google ---
    # Arkusz dla handlowcow jest natywnym Arkuszem Google (tylko taki da sie
    # naprawde zablokowac przed edycja). Nie da sie go nadpisac plikiem, wiec
    # skrypt w Arkuszu wczytuje z tego CSV same liczby i wpisuje je do ukrytej
    # tabelki. Dzieki temu panel, ochrona zakresow i udostepnienie zostaja
    # nietkniete - zmieniaja sie wylacznie wartosci.
    # Format: srednik jako separator, kropka dziesietna, kodowanie UTF-8 z BOM
    # (Arkusze i Excel czytaja wtedy polskie znaki poprawnie).
    csv_path = os.path.join(SCRIPT_DIR, CSV_NAME)
    try:
        with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
            f.write("Miesiac;Cel;Aktualna;PierwszyDzien\n")
            for label, cel, aktualna in months:
                year, month = _label_to_year_month(label)
                f.write(f"{label};{cel or 0};{aktualna or 0};"
                        f"{datetime.date(year, month, 1).isoformat()}\n")
    except Exception:
        # Brak CSV nie moze wywrocic generowania samego podgladu.
        csv_path = None

    # Zwroc podglad danych dla biezacego miesiaca (do logu w konsoli)
    cur = next((m for m in months if m[0] == default_label), None)
    if cur:
        return default_label, cur[1], cur[2]
    return default_label, 0, 0


if __name__ == "__main__":
    out_path = os.path.join(BASE_DIR, OUT_NAME)
    label, cel, zrobione = generate(SRC_XLSX, out_path)
    print(f"Wygenerowano podgląd (domyślny miesiąc: {label})")
    print(f"  Cel: {cel:.2f} zł | Zrobione: {zrobione:.2f} zł")
    print("Zapisano:", out_path)
