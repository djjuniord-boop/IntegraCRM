"""Uruchamiacz: łapie błędy startu i zapisuje je do data/error.log."""
import datetime
import sys
import traceback
from pathlib import Path

APP = Path(__file__).resolve().parent
sys.path.insert(0, str(APP))


def main():
    try:
        import gui
        gui.main()
    except Exception:
        log = APP.parent / "data" / "error.log"
        try:
            log.parent.mkdir(parents=True, exist_ok=True)
            with open(log, "a", encoding="utf-8") as f:
                f.write(f"\n[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}]\n{traceback.format_exc()}")
        except OSError:
            pass
        try:
            import tkinter
            from tkinter import messagebox
            r = tkinter.Tk()
            r.withdraw()
            messagebox.showerror(
                "Błąd programu",
                f"Program napotkał błąd i nie może się uruchomić.\n\nSzczegóły: {log}\n\n"
                "Jeśli to zaczęło się po aktualizacji, uruchom Przywroc-poprzednia.bat.")
        except Exception:
            pass
        sys.exit(1)


main()
