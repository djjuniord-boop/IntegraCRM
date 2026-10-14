"""Test okna programu „jak nowy użytkownik” – bez sieci i bez prawdziwego konta.

Uruchamia program z udawaną sesją (admin, pracownik Kontroli CRM z Opola, pracownik MARŻA+SERWIS),
przechodzi przez każdą zakładkę i okno dialogowe, robi zrzuty ekranu i zbiera błędy.
Działa na kopii folderu programu (dane użytkownika nie są ruszane).

Użycie (Linux z wirtualnym ekranem):
    xvfb-run -a -s "-screen 0 1600x1000x24" python tests/ui_smoke.py <folder_programu> <folder_wyników>
Wynik: <folder_wyników>/raport.json + zrzuty PNG. Kod wyjścia 0 = brak błędów.
"""
import json
import os
import shutil
import sys
import tempfile
import traceback
from pathlib import Path

SRC = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2]).resolve()
OUT.mkdir(parents=True, exist_ok=True)

# kopia programu w folderze tymczasowym – testy nie zapisują nic w prawdziwym folderze „data”
WORK = Path(tempfile.mkdtemp(prefix="integra_ui_"))
shutil.copytree(SRC / "app", WORK / "app", ignore=shutil.ignore_patterns("__pycache__"))
(WORK / "data").mkdir()
(WORK / "data" / "config.json").write_text(json.dumps({
    "update_source": "/brak-zrodla-aktualizacji-test", "stats_enabled": False,
    "gmail_user": "test@example.com", "gmail_app_password": "x", "recipients": ["odbiorca@example.com"],
    "marza_folder": ""}), encoding="utf-8")
sys.path.insert(0, str(WORK / "app"))
os.chdir(WORK)

import tkinter as tk  # noqa: E402
from tkinter import messagebox  # noqa: E402

errors, shots, notes = [], [], []

# okna komunikatów nie mogą blokować testu – zapisujemy, co program chciał powiedzieć
for _n in ("showinfo", "showwarning", "showerror", "askyesno", "askokcancel"):
    def _fake(title="", message="", _n=_n, **k):
        notes.append(f"{_n}: {title} – {str(message)[:160]}")
        return False
    setattr(messagebox, _n, _fake)

import cloud  # noqa: E402

COMPANY = {"recipients": ["odbiorca@example.com"], "sender_name": "Kontrola eksportu – Latex Serwis",
           "by_branch": {"Latex Opole": ["opole@example.com"]},
           "marza": {"wroclaw": [{"email": "a@example.com", "on": True}],
                     "opole": [{"email": "b@example.com", "on": False}]}}


def _wyniki_dane():
    """Przykładowe wyniki marży: bieżący miesiąc i 3 poprzednie dla obu oddziałów + aktualizacje z tego miesiąca."""
    import datetime
    t = datetime.date.today()
    names = ["Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec", "Lipiec", "Sierpień", "Wrzesień",
             "Październik", "Listopad", "Grudzień"]
    months, runs = [], []
    for branch, cel, frac in (("wroclaw", 300000, 0.43), ("opole", 160000, 0.39)):
        y, m = t.year, t.month
        for k in range(4):
            done = round(cel * (frac if k == 0 else (0.9 + 0.06 * k)), 2)
            months.append({"branch": branch, "year": y, "month": m, "label": f"{names[m - 1]} {y}", "target": cel,
                           "done": done, "holidays": [], "updated_at": f"{t.isoformat()}T05:40:00Z"})
            y, m = (y - 1, 12) if m == 1 else (y, m - 1)
        for day in (1, 3, 6):
            if day < t.day:
                runs.append({"branch": branch, "month_label": months[-4]["label"], "target": cel,
                             "done": round(cel * frac * day / max(t.day, 1), 2),
                             "run_at": t.replace(day=day).isoformat() + "T07:00:00Z"})
    return months, runs


WYNIKI_MONTHS, WYNIKI_RUNS = _wyniki_dane()
_WYN_BRANCH = {"wroclaw": "Latex Wrocław", "opole": "Latex Opole"}


