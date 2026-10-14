"""Zakładka KONTROLA: PDF z Integry + raport .xlsx z CRM → braki → mail (+ liczniki dzienne)."""
import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import paths
from kontrola import analyze, crm_report, mailer
from ui import BG, BLACK, ERR_BG, FlatButton, INK, LINE, MUTED, OK, OK_BG, RED, RED_DARK, SURFACE, WARN, WARN_BG, card, step_badge
from konfig import load_config, recipients_for, save_config
from ustawienia import SettingsDialog
try:
    from kontrola import history
except Exception:   # pragma: no cover – stare .exe bez bibliotek historii
    history = None


class KontrolaMixin:
    """Zakładka KONTROLA: PDF z Integry + raport .xlsx z CRM → braki → mail.
    Część klasy okna programu (App) – metody korzystają z jej pól (self.*)."""

    def _build_main(self, page):
        f = self.fonts
        steps = tk.Frame(page, bg=BG)
        steps.pack(fill="x")
        steps.columnconfigure(0, weight=1, uniform="s")
        steps.columnconfigure(1, weight=1, uniform="s")

        # krok 1 – PDF
        c1 = card(steps, padx=14, pady=10)
        c1.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        h = tk.Frame(c1, bg=SURFACE)
        h.pack(fill="x")
        step_badge(h, 1, f).pack(side="left")
        tk.Label(h, text="Raport z Integra 7 (PDF)", bg=SURFACE, fg=BLACK, font=f.h2).pack(side="left", padx=8)
        self.pdf_box = tk.Label(c1, text="Przeciągnij tutaj plik PDF\nalbo kliknij, aby wybrać", bg=BG, fg=MUTED, font=f.body, anchor="w",
                                padx=12, pady=6, cursor="hand2", justify="center")
        self.pdf_box.pack(fill="x", pady=(8, 8))
        self.pdf_box.bind("<Button-1>", lambda e: self.pick_pdf())
        FlatButton(c1, "Wybierz PDF", self.pick_pdf, "dark", f.body, 14, 6).pack(anchor="w")

        # krok 2 – CRM
        c2 = card(steps, padx=14, pady=10)
        c2.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        h = tk.Frame(c2, bg=SURFACE)
        h.pack(fill="x")
        step_badge(h, 2, f).pack(side="left")
        tk.Label(h, text="Raport z CRM (.xlsx)", bg=SURFACE, fg=BLACK, font=f.h2).pack(side="left", padx=8)
        self.preview = tk.Label(c2, text="Przeciągnij tutaj raport .xlsx z „Listy kontrolne”\n"
                                "albo kliknij, aby wybrać",
                                bg=BG, fg=MUTED, font=f.body, pady=6, cursor="hand2", justify="center")
        self.preview.pack(fill="x", pady=(8, 8))
        self.preview.bind("<Button-1>", lambda e: self.pick_report())
        r = tk.Frame(c2, bg=SURFACE)
        r.pack(fill="x")
        FlatButton(r, "Raport z CRM (.xlsx)…", self.pick_report, "dark", f.body, 14, 6).pack(side="left")
        bl = tk.Frame(c2, bg=SURFACE)
        bl.pack(fill="x", pady=(8, 0))
        tk.Label(bl, text="Sprawdzaj serwisy:", bg=SURFACE, fg=MUTED, font=f.small).pack(side="left")
        self.branch_box = tk.Frame(bl, bg=SURFACE)
        self.branch_box.pack(side="left", padx=(6, 0))
        self._build_branches(crm_report.BRANCHES)

        # krok 3 – sprawdź
        self.btn_check = FlatButton(page, "SPRAWDŹ", self.check, "primary", f.big, 18, 8)
        self.btn_check.pack(fill="x", pady=(10, 8))

        # wynik
        self.banner = tk.Label(page, text="Wybierz PDF z Integry i raport .xlsx z CRM, potem kliknij „Sprawdź”.",
                               bg=SURFACE, fg=MUTED, font=f.label, anchor="w", padx=16, pady=8,
                               highlightthickness=1, highlightbackground=LINE, justify="left", wraplength=900)
        self.banner.pack(fill="x")

        bottom = tk.Frame(page, bg=BG)
        bottom.pack(fill="both", expand=True, pady=(8, 0))
        bottom.columnconfigure(0, weight=2, uniform="b")
        bottom.columnconfigure(1, weight=3, uniform="b")
        bottom.rowconfigure(0, weight=1)

        # lewa kolumna – numery
        left = card(bottom, padx=14, pady=10)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        FlatButton(left, "Szczegóły odczytu…", self.show_details, "ghost", f.small, 10, 4
                   ).pack(side="bottom", anchor="w", pady=(6, 0))
        lh = tk.Frame(left, bg=SURFACE)
        lh.pack(fill="x")
        tk.Label(lh, text="Brakuje w CRM", bg=SURFACE, fg=BLACK, font=f.h2).pack(side="left")
        self.btn_copy_all = FlatButton(lh, "Kopiuj wszystkie", self.copy_all, "ghost", f.small, 10, 4)
        self.btn_copy_all.pack(side="right")
        tk.Label(left, text="Kliknij numer, aby go skopiować", bg=SURFACE, fg=MUTED, font=f.small
                 ).pack(anchor="w", pady=(2, 0))
        self.chips = tk.Frame(left, bg=SURFACE)
        self.chips.pack(fill="x", pady=(6, 6))
        self.copy_info = tk.Label(left, text="", bg=SURFACE, fg=OK, font=f.small)
        self.copy_info.pack(anchor="w")
        # pełny dziennik w osobnym, dużym oknie (tutaj tylko przechowywany)
        self.log = tk.Text(self, font=f.mono)

        # prawa kolumna – mail
        right = card(bottom, padx=14, pady=10)
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        hr = tk.Frame(right, bg=SURFACE)
        hr.pack(fill="x")
        step_badge(hr, 3, f).pack(side="left")
        tk.Label(hr, text="Mail do handlowców", bg=SURFACE, fg=BLACK, font=f.h2).pack(side="left", padx=8)
        tk.Label(right, text="Temat", bg=SURFACE, fg=MUTED, font=f.small).pack(anchor="w", pady=(6, 2))
        self.subject = tk.StringVar()
        ttk.Entry(right, textvariable=self.subject, font=f.body).pack(fill="x", ipady=2)
        th = tk.Frame(right, bg=SURFACE)
        th.pack(fill="x", pady=(8, 2))
        tk.Label(th, text="Treść (możesz poprawić przed wysłaniem)", bg=SURFACE, fg=MUTED,
                 font=f.small).pack(side="left")
        FlatButton(th, "⤢  Powiększ", self.edit_mail_big, "ghost", f.small, 10, 3).pack(side="right")
        self.mail_body = tk.Text(right, height=8, font=f.body, bg=SURFACE, fg=INK, relief="flat",
                                 wrap="word", highlightthickness=1, highlightbackground=LINE,
                                 highlightcolor=RED, padx=8, pady=6)
        self.btn_send = FlatButton(right, "Wyślij maila", self.send_mail, "dark", f.btn, 18, 8)
        self.btn_send.pack(side="bottom", anchor="e", pady=(8, 0))   # zawsze widoczny
        self.mail_body.pack(fill="both", expand=True)
        self.btn_send.set_enabled(False)

    # ---------- wynik ----------
    def set_banner(self, kind, text):
        colors = {"idle": (SURFACE, MUTED), "ok": (OK_BG, OK), "warn": (WARN_BG, WARN),
                  "bad": (ERR_BG, RED_DARK), "busy": (SURFACE, INK)}
        bg, fg = colors[kind]
        self.banner.config(text=text, bg=bg, fg=fg)

    def copy_all(self):
        if not self.result or not (self.result[0] or self.result[1]):
            self.copy_info.config(text="Nie ma numerów do skopiowania.")
            return
        allp = list(self.result[0]) + [a for a, _ in self.result[1]]
        self.copy_text("\n".join(allp), f"✔ Skopiowano {len(allp)} numer(y) – każdy w osobnej linii")

    def show_details(self):
        content = self.log.get("1.0", "end").strip() or "Brak szczegółów – najpierw kliknij „Sprawdź”."
        self._text_window("Szczegóły odczytu", content)

    def edit_mail_big(self):
        def save(txt):
            self.mail_body.delete("1.0", "end")
            self.mail_body.insert("1.0", txt)
        return self._text_window(f"Treść maila – {self.subject.get() or 'bez tematu'}",
                          self.mail_body.get("1.0", "end").strip(), editable=True, on_save=save)

    def set_chips(self, missing, uncertain):
        for w in self.chips.winfo_children():
            w.destroy()
        f = self.fonts
        if not missing and not uncertain:
            tk.Label(self.chips, text="—", bg=SURFACE, fg=MUTED, font=f.body).pack(anchor="w")
            return
        wrap = tk.Frame(self.chips, bg=SURFACE)
        wrap.pack(fill="x")
        col = 0
        reg = history.reported() if history else {}
        for p in missing:
            cell = tk.Frame(wrap, bg=SURFACE)
            cell.grid(row=col // 3, column=col % 3, padx=(0, 6), pady=3, sticky="w")
            chip = tk.Label(cell, text=p, bg=RED, fg="white", font=(f.family, 11, "bold"), padx=10, pady=4,
                            cursor="hand2")
            chip.pack(anchor="w")
            chip.bind("<Button-1>", lambda e, v=p: self.copy_text(v))
            chip.bind("<Enter>", lambda e, w=chip: w.config(bg=RED_DARK))
            chip.bind("<Leave>", lambda e, w=chip: w.config(bg=RED))
            if p in reg:
                tk.Label(cell, text=f"zgłoszony {reg[p]}", bg=SURFACE, fg=MUTED, font=f.small).pack(anchor="w")
            col += 1
        if uncertain:
            tk.Label(self.chips, text="Do weryfikacji (podobny numer w CRM):", bg=SURFACE, fg=WARN,
                     font=f.small).pack(anchor="w", pady=(8, 2))
            for a, b in uncertain:
                u = tk.Label(self.chips, text=f"{a}  ≈  {b}", bg=WARN_BG, fg=WARN, font=f.label, padx=8, pady=3,
                             cursor="hand2")
                u.pack(anchor="w", pady=2)
                u.bind("<Button-1>", lambda e, v=a: self.copy_text(v))

    def _on_ctrl_v(self, event):
        # Ctrl+V działa zwyczajnie (wkleja tekst w polach maila) – wycinków ekranu już nie wklejamy
        return None

    # ---------- pliki / schowek ----------
    def pick_pdf(self):
        p = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf")])
        if p:
            self.set_pdf(p)

    def set_pdf(self, p):
        self.pdf_path.set(p)
        name = p.replace("\\", "/").split("/")[-1]
        self.pdf_box.config(text=f"✔  {name}", fg=OK, bg=OK_BG)

    # ---------- raport z CRM (.xlsx) i wybór serwisów ----------
    def _build_branches(self, names):
        chosen = {crm_report._key(b) for b in load_config().get("crm_branches", crm_report.BRANCHES)}
        if self.session and not self.session.is_admin:   # tylko oddziały przydzielone użytkownikowi
            allowed = {crm_report._key(b) for b in self.session.branches()}
            names = [n for n in names if crm_report._key(n) in allowed]
        for n in names:
            if n in self.branch_vars:
                continue
            v = tk.BooleanVar(value=crm_report._key(n) in chosen)
            self.branch_vars[n] = v
            tk.Checkbutton(self.branch_box, text=n, variable=v, command=self._branches_changed,
                           bg=SURFACE, activebackground=SURFACE, font=self.fonts.small,
                           selectcolor=SURFACE).pack(side="left", padx=(0, 6))

    def chosen_branches(self):
        return [n for n, v in self.branch_vars.items() if v.get()]

    def _branches_changed(self):
        cfg = load_config()
        cfg["crm_branches"] = self.chosen_branches()
        try:
            save_config(cfg)
        except OSError:
            pass
        self._show_report()

    def pick_report(self):
        p = filedialog.askopenfilename(filetypes=[("Raport CRM", "*.xlsx *.csv")])
        if p:
            self.set_report(p)

    def set_report(self, p):
        try:
            rows = crm_report.load(p)
        except Exception as e:
            messagebox.showerror("Raport z CRM", f"Nie udało się wczytać raportu:\n{e}")
            return
        self.crm_rows, self.crm_file, self.crm_img = rows, os.path.basename(p), None
        self._build_branches(crm_report.branches(rows))
        self._show_report()

    def _show_report(self):
        if not self.crm_rows:
            return
        counts = {}
        for r in self.crm_rows:
            counts[r["branch"]] = counts.get(r["branch"], 0) + 1
        sel = set(self.chosen_branches())
        n = sum(c for b, c in counts.items() if b in sel)
        ds = sorted(r["date"] for r in self.crm_rows if r["date"])
        rng = f"{ds[0]:%d.%m} – {ds[-1]:%d.%m.%Y}" if ds else "bez dat"
        det = ",  ".join(f"{b}: {c}" for b, c in counts.items())
        self.preview.config(image="", text=f"✔  {self.crm_file}   ({rng})\n{det}\nDo sprawdzenia: {n} numerów",
                            fg=OK if n else WARN, bg=OK_BG if n else WARN_BG)

    def set_image(self, img=None):
        """Wywoływane przez okno po upuszczeniu obrazu – wycinki ekranu nie są już obsługiwane."""
        messagebox.showinfo("Raport z CRM", "Zrzuty i wycinki ekranu z CRM nie są już obsługiwane.\n\n"
                            "W CRM otwórz „Listy kontrolne”, pobierz raport do Excela (.xlsx) "
                            "i przeciągnij go tutaj albo kliknij „Raport z CRM (.xlsx)…”.")

    def check(self):
        if not self.pdf_path.get():
            messagebox.showwarning("Brak PDF", "Wybierz raport PDF z Integry.")
            return
        if not self.crm_rows:
            messagebox.showwarning("Brak danych z CRM", "Wczytaj raport .xlsx z „Listy kontrolne” w CRM.")
            return
        if not self.chosen_branches():
            messagebox.showwarning("Serwisy", "Zaznacz co najmniej jeden serwis do sprawdzenia.")
            return
        self.btn_check.set_enabled(False, "SPRAWDZAM…")
        self.btn_send.set_enabled(False)
        self.log.delete("1.0", "end")
        self.set_chips([], [])
        self.set_banner("busy", "Sprawdzam…")
        # Tkinter nie jest bezpieczny dla wątków – wszystko z okna odczytujemy tutaj
        pdf = self.pdf_path.get()
        br = self.chosen_branches()
        src = {"rows": crm_report.select(self.crm_rows, br), "branches": br}
        threading.Thread(target=self._check_work, args=(pdf, src), daemon=True).start()

    def _check_work(self, pdf, src):
        try:
            tess = paths.find_tesseract(load_config().get("tesseract_cmd", ""))
            import time as _t
            _t0 = _t.time()
            res = analyze.run(pdf, src, tess, self.say)
            self._stat("check", n_integra=len(res["integra"]), n_crm=len(res["crm_main"]),
                       n_missing=len(res["missing"]), n_uncertain=len(res["uncertain"]),
                       n_autofix=len(res.get("autofix", [])), n_warnings=len(res["warnings"]),
                       seconds=round(_t.time() - _t0, 1))
            integra, crm, crm_main = res["integra"], res["crm"], res["crm_main"]
            warn = res["warnings"]

            self.result = None
            if not integra:
                self.ui(self.set_banner, "warn", "⚠  W PDF z Integry nie znaleziono żadnego numeru "
                        "rejestracyjnego – sprawdź, czy to właściwy plik.")
                return
            if not crm:
                self.ui(self.set_banner, "warn", "⚠  W raporcie z CRM nie ma numerów dla zaznaczonych serwisów.")
                return
            for w in warn:
                self.say("⚠ " + w)

            missing, uncertain = res["missing"], res["uncertain"]
            self.result = (missing, uncertain)
            try:
                if history is None:
                    raise RuntimeError("brak modułu historii – pobierz nową wersję .exe")
                name = os.path.basename(pdf)
                self.hist_index = history.add_check(name, len(integra), len(crm_main), missing, uncertain,
                                                    src.get("branches", []))
                self.last_branches = src.get("branches", [])
                self.ui(self.refresh_history)
            except Exception as e:
                self.say(f"Historia: nie zapisano ({e})")
            self._save_daily(res, src.get("branches", []))
            self.ui(self.set_chips, missing, uncertain)
            wtxt = ("\n⚠  " + "\n⚠  ".join(warn)) if warn else ""
            if not missing and not uncertain:
                self.ui(self.set_banner, "warn" if warn else "ok",
                        f"✔  Jest dobrze – wszystkie {len(integra)} zlecenia z Integry są w CRM.{wtxt}")
                self.ui(self.subject.set, "")
                self.ui(self.mail_body.delete, "1.0", "end")
                return
            if res.get("no_overlap"):   # prawie nic się nie pokrywa – mail byłby fałszywym alarmem
                self.ui(self.set_banner, "warn", f"⚠  Dane z CRM nie pasują do raportu Integry "
                        f"(wspólne numery: {res.get('n_common', 0)} z {len(integra)}). Sprawdź zaznaczone "
                        "serwisy i zakres dat. Mail nie został przygotowany." + wtxt)
                self.ui(self.subject.set, "")
                self.ui(self.mail_body.delete, "1.0", "end")
                return
            try:
                reg = history.reported(refresh=True) if history else {}
            except Exception:
                reg = history.reported() if history else {}
            subj, body = mailer.compose(missing, uncertain, reg)

            def fill():
                self.subject.set(subj)
                self.mail_body.delete("1.0", "end")
                self.mail_body.insert("1.0", body)
                self.btn_send.set_enabled(True, "Wyślij maila")
            self.ui(fill)
            parts = []
            if missing:
                parts.append(f"brakuje {len(missing)}")
            if uncertain:
                parts.append(f"{len(uncertain)} do weryfikacji")
            self.ui(self.set_banner, "bad", f"✖  W CRM {' i '.join(parts)} z {len(integra)} zleceń. "
                    "Mail jest gotowy – sprawdź treść i kliknij „Wyślij maila”." + wtxt)
        except Exception as e:
            self.say(f"Błąd: {e}")
            self._report(e, "sprawdzanie")
            self.ui(self.set_banner, "bad", f"✖  Błąd: {e}")
        finally:
            self.ui(self.btn_check.set_enabled, True, "SPRAWDŹ")

    def _save_daily(self, res, branches):
        """Liczniki dzienne do STATYSTYK (w wątku roboczym). Błąd zapisu nie psuje sprawdzenia."""
        daily = res.get("daily") or []
        if history is None or history.SESSION is None or not daily:
            return
        if len(branches) != 1:
            self.say("Statystyki: nie zapisano – zaznaczono kilka serwisów, a raport z Integry dotyczy jednego. "
                     "Aby zapisać statystyki, zaznacz tylko jeden serwis.")
            return
        if res.get("no_overlap"):
            self.say("Statystyki: nie zapisano – dane z CRM nie pasują do raportu z Integry.")
            return
        try:
            idx = self.hist_index if isinstance(self.hist_index, int) else None
            n = history.save_visit_stats(branches[0], daily, idx)
            self.say(f"Statystyki: zapisano {n} dzień/dni dla {branches[0]} ("
                     + ", ".join(f"{d['day']}: wizyty {d['visits']}, listy {d['lists']}, braki {d['missing']}"
                                 for d in daily) + ")")
        except Exception as e:
            self.say(f"Statystyki: nie zapisano ({e})")

    def send_mail(self):
        if not self.result or not (self.result[0] or self.result[1]):
            messagebox.showinfo("Wyślij maila", "Nie ma czego wysyłać – mail przygotowuje się tylko wtedy, "
                                "gdy czegoś brakuje w CRM.")
            return
        cfg = load_config()
        cfg["recipients"] = recipients_for(getattr(self, "last_branches", []), cfg)
        server = self.session is not None   # po zalogowaniu mail wysyła serwer (bez hasła Gmail na komputerze)
        if server and not cfg["recipients"]:
            messagebox.showwarning("Odbiorcy", "Brak odbiorców – administrator ustawia ich w Ustawieniach.")
            return
        if not server and not (cfg["gmail_user"] and cfg["gmail_app_password"] and cfg["recipients"]):
            messagebox.showwarning("Ustawienia", "Uzupełnij swój Gmail, hasło aplikacji i odbiorców.")
            SettingsDialog(self)
            return
        if not messagebox.askyesno("Wyślij maila", f"Wysłać do: {', '.join(cfg['recipients'])}?"):
            return
        branch = ", ".join(getattr(self, "last_branches", []))
        subj, body = self.subject.get(), self.mail_body.get("1.0", "end").strip()
        missing = list(self.result[0])
        hist_index = self.hist_index if self.hist_index is not None else -1
        self.btn_send.set_enabled(False, "WYSYŁAM…")
        self.set_banner("busy", "Wysyłam maila…")

        def work():   # wysyłka w tle – okno nie zamarza przy wolnym internecie
            try:
                sent = False
                if server:
                    try:
                        frm = mailer.send_server(self.session, subj, body, cfg["recipients"], cfg.get("cc_self", True))
                        cfg["gmail_user"] = self.session.email if cfg.get("cc_self", True) else frm
                        sent = True
                    except mailer.NotConfigured:
                        if not (cfg["gmail_user"] and cfg["gmail_app_password"]):
                            raise RuntimeError("Wysyłka z serwera nie jest jeszcze skonfigurowana, a na tym "
                                               "komputerze nie ma ustawionego Gmaila.") from None
                if not sent:
                    mailer.send(subj, body, cfg)
            except Exception as e:
                self._report(e, "wysyłka maila")
                self.ui(self.set_banner, "bad", f"✖  Nie udało się wysłać: {e}")
                self.ui(self.btn_send.set_enabled, True, "Wyślij maila")
                return
            cc = f" (kopia: {cfg['gmail_user']})" if cfg.get("cc_self", True) else ""
            self.ui(self.set_banner, "ok", f"✔  Mail wysłany do: {', '.join(cfg['recipients'])}{cc}")
            self.ui(self.btn_send.set_enabled, False, "Wysłano ✔")
            try:
                if history is None:
                    raise RuntimeError
                self._stat("mail_sent", n_recipients=len(cfg["recipients"]))
                # do rejestru „zgłoszone” trafiają tylko pewne braki, nie pozycje „do weryfikacji”
                history.mark_sent(hist_index, cfg["recipients"], missing, branch)
                self.ui(self.refresh_history)
            except Exception:
                pass
        threading.Thread(target=work, daemon=True).start()
