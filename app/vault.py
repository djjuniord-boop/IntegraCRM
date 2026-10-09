"""Szyfrowanie hasła aplikacji Google mechanizmem Windows (DPAPI).

Zaszyfrowane hasło da się odczytać tylko na tym samym koncie Windows – skopiowany
plik config.json na innym komputerze lub koncie nic nie zdradzi.
Poza Windows (testy) hasło zostaje w postaci jawnej.
"""
import base64
import os

PREFIX = "dpapi:"


LAST_ERROR = ""


def _call(fn_name: str, data: bytes) -> bytes:
    import ctypes

    class BLOB(ctypes.Structure):
        _fields_ = [("cbData", ctypes.c_uint32), ("pbData", ctypes.c_void_p)]

    crypt32, kernel32 = ctypes.windll.crypt32, ctypes.windll.kernel32
    fn = getattr(crypt32, fn_name)
    fn.argtypes = [ctypes.POINTER(BLOB), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                   ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(BLOB)]
    fn.restype = ctypes.c_int
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p

    buf = ctypes.create_string_buffer(data, len(data))
    src = BLOB(len(data), ctypes.cast(buf, ctypes.c_void_p))
    out = BLOB()
    if not fn(ctypes.byref(src), None, None, None, None, 0x01, ctypes.byref(out)):  # UI_FORBIDDEN
        raise OSError(f"{fn_name}: błąd {ctypes.GetLastError()}")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        kernel32.LocalFree(out.pbData)


def protect(plain: str) -> str:
    if not plain or os.name != "nt" or plain.startswith(PREFIX):
        return plain
    try:
        enc = _call("CryptProtectData", plain.encode("utf-8"))
        return PREFIX + base64.b64encode(enc).decode("ascii")
    except Exception as e:
        global LAST_ERROR
        LAST_ERROR = repr(e)
        return plain


def unprotect(stored: str) -> str:
    if not stored or not stored.startswith(PREFIX):
        return stored or ""
    try:
        return _call("CryptUnprotectData", base64.b64decode(stored[len(PREFIX):])).decode("utf-8")
    except Exception:
        return ""   # np. plik skopiowany z innego konta – trzeba wpisać hasło ponownie
