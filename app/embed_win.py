"""Osadzanie okna innego procesu (okno panelu SERWIS QR) wewnątrz ramki Tkinter – tylko Windows."""
import ctypes
import sys

_ok = sys.platform == "win32"
if _ok:
    from ctypes import wintypes
    u32 = ctypes.windll.user32
    u32.GetWindowLongW.restype = ctypes.c_long
    u32.SetWindowLongW.restype = ctypes.c_long
    u32.SetParent.restype = wintypes.HWND
    u32.SetParent.argtypes = [wintypes.HWND, wintypes.HWND]
    u32.IsWindow.argtypes = [wintypes.HWND]
    u32.MoveWindow.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.BOOL]
    u32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    u32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                 ctypes.c_int, ctypes.c_uint]
    u32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    u32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    u32.SetFocus.argtypes = [wintypes.HWND]

GWL_STYLE = -16
WS_CHILD, WS_POPUP, WS_CAPTION, WS_THICKFRAME = 0x40000000, 0x80000000, 0x00C00000, 0x00040000
WS_SYSMENU, WS_MINIMIZEBOX, WS_MAXIMIZEBOX, WS_CLIPCHILDREN = 0x00080000, 0x00020000, 0x00010000, 0x02000000
SWP_NOZORDER, SWP_FRAMECHANGED, SWP_NOMOVE, SWP_NOSIZE = 0x0004, 0x0020, 0x0002, 0x0001
SW_HIDE, SW_SHOW = 0, 5


def available() -> bool:
    return _ok


def find_window(pid: int, title: str) -> int:
    """Uchwyt okna najwyższego poziomu procesu pid o podanym tytule (0 = nie znaleziono)."""
    if not _ok:
        return 0
    found = []
    proto = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def cb(hwnd, _):
        p = wintypes.DWORD()
        u32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
        if p.value == pid:
            buf = ctypes.create_unicode_buffer(256)
            u32.GetWindowTextW(hwnd, buf, 256)
            if buf.value == title:
                found.append(hwnd)
                return False
        return True

    u32.EnumWindows(proto(cb), 0)
    return int(found[0]) if found else 0


def embed(hwnd: int, parent: int, w: int, h: int) -> bool:
    """Wstawia okno hwnd jako dziecko okna parent i dopasowuje do rozmiaru."""
    if not _ok or not hwnd or not u32.IsWindow(hwnd):
        return False
    ps = u32.GetWindowLongW(parent, GWL_STYLE)
    u32.SetWindowLongW(parent, GWL_STYLE, ps | WS_CLIPCHILDREN)   # Tk nie zamaluje panelu
    st = u32.GetWindowLongW(hwnd, GWL_STYLE) & 0xFFFFFFFF
    st &= ~(WS_POPUP | WS_CAPTION | WS_THICKFRAME | WS_SYSMENU | WS_MINIMIZEBOX | WS_MAXIMIZEBOX)
    st |= WS_CHILD
    u32.SetWindowLongW(hwnd, GWL_STYLE, ctypes.c_long(st - (1 << 32) if st >= (1 << 31) else st).value)
    u32.SetParent(hwnd, parent)
    u32.SetWindowPos(hwnd, 0, 0, 0, max(w, 1), max(h, 1), SWP_NOZORDER | SWP_FRAMECHANGED)
    u32.ShowWindow(hwnd, SW_SHOW)
    return True


def resize(hwnd: int, w: int, h: int) -> None:
    if _ok and hwnd and u32.IsWindow(hwnd):
        u32.MoveWindow(hwnd, 0, 0, max(w, 1), max(h, 1), True)


def show(hwnd: int, visible: bool) -> None:
    if _ok and hwnd and u32.IsWindow(hwnd):
        u32.ShowWindow(hwnd, SW_SHOW if visible else SW_HIDE)


def alive(hwnd: int) -> bool:
    return bool(_ok and hwnd and u32.IsWindow(hwnd))


def focus(hwnd: int) -> None:
    if _ok and hwnd and u32.IsWindow(hwnd):
        u32.SetFocus(hwnd)
