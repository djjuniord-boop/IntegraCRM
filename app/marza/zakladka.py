"""Zakładka MARŻA: kolejka raportów, aktualizacja kalkulatorów (silniki w marza/)."""
import os
import re
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from ui import BG, BLACK, ERR_BG, FlatButton, INK, LINE, MUTED, OK, OK_BG, RED, RED_DARK, SURFACE, WARN, WARN_BG, card
from konfig import COMPANY, load_config, save_config
from marza.okna import MarzaFilesWindow, MarzaRecipientsDialog, MarzaResultsWindow


class MarzaMixin:
    """Zakładka MARŻA: kolejka raportów, aktualizacja kalkulatorów (silniki w marza/).
    Część klasy okna programu (App) – metody korzystają z jej pól (self.*)."""

    # ---------- MARŻA ----------
    def _build_marza(self, page):
        f = self.fonts
        self.marza_busy = False
        top = card(page, padx=16, pady=12)
        top.pack(fill="x")
        h = tk.Frame(top, bg=SURFACE)
        h.pack(fill="x")
        tk.Label(h, text="Kalkulator marży – Wrocław + Opole", bg=SURFACE, fg=BLACK, font=f.h2).pack(side="left")
        FlatButton(h, "Zmień folder…", self.marza_pick_folder, "ghost", f.small, 10, 4).pack(side="right")
        self.marza_folder_lbl = tk.Label(top, text="", bg=SURFACE, fg=MUTED, font=f.small, anchor="w", justify="left")
        self.marza_folder_lbl.pack(fill="x", pady=(4, 8))
        links = tk.Frame(top, bg=SURFACE)
        links.pack(anchor="w")
        for txt, rel in (("Kalkulator Wrocław", ("Wrocław", "kalkulator_marzy_Wroclaw.xlsx")),
                         ("Kalkulator Opole", ("Opole", "kalkulator_marzy_Opole.xlsx")),
                         ("Folder LATEX Wyniki", ())):
            FlatButton(links, txt, lambda r=rel: self.marza_open(*r), "ghost", f.small, 10, 4).pack(side="left", padx=(0, 8))
        if self.session:
            for txt, cmd in (("Odbiorcy e-maili", lambda: MarzaRecipientsDialog(self)),
                             ("Wyniki online", lambda: MarzaResultsWindow(self)),
                             ("Kopie w chmurze", lambda: MarzaFilesWindow(self))):
                FlatButton(links, txt, cmd, "dark", f.small, 10, 4).pack(side="left", padx=(0, 8))

        drop = card(page, padx=16, pady=12)
        drop.pack(fill="x", pady=10)
        tk.Label(drop, text="Raporty sprzedaży z Integry („Raport sprzedaży towarów i usług”, od 1. dnia miesiąca)",
                 bg=SURFACE, fg=BLACK, font=f.label).pack(anchor="w")
        self.marza_drop = tk.Label(drop, text="Przeciągnij tutaj PDF-y z Wrocławia i Opola albo kliknij, aby wybrać\n"
                                   "(oddział jest rozpoznawany z treści raportu; plik jest PRZENOSZONY do kolejki, "
                                   "a po zapisie w kalkulatorze usuwany)",
                                   bg=BG, fg=MUTED, font=f.body, pady=10, cursor="hand2", justify="center")
        self.marza_drop.pack(fill="x", pady=(8, 6))
        self.marza_drop.bind("<Button-1>", lambda e: self.marza_pick_files())
        qh = tk.Frame(drop, bg=SURFACE)
        qh.pack(fill="x")
        tk.Label(qh, text="Kolejka (najwyżej 1 raport na oddział):", bg=SURFACE, fg=MUTED, font=f.small).pack(side="left")
        FlatButton(qh, "Wyczyść kolejkę", self.marza_clear, "ghost", f.small, 8, 2).pack(side="right")
        self.marza_queue = tk.Frame(drop, bg=SURFACE)
        self.marza_queue.pack(fill="x", pady=(4, 0))

        self.btn_marza = FlatButton(page, "AKTUALIZUJ WSZYSTKO", self.marza_run, "primary", f.big, 18, 8)
        self.btn_marza.pack(fill="x", pady=(0, 8))
        self.marza_banner = tk.Label(page, text="", bg=SURFACE, fg=MUTED, font=f.label, anchor="w", padx=16, pady=8,
                                     highlightthickness=1, highlightbackground=LINE, justify="left", wraplength=900)
        self.marza_banner.pack(fill="x")
        # wynik przebiegu: karta na oddział (status, miesiąc, było → jest, cel, kroki); pełny dziennik w „Szczegółach”
        dbar = tk.Frame(page, bg=BG)
        dbar.pack(fill="x", pady=(6, 0))
        self.btn_marza_log = FlatButton(dbar, "Szczegóły przebiegu (pełny dziennik)…", self.marza_show_log, "ghost",
                                        f.small, 10, 4)
        self.btn_marza_log.pack(side="left")
        # karty w przewijanym obszarze (Canvas + pasek + kółko myszy) – przy małym ekranie wszystko dostępne
        scr = tk.Frame(page, bg=BG)
        scr.pack(fill="both", expand=True, pady=(8, 0))
        self.marza_canvas = tk.Canvas(scr, bg=BG, highlightthickness=0, bd=0)
        self.marza_vsb = ttk.Scrollbar(scr, orient="vertical", command=self.marza_canvas.yview)
        self.marza_canvas.configure(yscrollcommand=self.marza_vsb.set)
        self.marza_vsb.pack(side="right", fill="y")
        self.marza_canvas.pack(side="left", fill="both", expand=True)
        self.marza_result = tk.Frame(self.marza_canvas, bg=BG)
        win = self.marza_canvas.create_window(0, 0, window=self.marza_result, anchor="nw")
        self.marza_result.bind("<Configure>", lambda e: self.marza_canvas.configure(
            scrollregion=self.marza_canvas.bbox("all")))
        self.marza_canvas.bind("<Configure>", lambda e: self.marza_canvas.itemconfigure(win, width=e.width))
        self._marza_bind_wheel(self.marza_canvas)
        # pełny dziennik przebiegu – zbierany tutaj (bez pokazywania), oglądany w oknie „Szczegóły przebiegu”
        self.marza_log = tk.Text(page, font=f.mono, wrap="word", height=1)
        self.marza_log_win = None
        self._marza_autodetect()
        self.marza_refresh()

    def _marza_autodetect(self):
        """Jeśli folder nie jest ustawiony, szuka „LATEX Wyniki” w typowych miejscach."""
        if self._marza_root():
            return
        home = os.path.expanduser("~")
        bases = [os.path.join(home, x) for x in ("Desktop", "Pulpit", "Documents", "Dokumenty", "Downloads",
                                                   os.path.join("OneDrive", "Desktop"),
                                                   os.path.join("OneDrive", "Pulpit"), "")]
        bases += [r"G:\Mój dysk", r"G:\My Drive", "C:\\", "D:\\"]
        from marza import runner
        for b in bases:
            cand = os.path.join(b, "LATEX Wyniki")
            if os.path.isdir(cand) and not runner.check_folder(cand):
                cfg = load_config()
                cfg["marza_folder"] = cand
                save_config(cfg)
                return

    def _marza_root(self):
        return load_config().get("marza_folder", "")

    def marza_refresh(self):
        from marza import runner
        root = self._marza_root()
        prob = runner.check_folder(root)
        self.marza_folder_lbl.config(text=(f"Folder: {root}" if not prob else "⚠ " + prob),
                                     fg=MUTED if not prob else WARN)
        missing = runner.deps_ok()
        if missing:
            self.marza_set_banner("warn", f"⚠ Ta wersja IntegraCRM.exe nie ma bibliotek: {missing}. "
                                  "Pobierz najnowszą paczkę .exe z GitHuba.")
        elif prob:
            self.marza_set_banner("warn", "⚠ Wskaż folder „LATEX Wyniki” (przycisk „Zmień folder…”).")
        else:
            self.marza_set_banner("idle", "Dodaj raporty i kliknij „AKTUALIZUJ WSZYSTKO”. "
                                  "Bez nowych raportów odświeżony zostanie tylko podgląd dla handlowców.")
        self.marza_refresh_pending_only()

    def marza_set_banner(self, kind, text):
        colors = {"idle": (SURFACE, MUTED), "ok": (OK_BG, OK), "warn": (WARN_BG, WARN),
                  "bad": (ERR_BG, RED_DARK), "busy": (SURFACE, INK)}
        bg, fg = colors[kind]
        self.marza_banner.config(text=text, bg=bg, fg=fg)

    def marza_pick_folder(self):
        d = filedialog.askdirectory(title="Wskaż folder „LATEX Wyniki”")
        if d:
            cfg = load_config()
            cfg["marza_folder"] = d
            save_config(cfg)
            self.marza_refresh()

    def marza_open(self, *rel):
        root = self._marza_root()
        if not root:
            if messagebox.askyesno("MARŻA", "Nie wskazano jeszcze folderu „LATEX Wyniki”.\n\nWskazać go teraz?"):
                self.marza_pick_folder()
            root = self._marza_root()
            if not root:
                return
        path = os.path.join(root, *rel)
        try:
            os.startfile(path)
        except Exception as e:
            messagebox.showinfo("Otwórz", f"{path}\n\n{e}")

    def marza_pick_files(self):
        fs = filedialog.askopenfilenames(filetypes=[("PDF", "*.pdf")])
        if fs:
            self.marza_add(list(fs))

    def marza_add(self, files):
        from marza import runner
        root = self._marza_root()
        prob = runner.check_folder(root)
        if prob:
            messagebox.showwarning("MARŻA", prob)
            return
        def ask_replace(branch, old):
            return messagebox.askyesno("MARŻA", f"W kolejce jest już raport dla oddziału "
                                       f"{runner.BRANCH_NAMES[branch]}:\n{old}\n\nZastąpić go nowym?\n\nStary raport zostanie "
                                       "usunięty z komputera.")
        added, rejected, notes = runner.add_reports(root, files, ask_replace)
        self.marza_refresh_pending_only()
        if rejected:
            messagebox.showwarning("MARŻA – nie dodano",
                                   "\n\n".join(f"{n}\n→ {why}" for n, why in rejected))
        if notes:
            messagebox.showwarning("MARŻA – uwaga", "\n\n".join(f"{n}\n→ {why}" for n, why in notes))
        if added:
            self.marza_set_banner("idle", "Dodano: " + ", ".join(f"{n} ({runner.BRANCH_NAMES[b]})" for n, b in added)
                                  + ". Kliknij „AKTUALIZUJ WSZYSTKO”.")

    def marza_run(self):
        from marza import runner
        if self.marza_busy:
            return
        root = self._marza_root()
        prob = runner.check_folder(root) or (("Brak bibliotek: " + runner.deps_ok()) if runner.deps_ok() else "")
        if prob:
            messagebox.showwarning("MARŻA", prob)
            return
        self.marza_busy = True
        self.btn_marza.set_enabled(False, "AKTUALIZUJĘ…")
        self.marza_log.delete("1.0", "end")
        for w in self.marza_result.winfo_children():
            w.destroy()
        self._marza_step = ""
        self.marza_set_banner("busy", "Trwa aktualizacja… Krok 1/3: rozdzielanie raportów")
        threading.Thread(target=self._marza_work, args=(root,), daemon=True).start()

    def _marza_ask(self, question):
        """Pytanie z wątku roboczego – odpowiedź z okna."""
        ev, box = threading.Event(), {}

        def _q():
            box["a"] = messagebox.askyesno("MARŻA – potwierdzenie", question + "\n\nZapisać mimo to?")
            ev.set()
        self.after(0, _q)
        ev.wait()
        return box.get("a", False)

    def _marza_work(self, root):
        from marza import runner

        def logline(line):
            self.after(0, lambda l=line: (self.marza_log.insert("end", l + "\n"), self.marza_log.see("end")))
            step = marza_step_text(line)
            if step:
                self.after(0, self.marza_set_banner, "busy", "Trwa aktualizacja… " + step)
        try:
            cfg = load_config()
            fresh = None
            if self.session is not None:   # odbiorcy świeżo z bazy (przy starcie mogło nie być internetu)
                try:
                    fresh = dict(self.session.company() or {}) or None
                    if fresh:   # wspólny słownik okna podmieniany w wątku okna (nie w tle)
                        self.after(0, lambda c=fresh: (COMPANY.clear(), COMPANY.update(c)))
                except Exception as e:
                    logline(f"Uwaga: nie udało się wczytać odbiorców e-maili z bazy ({e}).")
            mz = (fresh or COMPANY).get("marza") or {}
            if self.session is not None:   # odbiorcy maili MARŻY z ustawień firmowych (tylko zaznaczeni)
                cfg["marza_recipients"] = {k: [r["email"] for r in (mz.get(k) or []) if r.get("on")]
                                           for k in ("wroclaw", "opole")}
                names = {"wroclaw": "Wrocław", "opole": "Opole"}
                for k, v in cfg["marza_recipients"].items():
                    if not v:
                        logline(f"⚠ UWAGA: oddział {names[k]} nie ma zaznaczonych odbiorców e-maili – e-mail NIE zostanie "
                                "wysłany (MARŻA → „Odbiorcy e-maili”).")
            res = runner.run_all(root, cfg, log=logline, ask=self._marza_ask)
            n = sum(res.get("counts", {}).values())
            self._stat("marza", n_integra=n)
            if res["ok"]:
                self.after(0, self.marza_set_banner, "ok", f"✔  Gotowe – przetworzono raportów: {n}. Wszystko w porządku.")
            else:
                self.after(0, self.marza_set_banner, "warn", "⚠  Są uwagi – przeczytaj je przy oddziałach poniżej.")
            self.after(0, self.marza_show_result, res)
        except Exception as e:
            self._report(e, "kalkulator marży")
            self.after(0, self.marza_set_banner, "bad", f"✖  Błąd: {e}")
        finally:
            def done():
                self.marza_busy = False
                self.btn_marza.set_enabled(True, "AKTUALIZUJ WSZYSTKO")
                try:
                    self.marza_refresh_pending_only()
                except Exception:
                    pass
            self.after(0, done)

    def marza_refresh_pending_only(self):
        from marza import runner
        f = self.fonts
        for w in self.marza_queue.winfo_children():
            w.destroy()
        root = self._marza_root()
        items = runner.pending_info(root) if root and not runner.check_folder(root) else []
        if not items:
            tk.Label(self.marza_queue, text="Brak raportów w kolejce.", bg=SURFACE, fg=MUTED, font=f.small
                     ).pack(anchor="w")
            return
        for name, branch in items:
            row = tk.Frame(self.marza_queue, bg=BG)
            row.pack(fill="x", pady=2)
            tag = runner.BRANCH_NAMES.get(branch, "NIEROZPOZNANY")
            tk.Label(row, text=f" {tag} ", bg=(BLACK if branch else RED), fg="white", font=f.small
                     ).pack(side="left", padx=(6, 8), pady=4)
            tk.Label(row, text=name, bg=BG, fg=INK, font=f.body).pack(side="left")
            FlatButton(row, "✕ Usuń", lambda n=name: self.marza_remove(n), "ghost", f.small, 8, 2
                       ).pack(side="right", padx=6, pady=3)

    def marza_remove(self, name):
        from marza import runner
        if self.marza_busy:
            return
        if not messagebox.askyesno("MARŻA", f"Usunąć raport {name} z kolejki?\n\nPlik zostanie usunięty z komputera "
                                   "(przy dodaniu został przeniesiony do kolejki). Gdy będzie potrzebny, wygeneruj "
                                   "go ponownie w Integrze."):
            return
        runner.remove_pending(self._marza_root(), name)
        self.marza_refresh_pending_only()
        self._marza_banner_after_change(f"Usunięto z kolejki: {name}.")

    def marza_clear(self):
        from marza import runner
        if self.marza_busy:
            return
        root = self._marza_root()
        names = runner.pending(root) if root else []
        if names and not messagebox.askyesno("MARŻA", f"Usunąć z kolejki raporty ({len(names)})?\n\nPliki zostaną "
                                             "usunięte z komputera (przy dodaniu zostały przeniesione do kolejki)."):
            return
        for n in names:
            runner.remove_pending(root, n)
        self.marza_refresh_pending_only()
        self._marza_banner_after_change("Kolejka wyczyszczona.")

    def _marza_banner_after_change(self, msg):
        from marza import runner
        root = self._marza_root()
        left = runner.pending_info(root) if root and not runner.check_folder(root) else []
        if left:
            names = ", ".join(f"{n} ({runner.BRANCH_NAMES.get(b, '?')})" for n, b in left)
            self.marza_set_banner("idle", f"{msg} W kolejce: {names}. Kliknij „AKTUALIZUJ WSZYSTKO”.")
        else:
            self.marza_set_banner("idle", f"{msg} Kolejka pusta – dodaj raporty sprzedaży (PDF).")

    # ---------- czytelny przebieg ----------
    def marza_show_log(self):
        """Okno z pełnym dziennikiem ostatniego przebiegu (to, co dawniej było w zakładce)."""
        from ui import set_icon
        if self.marza_log_win is not None and self.marza_log_win.winfo_exists():
            self.marza_log_win.destroy()
        w = self.marza_log_win = tk.Toplevel(self)
        w.title("MARŻA – szczegóły przebiegu")
        w.geometry("980x640")
        w.configure(bg=BG, padx=12, pady=10)
        set_icon(w)
        box = card(w, padx=8, pady=6)
        box.pack(fill="both", expand=True)
        t = tk.Text(box, font=self.fonts.mono, bg=SURFACE, fg=INK, relief="flat", wrap="word")
        sb = ttk.Scrollbar(box, command=t.yview)
        t.config(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        t.pack(fill="both", expand=True)
        txt = self.marza_log.get("1.0", "end").strip()
        t.insert("1.0", txt or "Brak przebiegu – kliknij „AKTUALIZUJ WSZYSTKO”.")
        t.see("end")
        t.config(state="disabled")
        FlatButton(w, "Zamknij", w.destroy, "ghost", self.fonts.body, 14, 6).pack(anchor="e", pady=(8, 0))

    def marza_show_result(self, res):
        """Karty oddziałów po zakończeniu przebiegu (dane z runner.run_all → results)."""
        from marza.rozdziel import kwota
        from marza.runner import BRANCH_NAMES
        f = self.fonts
        box = self.marza_result
        for w in box.winfo_children():
            w.destroy()
        results = res.get("results") or {}
        icons = {"OK": ("✔", OK), "UWAGA": ("⚠", WARN), "BŁĄD": ("✖", RED_DARK)}
        row = tk.Frame(box, bg=BG)
        row.pack(fill="x")
        for i, key in enumerate(("wroclaw", "opole")):
            w = results.get(key)
            if not w:
                continue
            c = card(row, padx=14, pady=10)
            c.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 5, 5 if i == 0 else 0))
            row.grid_columnconfigure(i, weight=1, uniform="oddz")
            ic, col = icons.get(w.get("status"), ("?", MUTED))
            h = tk.Frame(c, bg=SURFACE)
            h.pack(fill="x")
            tk.Label(h, text=ic, bg=SURFACE, fg=col, font=f.big).pack(side="left")
            tk.Label(h, text=f" {BRANCH_NAMES[key]}", bg=SURFACE, fg=BLACK, font=f.h2).pack(side="left")
            tk.Label(h, text=w.get("miesiac") or "—", bg=SURFACE, fg=MUTED, font=f.label).pack(side="right")
            lines = []
            if w.get("jest") is not None:
                zm = w.get("zmiana")
                lines.append(("Było → jest", f"{kwota(w.get('bylo'))} → {kwota(w.get('jest'))}"))
                lines.append(("Zmiana", kwota(zm, znak=True) if zm is not None else "—"))
            else:
                lines.append(("Było → jest", "— (brak nowego raportu)"))
            lines.append(("Cel", kwota(w.get("cel"))))
            lines.append(("Zrobione", kwota(w.get("zrobione"))))
            pc = w.get("procent")
            lines.append(("Wykonanie celu", f"{pc}%" if pc is not None else "—"))
            em = w.get("emaile")
            lines.append(("Wysłane e-maile", str(em) if em is not None else "—"))
            g = tk.Frame(c, bg=SURFACE)
            g.pack(fill="x", pady=(6, 4))
            for r, (k, v) in enumerate(lines):
                tk.Label(g, text=k, bg=SURFACE, fg=MUTED, font=f.small, anchor="w").grid(row=r, column=0, sticky="w")
                tk.Label(g, text=v, bg=SURFACE, fg=INK, font=f.label if k in ("Było → jest", "Zmiana") else f.body,
                         anchor="w").grid(row=r, column=1, sticky="w", padx=(12, 0))
            kr = w.get("kroki") or {}
            steps = [("raport", "Raport odczytany"), ("kalkulator", "Kalkulator zaktualizowany"),
                     ("podglad", "Podgląd dla handlowców"), ("dysk", "Dysk Google"),
                     ("email", "E-maile"), ("baza", "Baza / WYNIKI")]
            st = tk.Frame(c, bg=SURFACE)
            st.pack(fill="x", pady=(2, 2))
            for j, (k, txt) in enumerate(steps):
                v = kr.get(k)
                mark, mc = ("✔", OK) if v is True else ("✖", RED_DARK) if v is False else ("—", MUTED)
                tk.Label(st, text=f"{mark} {txt}", bg=SURFACE, fg=mc, font=f.small, anchor="w"
                         ).grid(row=j // 2, column=j % 2, sticky="w", padx=(0, 14))
            od = w.get("odjete")
            if od:
                self._marza_deductions(c, od)
            notes = list(w.get("uwagi") or [])
            for n in w.get("odrzucone") or []:
                why = (w.get("odrzucone_powody") or {}).get(n, "")
                notes.append(f"Raport {n} NIE został zapisany" + (f" – {why}" if why else "") +
                             ". Leży w „1. WRZUC RAPORTY TUTAJ\\_ODRZUCONE” – popraw go i dodaj ponownie.")
            infos = [t for t in (w.get("info") or []) if not t.startswith("Wysłano ")]
            for t in notes:
                tk.Label(c, text="⚠ " + t, bg=WARN_BG, fg=WARN, font=f.small, anchor="w", justify="left",
                         wraplength=420, padx=6, pady=3).pack(fill="x", pady=(4, 0))
            for t in infos:
                tk.Label(c, text="ℹ " + t, bg=SURFACE, fg=MUTED, font=f.small, anchor="w", justify="left",
                         wraplength=420).pack(fill="x", pady=(4, 0))
        self.after_idle(lambda: (self._marza_bind_wheel(self.marza_result), self.marza_canvas.yview_moveto(0)))
        bad = res.get("rejected_input") or []
        if bad:
            c = card(box, padx=14, pady=8)
            c.pack(fill="x", pady=(8, 0))
            tk.Label(c, text="⚠ Nierozpoznane pliki (nie trafiły do żadnego oddziału):", bg=SURFACE, fg=WARN,
                     font=f.label).pack(anchor="w")
            for n, why in bad:
                tk.Label(c, text=f"• {n}: {why}. Leży w „_ODRZUCONE” – dodaj właściwy raport sprzedaży z Integry.",
                         bg=SURFACE, fg=INK, font=f.small, anchor="w", justify="left", wraplength=880
                         ).pack(fill="x")

    def _marza_wheel(self, e):
        c = self.marza_canvas
        if c.yview() == (0.0, 1.0):
            return "break"
        if getattr(e, "num", None) == 4:
            step = -3
        elif getattr(e, "num", None) == 5:
            step = 3
        else:
            step = -1 * (e.delta // 120 if abs(e.delta) >= 120 else (1 if e.delta > 0 else -1)) * 3
        c.yview_scroll(step, "units")
        return "break"

    def _marza_bind_wheel(self, w):
        """Kółko myszy działa nad całym obszarem kart – także nad etykietami w środku."""
        for ev in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            w.bind(ev, self._marza_wheel)
        for ch in w.winfo_children():
            self._marza_bind_wheel(ch)

    def _marza_deductions(self, parent, od):
        """Opole: kategorie odjęte od marży z raportu – rozwijane."""
        from marza.rozdziel import kwota
        f = self.fonts
        holder = tk.Frame(parent, bg=SURFACE)
        holder.pack(fill="x", pady=(4, 0))
        body = tk.Frame(holder, bg=BG, padx=8, pady=4)
        state = {"open": False}
        title = f"Odjęto od marży: {kwota(od.get('odjeto'))} (z raportu {kwota(od.get('z_raportu'))})"

        def toggle():
            state["open"] = not state["open"]
            btn.config(text=("▾ " if state["open"] else "▸ ") + title)
            if state["open"]:
                body.pack(fill="x")
                self._marza_bind_wheel(body)
            else:
                body.pack_forget()
        btn = tk.Label(holder, text="▸ " + title, bg=SURFACE, fg=INK, font=f.small, cursor="hand2", anchor="w")
        btn.pack(fill="x")
        btn.bind("<Button-1>", lambda e: toggle())
        for name, v, brak in od.get("pozycje") or []:
            tk.Label(body, text=f"{name}: {kwota(v)}" + ("  (brak sprzedaży w tym miesiącu)" if brak else ""),
                     bg=BG, fg=MUTED if brak else INK, font=f.small, anchor="w").pack(fill="x")


_KROK_RE = re.compile(r"^--- Krok (\d)/3: (.+?) ---$")
_PODKROKI = (("Odczytane raporty:", "odczyt raportu"), ("Zaktualizowano w Excelu:", "zapis w kalkulatorze"),
             ("Odświeżono plik podglądowy", "podgląd dla handlowców"), ("Skopiowano na Dysk Google", "Dysk Google"),
             ("Wysłano ", "e-maile wysłane"), ("Kopia kalkulatora zapisana", "kopia w chmurze"),
             ("Wyniki zapisane w bazie", "zapis wyników w bazie"))
_marza_krok = {"t": ""}


def marza_step_text(line):
    """Linia dziennika → opis bieżącego kroku do paska („Krok 2/3: Wrocław – zapis w kalkulatorze…”) albo None."""
    m = _KROK_RE.match(line.strip())
    if m:
        _marza_krok["t"] = f"Krok {m.group(1)}/3: {m.group(2)}"
        return _marza_krok["t"] + "…"
    if not _marza_krok["t"].startswith(("Krok 2", "Krok 3")):
        return None
    for frag, txt in _PODKROKI:
        if line.startswith(frag):
            return f"{_marza_krok['t']} – {txt}…"
    return None
