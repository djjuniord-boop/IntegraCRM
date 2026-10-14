"""Okna MARŻY w chmurze: odbiorcy maili, wyniki online, kopie plików."""
import os
import threading
import tkinter as tk
from tkinter import filedialog, ttk
from ui import BG, BLACK, FlatButton, INK, MUTED, OK, RED, SURFACE, set_icon
from konfig import COMPANY


# ---------- MARŻA w chmurze ----------
MARZA_BRANCHES = [("wroclaw", "Wrocław"), ("opole", "Opole")]


class MarzaRecipientsDialog(tk.Toplevel):
    """Odbiorcy maili MARŻY: zaznacz, kto ma dostawać, albo dopisz nowy adres (zapis dla całej firmy)."""

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("Odbiorcy maili MARŻA")
        self.configure(bg=SURFACE, padx=22, pady=16)
        self.transient(app)
        self.resizable(False, False)
        set_icon(self)
        f = app.fonts
        self.admin = app.session.is_admin
        data = COMPANY.get("marza") or {}
        self.rows = {}
        tk.Label(self, text="Kto dostaje mail po aktualizacji MARŻY", bg=SURFACE, fg=BLACK,
                 font=f.h2).pack(anchor="w", pady=(0, 8))
        for key, name in MARZA_BRANCHES:
            box = tk.LabelFrame(self, text=f"  {name}  ", bg=SURFACE, fg=INK, font=f.label, padx=10, pady=6)
            box.pack(fill="x", pady=6)
            lst = tk.Frame(box, bg=SURFACE)
            lst.pack(fill="x")
            self.rows[key] = []
            for r in data.get(key) or []:
                self._add_row(key, lst, r.get("email", ""), bool(r.get("on", True)))
            if self.admin:
                add = tk.Frame(box, bg=SURFACE)
                add.pack(fill="x", pady=(6, 0))
                v = tk.StringVar()
                e = tk.Entry(add, textvariable=v, width=34, font=f.body, relief="solid", bd=1)
                e.pack(side="left", ipady=3)
                cb = lambda k=key, l=lst, var=v: self._add_new(k, l, var)
                e.bind("<Return>", lambda ev, c=cb: c())
                FlatButton(add, "+ Dodaj", cb, "ghost", f.small, 10, 4).pack(side="left", padx=6)
        self.msg = tk.Label(self, text="" if self.admin else "Odbiorców zmienia administrator.",
                            bg=SURFACE, fg=MUTED, font=f.small)
        self.msg.pack(anchor="w", pady=(8, 4))
        bar = tk.Frame(self, bg=SURFACE)
        bar.pack(fill="x")
        if self.admin:
            FlatButton(bar, "Zapisz", self.save, "primary", f.btn).pack(side="right")
        FlatButton(bar, "Zamknij", self.destroy, "ghost", f.body, 14, 8).pack(side="right", padx=8)

    def _add_row(self, key, parent, email, on):
        v = tk.BooleanVar(value=on)
        row = tk.Frame(parent, bg=SURFACE)
        row.pack(fill="x")
        tk.Checkbutton(row, text=email, variable=v, bg=SURFACE, activebackground=SURFACE,
                       font=self.app.fonts.body, state="normal" if self.admin else "disabled").pack(side="left")
        item = {"email": email, "var": v, "row": row}
        if self.admin:
            x = tk.Label(row, text="✕", bg=SURFACE, fg=MUTED, cursor="hand2", font=self.app.fonts.small)
            x.pack(side="left", padx=6)
            x.bind("<Button-1>", lambda e: (row.destroy(), self.rows[key].remove(item)))
        self.rows[key].append(item)

    def _add_new(self, key, parent, var):
        e = var.get().strip().lower()
        if not e or "@" not in e or "." not in e.split("@")[-1]:
            self.msg.config(text="Wpisz poprawny adres e-mail.", fg=RED)
            return
        if any(i["email"].lower() == e for i in self.rows[key]):
            self.msg.config(text="Ten adres już jest na liście.", fg=RED)
            return
        self._add_row(key, parent, e, True)
        var.set("")
        self.msg.config(text="")

    def save(self):
        mz = {k: [{"email": i["email"], "on": bool(i["var"].get())} for i in items] for k, items in self.rows.items()}
        try:   # świeży stan z bazy – zmieniamy tylko listę MARŻY, reszta ustawień firmowych zostaje
            value = dict(self.app.session.company() or COMPANY)
            value["marza"] = mz
            self.app.session.set_company(value)
        except Exception as e:
            self.msg.config(text=f"Nie zapisano: {e}", fg=RED)
            return
        COMPANY.clear()
        COMPANY.update(value)
        self.destroy()


