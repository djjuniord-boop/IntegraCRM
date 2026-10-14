"""Zakładka WYNIKI: aktualny wynik marży oddziału dla handlowców (Wrocław / Opole), admin widzi oba."""
import threading
import tkinter as tk
from tkinter import ttk

from ui import BG, BLACK, FlatButton, INK, LINE, MUTED, OK, RED, SURFACE, WARN, card
from wyniki import dane

ODSWIEZ_MS = 5 * 60 * 1000   # automatyczne odświeżanie, gdy program jest otwarty
DARK, DARK_MUTED, BAR_BG, PLAN = "#111111", "#BDBDBD", "#2C2C2C", "#FFFFFF"


class WynikiMixin:
    """Zakładka WYNIKI. Część klasy okna programu (App) – metody korzystają z jej pól (self.*).
    Dane: tabele marza_months (miesiące z kalkulatora) i marza_results (kolejne aktualizacje) – kto co widzi,
    pilnuje baza (funkcja can_see_marza)."""

    def wyniki_oddzialy(self) -> list:
        """Oddziały, których wyniki to konto może oglądać (admin i MARŻA – oba)."""
        s = self.session
        if s is None or s.is_admin or s.can("marza"):
            return [k for k, _ in dane.ODDZIALY]
        mine = {dane.ODDZIAL_KONTA.get(b) for b in s.branches()}
        return [k for k, _ in dane.ODDZIALY if k in mine]

    # ---------- układ ----------
    def _build_wyniki(self, page):
        f = self.fonts
        self.wyn_branches = self.wyniki_oddzialy()
        self.wyn_branch = self.wyn_branches[0] if self.wyn_branches else None
        self.wyn_data = {}          # oddział → {"months": [...], "runs": [...]}
        self.wyn_loading = False

        bar = tk.Frame(page, bg=BG)
        bar.pack(fill="x", pady=(4, 10))
        tk.Label(bar, text="Wyniki marży", bg=BG, fg=BLACK, font=f.h1).pack(side="left")
        self.wyn_tabs = {}
        if len(self.wyn_branches) > 1:
            sw = tk.Frame(bar, bg=BLACK, padx=3, pady=3)
            sw.pack(side="left", padx=18)
            for key, name in dane.ODDZIALY:
                if key in self.wyn_branches:
                    b = tk.Label(sw, text=name, font=f.label, padx=16, pady=6, cursor="hand2")
                    b.pack(side="left", padx=1)
                    b.bind("<Button-1>", lambda e, k=key: self.wyniki_pokaz(k))
                    self.wyn_tabs[key] = b
        FlatButton(bar, "Odśwież", lambda: self.wyniki_odswiez(), "ghost", f.body, 14, 6).pack(side="right")
        self.wyn_info = tk.Label(bar, text="", bg=BG, fg=MUTED, font=f.small)
        self.wyn_info.pack(side="right", padx=12)
        self.wyn_obie = tk.Label(page, text="", bg=BG, fg=INK, font=f.body, anchor="w")
        if len(self.wyn_branches) > 1:
            self.wyn_obie.pack(fill="x", pady=(0, 8))

        self.wyn_body = tk.Frame(page, bg=BG)
        self.wyn_body.pack(fill="both", expand=True)
        self.wyn_msg = tk.Label(self.wyn_body, text="Wczytuję wyniki…", bg=BG, fg=MUTED, font=f.body)
        self.wyn_msg.pack(anchor="w", pady=20)
        self._wyn_build_cards()
        if self.session is None:
            self.wyn_msg.config(text="Wyniki są dostępne po zalogowaniu.")
            return
        if not self.wyn_branches:
            self.wyn_msg.config(text="Twoje konto nie ma przypisanego oddziału z wynikami marży "
                                     "(Wrocław albo Opole). Skontaktuj się z administratorem.", fg=WARN)
            return
        self.after(200, self.wyniki_odswiez)
        self.after(ODSWIEZ_MS, self._wyn_auto)

    def _wyn_build_cards(self):
        f = self.fonts
        self.wyn_main = tk.Frame(self.wyn_body, bg=BG)   # pokazywane po wczytaniu danych
        top = tk.Frame(self.wyn_main, bg=BG)
        top.pack(fill="x")
        hero = tk.Frame(top, bg=DARK, padx=22, pady=18)
        hero.pack(side="left", fill="both", expand=True)
        self.wyn_month = tk.Label(hero, text="", bg=DARK, fg=DARK_MUTED, font=f.label, anchor="w")
        self.wyn_month.pack(fill="x")
        row = tk.Frame(hero, bg=DARK)
        row.pack(fill="x", pady=(6, 2))
        left = tk.Frame(row, bg=DARK)
        left.pack(side="left")
        tk.Label(left, text="ZROBIONE", bg=DARK, fg=DARK_MUTED, font=f.small).pack(anchor="w")
        self.wyn_done = tk.Label(left, text="", bg=DARK, fg="white", font=(f.family, 30, "bold"))
        self.wyn_done.pack(anchor="w")
        self.wyn_target = tk.Label(left, text="", bg=DARK, fg=DARK_MUTED, font=f.body)
        self.wyn_target.pack(anchor="w")
        self.wyn_pct = tk.Label(row, text="", bg=DARK, fg="#FF4A55", font=(f.family, 40, "bold"))
        self.wyn_pct.pack(side="right", anchor="s")
        tk.Label(row, text="realizacji celu", bg=DARK, fg=DARK_MUTED, font=f.small).pack(side="right", anchor="s",
                                                                                         padx=(0, 8), pady=(0, 10))
        self.wyn_bar = tk.Canvas(hero, height=16, bg=DARK, highlightthickness=0)
        self.wyn_bar.pack(fill="x", pady=(10, 4))
        self.wyn_bar.bind("<Configure>", lambda e: self._wyn_draw_bar())
        self.wyn_plan = tk.Label(hero, text="", bg=DARK, fg=DARK_MUTED, font=f.small, anchor="w")
        self.wyn_plan.pack(fill="x")

        tiles = tk.Frame(top, bg=BG)
        tiles.pack(side="left", fill="y", padx=(14, 0))
        self.wyn_tiles = {}
        for i, (key, title) in enumerate((("brakuje", "Brakuje do celu"), ("potrzeba", "Potrzeba dziennie"),
                                          ("srednio", "Średnio dziennie dotąd"), ("prognoza", "Prognoza na koniec"),
                                          ("tempo", "Tempo wobec planu"), ("dni", "Zostało dni roboczych"))):
            c = card(tiles, padx=14, pady=10)
            c.grid(row=i // 2, column=i % 2, padx=(0, 10), pady=(0, 10), sticky="nsew")
            tk.Label(c, text=title, bg=SURFACE, fg=MUTED, font=f.small, anchor="w").pack(fill="x")
            v = tk.Label(c, text="—", bg=SURFACE, fg=BLACK, font=(f.family, 16, "bold"), anchor="w", width=13)
            v.pack(fill="x")
            self.wyn_tiles[key] = v

        low = tk.Frame(self.wyn_main, bg=BG)
        low.pack(fill="both", expand=True, pady=(4, 0))
        ch = card(low, padx=14, pady=10)
        ch.pack(side="left", fill="both", expand=True)
        hd = tk.Frame(ch, bg=SURFACE)
        hd.pack(fill="x")
        tk.Label(hd, text="Plan i wykonanie (narastająco)", bg=SURFACE, fg=BLACK, font=f.label).pack(side="left")
        leg = tk.Frame(hd, bg=SURFACE)
        leg.pack(side="right")
        tk.Label(leg, text="■ wykonanie", bg=SURFACE, fg=RED, font=f.small).pack(side="left", padx=6)
        tk.Label(leg, text="— plan", bg=SURFACE, fg=INK, font=f.small).pack(side="left")
        self.wyn_chart = tk.Canvas(ch, height=230, bg=SURFACE, highlightthickness=0)
        self.wyn_chart.pack(fill="both", expand=True, pady=(8, 0))
        self.wyn_chart.bind("<Configure>", lambda e: self._wyn_draw_chart())
        self.wyn_chart_note = tk.Label(ch, text="", bg=SURFACE, fg=MUTED, font=f.small, anchor="w")
        self.wyn_chart_note.pack(fill="x")

        hist = card(low, padx=14, pady=10)
        hist.pack(side="left", fill="both", padx=(14, 0))
        tk.Label(hist, text="Poprzednie miesiące", bg=SURFACE, fg=BLACK, font=f.label, anchor="w").pack(fill="x")
        self.wyn_hist = ttk.Treeview(hist, columns=("m", "done", "cel", "pct"), show="headings", height=6,
                                     style="H.Treeview")
        for c, t, w, a in (("m", "Miesiąc", 140, "w"), ("done", "Zrobione", 110, "e"), ("cel", "Cel", 110, "e"),
                           ("pct", "% celu", 70, "e")):
            self.wyn_hist.heading(c, text=t, anchor=a)
            self.wyn_hist.column(c, width=w, anchor=a)
        self.wyn_hist.tag_configure("ok", foreground=OK)
        self.wyn_hist.tag_configure("bad", foreground=RED)
        self.wyn_hist.pack(fill="both", expand=True, pady=(6, 0))
        self.wyn_sum = None

    # ---------- dane ----------
    def wyniki_odswiez(self):
        if self.wyn_loading or not self.wyn_branches or self.session is None:
            return
        self.wyn_loading = True
        self.wyn_info.config(text="Wczytuję…", fg=MUTED)
        from datetime import date
        od = date.today().replace(day=1)
        od = (od.replace(year=od.year - 1, month=12) if od.month == 1 else od.replace(month=od.month - 1)).isoformat()

        def work():
            try:
                months = self.session.call("GET", "/rest/v1/marza_months?select=*&order=year.desc,month.desc") or []
                runs = self.session.call(
                    "GET", "/rest/v1/marza_results?select=branch,month_label,done,target,run_at"
                           f"&run_at=gte.{od}&order=run_at.asc") or []
                data = {k: {"months": [m for m in months if m.get("branch") == k],
                            "runs": [r for r in runs if r.get("branch") == k]} for k in self.wyn_branches}
                self.after(0, self._wyn_loaded, data, None)
            except Exception as e:
                self.after(0, self._wyn_loaded, None, e)
        threading.Thread(target=work, daemon=True).start()

    def _wyn_loaded(self, data, err):
        self.wyn_loading = False
        if err is not None:
            self.wyn_info.config(text=f"Nie udało się wczytać wyników: {err}", fg=RED)
            if not self.wyn_data:
                self.wyn_msg.config(text="Nie udało się wczytać wyników. Sprawdź internet i kliknij „Odśwież”.",
                                    fg=RED)
            return
        self.wyn_data = data
        self.wyniki_pokaz(self.wyn_branch)

    def _wyn_auto(self):
        try:
            if getattr(self, "current_tab", "") == "wyniki":
                self.wyniki_odswiez()
        finally:
            self.after(ODSWIEZ_MS, self._wyn_auto)

    # ---------- wyświetlanie ----------
    def wyniki_pokaz(self, branch):
        self.wyn_branch = branch
        for k, b in self.wyn_tabs.items():
            b.config(bg=RED if k == branch else BLACK, fg="white" if k == branch else "#CFCFCF")
        names = dict(dane.ODDZIALY)
        if len(self.wyn_branches) > 1:   # szybki podgląd obu oddziałów
            parts = []
            for k in self.wyn_branches:
                m = dane.wybierz_miesiac((self.wyn_data.get(k) or {}).get("months", []))
                s = dane.podsumowanie(m) if m else None
                parts.append(f"{names[k]}: " + (f"{s['pct']:.0f}% celu" if s and s["pct"] is not None else "brak danych"))
            self.wyn_obie.config(text="   ·   ".join(parts))
        d = self.wyn_data.get(branch) or {}
        m = dane.wybierz_miesiac(d.get("months", []))
        if m is None:
            self.wyn_main.pack_forget()
            self.wyn_msg.pack(anchor="w", pady=20)
            self.wyn_msg.config(text=f"Brak wyników dla oddziału {names.get(branch, branch)} – pojawią się po "
                                     "najbliższej aktualizacji MARŻY.", fg=MUTED)
            self.wyn_info.config(text="")
            return
        s = dane.podsumowanie(m)
        self.wyn_sum, self.wyn_points = s, dane.punkty_wykresu(m, d.get("runs", []))
        self.wyn_msg.pack_forget()
        self.wyn_main.pack(fill="both", expand=True)
        self.wyn_month.config(text=f"{names.get(branch, branch).upper()}  ·  {s['label']}"
                                   + ("" if s["biezacy"] else "  (ostatni miesiąc z wynikami)"))
        self.wyn_done.config(text=dane.zl(s["zrobione"]))
        self.wyn_target.config(text=f"cel {dane.zl(s['cel'])}")
        self.wyn_pct.config(text=f"{s['pct']:.0f}%" if s["pct"] is not None else "—")
        self.wyn_plan.config(text=(f"▲ plan na dziś {dane.zl(s['plan_dzis'])}  ·  dzień roboczy "
                                   f"{min(s['dni_minelo'] + 1, s['dni_all'])} z {s['dni_all']}")
                             if s["biezacy"] and s["plan_dzis"] is not None else
                             ("brak celu w kalkulatorze" if s["cel"] is None else ""))
        t = self.wyn_tiles
        t["brakuje"].config(text=dane.zl(s["brakuje"]))
        t["potrzeba"].config(text=dane.zl(s["potrzeba_dziennie"]) if s["biezacy"] else "—", fg=RED)
        t["srednio"].config(text=dane.zl(s["srednio_dziennie"]))
        t["prognoza"].config(text=dane.zl(s["prognoza"]) if s["biezacy"] else "—")
        tempo = s["tempo"]
        t["tempo"].config(text=f"{tempo:.0f}%" if tempo is not None else "—",
                          fg=(OK if tempo is not None and tempo >= 100 else RED) if tempo is not None else BLACK)
        t["dni"].config(text=str(s["dni_zostalo"]) if s["biezacy"] else "—")
        self.wyn_hist.delete(*self.wyn_hist.get_children())
        for r in dane.poprzednie(d.get("months", []), m):
            p = dane.podsumowanie(r)
            tag = () if p["pct"] is None else (("ok",) if p["pct"] >= 100 else ("bad",))
            self.wyn_hist.insert("", "end", values=(p["label"], dane.zl(p["zrobione"]), dane.zl(p["cel"]),
                                                    f"{p['pct']:.0f}%" if p["pct"] is not None else "—"), tags=tag)
        when = _kiedy(m.get("updated_at"))
        self.wyn_info.config(text=f"Zaktualizowano {when}" if when else "", fg=MUTED)
        self._wyn_draw_bar()
        self._wyn_draw_chart()

    def _wyn_draw_bar(self):
        c, s = self.wyn_bar, getattr(self, "wyn_sum", None)
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        if w < 10 or not s:
            return
        c.create_rectangle(0, 0, w, h, fill=BAR_BG, width=0)
        if s["pct"] is not None:
            c.create_rectangle(0, 0, w * min(s["pct"], 100) / 100, h, fill=RED, width=0)
        if s["biezacy"] and s["cel"] and s["plan_dzis"] is not None:
            x = w * min(s["plan_dzis"] / s["cel"], 1)
            c.create_rectangle(x - 1, 0, x + 1, h, fill=PLAN, width=0)

    def _wyn_draw_chart(self):
        c, s = self.wyn_chart, getattr(self, "wyn_sum", None)
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        if w < 50 or not s or not s["dni_all"]:
            return
        f = self.fonts
        pts = getattr(self, "wyn_points", [])
        top = max([s["cel"] or 0] + [v for _, v in pts] + [1]) * 1.08
        L, R, T, B = 70, 12, 8, 22
        X = lambda i: L + (w - L - R) * i / s["dni_all"]
        Y = lambda v: T + (h - T - B) * (1 - v / top)
        for k in range(5):   # siatka i opis osi
            v = top * k / 4
            c.create_line(L, Y(v), w - R, Y(v), fill=LINE)
            c.create_text(L - 6, Y(v), text=dane.zl(v).replace(" zł", ""), anchor="e", fill=MUTED, font=f.small)
        c.create_text(L, h - 4, text="1. dzień", anchor="sw", fill=MUTED, font=f.small)
        c.create_text(w - R, h - 4, text=f"{s['dni_all']}. dzień roboczy", anchor="se", fill=MUTED, font=f.small)
        if s["cel"]:
            c.create_line(X(0), Y(0), X(s["dni_all"]), Y(s["cel"]), fill=INK, width=2, dash=(6, 4))
        if pts:
            line = [X(0), Y(0)]
            for i, v in pts:
                line += [X(i), Y(v)]
            c.create_line(*line, fill=RED, width=3)
            for i, v in pts:
                c.create_oval(X(i) - 4, Y(v) - 4, X(i) + 4, Y(v) + 4, fill=RED, outline=SURFACE, width=2)
        self.wyn_chart_note.config(
            text="Wykres uzupełnia się przy każdej aktualizacji MARŻY." if len(pts) < 3 else "")


def _kiedy(ts) -> str:
    if not ts:
        return ""
    from datetime import datetime
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00")).astimezone().strftime("%d.%m.%Y, %H:%M")
    except ValueError:
        return str(ts)[:16]
