"""Wspólne dla testów modułów: ścieżka do app/, folder tymczasowy zamiast prawdziwego data/."""
import sys
import tempfile
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))


def temp_data():
    """Przekierowuje data/ programu do folderu tymczasowego (nic nie trafia do prawdziwych ustawień)."""
    import paths
    d = Path(tempfile.mkdtemp(prefix="integra_test_"))
    paths.DATA_DIR = d
    paths.CONFIG_PATH = d / "config.json"
    return d
