"""Zakładka DEPOZYT: spis opon w przechowalni (lokalizacje na regałach) dla całego oddziału na żywo.

Odhaczanie „przywiezione” z datą, godziną i nazwiskiem, komentarze, „do wyjaśnienia”, wyszukiwanie odporne
na literówki, historia zmian, duplikaty, eksport do Excela oraz lista dla magazyniera z raportu Integry
(okno `PrzygotowanieOkno`). Zapis tylko funkcjami bazy (dane.zmien / dane.dodaj); wątki nie dotykają okna.
"""
import datetime
import os
import tempfile
import threading
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox, ttk

from depozyt import dane, szukaj
from ui import BG, BLACK, FlatButton, INK, LINE, MUTED, OK, RED, SURFACE, odmiana, opis_bledu, set_icon

ODSWIEZ_MS = 60 * 1000          # gdy zakładka jest otwarta – zmiany innych osób
LIMIT_WIERSZY = 400             # tyle pokazujemy naraz (reszta: „pokaż więcej”)
KOLOR_PRZYW, KOLOR_WYJ, KOLOR_PRZYG = "#F6C9C9", "#FFE2B8", "#D9EAD3"
FILTRY = ["Wszystkie", "Nieprzywiezione", "Przywiezione", "Przywiezione dziś", "Do wyjaśnienia", "Z komentarzem"]


def esc(s) -> str:
    """Tekst do HTML (bez modułu html – nie ma go w paczce .exe)."""
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;").replace("'", "&#39;"))


def zapytaj(okno, tytul, tekst, initialvalue=""):
    """Okienko z jednym polem tekstowym. Zwraca tekst albo None (Anuluj / Esc)."""
    w = tk.Toplevel(okno)
    w.title(tytul)
    set_icon(w)
    w.transient(okno)
    w.resizable(False, False)
    w.configure(bg=SURFACE, padx=18, pady=14)
    f = okno.fonts
    tk.Label(w, text=tekst, bg=SURFACE, fg=INK, font=f.body, wraplength=420, justify="left").pack(anchor="w")
    v = tk.StringVar(value=initialvalue)
    e = tk.Entry(w, textvariable=v, font=f.big, width=34, relief="solid", bd=1)
    e.pack(fill="x", pady=(8, 12), ipady=3)
    wynik = {"v": None}

    def ok(_=None):
        wynik["v"] = v.get()
        w.destroy()
    przyc = tk.Frame(w, bg=SURFACE)
    przyc.pack(anchor="e")
    FlatButton(przyc, "Anuluj", w.destroy, "ghost", f.body, 12, 5).pack(side="right")
    FlatButton(przyc, "OK", ok, "primary", f.body, 16, 5).pack(side="right", padx=(0, 6))
    e.bind("<Return>", ok)
    w.bind("<Escape>", lambda _: w.destroy())
    e.focus_set()
    e.select_range(0, "end")
    w.grab_set()
    okno.wait_window(w)
    return wynik["v"]


def _plik_ostatni():
    import paths
    return paths.DATA_DIR / "depozyt_ostatni_raport.json"


