"""Zakładka STATYSTYKI: ile list kontrolnych w CRM przypada na zlecenia (wizyty) z Integry + prognoza."""
import threading
import tkinter as tk
from datetime import date, timedelta
from tkinter import ttk

from statystyki import dane
from ui import BG, BLACK, FlatButton, INK, MUTED, OK, RED, SURFACE, WARN, card

WSZYSTKIE = "Wszystkie oddziały"


class StatystykiMixin:
    """Zakładka STATYSTYKI. Część klasy okna programu (App). Dane: tabela visit_stats (liczniki dzienne zapisywane
    przy każdym sprawdzeniu w KONTROLI) – oddziały widoczne dla konta wybiera baza."""

    # ---------- układ ----------
    def _build_statystyki(self, page):
        f = self.fonts
        self.st_rows = []
        s = self.session
        oddzialy = list(s.branches()) if s is not None else ["Latex Wrocław", "Latex Opole", "Stangum Opole"]
        self.st_choices = ([WSZYSTKIE] if len(oddzialy) > 1 else []) + oddzialy
        self.st_branch = tk.StringVar(value=self.st_choices[0] if self.st_choices else "")

        bar = tk.Frame(page, bg=BG)
        bar.pack(fill="x", pady=(4, 10))
        tk.Label(bar, text="Statystyki list kontrolnych", bg=BG, fg=BLACK, font=f.h1).pack(side="left")
        if len(self.st_choices) > 1:
            cb = ttk.Combobox(bar, textvariable=self.st_branch, values=self.st_choices, state="readonly",
                              width=22, font=f.body)
            cb.pack(side="left", padx=18)
            cb.bind("<<ComboboxSelected>>", lambda e: self._st_show())
        FlatButton(bar, "Odśwież", self.statystyki_refresh, "ghost", f.body, 14, 6).pack(side="right")
        self.st_msg = tk.Label(bar, text="", bg=BG, fg=MUTED, font=f.small)
        self.st_msg.pack(side="right", padx=12)

        # kafle: wskaźnik z 90 dni + liczby
        tiles = tk.Frame(page, bg=BG)
        tiles.pack(fill="x")
        self.st_tiles = {}
        for i, (key, title) in enumerate((("na10", "List na 10 zleceń (90 dni)"), ("visits", "Zlecenia (90 dni)"),
                                          ("lists", "Listy kontrolne (90 dni)"), ("missing", "Zlecenia bez listy (90 dni)"))):
            c = card(tiles, padx=16, pady=12)
            c.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 10, 0))
            tiles.grid_columnconfigure(i, weight=1)
            tk.Label(c, text=title, bg=SURFACE, fg=MUTED, font=f.small).pack(anchor="w")
            v = tk.Label(c, text="—", bg=SURFACE, fg=RED if key == "na10" else BLACK, font=(f.family, 22, "bold"))
            v.pack(anchor="w")
            self.st_tiles[key] = v

        # prognoza
        calc = card(page, padx=16, pady=14)
        calc.pack(fill="x", pady=12)
        tk.Label(calc, text="Prognoza", bg=SURFACE, fg=BLACK, font=f.h2).pack(anchor="w")
        row = tk.Frame(calc, bg=SURFACE)
        row.pack(fill="x", pady=(6, 0))
        tk.Label(row, text="Jeśli będzie", bg=SURFACE, fg=INK, font=f.body).pack(side="left")
        self.st_n = tk.StringVar(value="1000")
        e = ttk.Entry(row, textvariable=self.st_n, width=10, font=f.body, justify="right")
        e.pack(side="left", padx=8, ipady=3)
        tk.Label(row, text="zleceń, spodziewaj się", bg=SURFACE, fg=INK, font=f.body).pack(side="left")
        self.st_wynik = tk.Label(row, text="—", bg=SURFACE, fg=RED, font=(f.family, 16, "bold"))
        self.st_wynik.pack(side="left", padx=8)
        self.st_opis = tk.Label(calc, text="", bg=SURFACE, fg=MUTED, font=f.small, justify="left", anchor="w")
        self.st_opis.pack(fill="x", pady=(6, 0))
        self.st_n.trace_add("write", lambda *a: self._st_prognoza())

        # miesiące
        box = card(page, padx=2, pady=2)
        box.pack(fill="both", expand=True)
        cols = ("m", "v", "l", "x", "w", "d")
        self.st_tree = ttk.Treeview(box, columns=cols, show="headings", height=8)
        for c, t, w, a in (("m", "Miesiąc", 170, "w"), ("v", "Zlecenia", 110, "e"), ("l", "Listy kontrolne", 130, "e"),
                           ("x", "Bez listy", 110, "e"), ("w", "List na 10 zleceń", 150, "e"),
                           ("d", "Dni z danymi", 120, "e")):
            self.st_tree.heading(c, text=t, anchor=a)
            self.st_tree.column(c, width=w, anchor=a)
        self.st_tree.pack(fill="both", expand=True)
        tk.Label(page, text="Dane zbierają się przy każdym sprawdzeniu w zakładce KONTROLA (raport .xlsx z CRM, jeden "
                 "zaznaczony oddział). Każde zlecenie z pojazdem w Integrze to jedna wizyta – także to samo auto "
                 "drugi raz. „Bez listy” oznacza brak listy w CRM z tego samego dnia. Ponowne sprawdzenie tego samego dnia nadpisuje liczby, więc nic nie liczy się podwójnie.",
                 bg=BG, fg=MUTED, font=f.small, wraplength=1300, justify="left").pack(anchor="w", pady=(8, 0))
        self.after(300, self.statystyki_refresh)   # wątek dopiero po starcie pętli okna

    # ---------- dane ----------
    def statystyki_refresh(self):
        self.st_msg.config(text="Wczytuję…", fg=MUTED)
        od = (date.today() - timedelta(days=400)).isoformat()

        def work():
            try:
                rows = self.session.call(
                    "GET", f"/rest/v1/visit_stats?select=branch,day,visits,lists,missing&day=gte.{od}&order=day") or []
                res = (rows, None)
            except Exception as e:
                res = (None, str(e))
            try:
                self.after(0, self._st_loaded, *res)
            except RuntimeError:   # okno zamknięte
                pass
        threading.Thread(target=work, daemon=True).start()

    def _st_loaded(self, rows, err):
        if err:
            self.st_msg.config(text="Nie udało się wczytać statystyk – sprawdź internet i kliknij „Odśwież”.", fg=RED)
            return
        self.st_rows = rows or []
        self.st_msg.config(text=f"Dni z danymi: {len({(r['branch'], r['day']) for r in self.st_rows})}", fg=MUTED)
        self._st_show()

    def _st_selected(self):
        b = self.st_branch.get()
        return dane.filtruj(self.st_rows, None if b == WSZYSTKIE else b)

    def _st_show(self):
        rows = self._st_selected()
        o = dane.okres(rows, 90)
        self.st_tiles["na10"].config(text=dane.fmt_na10(o["na10"]))
        self.st_tiles["visits"].config(text=dane.fmt_int(o["visits"]))
        self.st_tiles["lists"].config(text=dane.fmt_int(o["lists"]))
        self.st_tiles["missing"].config(text=dane.fmt_int(o["missing"]), fg=WARN if o["missing"] else OK)
        t = self.st_tree
        t.delete(*t.get_children())
        for m in dane.miesiace(rows):
            t.insert("", "end", values=(m["nazwa"], dane.fmt_int(m["visits"]), dane.fmt_int(m["lists"]),
                                        dane.fmt_int(m["missing"]), dane.fmt_na10(m["na10"]), m["dni"]))
        if not rows:
            self.st_msg.config(text="Brak danych – pojawią się po pierwszym sprawdzeniu w KONTROLI w tej wersji "
                                    "programu (raport .xlsx, jeden oddział).", fg=WARN)
        self._st_prognoza()

    def _st_prognoza(self):
        n = dane.liczba(self.st_n.get())
        p = dane.prognoza(n, self._st_selected()) if n else None
        if p is None:
            self.st_wynik.config(text="—")
            self.st_opis.config(text="Wpisz liczbę zleceń." if not n else "Za mało danych do prognozy.")
            return
        rng = "" if p["od"] == p["do"] else f"  (od {dane.fmt_int(p['od'])} do {dane.fmt_int(p['do'])})"
        self.st_wynik.config(text=f"ok. {dane.fmt_int(p['srodek'])} list kontrolnych{rng}")
        pewnosc = ("Widełki: najsłabszy i najlepszy pełniejszy miesiąc." if p["miesiecy"] >= 2 else
                   "Widełki pojawią się, gdy będą dane z co najmniej 2 miesięcy (min. "
                   f"{dane.MIN_WIZYT_MIESIAC} zleceń w miesiącu).")
        self.st_opis.config(text=f"Wskaźnik {dane.fmt_na10(p['na10'])} listy na 10 zleceń – z "
                                 f"{dane.fmt_int(p['wizyt_w_bazie'])} zleceń z {p['zakres']}. {pewnosc}")
