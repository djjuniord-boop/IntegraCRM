"""Zakładka MARŻA: kolejka raportów, aktualizacja kalkulatorów (silniki w marza/)."""
import os
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
            for txt, cmd in (("Odbiorcy maili", lambda: MarzaRecipientsDialog(self)),
                             ("Wyniki online", lambda: MarzaResultsWindow(self)),
                             ("Kopie w chmurze", lambda: MarzaFilesWindow(self))):
                FlatButton(links, txt, cmd, "dark", f.small, 10, 4).pack(side="left", padx=(0, 8))

        drop = card(page, padx=16, pady=12)
        drop.pack(fill="x", pady=10)
        tk.Label(drop, text="Raporty sprzedaży z Integry („Raport sprzedaży towarów i usług”, od 1. dnia miesiąca)",
                 bg=SURFACE, fg=BLACK, font=f.label).pack(anchor="w")
        self.marza_drop = tk.Label(drop, text="Przeciągnij tutaj PDF-y z Wrocławia i Opola albo kliknij, aby wybrać\n"
                                   "(oddział jest rozpoznawany z treści raportu)",
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
        out = card(page, padx=10, pady=8)
        out.pack(fill="both", expand=True, pady=(8, 0))
        self.marza_log = tk.Text(out, font=f.mono, bg=SURFACE, fg=INK, relief="flat", wrap="word", height=8)
        sb = ttk.Scrollbar(out, command=self.marza_log.yview)
        self.marza_log.config(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.marza_log.pack(fill="both", expand=True)
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
                                       f"{runner.BRANCH_NAMES[branch]}:\n{old}\n\nZastąpić go nowym?")
        added, rejected = runner.add_reports(root, files, ask_replace)
        self.marza_refresh_pending_only()
        if rejected:
            messagebox.showwarning("MARŻA – nie dodano",
                                   "\n\n".join(f"{n}\n→ {why}" for n, why in rejected))
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
        self.marza_set_banner("busy", "Trwa aktualizacja… (rozdzielanie raportów, kalkulatory, podgląd, e-maile)")
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
        try:
            cfg = load_config()
            fresh = None
            if self.session is not None:   # odbiorcy świeżo z bazy (przy starcie mogło nie być internetu)
                try:
                    fresh = dict(self.session.company() or {}) or None
                    if fresh:   # wspólny słownik okna podmieniany w wątku okna (nie w tle)
                        self.after(0, lambda c=fresh: (COMPANY.clear(), COMPANY.update(c)))
                except Exception as e:
                    logline(f"Uwaga: nie udało się wczytać odbiorców maili z bazy ({e}).")
            mz = (fresh or COMPANY).get("marza") or {}
            if self.session is not None:   # odbiorcy maili MARŻY z ustawień firmowych (tylko zaznaczeni)
                cfg["marza_recipients"] = {k: [r["email"] for r in (mz.get(k) or []) if r.get("on")]
                                           for k in ("wroclaw", "opole")}
                names = {"wroclaw": "Wrocław", "opole": "Opole"}
                for k, v in cfg["marza_recipients"].items():
                    if not v:
                        logline(f"⚠ UWAGA: oddział {names[k]} nie ma zaznaczonych odbiorców maili – mail NIE zostanie "
                                "wysłany (MARŻA → „Odbiorcy maili”).")
            res = runner.run_all(root, cfg, log=logline, ask=self._marza_ask)
            n = sum(res.get("counts", {}).values())
            self._stat("marza", n_integra=n)
            if res["ok"]:
                self.after(0, self.marza_set_banner, "ok", f"✔  Gotowe – przetworzono raportów: {n}. Szczegóły poniżej.")
            else:
                self.after(0, self.marza_set_banner, "warn", "⚠  Są uwagi – przeczytaj podsumowanie poniżej.")
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
        runner.remove_pending(self._marza_root(), name)
        self.marza_refresh_pending_only()
        self._marza_banner_after_change(f"Usunięto z kolejki: {name}.")

    def marza_clear(self):
        from marza import runner
        if self.marza_busy:
            return
        root = self._marza_root()
        for n in runner.pending(root) if root else []:
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
