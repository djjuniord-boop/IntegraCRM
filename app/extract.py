"""Odczyt tekstu z PDF (Integra 7) i ze screenshota (CRM)."""
import os
from pathlib import Path


def _ascii_path(p: str) -> str:
    """Tesseract nie obsługuje polskich znaków w ścieżkach (np. C:\\Users\\Użytkownik).
    Na Windows zamieniamy ścieżkę na krótką postać 8.3, która jest czysto ASCII."""
    if os.name != "nt" or not p or p.isascii():
        return p
    try:
        import ctypes
        buf = ctypes.create_unicode_buffer(1024)
        if ctypes.windll.kernel32.GetShortPathNameW(str(p), buf, 1024) and buf.value.isascii():
            return buf.value
    except Exception:
        pass
    return p


def _ascii_tempdir() -> None:
    """Pliki tymczasowe dla Tesseracta w folderze bez polskich znaków."""
    import tempfile
    cur = tempfile.gettempdir()
    if os.name != "nt" or cur.isascii():
        return
    short = _ascii_path(cur)
    if short.isascii():
        tempfile.tempdir = short
        return
    for cand in (os.path.join(os.environ.get("PUBLIC", r"C:\Users\Public"), "IntegraCRM-tmp"),
                 r"C:\ProgramData\IntegraCRM-tmp"):
        try:
            if cand.isascii():
                os.makedirs(cand, exist_ok=True)
                tempfile.tempdir = cand
                return
        except OSError:
            pass


def _tess(tesseract_cmd):
    import pytesseract
    _ascii_tempdir()
    if tesseract_cmd:
        exe = _ascii_path(str(tesseract_cmd))
        pytesseract.pytesseract.tesseract_cmd = exe
        tessdata = os.path.join(os.path.dirname(str(tesseract_cmd)), "tessdata")
        if os.path.isdir(tessdata):
            os.environ["TESSDATA_PREFIX"] = _ascii_path(tessdata)
    return pytesseract


def text_from_pdf(path: str, tesseract_cmd: str | None = None, lang: str = "eng") -> str:
    """Najpierw tekst wprost z PDF; jeśli to skan – OCR stron."""
    import pdfplumber

    with pdfplumber.open(path) as pdf:
        text = "\n".join((p.extract_text() or "") for p in pdf.pages)
    if len(text.strip()) >= 20:
        return text

    pt = _tess(tesseract_cmd)
    out = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            out.append(pt.image_to_string(page.to_image(resolution=300).original, lang=lang))
    return "\n".join(out)


def text_from_image(img_or_path, tesseract_cmd: str | None = None, lang: str = "eng") -> str:
    """OCR zrzutu ekranu (obiekt PIL.Image albo ścieżka do pliku)."""
    from PIL import Image, ImageOps

    pt = _tess(tesseract_cmd)
    img = Image.open(img_or_path) if isinstance(img_or_path, (str, Path)) else img_or_path
    img = img.convert("L")
    if img.width < 2000:  # powiększenie poprawia trafność OCR małych czcionek
        k = 2000 / img.width
        img = img.resize((int(img.width * k), int(img.height * k)), Image.LANCZOS)
    img = ImageOps.autocontrast(img)
    return pt.image_to_string(img, lang=lang, config="--psm 6")


def ocr_variants(img_or_path, tesseract_cmd: str | None = None, lang: str = "eng") -> list[str]:
    """Kilka przebiegów OCR (różne skale i tryby). Pierwszy wynik = główny.

    Pojedynczy przebieg myli podobne znaki (9/O, 7/Z, 1/I); wiele przebiegów daje
    wyniki, z których zwykle któryś jest poprawny dla każdego numeru."""
    from PIL import Image, ImageOps

    import os
    from concurrent.futures import ThreadPoolExecutor

    pt = _tess(tesseract_cmd)
    base = Image.open(img_or_path) if isinstance(img_or_path, (str, Path)) else img_or_path
    base = base.convert("L")
    os.environ.setdefault("OMP_THREAD_LIMIT", "1")   # każdy przebieg na 1 rdzeniu – razem równolegle

    def one(variant):
        width, psm = variant
        k = width / base.width
        img = base.resize((int(base.width * k), int(base.height * k)), Image.LANCZOS)
        img = ImageOps.autocontrast(img)
        return pt.image_to_string(img, lang=lang, config=f"--psm {psm}")

    variants = ((2000, 6), (2000, 4), (1800, 6), (1800, 4), (2200, 6), (2200, 4))
    with ThreadPoolExecutor(max_workers=min(6, os.cpu_count() or 2)) as ex:
        return list(ex.map(one, variants))   # kolejność zachowana – pierwszy = główny


def image_from_clipboard():
    """Zwraca obraz ze schowka (np. wycinek z Narzędzia Wycinanie) albo None."""
    from PIL import Image, ImageGrab

    data = ImageGrab.grabclipboard()
    if isinstance(data, Image.Image):
        return data
    if isinstance(data, list) and data:  # skopiowany plik graficzny
        try:
            return Image.open(data[0])
        except Exception:
            return None
    return None