def _pln(v):
    try:
        return f"{float(v):,.2f} zł".replace(",", " ").replace(".", ",")
    except (TypeError, ValueError):
        return "—"


class MarzaResultsWindow(tk.Toplevel):
    """Wyniki MARŻY z bazy – ostatni stan każdego miesiąca dla oddziałów (z każdego komputera)."""

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("MARŻA – wyniki online")
        self.geometry("1000x560")
        self.configure(bg=BG, padx=16, pady=12)
        set_icon(self)
        f = app.fonts
        self.msg = tk.Label(self, text="Wczytuję…", bg=BG, fg=MUTED, font=f.small, anchor="w")
        self.msg.pack(fill="x")
        cols = ("branch", "month", "margin", "target", "done", "pct", "at", "who")
        self.tv = ttk.Treeview(self, columns=cols, show="headings")
        for c, h, w in zip(cols, ("Oddział", "Miesiąc", "Marża z raportu", "Cel", "Zrobione", "% celu",
                                  "Ostatnia aktualizacja", "Kto"), (80, 130, 120, 110, 110, 60, 150, 190)):
            self.tv.heading(c, text=h, anchor="w")
            self.tv.column(c, width=w, anchor="w")
        self.tv.pack(fill="both", expand=True, pady=(8, 0))
        tk.Label(self, text="Każda aktualizacja jest też w Dzienniku zmian. Pliki z danego dnia: „Kopie w chmurze”.",
                 bg=BG, fg=MUTED, font=f.small).pack(anchor="w", pady=(6, 0))
        threading.Thread(target=self._load, daemon=True).start()

    def _load(self):
        try:
            rows = self.app.session.call("GET", "/rest/v1/marza_results?select=*&order=run_at.desc&limit=2000") or []
            self.app.after(0, self._show, rows)
        except Exception as e:
            self.app.after(0, lambda err=str(e): self.msg.config(text=f"Błąd: {err}", fg=RED))

    def _show(self, rows):
        if not self.winfo_exists():
            return
        from datetime import datetime as _dt
        names = dict(MARZA_BRANCHES)
        latest, order = {}, []
        for r in rows:   # najnowszy wpis dla oddziału i miesiąca
            k = (r["branch"], r.get("month_label"))
            if k not in latest:
                latest[k] = r
                order.append(k)
        order.sort(key=lambda k: (k[0], str(latest[k].get("period_from") or "")), reverse=True)
        for k in order:
            r = latest[k]
            try:
                at = _dt.fromisoformat(str(r["run_at"]).replace("Z", "+00:00")).astimezone().strftime("%Y-%m-%d %H:%M")
            except ValueError:
                at = str(r.get("run_at", ""))[:16]
            pct = ""
            try:
                pct = f"{100 * float(r['done']) / float(r['target']):.0f}%"
            except (TypeError, ValueError, ZeroDivisionError, KeyError):
                pass
            self.tv.insert("", "end", values=(names.get(r["branch"], r["branch"]), r.get("month_label") or "",
                                              _pln(r.get("margin")), _pln(r.get("target")), _pln(r.get("done")),
                                              pct, at, r.get("user_email") or ""))
        self.msg.config(text=f"Miesięcy: {len(order)}" if order else "Brak wyników – pojawią się po pierwszej "
                        "aktualizacji MARŻY w tej wersji programu.", fg=MUTED)


