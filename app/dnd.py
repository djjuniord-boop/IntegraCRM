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

        user32, shell32 = ctypes.windll.user32, ctypes.windll.shell32
        LRESULT = ctypes.c_ssize_t
        WNDPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t)
        user32.CallWindowProcW.restype = LRESULT
        user32.CallWindowProcW.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint,
                                           ctypes.c_size_t, ctypes.c_ssize_t]
        setter = getattr(user32, "SetWindowLongPtrW", None) or user32.SetWindowLongW
        setter.restype = ctypes.c_void_p
        setter.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
        shell32.DragQueryFileW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_wchar_p, ctypes.c_uint]
        shell32.DragQueryFileW.restype = ctypes.c_uint
        shell32.DragFinish.argtypes = [ctypes.c_void_p]

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
