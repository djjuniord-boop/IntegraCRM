"""Szyfrowanie hasła aplikacji Google mechanizmem Windows (DPAPI).

Zaszyfrowane hasło da się odczytać tylko na tym samym koncie Windows – skopiowany
plik config.json na innym komputerze lub koncie nic nie zdradzi.
Poza Windows (testy) hasło zostaje w postaci jawnej.
"""
import base64
import os

PREFIX = "dpapi:"


def _blob(data: bytes):
    import ctypes
    from ctypes import wintypes

    class BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    buf = ctypes.create_string_buffer(data, len(data))
    return BLOB, BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), buf


def _call(fn_name: str, data: bytes) -> bytes:
    import ctypes
    BLOB, src, _keep = _blob(data)
    out = BLOB()
    fn = getattr(ctypes.windll.crypt32, fn_name)
    ok = fn(ctypes.byref(src), None, None, None, None, 0x01, ctypes.byref(out))  # UI_FORBIDDEN
    if not ok:
        raise OSError(f"{fn_name} nie powiodło się")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(out.pbData)


def protect(plain: str) -> str:
    if not plain or os.name != "nt" or plain.startswith(PREFIX):
        return plain
    try:
        enc = _call("CryptProtectData", plain.encode("utf-8"))
        return PREFIX + base64.b64encode(enc).decode("ascii")
    except Exception:
        return plain


def unprotect(stored: str) -> str:
    if not stored or not stored.startswith(PREFIX):
        return stored or ""
    try:
        return _call("CryptUnprotectData", base64.b64decode(stored[len(PREFIX):])).decode("utf-8")
    except Exception:
        return ""   # np. plik skopiowany z innego konta – trzeba wpisać hasło ponownie