class FakeSession(cloud.Session):
    """Sesja bez sieci: odpowiada przykładowymi danymi."""

    def __init__(self, role, modules, branches, email="test@example.com"):
        self.access = self.refresh_token = "x"
        self.email = email
        self.profile = {"email": email, "name": "Test " + role, "role": role, "modules": modules,
                        "branches": branches, "active": True}

    def call(self, method, path, body=None, prefer=None):
        if "app_config" in path and "crm" in path and method == "GET":
            return [{"value": COMPANY}]
        if ("marza_months" in path or "marza_results" in path) and method == "GET" and (
                "marza_months" in path or "month_label,done" in path):   # jak can_see_marza w bazie
            rows = WYNIKI_MONTHS if "marza_months" in path else WYNIKI_RUNS
            mods = self.profile["modules"]
            return [r for r in rows if self.is_admin or "marza" in mods or
                    ("wyniki" in mods and _WYN_BRANCH[r["branch"]] in self.profile["branches"])]
        if "marza_results" in path and method == "GET":
            return [{"branch": "wroclaw", "month_label": "Październik 2026", "period_from": "2026-10-01",
                     "margin": 12345.5, "target": 300000, "done": 120000.5, "run_at": "2026-10-13T15:40:00Z",
                     "user_email": "test@example.com"}]
        if "checks" in path and method == "GET":   # jak zasada w bazie: admin wszystko, pracownik swoje oddziały
            rows = [{"created_at": "2026-10-13T10:00:00Z", "pdf_name": "wroclaw.pdf", "n_integra": 9, "n_crm": 8,
                     "missing": ["DW3M448"], "uncertain": [], "user_email": "wroclaw@example.com",
                     "branches": ["Latex Wrocław"]},
                    {"created_at": "2026-10-13T11:00:00Z", "pdf_name": "opole.pdf", "n_integra": 5, "n_crm": 5,
                     "missing": [], "uncertain": [], "user_email": "opole@example.com", "branches": ["Latex Opole"]}]
            return [r for r in rows if self.is_admin or set(r["branches"]) & set(self.profile["branches"])]
        if "visit_stats" in path and method == "GET":   # jak zasada stats_read: moduł statystyki + oddział
            if not (self.is_admin or "statystyki" in self.profile["modules"]):
                return []
            rows = [{"branch": b, "day": f"2026-{m:02d}-{d:02d}", "visits": v, "lists": l_, "missing": v - l_}
                    for b, k in (("Latex Wrocław", 1), ("Latex Opole", 2))
                    for m in (8, 9, 10) for d, v, l_ in ((6, 40 * k, 36 * k - m + 8), (7, 35 * k, 30 * k))]
            return [r for r in rows if self.is_admin or r["branch"] in self.profile["branches"]]
        if "audit_log" in path:
            return [{"at": "2026-10-13T15:40:00Z", "email": "test@example.com", "action": "mail",
                     "entity": "sprawdzenie", "label": "test.pdf", "detail": {"do": "a@example.com"}}]
        return []

    def rpc(self, fn, **a):
        return None

    def refresh(self):
        pass

    def list_users(self):
        return [{"email": "admin@example.com", "role": "admin", "active": True, "last_seen": "2026-10-13T15:00:00"},
                {"email": "opole@example.com", "name": "Jan", "role": "user", "modules": ["crm"],
                 "branches": ["Latex Opole"], "active": False}]

    def list_files(self, bucket, prefix):
        return []

    def min_version(self):
        return ""


SCENARIOS = [
    ("admin", FakeSession("admin", [], [])),
    ("kontrola_opole", FakeSession("user", ["crm", "historia"], ["Latex Opole"])),
    ("statystyki_wroclaw", FakeSession("user", ["statystyki"], ["Latex Wrocław"])),
    ("marza_serwis", FakeSession("user", ["marza", "serwis"], ["Latex Wrocław"])),
    ("handlowiec_wroclaw", FakeSession("user", ["wyniki"], ["Latex Wrocław"])),
    ("handlowiec_stangum", FakeSession("user", ["wyniki"], ["Stangum Opole"])),
]


def grab(win, path):
    """Zrzut okna osobnym procesem (ImageMagick „import”) – bez łączenia się z ekranem z tego procesu."""
    import subprocess
    win.update_idletasks()
    x, y, w, h = win.winfo_rootx(), win.winfo_rooty(), win.winfo_width(), win.winfo_height()
    subprocess.run(["import", "-window", "root", "-crop", f"{w}x{h}+{x}+{y}", "+repage", str(path)],
                   check=True, timeout=30, capture_output=True)


def shot(app, name):
    try:
        p = OUT / f"{name}.png"
        grab(app, p)
        shots.append(p.name)
    except Exception as e:
        errors.append(f"zrzut {name}: {e}")


