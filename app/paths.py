"""Ścieżki programu – wszystko względem folderu głównego (układ przenośny)."""
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent      # kod programu (podmieniany przy aktualizacji)
ROOT = APP_DIR.parent                          # folder główny – można go kopiować gdziekolwiek
DATA_DIR = ROOT / "data"                       # ustawienia użytkownika (aktualizacja ich nie rusza)
CONFIG_PATH = DATA_DIR / "config.json"
BACKUP_DIR = DATA_DIR / "backup"
LOG_PATH = DATA_DIR / "error.log"
SKIP_FILE = DATA_DIR / "skip_version.txt"      # wersja pominięta po przywróceniu poprzedniej

RUNTIME_TESS = ROOT / "runtime" / "tesseract" / "tesseract.exe"
BUNDLED_TESS = ROOT / "tesseract" / "tesseract.exe"   # wersja .exe
SYSTEM_TESS = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")


def find_tesseract(configured: str = "") -> str | None:
    """Kolejność: ścieżka z Ustawień → Tesseract z folderu programu → zainstalowany w systemie."""
    for cand in (configured, BUNDLED_TESS, RUNTIME_TESS, SYSTEM_TESS):
        if cand and Path(cand).exists():
            return str(cand)
    return None
