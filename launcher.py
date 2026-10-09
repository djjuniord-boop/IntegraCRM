"""Punkt wejścia IntegraCRM.exe (PyInstaller).

Plik .exe zawiera Pythona i biblioteki, a sam kod programu wczytuje z folderu app\\ obok,
dzięki czemu aktualizacje podmieniają tylko małe pliki .py – bez przebudowy .exe.
"""
# Importy poniżej nie są tu używane – są po to, żeby PyInstaller dołączył do .exe
# wszystkie moduły, których potrzebuje kod w app\.
import ctypes, datetime, hashlib, json, os, py_compile, re, shutil, smtplib, ssl  # noqa: F401,E401
import subprocess, tempfile, threading, traceback, zipfile, csv, base64, concurrent.futures  # noqa: F401,E401
import urllib.request, urllib.parse  # noqa: F401,E401
import email.message  # noqa: F401
import tkinter, tkinter.ttk, tkinter.font, tkinter.filedialog, tkinter.messagebox, tkinter.scrolledtext  # noqa: F401,E401
import pdfplumber  # noqa: F401
import pytesseract  # noqa: F401
from PIL import Image, ImageGrab, ImageTk, ImageOps, ImageFilter  # noqa: F401

import runpy
import sys
from pathlib import Path

ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
START = ROOT / "app" / "start.py"

if not START.exists():
    from tkinter import messagebox
    r = tkinter.Tk()
    r.withdraw()
    messagebox.showerror("IntegraCRM", f"Nie znaleziono folderu programu:\n{START.parent}\n\n"
                         "Rozpakuj całą paczkę, nie tylko plik IntegraCRM.exe.")
    sys.exit(1)

runpy.run_path(str(START), run_name="__main__")
