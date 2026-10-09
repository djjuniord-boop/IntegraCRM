#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AKTUALIZUJ KALKULATOR MARZY - skrypt lokalny (LATEX)
======================================================
Dziala calkowicie samodzielnie na Twoim komputerze - nic nie wysyla nigdzie
w internet, tylko czyta pliki PDF z folderu "Wyniki" i wpisuje kwote
"Marza towary + sprzedaz uslug netto" do wlasciwego miesiaca w Excelu.

WYMAGANIA (jednorazowa instalacja):
    pip install openpyxl pypdf

UZYCIE:
    Uruchom plik "AKTUALIZUJ.bat" (podwojne klikniecie) w tym samym folderze,
    LUB recznie w wierszu polecen:
        python aktualizuj_kalkulator.py

Skrypt zaklada strukture folderow:
    Wyniki/
      aktualizuj_kalkulator.py   <- ten plik
      AKTUALIZUJ.bat             <- uruchamiacz
      kalkulator_marzy_latex.xlsx  <- plik kalkulatora (aktualizowany w miejscu)
      *.pdf                       <- raporty sprzedazy z Integry (wrzucasz tutaj)

Kazdy PDF musi byc raportem "Raport sprzedazy towarow i uslug" z Integry,
obejmujacym DOKLADNIE JEDEN miesiac. Miesiac/rok sa rozpoznawane z daty
POCZATKOWEJ zakresu w raporcie ("Zakres dat: od RRRR-MM-DD do ...").
"""
import re
import sys
import os
import io
import glob
import shutil
import datetime
from copy import copy as _copy_style

# Nie twórz folderu __pycache__ obok skryptu. Folder "Wyniki" jest
# synchronizowany z Dyskiem Google, a __pycache__ to pliki czysto techniczne,
# ktore nie maja po co tam trafiac.
sys.dont_write_bytecode = True

# Sciezka do zsynchronizowanego folderu Dysku Google na tym komputerze.
# Po kazdej aktualizacji plik PODGLAD_dla_handlowcow.xlsx jest tam
# automatycznie kopiowany, zeby handlowcy mieli do niego dostep.
# Zmien te sciezke, jesli Twoj folder Dysku Google jest gdzie indziej.
GOOGLE_DRIVE_FOLDER = r"G:\Mój dysk"

# Podglad ladauje wprost w katalogu glownym Dysku - tam, gdzie lezal od
# poczatku i gdzie handlowcy maja do niego link.
# UWAGA na przyszlosc: probowalismy przeniesc go do osobnego podfolderu
# "dla porzadku". Efekt byl taki, ze stara kopia w katalogu glownym zostala
# na miejscu, wygladala na aktualna i po cichu przestala sie odswiezac -
# przez co wygladalo, jakby aktualizacja przestala dzialac. Jesli kiedys
# zmieniasz to miejsce, SKASUJ stary plik w tej samej chwili.
GOOGLE_DRIVE_SUBFOLDER = "LATEX Wrocław"

# Ktory rok obejmuje to narzedzie.
# To wydanie jest CELOWO tylko na 2026 - na 2027 powstanie osobny plik.
# Dzieki przypieciu roku na sztywno nic sie nie zepsuje w styczniu 2027:
# podglad dalej bedzie pokazywal miesiace 2026 zamiast probowac przeskoczyc
# na rok, ktorego w tabeli nie ma.
# (Gdyby kiedys mial dzialac wieloletnio, wpisz tu None = zawsze biezacy rok.)
PODGLAD_ROK = 2026

try:
    import openpyxl
except ImportError:
    print("BLAD: brak biblioteki openpyxl. Zainstaluj: pip install openpyxl")
    sys.exit(1)

try:
    import pypdf
except ImportError:
    print("BLAD: brak biblioteki pypdf. Zainstaluj: pip install pypdf")
    sys.exit(1)


MONTHS_PL = ["Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec",
             "Lipiec", "Sierpień", "Wrzesień", "Październik", "Listopad", "Grudzień"]

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Skrypty mieszkaja w podfolderze "silnik", a dane (kalkulator, PDF-y,
# podglad, folder "przetworzone") leza PIETRO WYZEJ - w glownym folderze
# roboczym. Rozdzielenie tych dwoch rzeczy sprawia, ze na wierzchu widac
# tylko to, czego uzywasz, a techniczne pliki nie zasmiecaja widoku.
# BASE_DIR wskazuje folder z danymi; SCRIPT_DIR - folder ze skryptami.
BASE_DIR = os.path.dirname(SCRIPT_DIR)
XLSX_NAME = "kalkulator_marzy_Wroclaw.xlsx"
LOG_NAME = "log_aktualizacji.txt"
PROCESSED_MARKER = ".przetworzone"  # folder z podfolderem na juz-uzyte PDFy


def log(msg, log_lines):
    print(msg)
    log_lines.append(msg)


def extract_text(pdf_path):
    reader = pypdf.PdfReader(pdf_path)
    text = ""
    for page in reader.pages:
        # extract_text() potrafi zwrocic None dla stron bez warstwy tekstowej
        text += (page.extract_text() or "") + "\n"
    return text


def parse_report(text, source_name):
    m_range = re.search(
        r"Zakres dat:\s*od\s*(\d{4}-\d{2}-\d{2})\s*do\s*(\d{4}-\d{2}-\d{2})", text)
    if not m_range:
        raise ValueError("nie znaleziono 'Zakres dat' w pliku PDF")
    start_date = m_range.group(1)
    end_date = m_range.group(2)
    year = int(start_date[:4])
    month = int(start_date[5:7])

    m_margin = re.search(
        r"Mar[żz]a towary \+ sprzeda[żz]\s*us[łl]ug netto:\s*(-?[\d\s\xa0]+,\d{2})", text)
    if not m_margin:
        raise ValueError("nie znaleziono kwoty 'Marża towary + sprzedaż usług netto'")
    raw = m_margin.group(1).replace(" ", "").replace("\xa0", "").replace(",", ".")
    margin_value = float(raw)

    # --- Kontrola zakresu dat -------------------------------------------
    # Miesiac bierzemy z daty POCZATKOWEJ, wiec cala kwota z raportu ladauje
    # w tym jednym miesiacu. Jesli zakres siega poza ten miesiac, trzeba to
    # sprawdzic, zeby nie wpisac marzy z kilku miesiecy jako jednego.
    d_start = datetime.date(year, month, 1)
    d_end = datetime.date(int(end_date[:4]), int(end_date[5:7]), int(end_date[8:10]))
    today = datetime.date.today()
    spans_months = (d_end.year, d_end.month) != (year, month)
    # Jesli zakres siega w PRZYSZLOSC, dalsze miesiace nie moga miec jeszcze
    # sprzedazy - kwota i tak dotyczy tylko miesiaca poczatkowego (typowy
    # przypadek: raport "od 1. dnia biezacego miesiaca do konca roku").
    risky = spans_months and d_end <= today

    return {
        "source": source_name,
        "start_date": start_date,
        "end_date": end_date,
        "label": f"{MONTHS_PL[month-1]} {year}",
        "margin_netto": margin_value,
        "spans_months": spans_months,
        "risky_range": risky,
    }


def find_month_rows(ws):
    header_row = None
    for row in ws.iter_rows(min_row=1, max_row=60):
        for cell in row:
            if cell.value == "Miesiąc":
                header_row = cell.row
                break
        if header_row:
            break
    if header_row is None:
        raise ValueError("Nie znaleziono nagłówka tabeli miesięcy ('Miesiąc') w arkuszu głównym.")

    month_rows = {}
    r = header_row + 1
    while True:
        label = ws.cell(row=r, column=2).value
        if label is None or label == "":
            break
        month_rows[label] = r
        r += 1
    return month_rows


# Kopie zapasowe trzymamy OBOK folderu roboczego, a nie w srodku niego.
# Folder "Wyniki" jest synchronizowany z Dyskiem Google, wiec kopie
# zapisywane w nim wysylalyby sie na Dysk przy kazdym uruchomieniu i
# zasmiecaly go dziesiatkami plikow.
BACKUP_DIRNAME = "kopie_zapasowe"
BACKUP_KEEP = 10


def _make_backup(xlsx_path, log_lines):
    """Robi datowana kopie kalkulatora PRZED nadpisaniem go nowymi danymi.
    Trzyma ostatnie BACKUP_KEEP kopii, starsze kasuje, zeby folder nie rosl
    w nieskonczonosc."""
    try:
        backup_dir = os.path.join(BASE_DIR, BACKUP_DIRNAME)
        os.makedirs(backup_dir, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        base, ext = os.path.splitext(XLSX_NAME)
        dst = os.path.join(backup_dir, f"{base}_{stamp}{ext}")
        shutil.copy2(xlsx_path, dst)
        log(f"Kopia zapasowa: {dst}", log_lines)

        kopie = sorted(glob.glob(os.path.join(backup_dir, f"{base}_*{ext}")))
        for stara in kopie[:-BACKUP_KEEP]:
            try:
                os.remove(stara)
            except OSError:
                pass
    except Exception as e:
        log(f"Uwaga: nie udało się zrobić kopii zapasowej: {e}", log_lines)



# --- Generator wykresu do maila (panel HUD, matplotlib) --------------------
def _sales_days_dla_wykresu(year, month, holidays):
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


def _generuj_wykres_png(miesiac_etykieta, cel, zrobione, year, month, holidays=None, log_lines=None):
    try:
        import matplotlib
    except ImportError:
        try:
            import subprocess
            wynik = subprocess.run([sys.executable, "-m", "pip", "install", "--user", "-q", "matplotlib"],
                                    check=False, capture_output=True, text=True)
            import matplotlib  # noqa
        except Exception as e:
            if log_lines is not None:
                log(f"Uwaga: nie udalo sie zainstalowac/zaimportowac matplotlib do wykresu: {e}", log_lines)
            return None

    try:
        import numpy as np
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import Circle
        from matplotlib.colors import LinearSegmentedColormap
        import matplotlib.patheffects as pe

        holidays = holidays or set()
        procent = (zrobione / cel) if cel else 0
        procent_pct = procent * 100
        cel_osiagniety = zrobione >= cel and cel > 0

        if cel_osiagniety:
            neon, neon2 = "#00ffb0", "#00c8ff"
        else:
            neon, neon2 = "#ff3b5c", "#ff9d3b"

        BG, TXT_MAIN, TXT_DIM, GRID = "#05070d", "#eef2ff", "#5c6785", "#161d2e"

        dni_all, dni_rem = _sales_days_dla_wykresu(year, month, holidays)
        dni_min = dni_all - dni_rem

        tempo = zrobione / (cel * dni_min / dni_all) if (cel > 0 and dni_all > 0 and dni_min > 0) else None
        prognoza = (zrobione / dni_min * dni_all) if (dni_all > 0 and dni_min > 0) else None
        prognoza_vs_cel = (prognoza - cel) if (prognoza is not None and cel > 0) else None

        fig = plt.figure(figsize=(7.2, 3.8), dpi=160)
        fig.patch.set_facecolor(BG)
        gs = fig.add_gridspec(1, 2, width_ratios=[1, 1.35], wspace=0.05,
                               left=0.03, right=0.97, top=0.90, bottom=0.08)

        ax = fig.add_subplot(gs[0, 0])
        ax.set_facecolor(BG)
        ax.set_xlim(-1.3, 1.3)
        ax.set_ylim(-1.3, 1.3)
        ax.set_aspect("equal")
        ax.axis("off")

        for r in (0.98, 0.78, 0.58):
            ax.add_patch(Circle((0, 0), r, fill=False, edgecolor=GRID, linewidth=0.8, zorder=1))

        udzial = min(procent, 1.0)
        r_out, r_in = 0.98, 0.74
        n_seg = max(int(udzial * 240), 1) if udzial > 0 else 0
        theta_full = np.linspace(90, 90 - 360 * udzial, n_seg + 1) if n_seg > 0 else np.array([90])
        cmap = LinearSegmentedColormap.from_list("neon", [neon2, neon])

        for i in range(len(theta_full) - 1):
            t0, t1 = theta_full[i], theta_full[i + 1]
            frac = i / max(len(theta_full) - 2, 1)
            color = cmap(frac)
            wedge_theta = np.linspace(t0, t1, 3)
            xo = r_out * np.cos(np.radians(wedge_theta))
            yo = r_out * np.sin(np.radians(wedge_theta))
            xi = r_in * np.cos(np.radians(wedge_theta))[::-1]
            yi = r_in * np.sin(np.radians(wedge_theta))[::-1]
            ax.fill(np.concatenate([xo, xi]), np.concatenate([yo, yi]), color=color, linewidth=0, zorder=3)

        if udzial < 1.0:
            theta_rest = np.linspace(90 - 360 * udzial, 90 - 360, 120)
            xo = r_out * np.cos(np.radians(theta_rest))
            yo = r_out * np.sin(np.radians(theta_rest))
            xi = r_in * np.cos(np.radians(theta_rest))[::-1]
            yi = r_in * np.sin(np.radians(theta_rest))[::-1]
            ax.fill(np.concatenate([xo, xi]), np.concatenate([yo, yi]), color="#1a2033", linewidth=0, zorder=2)

        for glow_w, alpha in [(0.14, 0.10), (0.09, 0.16), (0.045, 0.22)]:
            for i in range(len(theta_full) - 1):
                t0, t1 = theta_full[i], theta_full[i + 1]
                wedge_theta = np.linspace(t0, t1, 3)
                xo = (r_out + glow_w) * np.cos(np.radians(wedge_theta))
                yo = (r_out + glow_w) * np.sin(np.radians(wedge_theta))
                xi = r_out * np.cos(np.radians(wedge_theta))[::-1]
                yi = r_out * np.sin(np.radians(wedge_theta))[::-1]
                ax.fill(np.concatenate([xo, xi]), np.concatenate([yo, yi]), color=neon, alpha=alpha, linewidth=0, zorder=1.5)

        ax.text(0, 0.10, f"{procent_pct:.0f}", ha="center", va="center",
                fontsize=40, fontweight="bold", color=TXT_MAIN, zorder=5,
                fontfamily="monospace",
                path_effects=[pe.withStroke(linewidth=3, foreground=neon, alpha=0.35)])
        ax.text(0, -0.20, "%  REALIZACJI", ha="center", va="center",
                fontsize=9, color=neon, zorder=5, fontfamily="monospace", fontweight="bold")
        ax.text(0, 1.18, miesiac_etykieta.upper(), ha="center", va="center",
                fontsize=11, color=TXT_DIM, zorder=5, fontfamily="monospace", fontweight="bold")

        ax2 = fig.add_subplot(gs[0, 1])
        ax2.set_facecolor(BG)
        ax2.set_xlim(0, 1)
        ax2.set_ylim(0, 1)
        ax2.axis("off")

        def fmt_zl(v):
            return f"{v:,.0f} zł".replace(",", " ")

        linie = [("CEL", fmt_zl(cel), TXT_MAIN, None), ("ZROBIONE", fmt_zl(zrobione), neon, neon)]
        if tempo is not None:
            kolor_tempo = "#00ffb0" if tempo >= 1 else "#ff3b5c"
            linie.append(("TEMPO", f"{tempo * 100:.0f}%  (cel = 100%)", kolor_tempo, kolor_tempo))
        if dni_rem is not None:
            linie.append(("DNI SPRZEDAŻOWE POZOSTAŁE", f"{dni_rem}", TXT_MAIN, None))
        if prognoza is not None:
            etykieta_prog = "WYNIK KOŃCOWY" if dni_rem == 0 else "PROGNOZA KOŃCOWA"
            linie.append((etykieta_prog, fmt_zl(prognoza), "#5aa9ff", "#5aa9ff"))
        if prognoza_vs_cel is not None:
            znak = "+" if prognoza_vs_cel >= 0 else ""
            kolor_diff = "#00ffb0" if prognoza_vs_cel >= 0 else "#ff3b5c"
            etykieta_diff = "WYNIK VS CEL" if dni_rem == 0 else "PROGNOZA VS CEL"
            linie.append((etykieta_diff, f"{znak}{fmt_zl(prognoza_vs_cel)}", kolor_diff, kolor_diff))

        n = len(linie)
        row_h = 1.0 / n
        for i, (etykieta, wartosc, kol_val, kol_bar) in enumerate(linie):
            y_top = 1.0 - i * row_h
            if i > 0:
                ax2.plot([0, 1], [y_top, y_top], color=GRID, linewidth=0.8, zorder=1)
            if kol_bar:
                ax2.add_patch(plt.Rectangle((0, y_top - row_h + row_h * 0.18), 0.012, row_h * 0.64,
                                             color=kol_bar, zorder=3, linewidth=0))
            ax2.text(0.035, y_top - row_h * 0.28, etykieta, fontsize=8, color=TXT_DIM,
                      va="center", fontfamily="monospace", fontweight="bold", zorder=3)
            ax2.text(0.035, y_top - row_h * 0.68, wartosc, fontsize=14.5, color=kol_val,
                      va="center", fontfamily="monospace", fontweight="bold", zorder=3)

        fig.suptitle("PANEL WYNIKÓW  ·  LATEX AUTO SERWIS", fontsize=9.5, color=TXT_DIM,
                     fontfamily="monospace", fontweight="bold", x=0.5, y=0.985)

        buf = io.BytesIO()
        fig.savefig(buf, format="png", facecolor=BG)
        plt.close(fig)
        return buf.getvalue()
    except Exception as e:
        if log_lines is not None:
            import traceback
            log(f"Uwaga: blad podczas rysowania wykresu do maila: {e}", log_lines)
            log(f"Szczegoly bledu wykresu:\n{traceback.format_exc()}", log_lines)
        return None
# --- Powiadomienie e-mail dla handlowcow -----------------------------------
# Wysylane WYLACZNIE lokalnie z tego skryptu, bez zadnej chmury/automatyki -
# zgodnie z zasada "tylko reczna aktualizacja". Haslo aplikacji Gmail lezy
# w osobnym pliku email_config.txt (obok tego skryptu), nie w kodzie.
EMAIL_CONFIG_FILE = os.path.join(SCRIPT_DIR, "email_config.txt")
EMAIL_NADAWCA = "djjuniord@gmail.com"
EMAIL_NADAWCA_NAZWA = "Panel Wynikow LATEX"
EMAIL_ODBIORCY = [
    "durbaniak@latexopony.eu",
    "wroclaw@latexserwis.pl",
]
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def _wczytaj_haslo_email():
    """Czyta haslo aplikacji Gmail z email_config.txt (pierwsza linia bez #)."""
    if not os.path.exists(EMAIL_CONFIG_FILE):
        return None
    try:
        with open(EMAIL_CONFIG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    return line.replace(" ", "")
    except Exception:
        return None
    return None


def _wyslij_powiadomienie_email(updated, log_lines, label=None, cel=None, zrob=None, holidays=None):
    """Wysyla osobny e-mail HTML do KAZDEGO odbiorcy z osobna."""
    if os.environ.get("LATEX_TRYB_TESTOWY") == "1":
        log("[TRYB TESTOWY] E-mail NIE został wysłany.", log_lines)
        return
    haslo = _wczytaj_haslo_email()
    if not haslo:
        log(f"Uwaga: nie znaleziono hasla aplikacji w {EMAIL_CONFIG_FILE} - "
            f"powiadomienie e-mail NIE zostalo wyslane.", log_lines)
        return
    try:
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        from email.mime.image import MIMEImage
        from email.utils import formatdate, formataddr

        png_bytes = None
        if label is not None and cel is not None and zrob is not None:
            try:
                miesiace = ["Styczeń","Luty","Marzec","Kwiecień","Maj","Czerwiec",
                            "Lipiec","Sierpień","Wrzesień","Październik","Listopad","Grudzień"]
                nazwa_mies, rok_str = label.rsplit(" ", 1)
                year = int(rok_str)
                month = miesiace.index(nazwa_mies) + 1
                png_bytes = _generuj_wykres_png(label, cel, zrob, year, month, holidays=holidays, log_lines=log_lines)
            except Exception as e:
                log(f"Uwaga: nie udalo sie przygotowac wykresu do maila: {e}", log_lines)
                png_bytes = None

        tresc_tekst = (
            "Wyniki zostaly zaktualizowane.\n\n"
            "Nowy zestaw danych jest juz gotowy.\n\n"
            "To automatyczne powiadomienie - nie wymaga odpowiedzi.\n\n"
            "--\n"
            "LATEX Auto Serwis\n"
            "Opony - Felgi - Serwis\n"
            "Wiadomosc systemowa - panel wynikow"
        )

        tresc_html = """
<div style="background:#05070d; padding:24px 0; font-family: Arial, Helvetica, sans-serif;">
  <div style="max-width:600px; margin:0 auto; background:#0b0f1a; border-radius:10px;
              overflow:hidden; border:1px solid #1a2033;">
    <div style="padding:26px 30px 4px;">
      <p style="font-size:14px; line-height:1.7; color:#c9d1e8; margin:0 0 4px;">Wyniki zostały zaktualizowane.</p>
      <p style="font-size:14px; line-height:1.7; color:#c9d1e8; margin:0 0 16px;">Nowy zestaw danych jest już gotowy.</p>
    </div>
    __OBRAZEK__
    <div style="padding:14px 30px 4px;">
      <p style="font-size:14px; line-height:1.7; color:#c9d1e8; margin:0;">To automatyczne powiadomienie - nie wymaga odpowiedzi.</p>
    </div>
    <div style="padding:14px 30px 26px; margin-top:6px; border-top:1px solid #1a2033;">
      <p style="font-size:12px; line-height:1.7; color:#5c6785; margin:12px 0 0; white-space:pre-line;">--
LATEX Auto Serwis
Opony - Felgi - Serwis
Wiadomość systemowa - panel wyników</p>
    </div>
  </div>
</div>
"""
        if png_bytes:
            obrazek_tag = ('<div style="padding:0 16px 6px; text-align:center;">'
                           '<img src="cid:wykres_wynikow" alt="Wykres realizacji celu" '
                           'style="max-width:100%; border-radius:6px; display:block; margin:0 auto;"></div>')
        else:
            obrazek_tag = ""
        tresc_html = tresc_html.replace("__OBRAZEK__", obrazek_tag)

        wyslano = []
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as server:
            server.starttls()
            server.login(EMAIL_NADAWCA, haslo)
            for odbiorca in EMAIL_ODBIORCY:
                msg = MIMEMultipart("related")
                msg["Subject"] = "Aktualizacja wynikow"
                msg["From"] = formataddr((EMAIL_NADAWCA_NAZWA, EMAIL_NADAWCA))
                msg["To"] = odbiorca
                msg["Date"] = formatdate(localtime=True)

                alt = MIMEMultipart("alternative")
                alt.attach(MIMEText(tresc_tekst, "plain", "utf-8"))
                alt.attach(MIMEText(tresc_html, "html", "utf-8"))
                msg.attach(alt)

                if png_bytes:
                    img = MIMEImage(png_bytes, _subtype="png")
                    img.add_header("Content-ID", "<wykres_wynikow>")
                    img.add_header("Content-Disposition", "inline", filename="wykres_wynikow.png")
                    msg.attach(img)

                server.sendmail(EMAIL_NADAWCA, [odbiorca], msg.as_string())
                wyslano.append(odbiorca)

        log(f"Wyslano {len(wyslano)} osobnych powiadomien e-mail HTML "
            f"{'z wykresem' if png_bytes else '(bez wykresu - blad generowania)'} "
            f"(kazdy odbiorca widzi tylko siebie w polu Do).", log_lines)
    except Exception as e:
        log(f"Uwaga: nie udalo sie wyslac e-maila z powiadomieniem: {e}", log_lines)

def _refresh_podglad(xlsx_path, log_lines):
    """Zwraca (label, cel, zrob, holidays) do wysylki maila."""
    """Generuje/odswieza plik podgladowy dla handlowcow z aktualnej zawartosci
    xlsx_path (w tym recznie zmienionych celow) i kopiuje go na Dysk Google.
    Wywolywane zarowno po imporcie PDF-ow, jak i wtedy gdy nie ma nowych
    PDF-ow (np. po recznej zmianie celu w Excelu)."""
    try:
        import generuj_podglad
        podglad_path = os.path.join(BASE_DIR, generuj_podglad.OUT_NAME)
        rok = PODGLAD_ROK if PODGLAD_ROK else datetime.date.today().year
        label, cel, zrob = generuj_podglad.generate(xlsx_path, podglad_path,
                                                      only_year=rok)
        _, holidays_dla_maila = generuj_podglad._read_source_months(xlsx_path)
        log("", log_lines)
        log(f"Odświeżono plik podglądowy dla handlowców ({generuj_podglad.OUT_NAME}):", log_lines)
        log(f"  Miesiąc: {label} | Cel: {cel:.2f} zł | Zrobione: {zrob:.2f} zł", log_lines)

        # Skopiuj plik podglądowy na Dysk Google (zsynchronizowany folder)
        if os.environ.get("LATEX_TRYB_TESTOWY") == "1":
            log("[TRYB TESTOWY] Kopiowanie na Dysk Google pominięte.", log_lines)
        elif os.path.isdir(GOOGLE_DRIVE_FOLDER):
            dst_dir = (os.path.join(GOOGLE_DRIVE_FOLDER, GOOGLE_DRIVE_SUBFOLDER)
                       if GOOGLE_DRIVE_SUBFOLDER else GOOGLE_DRIVE_FOLDER)
            try:
                os.makedirs(dst_dir, exist_ok=True)
                dst = os.path.join(dst_dir, generuj_podglad.OUT_NAME)
                shutil.copyfile(podglad_path, dst)
                log(f"Skopiowano na Dysk Google: {dst}", log_lines)

                # Maly CSV z danymi - z niego chroniony Arkusz Google dla
                # handlowcow pobiera liczby (patrz INSTRUKCJA_arkusz.txt).
                csv_src = os.path.join(SCRIPT_DIR, generuj_podglad.CSV_NAME)
                if os.path.exists(csv_src):
                    csv_dst = os.path.join(dst_dir, os.path.basename(csv_src))
                    shutil.copyfile(csv_src, csv_dst)
                    log(f"Skopiowano dane dla Arkusza: {csv_dst}", log_lines)
            except Exception as e:
                log(f"Uwaga: nie udało się skopiować pliku na Dysk Google: {e}", log_lines)
        else:
            log(f"Uwaga: folder Dysku Google nie znaleziony ({GOOGLE_DRIVE_FOLDER}) — "
                f"plik podglądowy zapisany tylko lokalnie w folderze Wyniki.", log_lines)
        return label, cel, zrob, holidays_dla_maila
    except Exception as e:
        log("", log_lines)
        log(f"Uwaga: nie udało się wygenerować pliku podglądowego: {e}", log_lines)
        return None, None, None, None



# --- Karta "MARZA DZISIAJ" (przyrost od ostatniego wgrania) ------------------
_MD_HEADER_RE = re.compile(r"^=== Aktualizacja kalkulatora marż.*? — (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) ===")
_MD_CHANGE_RE = re.compile(r"^  (.+?): [\d\s,.]+ -> ([\d\s,.]+) zł")


def _wczorajsza_wartosc_z_logu(log_path, miesiac_etykieta):
    """Zwraca ostatnia zapisana wartosc marzy dla danego miesiaca z dni PRZED
    dzisiaj, na podstawie log_aktualizacji.txt (wpisy sprzed tego uruchomienia).
    None jesli brak historii z wczesniejszych dni."""
    if not os.path.exists(log_path):
        return None
    dzis = datetime.date.today()
    ostatnia_w_dniu = {}
    current_dt = None
    try:
        with open(log_path, encoding="utf-8") as f:
            for line in f:
                line = line.rstrip("\n")
                m_header = _MD_HEADER_RE.match(line)
                if m_header:
                    current_dt = datetime.datetime.strptime(m_header.group(1), "%Y-%m-%d %H:%M:%S")
                    continue
                m_change = _MD_CHANGE_RE.match(line)
                if m_change and current_dt and m_change.group(1) == miesiac_etykieta:
                    wartosc_str = m_change.group(2).replace(" ", "").replace("\xa0", "").replace(",", ".")
                    try:
                        wartosc = float(wartosc_str)
                    except ValueError:
                        continue
                    ostatnia_w_dniu[current_dt.date()] = wartosc
    except Exception:
        return None
    dni_wczesniejsze = sorted(d for d in ostatnia_w_dniu if d < dzis)
    if not dni_wczesniejsze:
        return None
    return ostatnia_w_dniu[dni_wczesniejsze[-1]]


def _dopisz_marze_dzisiaj(ws, log_lines, updated):
    """Dopisuje/aktualizuje karte 'MARZA DZISIAJ' pod istniejacym wykresem
    'Plan vs wykonanie' (wiersze 81-83), w tym samym czarnym stylu co karta
    'SREDNIA DZIENNA MARZA DO CELU'. NIE rusza zadnych innych wierszy/formul,
    zadnego wykresu ani stylu reszty arkusza."""
    try:
        from openpyxl.styles import Font
        from openpyxl.formatting.rule import FormulaRule

        teraz = datetime.datetime.now()
        biezacy_miesiac = f"{MONTHS_PL[teraz.month - 1]} {teraz.year}"

        wartosc_dzis = None
        for source, label, old, new in updated:
            if label == biezacy_miesiac:
                wartosc_dzis = new
        if wartosc_dzis is None:
            month_rows = find_month_rows(ws)
            row = month_rows.get(biezacy_miesiac)
            if row:
                wartosc_dzis = ws.cell(row=row, column=4).value

        if wartosc_dzis is None:
            log("Uwaga: nie mozna wyliczyc marzy dzisiaj — brak danych dla biezacego miesiaca.", log_lines)
            return

        log_path = os.path.join(SCRIPT_DIR, LOG_NAME)
        wartosc_wczoraj = _wczorajsza_wartosc_z_logu(log_path, biezacy_miesiac)
        przyrost = wartosc_dzis - wartosc_wczoraj if wartosc_wczoraj is not None else wartosc_dzis

        R_HEAD, R_VAL, R_SUB = 84, 85, 86

        istnieje = ws.cell(row=R_HEAD, column=2).value is not None

        if not istnieje:
            src_head = ws["B31"]
            src_val = ws["B32"]
            src_sub = ws["B33"]

            def kopiuj_styl(dst, src):
                dst.font = _copy_style(src.font)
                dst.fill = _copy_style(src.fill)
                dst.alignment = _copy_style(src.alignment)
                dst.border = _copy_style(src.border)
                dst.number_format = src.number_format

            ws.merge_cells(f"B{R_HEAD}:E{R_HEAD}")
            ws.merge_cells(f"B{R_VAL}:E{R_VAL}")
            ws.merge_cells(f"B{R_SUB}:E{R_SUB}")

            kopiuj_styl(ws[f"B{R_HEAD}"], src_head)
            kopiuj_styl(ws[f"B{R_VAL}"], src_val)
            kopiuj_styl(ws[f"B{R_SUB}"], src_sub)

            ws[f"B{R_HEAD}"].value = "MARŻA DZISIAJ (od ostatniego wgrania)"
            ws.row_dimensions[R_HEAD].height = 24.0
            ws.row_dimensions[R_VAL].height = 42.0
            ws.row_dimensions[R_SUB].height = 19.5

            ws.conditional_formatting.add(
                f"B{R_VAL}",
                FormulaRule(formula=[f"AND(ISNUMBER(B{R_VAL}),B{R_VAL}>=0)"],
                            font=Font(name="Consolas", size=26, bold=True, color="00FF9D")))
            ws.conditional_formatting.add(
                f"B{R_VAL}",
                FormulaRule(formula=[f"AND(ISNUMBER(B{R_VAL}),B{R_VAL}<0)"],
                            font=Font(name="Consolas", size=26, bold=True, color="FF5C5C")))

        ws[f"B{R_VAL}"].value = round(przyrost, 2)
        ws[f"B{R_VAL}"].number_format = '+#,##0" zł";-#,##0" zł"'
        ws[f"B{R_SUB}"].value = ("Stan na dziś: " + f"{wartosc_dzis:,.0f}".replace(",", " ") + " zł")

        log(f"Dopisano karte 'MARZA DZISIAJ': {przyrost:+.2f} zl (stan " + f"{wartosc_dzis:,.2f}".replace(",", " ") + " zl).", log_lines)
    except Exception as e:
        log(f"Uwaga: nie udalo sie zaktualizowac karty 'MARZA DZISIAJ': {e}", log_lines)


def main():
    log_lines = []
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log(f"=== Aktualizacja kalkulatora marży — SERWIS WROCŁAW — {now} ===", log_lines)
    log(f"Folder roboczy: {BASE_DIR}", log_lines)

    xlsx_path = os.path.join(BASE_DIR, XLSX_NAME)
    if not os.path.exists(xlsx_path):
        log(f"BŁĄD: nie znaleziono pliku {XLSX_NAME} w tym folderze. Przerywam.", log_lines)
        write_log(log_lines)
        return

    pdf_files = sorted(glob.glob(os.path.join(BASE_DIR, "*.pdf")))
    if not pdf_files:
        log("Brak nowych plików PDF w folderze — nic do zaimportowania z Integry.", log_lines)
        log("Mimo to odświeżam plik podglądowy dla handlowców (np. na wypadek", log_lines)
        log("ręcznej zmiany celów w Excelu).", log_lines)
        _refresh_podglad(xlsx_path, log_lines)
        write_log(log_lines)
        return

    reports = []
    errors = []
    for pdf in pdf_files:
        name = os.path.basename(pdf)
        try:
            text = extract_text(pdf)
            rep = parse_report(text, name)
            reports.append(rep)
        except Exception as e:
            errors.append((name, str(e)))

    log("", log_lines)
    log("Odczytane raporty:", log_lines)
    for rep in reports:
        log(f"  {rep['source']}: {rep['label']} "
            f"(zakres {rep['start_date']} – {rep['end_date']}) "
            f"-> marża netto = {rep['margin_netto']:.2f} zł", log_lines)

    if errors:
        log("", log_lines)
        log("Błędy odczytu (plik pominięty):", log_lines)
        for name, err in errors:
            log(f"  {name}: {err}", log_lines)

    if not reports:
        log("", log_lines)
        log("Żaden plik PDF nie został poprawnie odczytany — Excel NIE został zmieniony.", log_lines)
        write_log(log_lines)
        return

    # --- Ostrzezenie: kilka raportow na ten sam miesiac w jednej partii ---
    per_month = {}
    for rep in reports:
        per_month.setdefault(rep["label"], []).append(rep["source"])
    duplikaty = {lab: src for lab, src in per_month.items() if len(src) > 1}
    if duplikaty:
        log("", log_lines)
        log("UWAGA: kilka plików PDF dotyczy tego samego miesiąca —", log_lines)
        log("zapisana zostanie tylko wartość z OSTATNIEGO z nich:", log_lines)
        for lab, srcs in duplikaty.items():
            log(f"  {lab}: {', '.join(srcs)}", log_lines)

    # --- Ostrzezenie: raport obejmuje wiecej niz jeden miesiac ---
    ryzykowne = [r for r in reports if r["risky_range"]]
    odrzucone_zakresem = set()
    if ryzykowne:
        log("", log_lines)
        log("UWAGA: poniższe raporty obejmują zakres dat wykraczający poza", log_lines)
        log("miesiąc początkowy, a cała kwota zostałaby zapisana jako TEN", log_lines)
        log("jeden miesiąc:", log_lines)
        for r in ryzykowne:
            log(f"  {r['source']}: {r['start_date']} – {r['end_date']} "
                f"-> zapis jako {r['label']} ({r['margin_netto']:.2f} zł)", log_lines)
        print()
        try:
            odp = input("Zapisać mimo to? Wpisz T aby zapisać, cokolwiek innego = pomiń: ")
        except (EOFError, OSError):
            odp = ""
        if odp.strip().lower() not in ("t", "tak", "y", "yes"):
            odrzucone_zakresem = {r["source"] for r in ryzykowne}
            log("Decyzja: raporty o podejrzanym zakresie dat POMINIĘTE.", log_lines)
        else:
            log("Decyzja: zapisuję mimo ostrzeżenia (potwierdzone ręcznie).", log_lines)

    wb = openpyxl.load_workbook(xlsx_path)
    ws = wb["Kalkulator marży"]
    month_rows = find_month_rows(ws)

    updated = []
    skipped = []
    for rep in reports:
        label = rep["label"]
        if rep["source"] in odrzucone_zakresem:
            skipped.append((rep["source"], label, "podejrzany zakres dat"))
            continue
        if label not in month_rows:
            skipped.append((rep["source"], label, "brak takiego miesiąca w tabeli"))
            continue
        row = month_rows[label]
        old_value = ws.cell(row=row, column=4).value
        new_value = round(rep["margin_netto"], 2)
        ws.cell(row=row, column=4).value = new_value
        updated.append((rep["source"], label, old_value, new_value))

    if updated:
        _make_backup(xlsx_path, log_lines)
        _dopisz_marze_dzisiaj(ws, log_lines, updated)
        wb.calculation.calcMode = "auto"
        wb.calculation.fullCalcOnLoad = True
        wb.calculation.calcOnSave = True
        try:
            wb.save(xlsx_path)
        except PermissionError:
            log("", log_lines)
            log(f"BŁĄD: nie mogę zapisać {XLSX_NAME} — plik jest teraz otwarty "
                f"w Excelu.", log_lines)
            log("Zamknij go i uruchom AKTUALIZUJ WSZYSTKO jeszcze raz. "
                "Nic nie zostało zmienione.", log_lines)
            write_log(log_lines)
            return

    log("", log_lines)
    log("Zaktualizowano w Excelu:", log_lines)
    for source, label, old, new in updated:
        log(f"  {label}: {old} -> {new:.2f} zł  (z pliku {source})", log_lines)

    if skipped:
        log("", log_lines)
        log("POMINIĘTO (plik ZOSTAJE w folderze Wyniki — nic nie przepadło):", log_lines)
        for source, label, powod in skipped:
            log(f"  {source} ({label}) — {powod}", log_lines)

    # Przenies do podfolderu "przetworzone" TYLKO te PDFy, ktore faktycznie
    # trafily do Excela. Pominiete raporty zostaja w folderze roboczym, zeby
    # nie znikaly po cichu razem z danymi, ktorych nikt nie zapisal.
    processed_dir = os.path.join(BASE_DIR, "przetworzone")
    os.makedirs(processed_dir, exist_ok=True)
    zapisane_pliki = {source for source, _, _, _ in updated}
    for rep in reports:
        if rep["source"] not in zapisane_pliki:
            continue
        src = os.path.join(BASE_DIR, rep["source"])
        dst = os.path.join(processed_dir, rep["source"])
        try:
            if os.path.exists(dst):
                base, ext = os.path.splitext(rep["source"])
                dst = os.path.join(processed_dir, f"{base}_{now.replace(':','-')}{ext}")
            os.replace(src, dst)
        except Exception as e:
            log(f"Uwaga: nie udało się przenieść {rep['source']} do folderu 'przetworzone': {e}", log_lines)

    # Wygeneruj/odśwież uproszczony plik podglądowy dla handlowców (lista
    # rozwijana miesięcy, bez tabeli do edycji, zablokowany przed edycją).
    if updated:
        _podglad_label, _podglad_cel, _podglad_zrob, _podglad_holidays = _refresh_podglad(xlsx_path, log_lines)
        _wyslij_powiadomienie_email(updated, log_lines, label=_podglad_label,
                                    cel=_podglad_cel, zrob=_podglad_zrob,
                                    holidays=_podglad_holidays)

    log("", log_lines)
    log(f"Gotowe. Zamknij i otwórz ponownie plik {XLSX_NAME} w Excelu, jeśli jest już otwarty.", log_lines)
    write_log(log_lines)


def write_log(log_lines):
    log_path = os.path.join(SCRIPT_DIR, LOG_NAME)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write("\n".join(log_lines) + "\n\n")


if __name__ == "__main__":
    _kod_wyjscia = 0
    try:
        main()
    except Exception as e:
        print()
        print("NIEOCZEKIWANY BŁĄD:", e)
        print()
        _kod_wyjscia = 1
        # zapisz blad takze do logu - zeby bylo go widac po zamknieciu okna
        try:
            import traceback
            _teraz = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(os.path.join(SCRIPT_DIR, LOG_NAME), "a", encoding="utf-8") as _f:
                _f.write(f"=== NIEOCZEKIWANY BŁĄD — {_teraz} ===\n"
                         f"NIEOCZEKIWANY BŁĄD: {e}\n{traceback.format_exc()}\n\n")
        except Exception:
            pass
    # Gdy uruchamia nas "AKTUALIZUJ WSZYSTKO", pauza jest tylko raz - na samym
    # koncu calego przebiegu, a nie w polowie (miedzy Wroclawiem a Opolem).
    if os.environ.get("LATEX_BEZ_PAUZY") != "1":
        try:
            input("Naciśnij Enter, aby zamknąć to okno...")
        except (EOFError, OSError):
            pass
    sys.exit(_kod_wyjscia)
