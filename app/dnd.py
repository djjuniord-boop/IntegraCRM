"""Przeciąganie plików z Eksploratora na okno (Windows, bez dodatkowych bibliotek).

Podpina się pod komunikat WM_DROPFILES okna Tk. Na innych systemach nic nie robi.
"""
import os

WM_DROPFILES = 0x0233
GWLP_WNDPROC = -4
_keep = []   # referencje do callbacków, żeby nie zebrał ich garbage collector


def enable(widget, on_files) -> bool:
    """on_files(list[str]) wywoływane po upuszczeniu plików. Zwraca True, jeśli się udało."""
    if os.name != "nt":
        return False
    try:
        import ctypes
        from ctypes import wintypes

        user32, shell32 = ctypes.windll.user32, ctypes.windll.shell32
        LRESULT = ctypes.c_ssize_t
        WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
        user32.CallWindowProcW.restype = LRESULT
        user32.CallWindowProcW.argtypes = [ctypes.c_void_p, wintypes.HWND, wintypes.UINT,
                                           wintypes.WPARAM, wintypes.LPARAM]
        setter = getattr(user32, "SetWindowLongPtrW", None) or user32.SetWindowLongW
        setter.restype = ctypes.c_void_p
        setter.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
        shell32.DragQueryFileW.argtypes = [wintypes.HANDLE, wintypes.UINT, wintypes.LPWSTR, wintypes.UINT]
        shell32.DragQueryFileW.restype = wintypes.UINT
        shell32.DragFinish.argtypes = [wintypes.HANDLE]

        hwnd = widget.winfo_id()
        old = [None]

        def proc(h, msg, wp, lp):
            if msg == WM_DROPFILES:
                try:
                    n = shell32.DragQueryFileW(wp, 0xFFFFFFFF, None, 0)
                    files = []
                    for i in range(n):
                        size = shell32.DragQueryFileW(wp, i, None, 0) + 1
                        buf = ctypes.create_unicode_buffer(size)
                        shell32.DragQueryFileW(wp, i, buf, size)
                        files.append(buf.value)
                    shell32.DragFinish(wp)
                    widget.after(0, on_files, files)
                except Exception:
                    pass
                return 0
            return user32.CallWindowProcW(old[0], h, msg, wp, lp)

        cb = WNDPROC(proc)
        _keep.append(cb)
        old[0] = setter(hwnd, GWLP_WNDPROC, ctypes.cast(cb, ctypes.c_void_p))
        if not old[0]:
            return False
        shell32.DragAcceptFiles(hwnd, True)
        return True
    except Exception:
        return False