def _wczytaj_ostatni():
    """Ostatnio wczytany raport (odczytany z PDF/Excela) – żeby po zamknięciu okna albo programu wrócić do listy."""
    import json
    try:
        return json.loads(_plik_ostatni().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _zapisz_ostatni(rap: dict):
    import json
    p = _plik_ostatni()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(rap, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, p)
    except OSError:
        pass   # brak zapisu = tylko brak listy po ponownym uruchomieniu


def czas(iso) -> str:
    try:
        t = datetime.datetime.fromisoformat(str(iso).replace("Z", "+00:00")).astimezone()
        return f"{t:%d.%m.%Y %H:%M}"
    except (TypeError, ValueError):
        return ""


def opis_przywiezienia(p: dict) -> str:
    if not p.get("przywiezione"):
        return ""
    if not p.get("przywiezione_at"):
        return "wg Excela"
    return f"{czas(p['przywiezione_at'])}  {p.get('przywiezione_kto') or ''}".strip()


def dzis(p: dict) -> bool:
    try:
        t = datetime.datetime.fromisoformat(str(p.get("przywiezione_at")).replace("Z", "+00:00")).astimezone()
        return t.date() == datetime.date.today()
    except (TypeError, ValueError):
        return False


def filtruj(rows: list, zapytanie: str, filtr: str, lok: str) -> list:
    """[(pozycja, czy_przyblizone)] wg wyszukiwania i filtrów (wyszukiwanie: najlepsze najpierw)."""
    def pasuje(p):
        if filtr == "Nieprzywiezione" and p.get("przywiezione"):
            return False
        if filtr == "Przywiezione" and not p.get("przywiezione"):
            return False
        if filtr == "Przywiezione dziś" and not dzis(p):
            return False
        if filtr == "Do wyjaśnienia" and not p.get("wyjasnic"):
            return False
        if filtr == "Z komentarzem" and not p.get("komentarz"):
            return False
        return not lok or p.get("lok") == lok
    rows = [p for p in rows if pasuje(p)]
    if zapytanie.strip():
        return [(p, fz) for p, _, fz in szukaj.szukaj(rows, zapytanie)]
    return [(p, False) for p in rows]


def statystyki(rows: list) -> dict:
    przyw = sum(1 for p in rows if p.get("przywiezione"))
    return {"wszystkie": len(rows), "przywiezione": przyw, "zostalo": len(rows) - przyw,
            "dzis": sum(1 for p in rows if dzis(p)), "wyjasnic": sum(1 for p in rows if p.get("wyjasnic"))}


class DepozytMixin:
    """Zakładka DEPOZYT. Część klasy okna programu (App)."""

    def depozyt_oddzialy(self) -> list:
        s = self.session
        return s.branches() if s else ["Latex Wrocław"]

    # ---------- układ ----------
    def _build_depozyt(self, page):
        f = self.fonts
        self.dep_rows, self.dep_sezon, self.dep_limit = [], "", LIMIT_WIERSZY
        self.dep_branch = (self.depozyt_oddzialy() or ["Latex Wrocław"])[0]
        self.dep_ladowanie = False

        bar = tk.Frame(page, bg=BG)
        bar.pack(fill="x", pady=(4, 6))
        tk.Label(bar, text="Depozyt opon", bg=BG, fg=BLACK, font=f.h1).pack(side="left")
        if len(self.depozyt_oddzialy()) > 1:
            self.dep_branch_var = tk.StringVar(value=self.dep_branch)
            cb = ttk.Combobox(bar, textvariable=self.dep_branch_var, values=self.depozyt_oddzialy(),
                              state="readonly", width=16)
            cb.pack(side="left", padx=(16, 0))
            cb.bind("<<ComboboxSelected>>", lambda e: self._dep_zmien_oddzial())
        self.dep_sezon_var = tk.StringVar()
        self.dep_sezon_cb = ttk.Combobox(bar, textvariable=self.dep_sezon_var, state="readonly", width=16)
        self.dep_sezon_cb.pack(side="left", padx=(10, 0))
        self.dep_sezon_cb.bind("<<ComboboxSelected>>", lambda e: self._dep_render())
        FlatButton(bar, "Odśwież", lambda: self.depozyt_odswiez(), "ghost", f.body, 12, 6).pack(side="right")
        FlatButton(bar, "Eksport do Excela", self._dep_eksport, "ghost", f.body, 12, 6).pack(side="right", padx=(0, 6))
        FlatButton(bar, "Duplikaty", self._dep_duplikaty, "ghost", f.body, 12, 6).pack(side="right", padx=(0, 6))
        FlatButton(bar, "Historia zmian", lambda: self._dep_historia(None), "ghost", f.body, 12, 6).pack(side="right", padx=(0, 6))
        FlatButton(bar, "+ Dodaj pozycję", self._dep_dodaj, "ghost", f.body, 12, 6).pack(side="right", padx=(0, 6))
        rzad2 = tk.Frame(page, bg=BG)
        rzad2.pack(fill="x")
        self.dep_ostatni_btn = FlatButton(rzad2, "↺  Ostatnia lista", self.depozyt_ostatnia_lista, "ghost", f.body, 12, 6)
        self.dep_ostatni_btn.pack(side="right")
        FlatButton(rzad2, "📄  Wczytaj raport z Integry", self._dep_raport, "primary", f.body, 14, 6).pack(
            side="right", padx=(0, 6))
        self.dep_ostatni = _wczytaj_ostatni()
        self._dep_ostatni_opis()
        self.dep_stat = tk.Label(rzad2, text="Wczytywanie spisu…", bg=BG, fg=INK, font=f.body, anchor="w")
        self.dep_stat.pack(side="left", fill="x", expand=True)
        self.dep_pasek = tk.Canvas(page, height=6, bg=LINE, highlightthickness=0)
        self.dep_pasek.pack(fill="x", pady=(4, 8))
        self.dep_pasek.bind("<Configure>", lambda e: self._dep_rysuj_pasek())

        szuk = tk.Frame(page, bg=BG)
        szuk.pack(fill="x", pady=(0, 6))
        tk.Label(szuk, text="Szukaj:", bg=BG, fg=INK, font=f.label).pack(side="left")
        self.dep_q = tk.StringVar()
        e = tk.Entry(szuk, textvariable=self.dep_q, font=f.big, width=22, relief="solid", bd=1)
        e.pack(side="left", padx=(8, 6), ipady=3)
        self.dep_entry = e
        tk.Label(szuk, text="numer (też z literówką), lokalizacja, marka, komentarz\nEnter = odhacz, gdy jest jeden wynik",
                 bg=BG, fg=MUTED, font=f.small, justify="left").pack(side="left")
        self.dep_filtr = tk.StringVar(value=FILTRY[0])
        ttk.Combobox(szuk, textvariable=self.dep_filtr, values=FILTRY, state="readonly", width=18).pack(side="right")
        self.dep_lok = tk.StringVar(value="wszystkie")
        self.dep_lok_cb = ttk.Combobox(szuk, textvariable=self.dep_lok, state="readonly", width=12)
        self.dep_lok_cb.pack(side="right", padx=6)
        tk.Label(szuk, text="Lokalizacja:", bg=BG, fg=MUTED, font=f.small).pack(side="right")
        self._dep_job = None
        self.dep_q.trace_add("write", lambda *a: self._dep_render_pozniej())
        self.dep_filtr.trace_add("write", lambda *a: self._dep_render())
        self.dep_lok.trace_add("write", lambda *a: self._dep_render())
        e.bind("<Return>", lambda ev: self._dep_enter())
        e.bind("<Escape>", lambda ev: self.dep_q.set(""))

        box = tk.Frame(page, bg=SURFACE, highlightbackground=LINE, highlightthickness=1)
        box.pack(fill="both", expand=True)
        kol = [("ok", "✓", 36), ("nr", "Nr rej.", 110), ("lok", "Lok.", 80), ("marka", "Marka", 150),
               ("il", "Ilość / rodzaj", 115), ("uwagi", "Uwagi (spis)", 190), ("kom", "Komentarz", 230),
               ("kiedy", "Przywiezione", 210)]
        st = ttk.Style(page)
        st.configure("Dep.Treeview", rowheight=26, font=f.body)
        st.configure("Dep.Treeview.Heading", font=f.label)
        self.dep_tree = ttk.Treeview(box, columns=[k for k, _, _ in kol], show="headings", style="Dep.Treeview")
        for k, t, w in kol:
            self.dep_tree.heading(k, text=t)
            self.dep_tree.column(k, width=w, anchor="center" if k == "ok" else "w", stretch=k in ("uwagi", "kom"))
        self.dep_tree.tag_configure("przyw", background=KOLOR_PRZYW)
        self.dep_tree.tag_configure("wyj", background=KOLOR_WYJ)
        sb = ttk.Scrollbar(box, orient="vertical", command=self.dep_tree.yview)
        self.dep_tree.configure(yscrollcommand=sb.set)
        self.dep_tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.dep_tree.bind("<Double-1>", lambda e: self._dep_klik_podwojny(e))
        self.dep_tree.bind("<space>", lambda e: self._dep_przelacz_zaznaczone())
        self.dep_tree.bind("<Button-3>", self._dep_menu)
        self.dep_wiecej = FlatButton(page, "Pokaż więcej", self._dep_pokaz_wiecej, "ghost", f.body, 12, 5)
        tk.Label(page, text="Dwuklik lub spacja = przywiezione / cofnij · prawy przycisk = komentarz, do wyjaśnienia, "
                            "lokalizacja, historia", bg=BG, fg=MUTED, font=f.small).pack(anchor="w", pady=(6, 0))
        self.after(200, self.depozyt_odswiez)
        self.after(ODSWIEZ_MS, self._dep_auto)

    # ---------- dane ----------
    def depozyt_odswiez(self, cicho=False):
        if self.dep_ladowanie or self.session is None:
            return
        self.dep_ladowanie = True
        branch = self.dep_branch
        if not cicho:
            self.dep_stat.config(text="Wczytywanie spisu…", fg=MUTED)

        def work():
            try:
                rows, err = dane.pozycje(self.session, branch), None
            except Exception as e:
                rows, err = None, e
            self.after(0, lambda: self._dep_wczytane(rows, err, branch, cicho))
        threading.Thread(target=work, daemon=True).start()

    def _dep_wczytane(self, rows, err, branch=None, cicho=False):
        self.dep_ladowanie = False
        if branch is not None and branch != self.dep_branch:   # w trakcie wczytywania wybrano inny oddział
            self.depozyt_odswiez()
            return
        if err is not None:
            if cicho:   # odświeżanie w tle – chwilowy brak sieci nie zasłania spisu
                return
            self.dep_stat.config(text=f"Nie udało się wczytać spisu: {opis_bledu(err)}", fg=RED)
            return
        self.dep_rows = rows
        sezony = sorted({p.get("sezon") or "" for p in rows}, reverse=True)
        self.dep_sezon_cb.config(values=sezony)
        if self.dep_sezon_var.get() not in sezony:
            self.dep_sezon_var.set(sezony[0] if sezony else "")
        self._dep_render(zachowaj=cicho)

    def _dep_auto(self):
        try:
            if getattr(self, "current_tab", "") == "depozyt" and self.focus_displayof() is not None:
                self.depozyt_odswiez(cicho=True)
        finally:
            self.after(ODSWIEZ_MS, self._dep_auto)

    def _dep_zmien_oddzial(self):
        self.dep_branch = self.dep_branch_var.get()
        self.depozyt_odswiez()

    def _dep_sezonu(self) -> list:
        s = self.dep_sezon_var.get()
        return [p for p in self.dep_rows if (p.get("sezon") or "") == s]

    # ---------- widok ----------
    def _dep_render_pozniej(self):
        if self._dep_job:
            self.after_cancel(self._dep_job)
        self._dep_job = self.after(150, self._dep_render)

    def _dep_render(self, zachowaj=False):
        """zachowaj=True (odświeżanie w tle, zapis): bez skoku listy – zostaje zaznaczenie, przewinięcie i „pokaż więcej”."""
        self._dep_job = None
        t = self.dep_tree
        stan = (t.selection(), t.yview()[0]) if zachowaj else None
        if not zachowaj and not getattr(self, "_dep_wiecej_klik", False):
            self.dep_limit = LIMIT_WIERSZY
        self._dep_wiecej_klik = False
        rows = self._dep_sezonu()
        lok = sorted({p.get("lok") or "" for p in rows if p.get("lok")}, key=szukaj.klucz_lokalizacji)
        self.dep_lok_cb.config(values=["wszystkie"] + lok)
        lok_wyb = "" if self.dep_lok.get() == "wszystkie" else self.dep_lok.get()
        lista = filtruj(rows, self.dep_q.get(), self.dep_filtr.get(), lok_wyb)
        self.dep_widoczne = lista
        t.delete(*t.get_children())
        for p, fz in lista[:self.dep_limit]:
            tag = "przyw" if p.get("przywiezione") else "wyj" if p.get("wyjasnic") else ""
            il = " ".join(x for x in (p.get("ilosc"), p.get("rodzaj")) if x)
            marka = p.get("marka", "") + (f" / {p['marka2']}" if p.get("marka2") else "")
            t.insert("", "end", iid=str(p["id"]), tags=(tag,) if tag else (), values=(
                "✔" if p.get("przywiezione") else "☐", (p.get("nr") or "") + ("  ≈" if fz else ""), p.get("lok", ""),
                marka, il, p.get("uwagi", ""), p.get("komentarz", ""), opis_przywiezienia(p)))
        if len(lista) > self.dep_limit:
            self.dep_wiecej.set_enabled(True, f"Pokaż więcej ({len(lista) - self.dep_limit} ukrytych)")
            self.dep_wiecej.pack(pady=4)
        else:
            self.dep_wiecej.pack_forget()
        if stan:
            istnieja = [i for i in stan[0] if t.exists(i)]
            if istnieja:
                t.selection_set(istnieja)
                t.focus(istnieja[0])
            t.yview_moveto(stan[1])
        s = statystyki(rows)
        txt = (f"Wszystkich {s['wszystkie']}  ·  przywiezione {s['przywiezione']}  ·  zostało {s['zostalo']}  ·  "
               f"dziś {s['dzis']}" + (f"  ·  do wyjaśnienia {s['wyjasnic']}" if s["wyjasnic"] else ""))
        if self.dep_q.get().strip() or self.dep_filtr.get() != FILTRY[0] or lok_wyb:
            txt += f"     |  pokazano {len(lista)}"
        self.dep_stat.config(text=txt, fg=INK)
        self.dep_stat_liczby = s
        self._dep_rysuj_pasek()

    def _dep_rysuj_pasek(self):
        s = getattr(self, "dep_stat_liczby", None)
        self.dep_pasek.delete("all")
        if s and s["wszystkie"]:
            w = max(self.dep_pasek.winfo_width(), 1)
            self.dep_pasek.create_rectangle(0, 0, w * s["przywiezione"] / s["wszystkie"], 6, fill=RED, width=0)

    def _dep_pokaz_wiecej(self):
        self.dep_limit += LIMIT_WIERSZY
        self._dep_wiecej_klik = True
        self._dep_render()

    def _dep_podmien(self, nowy: dict) -> dict | None:
        """Wiersz z bazy podmienia pozycję o tym samym id w aktualnej liście (lista mogła się w międzyczasie odświeżyć)."""
        cur = next((p for p in self.dep_rows if p.get("id") == nowy.get("id")), None)
        if cur is not None:
            cur.clear()
            cur.update(nowy)
        return cur

    def _dep_poz(self, iid) -> dict | None:
        try:
            i = int(iid)
        except (TypeError, ValueError):
            return None
        return next((p for p in self.dep_rows if p.get("id") == i), None)

    # ---------- zmiany ----------
    def _dep_zapisz(self, poz: dict, pole: str, wartosc, po=None):
        """Zapis w tle; po sukcesie wiersz z bazy podmienia lokalny i odświeża widok."""
        def work():
            try:
                nowy, err = dane.zmien(self.session, poz["id"], pole, wartosc), None
            except Exception as e:
                nowy, err = None, e
            self.after(0, lambda: koniec(nowy, err))

        def koniec(nowy, err):
            if err is not None:
                messagebox.showerror("Depozyt", f"Nie zapisano zmiany ({poz.get('nr')}):\n{opis_bledu(err)}")
                return
            if isinstance(nowy, list):
                nowy = nowy[0] if nowy else None
            wiersz = (self._dep_podmien(nowy) or nowy) if nowy else poz
            self._dep_render(zachowaj=True)
            if po:
                po(wiersz)
        threading.Thread(target=work, daemon=True).start()

    def _dep_przelacz(self, poz: dict):
        if poz.get("przywiezione"):
            if not messagebox.askyesno("Cofnąć?", f"Cofnąć „przywiezione” dla {poz.get('nr')}?\n"
                                                  f"(zaznaczone: {opis_przywiezienia(poz)})"):
                return
            self._dep_zapisz(poz, "przywiezione", False)
        else:
            self._dep_zapisz(poz, "przywiezione", True,
                             po=lambda p: self.dep_stat.config(
                                 text=f"✓ {p.get('nr')} ({p.get('lok')}) – przywiezione {opis_przywiezienia(p)}", fg=OK))

    def _dep_klik_podwojny(self, e):
        if self.dep_tree.identify_region(e.x, e.y) != "cell":
            return
        poz = self._dep_poz(self.dep_tree.identify_row(e.y))
        if not poz:
            return
        if self.dep_tree.identify_column(e.x) == "#7":   # kolumna komentarza
            self._dep_komentarz(poz)
        else:
            self._dep_przelacz(poz)

    def _dep_przelacz_zaznaczone(self):
        for iid in self.dep_tree.selection()[:1]:
            poz = self._dep_poz(iid)
            if poz:
                self._dep_przelacz(poz)

    def _dep_enter(self):
        lista = getattr(self, "dep_widoczne", [])
        if len(lista) == 1 and not lista[0][0].get("przywiezione"):
            self._dep_przelacz(lista[0][0])
            self.dep_entry.select_range(0, "end")

    def _dep_komentarz(self, poz):
        v = zapytaj(self, "Komentarz", f"Komentarz do {poz.get('nr')} ({poz.get('lok')}):",
                                   initialvalue=poz.get("komentarz") or "")
        if v is not None and v.strip() != (poz.get("komentarz") or ""):
            self._dep_zapisz(poz, "komentarz", v.strip())

    def _dep_menu(self, e):
        iid = self.dep_tree.identify_row(e.y)
        poz = self._dep_poz(iid)
        if not poz:
            return
        self.dep_tree.selection_set(iid)
        m = tk.Menu(self, tearoff=0)
        m.add_command(label="Cofnij „przywiezione”" if poz.get("przywiezione") else "Przywiezione ✓",
                      command=lambda: self._dep_przelacz(poz))
        m.add_command(label="Komentarz…", command=lambda: self._dep_komentarz(poz))
        m.add_command(label="Zdejmij „do wyjaśnienia”" if poz.get("wyjasnic") else "Do wyjaśnienia",
                      command=lambda: self._dep_zapisz(poz, "wyjasnic", not poz.get("wyjasnic")))
        m.add_separator()
        for pole, nazwa in (("lok", "Zmień lokalizację…"), ("nr", "Popraw numer…"), ("marka", "Zmień markę…")):
            m.add_command(label=nazwa, command=lambda p=pole, n=nazwa: self._dep_edytuj(poz, p, n))
        m.add_separator()
        m.add_command(label="Historia tej pozycji", command=lambda: self._dep_historia(poz))
        m.tk_popup(e.x_root, e.y_root)

    def _dep_edytuj(self, poz, pole, nazwa):
        v = zapytaj(self, nazwa.rstrip("…"), f"{nazwa.rstrip('…')} – {poz.get('nr')}:",
                                   initialvalue=poz.get(pole) or "")
        if v is not None and v.strip() and v.strip().upper() != (poz.get(pole) or ""):
            self._dep_zapisz(poz, pole, v.strip())

    def _dep_dodaj(self):
        sezon = self.dep_sezon_var.get()
        if not sezon:
            sezon = zapytaj(self, "Nowy spis", "Nazwa sezonu (np. ZIMA 2026/27):")
            if not sezon:
                return
        nr = zapytaj(self, "Dodaj pozycję", "Numer rejestracyjny:")
        if not nr or not nr.strip():
            return
        lok = zapytaj(self, "Dodaj pozycję", f"{nr.upper()} – lokalizacja (np. K1.4):") or ""
        marka = zapytaj(self, "Dodaj pozycję", f"{nr.upper()} – marka opon:") or ""
        branch = self.dep_branch

        def work():
            try:
                nowy, err = dane.dodaj(self.session, branch, sezon, nr, lok, marka), None
            except Exception as e:
                nowy, err = None, e
            self.after(0, lambda: koniec(nowy, err))

        def koniec(nowy, err):
            if err is not None:
                messagebox.showerror("Depozyt", f"Nie dodano pozycji:\n{opis_bledu(err)}")
                return
            if isinstance(nowy, list):
                nowy = nowy[0] if nowy else None
            if nowy:
                self.dep_rows.append(nowy)
                self.dep_sezon_var.set(nowy.get("sezon") or sezon)
            self._dep_render()
        threading.Thread(target=work, daemon=True).start()

    # ---------- okna pomocnicze ----------
    def _dep_okno_tekst(self, tytul, wiersze):
        w = tk.Toplevel(self)
        w.title(tytul)
        set_icon(w)
        w.geometry("760x520")
        txt = tk.Text(w, font=self.fonts.body, wrap="word", bd=0, padx=12, pady=10)
        sb = ttk.Scrollbar(w, command=txt.yview)
        txt.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        txt.pack(fill="both", expand=True)
        txt.insert("end", "\n".join(wiersze) if wiersze else "Brak.")
        txt.config(state="disabled")
        return w, txt

    def _dep_historia(self, poz):
        tytul = f"Historia – {poz.get('nr')} ({poz.get('lok')})" if poz else "Historia zmian w depozycie"
        w, txt = self._dep_okno_tekst(tytul, ["Wczytywanie…"])

        def work():
            try:
                rows, err = dane.historia(self.session, poz.get("id") if poz else None), None
            except Exception as e:
                rows, err = None, e
            self.after(0, lambda: pokaz(rows, err))

        def pokaz(rows, err):
            if not w.winfo_exists():
                return
            txt.config(state="normal")
            txt.delete("1.0", "end")
            if err is not None:
                txt.insert("end", f"Nie udało się wczytać historii: {opis_bledu(err)}")
            else:
                for r in rows or []:
                    d = r.get("depozyt") or {}
                    txt.insert("end", f"{czas(r.get('at'))}   {d.get('nr', '')} {d.get('lok', '')}   "
                                      f"{r.get('co', '')}   — {r.get('kto', '')}\n")
                if not rows:
                    txt.insert("end", "Brak zmian.")
            txt.config(state="disabled")
        threading.Thread(target=work, daemon=True).start()

    def _dep_duplikaty(self):
        grupy = {}
        for p in self._dep_sezonu():
            k = szukaj.norm(p.get("nr"))
            if len(k) > 3:
                grupy.setdefault(k, []).append(p)
        wiersze = [f"{g[0].get('nr')}  →  " + ", ".join((p.get("lok") or "?") + (" ✓" if p.get("przywiezione") else "")
                                                         for p in g)
                   for g in sorted(grupy.values(), key=lambda g: g[0].get("nr")) if len(g) > 1]
        self._dep_okno_tekst(f"Numery w kilku miejscach ({len(wiersze)})", wiersze)

    def _dep_eksport(self):
        import openpyxl
        from openpyxl.styles import Font, PatternFill
        sezon = self.dep_sezon_var.get() or "spis"
        sciezka = filedialog.asksaveasfilename(
            parent=self, defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")],
            initialfile=f"Depozyt {sezon.replace('/', '-')} {datetime.date.today():%Y-%m-%d}.xlsx")
        if not sciezka:
            return
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "SPIS"
        ws.append(["NR REJ.", "LOK", "MARKA", "MARKA 2", "ILOŚĆ", "SEZON", "UWAGI", "KOMENTARZ", "STATUS",
                   "PRZYWIEZIONE", "KTO"])
        for c in ws[1]:
            c.font = Font(bold=True)
        red, org = PatternFill("solid", fgColor="FFFF0000"), PatternFill("solid", fgColor="FFFF9900")
        for p in sorted(self._dep_sezonu(), key=lambda p: p.get("id")):
            ws.append([p.get("nr"), p.get("lok"), p.get("marka"), p.get("marka2"), p.get("ilosc"), p.get("rodzaj"),
                       p.get("uwagi"), p.get("komentarz"),
                       "PRZYWIEZIONE" if p.get("przywiezione") else "DO WYJAŚNIENIA" if p.get("wyjasnic") else "",
                       ("wg Excela" if not p.get("przywiezione_at") else czas(p["przywiezione_at"]))
                       if p.get("przywiezione") else "", p.get("przywiezione_kto") or ""])
            fill = red if p.get("przywiezione") else org if p.get("wyjasnic") else None
            if fill:
                for c in ws[ws.max_row]:
                    c.fill = fill
        for col, w in zip("ABCDEFGHIJK", (12, 9, 14, 12, 7, 8, 24, 30, 16, 17, 16)):
            ws.column_dimensions[col].width = w
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = f"A1:K{ws.max_row}"
        tmp = sciezka + ".tmp"
        try:
            wb.save(tmp)
            os.replace(tmp, sciezka)
        except OSError as e:
            messagebox.showerror("Eksport", f"Nie zapisano pliku:\n{e}")
            return
        messagebox.showinfo("Eksport", f"Zapisano: {sciezka}")

    def _dep_raport(self):
        sciezka = filedialog.askopenfilename(
            parent=self, title="Raport z Integry: przechowalnia (PDF) albo harmonogram wizyt (Excel)",
            filetypes=[("Raport z Integry", "*.pdf *.xls *.xlsx"), ("PDF", "*.pdf"), ("Excel", "*.xls *.xlsx")])
        if sciezka:
            self.depozyt_wczytaj_raport(sciezka)

    def depozyt_wczytaj_raport(self, sciezka):
        """PDF przechowalni albo Excel z harmonogramem wizyt z Integry → okno listy dla magazyniera."""
        from depozyt import raport
        self.dep_stat.config(text="Czytam raport z Integry…", fg=MUTED)
        spis = self._dep_sezonu() or self.dep_rows

        def work():
            try:
                r = raport.wczytaj(sciezka)
                wynik, err = (r, raport.przygotuj(r, spis)), None
                if not r.get("pozycje"):
                    err = ValueError("W pliku nie ma pozycji – to na pewno raport przechowalni albo harmonogram wizyt "
                                     "z Integry?")
            except Exception as e:
                wynik, err = None, e
            self.after(0, lambda: koniec(wynik, err))

        def koniec(wynik, err):
            self._dep_render()
            if err is not None:
                messagebox.showerror("Raport z Integry", f"Nie udało się odczytać raportu:\n{opis_bledu(err)}")
                return
            self.dep_ostatni = wynik[0]
            _zapisz_ostatni(wynik[0])
            self._dep_ostatni_opis()
            self.dep_okno = PrzygotowanieOkno(self, *wynik)
        threading.Thread(target=work, daemon=True).start()

    def _dep_ostatni_opis(self):
        r = self.dep_ostatni
        if r:
            okres = r.get("od") if r.get("od") == r.get("do") else f"{r.get('od')} – {r.get('do')}"
            self.dep_ostatni_btn.set_enabled(True, f"↺  Ostatnia lista ({okres})")
        else:
            self.dep_ostatni_btn.set_enabled(False, "↺  Ostatnia lista")

    def depozyt_ostatnia_lista(self):
        """Ponownie otwiera listę z ostatnio wczytanego raportu – ze świeżym stanem spisu (kto co przygotował)."""
        from depozyt import raport
        if not self.dep_ostatni:
            return
        okno = getattr(self, "dep_okno", None)
        if okno is not None and okno.winfo_exists():
            okno.destroy()
        self.dep_okno = PrzygotowanieOkno(self, self.dep_ostatni,
                                          raport.przygotuj(self.dep_ostatni, self._dep_sezonu() or self.dep_rows))


class PrzygotowanieOkno(tk.Toplevel):
    """Lista z raportu Integry połączona ze spisem: trasa po regałach, uwagi, „przygotowane”, odhaczanie."""

    def __init__(self, app, rap: dict, wiersze: list):
        super().__init__(app)
        from depozyt import raport as rmod
        self.app, self.rap, self.wiersze = app, rap, wiersze
        self.tryb = rmod.tryb(rap)
        f = app.fonts
        self.terminy = rap.get("zrodlo") == "terminy"
        tytuly = {"przygotowanie": "Do przygotowania", "kontrola": "Kontrola z dni, które minęły", "okres": "Raport z okresu"}
        if self.terminy:
            tytuly = {k: "Wizyty – opony w depozycie" for k in tytuly}
        okres = rap.get("od") if rap.get("od") == rap.get("do") else f"{rap.get('od')} – {rap.get('do')}"
        self.title(f"{tytuly[self.tryb]} · {okres}")
        set_icon(self)
        self.geometry("1180x700")
        self.configure(bg=BG)
        top = tk.Frame(self, bg=BG, padx=14, pady=10)
        top.pack(fill="x")
        tk.Label(top, text=f"{tytuly[self.tryb]} – {okres}", bg=BG, fg=BLACK, font=f.h1).pack(anchor="w")
        bez = sum(1 for w in wiersze if not w["spis"])
        uw = sum(1 for w in wiersze if w["uwagi"])
        if self.terminy:
            opis = (f"{rap.get('tytul', '')} · {len(wiersze)} {odmiana(len(wiersze), 'wizyta', 'wizyty', 'wizyt')} · "
                    f"z oponami w depozycie: {len(wiersze) - bez} · kolejność: dniami, potem regały K → M → pozostałe")
        else:
            opis = (f"{rap.get('tytul', '')} · {len(wiersze)} {odmiana(len(wiersze), 'pozycja', 'pozycje', 'pozycji')}"
                    f" · {uw} z uwagami · {bez} bez lokalizacji w spisie · kolejność: regały K → M → pozostałe")
        tk.Label(top, text=opis, bg=BG, fg=MUTED, font=f.small).pack(anchor="w")
        przyc = tk.Frame(top, bg=BG)
        przyc.pack(fill="x", pady=(8, 0))
        FlatButton(przyc, "✓ Przygotowane", lambda: self._oznacz("przygotowane"), "primary", f.body, 14, 6).pack(side="left")
        FlatButton(przyc, "Odhacz „przywiezione” w spisie", lambda: self._oznacz("przywiezione"), "ghost", f.body,
                   12, 6).pack(side="left", padx=6)
        FlatButton(przyc, "🖨  Drukuj / otwórz w przeglądarce", self._drukuj, "ghost", f.body, 12, 6).pack(side="left")
        self.tylko_uwagi = tk.BooleanVar(value=False)
        self.tylko_depozyt = tk.BooleanVar(value=self.terminy)
        tk.Checkbutton(przyc, text="tylko z uwagami", variable=self.tylko_uwagi, bg=BG, font=f.body,
                       command=self._render).pack(side="right")
        if self.terminy:
            tk.Checkbutton(przyc, text="tylko auta z oponami w depozycie", variable=self.tylko_depozyt, bg=BG,
                           font=f.body, command=self._render).pack(side="right", padx=8)
        tk.Label(self, text="Zaznacz wiersze (Ctrl/Shift + klik) i użyj przycisków. „Przygotowane” zapisuje w spisie, "
                            "kto i kiedy przygotował opony.", bg=BG, fg=MUTED, font=f.small).pack(anchor="w", padx=14)
        box = tk.Frame(self, bg=SURFACE)
        box.pack(fill="both", expand=True, padx=14, pady=(6, 14))
        kol = [("dzien", "Termin" if self.terminy else "Dzień", 95), ("lok", "Lokalizacja", 110), ("nr", "Nr rej.", 95),
               ("opis", "Auto / opony w spisie" if self.terminy else "Opony (Integra)", 240),
               ("szcz", "Uwagi ze spisu" if self.terminy else "Rozmiar · rodzaj · felga · bieżnik", 250), ("klient", "Klient", 170), ("uwagi", "Uwagi", 300)]
        self.tree = ttk.Treeview(box, columns=[k for k, _, _ in kol], show="headings", style="Dep.Treeview")
        for k, t, w in kol:
            self.tree.heading(k, text=t)
            self.tree.column(k, width=w, anchor="w", stretch=k in ("uwagi", "opis"))
        self.tree.tag_configure("brak", background="#FDE3E3")
        self.tree.tag_configure("uwaga", background="#FFF4E0")
        self.tree.tag_configure("gotowe", background=KOLOR_PRZYG)
        self.tree.tag_configure("nie", foreground=MUTED)
        sb = ttk.Scrollbar(box, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self._render()

    def _widoczne(self) -> list:
        return [(i, w) for i, w in enumerate(self.wiersze)
                if not (self.tylko_uwagi.get() and not w["uwagi"]) and not (self.tylko_depozyt.get() and not w["spis"])]

    def _render(self):
        t = self.tree
        t.delete(*t.get_children())
        for i, w in self._widoczne():
            gotowe = w["spis"] and all(s.get("przygotowane_at") for s in w["spis"])
            tag = ("nie" if self.terminy else "brak") if not w["spis"] else "gotowe" if gotowe else \
                "uwaga" if w["uwagi"] else ""
            r = w["raport"]
            dzien = ".".join((r.get("data_wydania") or r.get("data_przyjecia") or "").split(".")[:2])
            t.insert("", "end", iid=str(i), tags=(tag,) if tag else (), values=(
                f"{dzien} {r.get('godzina', '')}".strip(), w["lok"] or "—", r["nr_rej"], w["opis"],
                w["szczegoly"], r.get("kontrahent", "")[:30],
                ("✓ przygotowane · " if gotowe else "") + " · ".join(w["uwagi"])))

    def _oznacz(self, pole):
        wybrane = [self.wiersze[int(i)] for i in self.tree.selection()]
        poz = [s for w in wybrane for s in w["spis"]]
        if not poz:
            messagebox.showinfo("Depozyt", "Zaznacz wiersze z lokalizacją w spisie.")
            return
        if pole == "przywiezione":
            poz = [p for p in poz if not p.get("przywiezione")]
            if not poz:
                messagebox.showinfo("Depozyt", "Zaznaczone pozycje są już odhaczone.")
                return
            if not messagebox.askyesno("Odhaczyć?", f"Odhaczyć „przywiezione” w spisie dla "
                                                    f"{len(poz)} {odmiana(len(poz), 'pozycji', 'pozycji', 'pozycji')}?",
                                       parent=self):
                return
        app = self.app

        def work():
            bledy = []
            for p in poz:
                try:
                    nowy = dane.zmien(app.session, p["id"], pole, True)
                    nowy = nowy[0] if isinstance(nowy, list) and nowy else nowy
                    if isinstance(nowy, dict):
                        app.after(0, lambda p=p, n=nowy: (p.clear(), p.update(n), app._dep_podmien(n)))
                except Exception as e:
                    bledy.append(f"{p.get('nr')}: {opis_bledu(e)}")
            app.after(0, lambda: koniec(bledy))

        def koniec(bledy):
            app._dep_render(zachowaj=True)
            if self.winfo_exists():
                self._render()
            if bledy:
                messagebox.showerror("Depozyt", "Nie zapisano:\n" + "\n".join(bledy[:10]))
        threading.Thread(target=work, daemon=True).start()

    def _drukuj(self):
        wiersze = [w for _, w in self._widoczne()]
        tr = "".join(
            f"<tr class='{'brak' if not w['spis'] else 'uw' if w['uwagi'] else ''}'><td class=c>☐</td>"
            f"<td class=lok>{esc(w['lok'] or '—')}</td><td class=nr>{esc(w['raport']['nr_rej'])}</td>"
            f"<td>{esc(w['opis'])}<br><small>{esc(w['szczegoly'])}</small></td>"
            f"<td><small>{esc(w['raport'].get('kontrahent', '')[:30])}</small></td>"
            f"<td class=u>{esc(' · '.join(w['uwagi']))}</td></tr>" for w in wiersze)
        rap = self.rap
        okres = rap.get("od") if rap.get("od") == rap.get("do") else f"{rap.get('od')} – {rap.get('do')}"
        doc = f"""<!DOCTYPE html><html lang=pl><head><meta charset=utf-8><title>Przygotowanie {esc(okres)}</title><style>
body{{font:13px Arial;margin:12mm}}h1{{font-size:18px;margin:0 0 4px}}table{{border-collapse:collapse;width:100%}}
th{{background:#111;color:#fff;text-align:left;padding:5px;font-size:11px}}td{{border-bottom:1px solid #ccc;padding:4px 5px;vertical-align:top}}
.lok{{font:bold 16px Consolas,monospace;white-space:nowrap}}.nr{{font:bold 14px Consolas,monospace}}.c{{font-size:18px}}
.u{{color:#8a5a00;font-weight:bold;font-size:11px}}tr.brak td{{background:#fde3e3}}tr.uw td{{background:#fff4e0}}small{{color:#555}}
@media print{{tr{{page-break-inside:avoid}}}}</style></head><body onload="window.print()">
<h1>Opony do przygotowania – {esc(okres)}</h1><div><small>Panel Latex Serwis · {len(wiersze)} pozycji · trasa: regały K → M → pozostałe ·
wydrukowano {datetime.datetime.now():%d.%m.%Y %H:%M}</small></div><br>
<table><tr><th></th><th>Lokalizacja</th><th>Nr rej.</th><th>{'Auto / opony w spisie' if self.terminy else 'Opony (Integra)'}</th><th>Klient</th><th>Uwagi</th></tr>{tr}</table></body></html>"""
        fd, sciezka = tempfile.mkstemp(prefix="przygotowanie_", suffix=".html")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(doc)
        webbrowser.open("file:///" + sciezka.replace(os.sep, "/").lstrip("/"))