def run_scenario(label, sess):
    """Kroki wykonywane w pętli okna (mainloop) – tak jak u użytkownika, łącznie z danymi wczytywanymi w tle."""
    import gui as g
    try:
        app = g.App(sess)
    except Exception:
        errors.append(f"[{label}] start okna: {traceback.format_exc()}")
        return {}
    app.report_callback_exception = lambda *a: errors.append(
        f"[{label}] zdarzenie: {''.join(traceback.format_exception(*a))[-1500:]}")
    app.geometry("1400x900+0+0")
    info = {"tabs": list(app.pages)}
    steps = []

    def tab_step(key):
        def go():
            app.show_tab(key)
        def snap():
            shot(app, f"{label}__{key}")
        steps.extend([(go, 900), (snap, 100)])

    for key in list(app.pages):
        tab_step(key)
    dialogs = [("ustawienia", lambda: g.SettingsDialog(app))]
    if sess.is_admin:
        dialogs += [("uzytkownik", lambda: g.UserDialog(app, sess.list_users()[1])),
                    ("nowy_uzytkownik", lambda: g.UserDialog(app)),
                    ("dziennik", lambda: g.AuditWindow(app))]
    if sess.can("marza"):
        dialogs += [("marza_odbiorcy", lambda: g.MarzaRecipientsDialog(app)),
                    ("marza_wyniki", lambda: g.MarzaResultsWindow(app)),
                    ("marza_kopie", lambda: g.MarzaFilesWindow(app))]
    holder = {}

    def dialog_step(name, make):
        def open_():
            holder["w"] = make()
        def snap_close():
            w = holder.pop("w", None)
            if w is None:
                return
            try:
                grab(w, OUT / f"{label}__okno_{name}.png")
                shots.append(f"{label}__okno_{name}.png")
            except Exception as e:
                errors.append(f"zrzut okna {name}: {e}")
            w.destroy()
        steps.extend([(open_, 1200), (snap_close, 100)])

    for name, make in dialogs:
        dialog_step(name, make)

    def collect():
        if "main" in app.pages:
            info["branches_crm"] = list(app.branch_vars)
        if "users" in app.pages:
            info["users_rows"] = len(app.users_tv.get_children())
        if "hist" in app.pages:
            info["history_rows"] = len(app.hist_tree.get_children())
        if "stat" in app.pages:
            info["stat_oddzialy"] = sorted({r["branch"] for r in app.st_rows})
            info["stat_miesiace"] = len(app.st_tree.get_children())
            info["stat_prognoza"] = app.st_wynik.cget("text")
        if "wyniki" in app.pages:
            info["wyniki_oddzialy"] = list(app.wyn_branches)
            info["wyniki_dane"] = sorted(app.wyn_data)
            info["wyniki_pokazane"] = bool(app.wyn_main.winfo_ismapped()) if app.wyn_data else False
            info["wyniki_procent"] = app.wyn_pct.cget("text")
    steps.append((collect, 10))

    def run(i=0):
        if i >= len(steps):
            app.quit()
            return
        fn, delay = steps[i]
        try:
            fn()
        except Exception:
            errors.append(f"[{label}] krok {i} ({getattr(fn, '__name__', '?')}): {traceback.format_exc()}")
        app.after(delay, run, i + 1)

    app.after(500, run)
    app.after(120000, app.quit)   # bezpiecznik
    app.mainloop()
    try:
        app._on_close() if hasattr(app, "_on_close") else app.destroy()
    except Exception:
        try:
            app.destroy()
        except Exception:
            pass
    return info


def run_login():
    """Okno logowania (bez zapamiętanej sesji): zrzut i zamknięcie."""
    import gui
    orig = tk.Tk.mainloop

    def mainloop(self, n=0):
        def snap():
            try:
                grab(self, OUT / "logowanie.png")
                shots.append("logowanie.png")
            except Exception as e:
                errors.append(f"zrzut logowania: {e}")
            self.destroy()
        self.after(1500, snap)
        return orig(self, n)
    tk.Tk.mainloop = mainloop
    try:
        sess = gui.login_flow()
        if sess is not None:
            errors.append("logowanie: okno zwróciło sesję bez wpisania hasła")
    except Exception:
        errors.append(f"logowanie: {traceback.format_exc()}")
    finally:
        tk.Tk.mainloop = orig
    return {"shown": "logowanie.png" in shots}


