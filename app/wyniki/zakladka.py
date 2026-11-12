"""Zakładka WYNIKI: aktualny wynik marży oddziału dla handlowców (Wrocław / Opole), admin widzi oba."""
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from ui import BG, BLACK, FlatButton, INK, LINE, MUTED, OK, RED, SURFACE, WARN, card, set_icon
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
        trow = tk.Frame(left, bg=DARK)
        trow.pack(anchor="w")
        self.wyn_target = tk.Label(trow, text="", bg=DARK, fg=DARK_MUTED, font=f.body)
        self.wyn_target.pack(side="left")
        self.wyn_admin_btns = []          # przyciski edycji – tylko administrator (bazę i tak chroni admin_set_month)
        if self._wyn_admin():
            b = tk.Label(trow, text="✎ Zmień cel…", bg=DARK, fg="white", font=f.small, cursor="hand2", padx=8)
            b.pack(side="left", padx=(10, 0))
            b.bind("<Button-1>", lambda e: self.wyniki_zmien_cel())
            self.wyn_admin_btns.append(b)
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
        tk.Label(leg, text="– – plan", bg=SURFACE, fg=INK, font=f.small).pack(side="left", padx=6)
        tk.Label(leg, text="··· prognoza", bg=SURFACE, fg=RED, font=f.small).pack(side="left")
        self.wyn_chart = tk.Canvas(ch, height=230, bg=SURFACE, highlightthickness=0)
        self.wyn_chart.pack(fill="both", expand=True, pady=(8, 0))
        self.wyn_chart.bind("<Configure>", lambda e: self._wyn_draw_chart())
        self.wyn_chart_note = tk.Label(ch, text="", bg=SURFACE, fg=MUTED, font=f.small, anchor="w")
        self.wyn_chart_note.pack(fill="x")

        hist = card(low, padx=14, pady=10)
        hist.pack(side="left", fill="both", padx=(14, 0))
        hh = tk.Frame(hist, bg=SURFACE)
        hh.pack(fill="x")
        tk.Label(hh, text="Poprzednie miesiące", bg=SURFACE, fg=BLACK, font=f.label, anchor="w").pack(side="left")
        if self._wyn_admin():
            b = FlatButton(hh, "+ Dodaj miesiąc…", lambda: self.wyniki_dodaj_miesiac(), "ghost", f.small, 8, 3)
            b.pack(side="right")
            self.wyn_admin_btns.append(b)
        # legenda nad tabelą (zawsze widoczna, także przy 1366x768)
        self.wyn_hist_note = tk.Label(hist, text="", bg=SURFACE, fg=MUTED, font=f.small, anchor="w", justify="left",
                                      wraplength=440)
        self.wyn_hist_note.pack(fill="x", pady=(2, 0))
        tv_box = tk.Frame(hist, bg=SURFACE)
        tv_box.pack(fill="both", expand=True, pady=(6, 0))
        self.wyn_hist = ttk.Treeview(tv_box, columns=("m", "done", "cel", "pct"), show="headings", height=6,
                                     style="H.Treeview")
        sb = ttk.Scrollbar(tv_box, orient="vertical", command=self.wyn_hist.yview)
        self.wyn_hist.configure(yscrollcommand=sb.set)
        for c, t, w, a in (("m", "Miesiąc", 190, "w"), ("done", "Zrobione", 110, "e"), ("cel", "Cel", 120, "e"),
                           ("pct", "% celu", 70, "e")):
            self.wyn_hist.heading(c, text=t, anchor=a)
            self.wyn_hist.column(c, width=w, anchor=a)
        self.wyn_hist.tag_configure("ok", foreground=OK)
        self.wyn_hist.tag_configure("bad", foreground=RED)
        sb.pack(side="right", fill="y")
        self.wyn_hist.pack(side="left", fill="both", expand=True)
        self.wyn_hist_rows = {}           # id wiersza tabeli → wiersz marza_months
        if self._wyn_admin():
            self.wyn_hist.bind("<Double-1>", lambda e: self._wyn_hist_dwuklik(e))
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
        self.wyn_days = dane.dni_sprzedazowe(s["year"], s["month"], m.get("holidays"))
        self.wyn_msg.pack_forget()
        self.wyn_main.pack(fill="both", expand=True)
        self.wyn_month.config(text=f"{names.get(branch, branch).upper()}  ·  {s['label']}"
                                   + ("" if s["biezacy"] else "  (ostatni miesiąc z wynikami)"))
        self.wyn_done.config(text=dane.zl(s["zrobione"]))
        self.wyn_cur_row = m
        self.wyn_target.config(text=f"cel {dane.zl(s['cel'])}"
                               + ("  ✎ czeka na Excel" if m.get("target_pending") else ""))
        self.wyn_pct.config(text=f"{s['pct']:.0f}%" if s["pct"] is not None else "—")
        self.wyn_plan.config(text=(f"▲ plan na dziś {dane.zl(s['plan_dzis'])}  ·  dzień roboczy "
                                   f"{s.get('dzien_dzis') or min(s['dni_minelo'] + 1, s['dni_all'])} z {s['dni_all']}")
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
        self.wyn_hist_rows = {}
        rows = dane.poprzednie(d.get("months", []), m)
        for r in rows:
            values, tag = dane.wiersz_tabeli(r)
            self.wyn_hist_rows[self.wyn_hist.insert("", "end", values=values, tags=tag)] = r
        notes = []
        if m.get("target_pending") or any(r.get("target_pending") for r in rows):
            notes.append("✎ cel czeka na wpisanie do Excela")
        if any(r.get("manual") for r in rows):
            notes.append("(ręcznie) – dopisany przez administratora")
        if self._wyn_admin():
            notes.append("dwuklik – zmiana celu")
        self.wyn_hist_note.config(text="  ·  ".join(notes))
        want = getattr(self, "wyn_zaznacz", None)      # po „Dodano miesiąc” – zaznacz i przewiń do niego
        if want and want[0] == branch:
            for iid, r in self.wyn_hist_rows.items():
                if (int(r["year"]), int(r["month"])) == want[1:]:
                    self.wyn_hist.selection_set(iid)
                    self.wyn_hist.see(iid)
                    self.wyn_zaznacz = None
                    break
        when = _kiedy(m.get("updated_at"))
        self.wyn_info.config(text=f"Zaktualizowano {when}" if when else "", fg=MUTED)
        self._wyn_draw_bar()
        self._wyn_draw_chart()

    # ---------- edycja (tylko administrator) ----------
    def _wyn_admin(self) -> bool:
        return bool(self.session is not None and self.session.is_admin)

    def _wyn_hist_dwuklik(self, event):
        iid = self.wyn_hist.identify_row(event.y)
        if iid in self.wyn_hist_rows:
            self.wyniki_zmien_cel(self.wyn_hist_rows[iid])

    def wyniki_zapisz(self, params: dict, done_cb):
        """admin_set_month w tle; wynik (błąd albo None) do okna przez after. Zwraca wątek (testy)."""
        sess = self.session

        def work():
            try:
                sess.rpc("admin_set_month", **params)
                self.after(0, done_cb, None)
            except Exception as e:
                self.after(0, done_cb, e)
        t = threading.Thread(target=work, daemon=True)
        t.start()
        return t

    def _wyn_odswiez_po_zapisie(self):
        if self.wyn_loading:          # trwa wczytywanie – spróbuj za chwilę, żeby pokazać nowe dane
            self.after(800, self._wyn_odswiez_po_zapisie)
        else:
            self.wyniki_odswiez()

    def _wyn_okno(self, title):
        f = self.fonts
        w = tk.Toplevel(self)
        w.title(title)
        w.configure(bg=SURFACE)
        w.resizable(False, False)
        w.transient(self)
        set_icon(w)
        tk.Frame(w, bg=RED, height=4).pack(fill="x")
        box = tk.Frame(w, bg=SURFACE, padx=20, pady=14)
        box.pack(fill="both", expand=True)
        tk.Label(box, text=title, bg=SURFACE, fg=BLACK, font=f.h2,
                 anchor="w").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))
        return w, box

    def _wyn_okno_dol(self, w, box, row, info, on_save):
        f = self.fonts
        msg = tk.Label(box, text=info, bg=SURFACE, fg=MUTED, font=f.small, anchor="w", justify="left",
                       wraplength=360)
        msg.grid(row=row, column=0, columnspan=2, sticky="w", pady=(10, 0))
        btns = tk.Frame(box, bg=SURFACE)
        btns.grid(row=row + 1, column=0, columnspan=2, sticky="e", pady=(14, 0))
        FlatButton(btns, "Anuluj", w.destroy, "ghost", f.body, 14, 6).pack(side="right")
        save = FlatButton(btns, "Zapisz", lambda: on_save(), "primary", f.body, 16, 6)
        save.pack(side="right", padx=(0, 8))
        w.bind("<Return>", lambda e: save._enabled and on_save())
        w.bind("<Escape>", lambda e: w.destroy())
        try:
            w.grab_set()
        except tk.TclError:
            pass
        return msg, save

    def _wyn_pole(self, box, row, label, value=""):
        f = self.fonts
        tk.Label(box, text=label, bg=SURFACE, fg=INK, font=f.body, anchor="w").grid(row=row, column=0, sticky="w",
                                                                                   pady=3, padx=(0, 12))
        e = tk.Entry(box, font=f.body, width=18, relief="flat", highlightthickness=1, highlightbackground=LINE,
                     justify="right")
        e.insert(0, value)
        e.grid(row=row, column=1, sticky="we", pady=3)
        return e

    def _wyn_wyslij(self, w, msg, save, params, ok_text, zaznacz=None):
        save.set_enabled(False, "Zapisuję…")
        msg.config(text="Zapisuję w bazie…", fg=MUTED)

        def done(err):
            if err is not None:
                if w.winfo_exists():
                    save.set_enabled(True, "Zapisz")
                    msg.config(text=dane.opis_bledu(err), fg=RED)
                return
            if w.winfo_exists():
                w.destroy()
            self.wyn_info.config(text=ok_text, fg=OK)
            if zaznacz:
                self.wyn_zaznacz = zaznacz
            self._wyn_odswiez_po_zapisie()
        self.wyniki_zapisz(params, done)

    def wyniki_zmien_cel(self, row=None, branch=None):
        """Okno zmiany celu miesiąca (domyślnie bieżącego). Ręczny miesiąc – także „zrobione”."""
        if not self._wyn_admin():
            return None
        branch = branch or self.wyn_branch
        row = row if row is not None else getattr(self, "wyn_cur_row", None)
        if row is None or branch is None:
            messagebox.showinfo("Zmiana celu", "Brak miesiąca do zmiany – najpierw wczytaj wyniki.")
            return None
        names = dict(dane.ODDZIALY)
        manual = bool(row.get("manual"))
        label = row.get("label") or f"{dane.MIESIACE[int(row['month']) - 1]} {row['year']}"
        w, box = self._wyn_okno("Zmień cel miesiąca")
        f = self.fonts
        for i, (k, v) in enumerate((("Oddział", names.get(branch, branch)),
                                    ("Miesiąc", label + (" (ręcznie)" if manual else "")),
                                    ("Obecny cel", dane.zl(row.get("target"))
                                     + ("  ✎ czeka na Excel" if row.get("target_pending") else "")))):
            tk.Label(box, text=k, bg=SURFACE, fg=MUTED, font=f.body, anchor="w").grid(row=1 + i, column=0,
                                                                                     sticky="w", pady=2)
            tk.Label(box, text=v, bg=SURFACE, fg=BLACK, font=f.label, anchor="w").grid(row=1 + i, column=1,
                                                                                      sticky="w", pady=2)
        e_cel = self._wyn_pole(box, 4, "Nowy cel (zł)", dane.kwota_do_pola(row.get("target")))
        e_done = self._wyn_pole(box, 5, "Zrobione (zł)", dane.kwota_do_pola(row.get("done"))) if manual else None
        info = ("Miesiąc dopisany ręcznie – zmieniasz cel i wynik tylko w programie." if manual else
                "Cel zostanie też wpisany do kalkulatora Excel przy najbliższej aktualizacji MARŻY.")

        def on_save():
            try:
                cel = dane.parsuj_kwote(e_cel.get())
            except ValueError as ex:
                msg.config(text=f"Cel: {ex}", fg=RED)
                return
            done_v = None
            if manual:
                try:
                    done_v = dane.parsuj_kwote(e_done.get())
                except ValueError as ex:
                    msg.config(text=f"Zrobione: {ex}", fg=RED)
                    return
            self._wyn_wyslij(w, msg, save, dane.parametry_rpc(branch, row["year"], row["month"], cel, done_v),
                             f"Zapisano cel: {label}")
        msg, save = self._wyn_okno_dol(w, box, 6, info, on_save)
        e_cel.focus_set()
        e_cel.select_range(0, "end")
        return w

    def wyniki_dodaj_miesiac(self):
        """Okno dopisania brakującego starego miesiąca (np. sprzed kalkulatora): cel i zrobione."""
        if not self._wyn_admin():
            return None
        from datetime import date
        today = date.today()
        names = dict(dane.ODDZIALY)
        w, box = self._wyn_okno("Dodaj miesiąc")
        f = self.fonts
        r = 1
        v_br = tk.StringVar(value=names.get(self.wyn_branch, ""))
        if len(self.wyn_branches) > 1:
            tk.Label(box, text="Oddział", bg=SURFACE, fg=INK, font=f.body, anchor="w").grid(row=r, column=0,
                                                                                           sticky="w", pady=3)
            ttk.Combobox(box, textvariable=v_br, state="readonly", width=16, font=f.body,
                         values=[names[k] for k in self.wyn_branches]).grid(row=r, column=1, sticky="we", pady=3)
        else:
            tk.Label(box, text="Oddział", bg=SURFACE, fg=MUTED, font=f.body, anchor="w").grid(row=r, column=0,
                                                                                             sticky="w", pady=3)
            tk.Label(box, text=v_br.get(), bg=SURFACE, fg=BLACK, font=f.label).grid(row=r, column=1, sticky="w")
        prev = dane.domyslny_nowy_miesiac((self.wyn_data.get(self.wyn_branch) or {}).get("months", []), today)
        v_m = tk.StringVar(value=dane.MIESIACE[prev[1] - 1])
        v_y = tk.StringVar(value=str(prev[0]))
        tk.Label(box, text="Miesiąc", bg=SURFACE, fg=INK, font=f.body, anchor="w").grid(row=r + 1, column=0,
                                                                                       sticky="w", pady=3)
        ttk.Combobox(box, textvariable=v_m, state="readonly", width=16, font=f.body,
                     values=dane.MIESIACE).grid(row=r + 1, column=1, sticky="we", pady=3)
        tk.Label(box, text="Rok", bg=SURFACE, fg=INK, font=f.body, anchor="w").grid(row=r + 2, column=0,
                                                                                   sticky="w", pady=3)
        ttk.Combobox(box, textvariable=v_y, state="readonly", width=16, font=f.body,
                     values=[str(y) for y in range(today.year, 2019, -1)]).grid(row=r + 2, column=1, sticky="we",
                                                                                 pady=3)
        e_cel = self._wyn_pole(box, r + 3, "Cel (zł)")
        e_done = self._wyn_pole(box, r + 4, "Zrobione (zł)")

        def on_save():
            branch = {v: k for k, v in names.items()}.get(v_br.get())
            if branch not in self.wyn_branches:
                msg.config(text="Wybierz oddział.", fg=RED)
                return
            year, month = int(v_y.get()), dane.MIESIACE.index(v_m.get()) + 1
            if (year, month) >= (today.year, today.month):
                msg.config(text="Można dopisać tylko miesiąc, który już się skończył.", fg=RED)
                return
            label = f"{v_m.get()} {year}"
            old = dane.znajdz_miesiac((self.wyn_data.get(branch) or {}).get("months", []), year, month)
            if old is not None:
                co = "cel i wynik" if old.get("manual") else "cel"
                if messagebox.askyesno("Dodaj miesiąc", f"{label} ({names[branch]}) jest już w wynikach.\n"
                                       f"Możesz zmienić jego {co}. Otworzyć zmianę?", parent=w):
                    w.destroy()
                    self.wyniki_zmien_cel(old, branch)
                return
            vals = {}
            for key, e, nazwa in (("cel", e_cel, "Cel"), ("done", e_done, "Zrobione")):
                try:
                    vals[key] = dane.parsuj_kwote(e.get())
                except ValueError as ex:
                    msg.config(text=f"{nazwa}: {ex}", fg=RED)
                    return
            self._wyn_wyslij(w, msg, save, dane.parametry_rpc(branch, year, month, vals["cel"], vals["done"]),
                             f"Dodano miesiąc: {label}", (branch, year, month))
        msg, save = self._wyn_okno_dol(w, box, r + 5, "Miesiąc sprzed kalkulatora – wpisz cel i to, co zostało "
                                       "zrobione. Pojawi się w tabeli z dopiskiem „(ręcznie)”.", on_save)
        e_cel.focus_set()
        return w

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
        """Wykres narastająco: plan (linia przerywana do celu), wykonanie (czerwona linia z wypełnieniem),
        prognoza do końca miesiąca (kropki), znacznik „dziś” z różnicą do planu. Oś Y w okrągłych kwotach,
        oś X – daty dni sprzedażowych."""
        c, s = self.wyn_chart, getattr(self, "wyn_sum", None)
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        if w < 50 or not s or not s["dni_all"]:
            return
        f, n = self.fonts, s["dni_all"]
        pts = getattr(self, "wyn_points", [])
        dni = getattr(self, "wyn_days", None) or []
        prog = s["prognoza"] if s["biezacy"] and pts and s["prognoza"] else None
        osie = dane.podzialka(max([s["cel"] or 0, prog or 0] + [v for _, v in pts] + [1]) * 1.04)
        top = osie[-1]
        L, R, T, B = 62, 118, 14, 24
        X = lambda i: L + (w - L - R) * i / n
        Y = lambda v: T + (h - T - B) * (1 - v / top)
        for v in osie:   # siatka i opis osi
            c.create_line(L, Y(v), w - R, Y(v), fill=LINE)
            c.create_text(L - 8, Y(v), text=dane.krotko_zl(v), anchor="e", fill=MUTED, font=f.small)
        li, lv = pts[-1] if pts else (None, None)
        dzis = li if s["biezacy"] and pts else None
        # oś X: daty co ok. 5 dni sprzedażowych + pierwszy, ostatni i dzisiejszy (pogrubiony)
        co = max(1, round(n / 5))
        opisy = {1, n} | {i for i in range(co, n, co) if n - i >= co / 2}
        if dzis:
            opisy = {i for i in opisy if abs(i - dzis) >= co / 2 or i in (1, n)} | {dzis}
        for i in range(1, n + 1):
            c.create_line(X(i), Y(0), X(i), Y(0) + 3, fill=LINE)
            if i in opisy:
                txt = f"{dni[i - 1].day}.{dni[i - 1].month:02d}" if len(dni) == n else f"{i}. dzień"
                c.create_text(X(i), h - 4, text=txt, anchor="s", fill=BLACK if i == dzis else MUTED,
                              font=f.label if i == dzis else f.small)
        prawe = []   # opisy przy prawej krawędzi: (y, tekst, kolor)
        if s["cel"]:
            c.create_line(X(0), Y(0), X(n), Y(s["cel"]), fill=INK, width=2, dash=(6, 4))
            prawe.append([Y(s["cel"]), "cel " + dane.krotko_zl(s["cel"]), INK])
        if pts:
            line = [X(0), Y(0)]
            for i, v in pts:
                line += [X(i), Y(v)]
            c.create_polygon(*line, X(li), Y(0), fill="#FCE4E5", outline="")
            if prog:
                c.create_line(X(li), Y(lv), X(n), Y(prog), fill=RED, width=2, dash=(2, 4))
                prawe.append([Y(prog), "prognoza " + dane.krotko_zl(prog), RED])
            if dzis and s["cel"]:   # dziś: gdzie powinniśmy być według planu
                pl = s["cel"] * li / n
                c.create_line(X(li), Y(max(pl, lv)) - 8, X(li), Y(0), fill=MUTED, dash=(2, 3))
                c.create_oval(X(li) - 4, Y(pl) - 4, X(li) + 4, Y(pl) + 4, fill=SURFACE, outline=INK, width=2)
                roz = lv - pl
                c.create_text(X(li) - 8, Y(max(pl, lv)) - 8, anchor="se",
                              text=("−" if roz < 0 else "+") + dane.krotko_zl(abs(roz))
                              + (" do planu" if roz < 0 else " ponad plan"),
                              fill=RED if roz < 0 else OK, font=f.label)
            c.create_line(*line, fill=RED, width=3, joinstyle="round")
            for i, v in pts:
                c.create_oval(X(i) - 3, Y(v) - 3, X(i) + 3, Y(v) + 3, fill=RED, outline=SURFACE, width=1)
            c.create_oval(X(li) - 6, Y(lv) - 6, X(li) + 6, Y(lv) + 6, fill=RED, outline=SURFACE, width=2)
            c.create_text(X(li) + 10, Y(lv) + 4, anchor="nw", text=dane.krotko_zl(lv, True),
                          fill=BLACK, font=f.label)
        prawe.sort()
        for a_, b_ in zip(prawe, prawe[1:]):   # rozsuń, gdy cel i prognoza są blisko siebie
            if b_[0] - a_[0] < 16:
                d = (16 - (b_[0] - a_[0])) / 2
                a_[0] -= d
                b_[0] += d
        for y, txt, col in prawe:
            c.create_text(X(n) + 8, y, text=txt, anchor="w", fill=col, font=f.small)
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
