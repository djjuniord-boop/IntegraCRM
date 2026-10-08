"""Aktualizacje: pobranie paczki wskazanej w version.json (adres WWW lub folder),
weryfikacja, kopia poprzedniej wersji i podmiana folderu app/. Dane użytkownika (data/) nie są ruszane."""
import hashlib
import json
import os
import py_compile
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from urllib.parse import urljoin

import paths
from version import VERSION

TIMEOUT = 15


def _ver(v: str) -> tuple:
    return tuple(int(x) for x in v.strip().split("."))


def _is_url(s: str) -> bool:
    return s.lower().startswith(("http://", "https://"))


def _manifest_location(source: str) -> str:
    s = source.strip().strip('"')
    if _is_url(s):
        return s
    p = Path(s)
    return str(p / "version.json") if p.is_dir() else s


def _read_bytes(loc: str) -> bytes:
    if _is_url(loc):
        req = urllib.request.Request(loc, headers={"User-Agent": f"IntegraCRM/{VERSION}"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.read()
    return Path(loc).read_bytes()


def _resolve(base: str, ref: str) -> str:
    if _is_url(ref) or Path(ref).is_absolute():
        return ref
    if _is_url(base):
        return urljoin(base, ref)
    return str(Path(base).parent / ref)


def _pinned() -> str:
    try:
        return paths.SKIP_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def check(source: str):
    """Zwraca (manifest, czy_jest_nowsza_wersja). Rzuca wyjątek, gdy źródło niedostępne."""
    loc = _manifest_location(source)
    m = json.loads(_read_bytes(loc).decode("utf-8-sig"))
    if "version" not in m or "package" not in m:
        raise RuntimeError("Nieprawidłowy plik version.json")
    m["_base"] = loc
    newer = _ver(m["version"]) > _ver(VERSION) and m["version"] != _pinned()
    return m, newer


def _safe_extract(z: zipfile.ZipFile, dest: Path) -> None:
    dest = dest.resolve()
    for info in z.infolist():
        target = (dest / info.filename).resolve()
        if target != dest and dest not in target.parents:
            raise RuntimeError("Nieprawidłowa paczka (ścieżka poza folderem)")
    z.extractall(dest)


def has_backup() -> bool:
    return (paths.BACKUP_DIR / "app" / "version.py").exists()


def _disk_version() -> str:
    try:
        text = (paths.APP_DIR / "version.py").read_text(encoding="utf-8")
        return re.search(r'VERSION\s*=\s*"([^"]+)"', text).group(1)
    except Exception:
        return VERSION


def _backup() -> None:
    dest = paths.BACKUP_DIR / "app"
    if dest.exists():
        shutil.rmtree(dest)
    paths.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copytree(paths.APP_DIR, dest, ignore=shutil.ignore_patterns("__pycache__"))


def _install(new_app: Path) -> None:
    new_files = set()
    for src in new_app.rglob("*"):
        if src.is_dir() or "__pycache__" in src.parts:
            continue
        rel = src.relative_to(new_app)
        new_files.add(rel)
        dst = paths.APP_DIR / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    for old in list(paths.APP_DIR.rglob("*.py")):
        rel = old.relative_to(paths.APP_DIR)
        if rel not in new_files and "__pycache__" not in rel.parts:
            old.unlink()
    shutil.rmtree(paths.APP_DIR / "__pycache__", ignore_errors=True)


def apply(m: dict) -> None:
    """Pobiera paczkę, sprawdza ją i podmienia kod. Po błędzie przywraca poprzedni stan."""
    data = _read_bytes(_resolve(m["_base"], m["package"]))
    want = (m.get("sha256") or "").lower()
    if want and hashlib.sha256(data).hexdigest() != want:
        raise RuntimeError("Suma kontrolna paczki się nie zgadza – plik pobrał się uszkodzony.")
    tmp = Path(tempfile.mkdtemp(prefix="integra_upd_"))
    try:
        pkg = tmp / "pkg.zip"
        pkg.write_bytes(data)
        out = tmp / "new"
        out.mkdir()
        with zipfile.ZipFile(pkg) as z:
            _safe_extract(z, out)
        new_app = out / "app"
        vfile = new_app / "version.py"
        if not vfile.exists():
            raise RuntimeError("Paczka nie zawiera folderu app.")
        if f'VERSION = "{m["version"]}"' not in vfile.read_text(encoding="utf-8"):
            raise RuntimeError("Wersja w paczce nie zgadza się z opisem aktualizacji.")
        for f in new_app.rglob("*.py"):
            py_compile.compile(str(f), cfile=str(tmp / "check.pyc"), doraise=True)
        _backup()
        try:
            _install(new_app)
        except Exception:
            rollback(pin=False)
            raise
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def rollback(pin: bool = True) -> None:
    """Przywraca poprzednią wersję. pin=True – nie instaluj ponownie wycofanej wersji."""
    src = paths.BACKUP_DIR / "app"
    if not has_backup():
        raise RuntimeError("Brak kopii poprzedniej wersji.")
    if pin:
        paths.DATA_DIR.mkdir(parents=True, exist_ok=True)
        paths.SKIP_FILE.write_text(_disk_version(), encoding="utf-8")
    for f in list(paths.APP_DIR.rglob("*.py")):
        if "__pycache__" not in f.parts:
            f.unlink()
    shutil.rmtree(paths.APP_DIR / "__pycache__", ignore_errors=True)
    shutil.copytree(src, paths.APP_DIR, dirs_exist_ok=True)


def restart() -> None:
    subprocess.Popen([sys.executable, str(paths.APP_DIR / "start.py")], cwd=str(paths.ROOT))
    os._exit(0)