def main():
    only = os.environ.get("UI_SMOKE_ONLY")
    if only == "logowanie":
        info = run_login()
        (OUT / "_logowanie.json").write_text(json.dumps({"info": info, "errors": errors, "messages": notes,
                                                         "shots": shots}, ensure_ascii=False), encoding="utf-8")
        shutil.rmtree(WORK, ignore_errors=True)
        os._exit(0)
    if only:   # proces potomny: jeden scenariusz
        sess = dict(SCENARIOS)[only]
        info = run_scenario(only, sess)
        (OUT / f"_{only}.json").write_text(json.dumps({"info": info, "errors": errors, "messages": notes,
                                                       "shots": shots}, ensure_ascii=False), encoding="utf-8")
        shutil.rmtree(WORK, ignore_errors=True)
        os._exit(0)
    import subprocess
    result, all_err, all_notes, all_shots = {}, [], [], []
    for label in ["logowanie"] + [lb for lb, _ in SCENARIOS]:
        env = dict(os.environ, UI_SMOKE_ONLY=label)
        p = subprocess.run([sys.executable, __file__, str(SRC), str(OUT)], env=env, timeout=300,
                           capture_output=True, text=True)
        part = OUT / f"_{label}.json"
        if p.returncode != 0 or not part.exists():
            all_err.append(f"[{label}] proces zakończony kodem {p.returncode}: {(p.stderr or '')[-1500:]}")
            continue
        d = json.loads(part.read_text(encoding="utf-8"))
        part.unlink()
        result[label] = d["info"]
        all_err += d["errors"]
        all_notes += d["messages"]
        all_shots += d["shots"]
    checks = {
        "admin_ma_wszystkie_zakladki": all(t in result.get("admin", {}).get("tabs", []) for t in
                                           ("main", "hist", "stat", "marza", "wyniki", "serwis", "users", "help")),
        "admin_lista_uzytkownikow": result.get("admin", {}).get("users_rows") == 2,
        "okno_logowania": result.get("logowanie", {}).get("shown") is True,
        "historia_z_bazy": result.get("admin", {}).get("history_rows") == 2,
        "historia_opole_tylko_swoja": result.get("kontrola_opole", {}).get("history_rows") == 1,
        "opole_tylko_kontrola": result.get("kontrola_opole", {}).get("tabs") == ["main", "hist", "help"],
        "opole_tylko_swoj_oddzial": result.get("kontrola_opole", {}).get("branches_crm") == ["Latex Opole"],
        "marza_serwis_bez_kontroli": "main" not in result.get("marza_serwis", {}).get("tabs", ["main"]),
        "marza_ma_wyniki": "wyniki" in result.get("marza_serwis", {}).get("tabs", []),
        "admin_statystyki_oba": result.get("admin", {}).get("stat_oddzialy") == ["Latex Opole", "Latex Wrocław"],
        "statystyki_tylko_swoje": (result.get("statystyki_wroclaw", {}).get("tabs") == ["stat", "help"]
                                   and result.get("statystyki_wroclaw", {}).get("stat_oddzialy") == ["Latex Wrocław"]
                                   and result.get("statystyki_wroclaw", {}).get("stat_miesiace") == 3),
        "statystyki_prognoza": "list kontrolnych" in result.get("statystyki_wroclaw", {}).get("stat_prognoza", ""),
        "admin_wyniki_oba_oddzialy": result.get("admin", {}).get("wyniki_dane") == ["opole", "wroclaw"],
        "handlowiec_tylko_wyniki": result.get("handlowiec_wroclaw", {}).get("tabs") == ["wyniki", "help"],
        "handlowiec_tylko_wroclaw": (result.get("handlowiec_wroclaw", {}).get("wyniki_oddzialy") == ["wroclaw"]
                                     and result.get("handlowiec_wroclaw", {}).get("wyniki_dane") == ["wroclaw"]),
        "handlowiec_widzi_wynik": result.get("handlowiec_wroclaw", {}).get("wyniki_procent") == "43%",
        "stangum_bez_wynikow": result.get("handlowiec_stangum", {}).get("wyniki_oddzialy") == [],
    }
    report = {"ok": not all_err and all(checks.values()), "checks": checks, "scenarios": result,
              "errors": all_err, "messages": all_notes, "screenshots": all_shots}
    (OUT / "raport.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "checks": checks, "errors": len(all_err), "screens": len(all_shots)},
                     ensure_ascii=False))
    for e in all_err:
        print("BŁĄD:", e[-800:])
    shutil.rmtree(WORK, ignore_errors=True)
    os._exit(0 if report["ok"] else 1)


main()