class MarzaFilesWindow(tk.Toplevel):
    """Kopie kalkulatorów i raportów w chmurze – pobranie na ten komputer."""

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("MARŻA – kopie w chmurze")
        self.geometry("760x520")
        self.configure(bg=BG, padx=16, pady=12)
        set_icon(self)
        f = app.fonts
        bar = tk.Frame(self, bg=BG)
        bar.pack(fill="x")
        self.v_branch = tk.StringVar(value="wroclaw")
        for key, name in MARZA_BRANCHES:
            tk.Radiobutton(bar, text=name, variable=self.v_branch, value=key, bg=BG, activebackground=BG,
                           font=f.body, command=self.load).pack(side="left", padx=(0, 10))
        FlatButton(bar, "Pobierz zaznaczone…", self.download, "primary", f.body, 14, 6).pack(side="right")
        self.msg = tk.Label(self, text="", bg=BG, fg=MUTED, font=f.small, anchor="w")
        self.msg.pack(fill="x", pady=(6, 0))
        self.tv = ttk.Treeview(self, columns=("size",), show="tree headings")
        self.tv.heading("#0", text="Aktualizacja / plik", anchor="w")
        self.tv.heading("size", text="Rozmiar", anchor="w")
        self.tv.column("#0", width=560)
        self.tv.column("size", width=120)
        self.tv.pack(fill="both", expand=True, pady=(6, 0))
        self.load()

    def load(self):
        self.msg.config(text="Wczytuję…", fg=MUTED)
        key = self.v_branch.get()

        def work():
            try:
                s = self.app.session
                out = []
                for y in s.list_files("marza", f"{key}/"):
                    if y.get("id"):
                        continue
                    for run in s.list_files("marza", f"{key}/{y['name']}/")[:60]:
                        if run.get("id"):
                            continue
                        files = s.list_files("marza", f"{key}/{y['name']}/{run['name']}/")
                        out.append((f"{key}/{y['name']}/{run['name']}", files))
                out.sort(reverse=True)
                self.app.after(0, self._show, out)
            except Exception as e:
                self.app.after(0, lambda err=str(e): self.msg.config(text=f"Błąd: {err}", fg=RED))
        threading.Thread(target=work, daemon=True).start()

    def _show(self, runs):
        if not self.winfo_exists():
            return
        self.tv.delete(*self.tv.get_children())
        for path, files in runs:
            label = path.split("/")[-1].replace("_", "  ")
            node = self.tv.insert("", "end", iid=path, text=label, open=False)
            for fl in files:
                size = (fl.get("metadata") or {}).get("size") or 0
                self.tv.insert(node, "end", iid=f"{path}/{fl['name']}", text=fl["name"],
                               values=(f"{size / 1024:.0f} KB",))
        self.msg.config(text=f"Aktualizacji: {len(runs)} (rozwiń, zaznacz plik albo całą aktualizację)"
                        if runs else "Brak kopii – pojawią się po pierwszej aktualizacji MARŻY w tej wersji.", fg=MUTED)

    def download(self):
        sel = self.tv.selection()
        if not sel:
            self.msg.config(text="Zaznacz plik albo aktualizację.", fg=RED)
            return
        paths = []
        for i in sel:
            kids = self.tv.get_children(i)
            paths += list(kids) if kids else [i]
        dest = filedialog.askdirectory(title="Gdzie zapisać pobrane pliki?", parent=self)
        if not dest:
            return
        self.msg.config(text="Pobieram…", fg=MUTED)

        def work():
            try:
                for p in paths:
                    data = self.app.session.download("marza", p)
                    name = f"{p.split('/')[-2]}_{p.split('/')[-1]}"
                    with open(os.path.join(dest, name), "wb") as fh:
                        fh.write(data)
                self.app.after(0, lambda: self.msg.config(text=f"Pobrano plików: {len(paths)} → {dest}", fg=OK))
            except Exception as e:
                self.app.after(0, lambda err=str(e): self.msg.config(text=f"Błąd: {err}", fg=RED))
        threading.Thread(target=work, daemon=True).start()
