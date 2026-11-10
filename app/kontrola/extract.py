"""Odczyt tekstu z PDF (Integra 7) i ze screenshota (CRM)."""
import os


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
