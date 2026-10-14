"""Zakładka SERWIS QR: panel (osobny proces z oknem WebView2) osadzony w zakładce."""
import tkinter as tk
from tkinter import messagebox, ttk
from ui import BG, BLACK, FlatButton, INK, LINE, MUTED, OK, RED, SURFACE, WARN, WARN_BG, card
from konfig import load_config, save_config


class SerwisMixin:
    """Zakładka SERWIS QR: panel (osobny proces z oknem WebView2) osadzony w zakładce.
    Część klasy okna programu (App) – metody korzystają z jej pól (self.*)."""

    # ---------- SERWIS QR (beta) – panel osadzony w zakładce ----------
    def _build_serwis(self, page):
        f = self.fonts
        cfg = load_config()
        self._serwis_proc = None
        self._serwis_hwnd = 0
        self._serwis_gen = 0          # numer uruchomienia – stare sprawdzania po „Uruchom ponownie” same się kończą
        self._serwis_settings_open = False
        page.configure(padx=0, pady=0)
        bar = tk.Frame(page, bg=SURFACE, padx=16, pady=6, highlightthickness=1, highlightbackground=LINE)
        bar.pack(fill="x")
        tk.Label(bar, text="Historia serwisowa", bg=SURFACE, fg=BLACK, font=f.label).pack(side="left")
        tk.Label(bar, text=" BETA ", bg=WARN_BG, fg=WARN, font=f.small).pack(side="left", padx=8)
        self.serwis_banner = tk.Label(bar, text="", bg=SURFACE, fg=MUTED, font=f.small, anchor="w")
        self.serwis_banner.pack(side="left", padx=(8, 0), fill="x", expand=True)
        FlatButton(bar, "Uruchom ponownie", self.serwis_restart, "ghost", f.small, 10, 3).pack(side="right")
        self.btn_sv_settings = FlatButton(bar, "⚙  Ustawienia panelu", self.serwis_toggle_settings, "ghost", f.small, 10, 3)
        self.btn_sv_settings.pack(side="right", padx=(0, 8))

        # ustawienia (chowane) – przykrywają panel, gdy otwarte
        self.serwis_settings = box = tk.Frame(page, bg=BG, padx=22, pady=12)
        inner = card(box, padx=16, pady=12)
        inner.pack(fill="x")
        tk.Label(inner, text="Ustawienia panelu", bg=SURFACE, fg=BLACK, font=f.label).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        self.v_sv_base = tk.StringVar(value=cfg.get("serwis_base", ""))
        self.v_sv_url = tk.StringVar(value=cfg.get("serwis_sb_url", ""))
        self.v_sv_key = tk.StringVar(value=cfg.get("serwis_sb_key", ""))
        rows = (("Adres strony dla klientów (QR)", self.v_sv_base, "np. https://serwis.latex.net.pl/  – puste: kod QR "
                 "nie zadziała u klienta, panel działa normalnie"),
                ("Baza Supabase – adres", self.v_sv_url, "puste = tryb lokalny (dane w folderze programu na tym komputerze)"),
                ("Baza Supabase – klucz anon", self.v_sv_key, "klucz publiczny „anon” z Supabase → Project Settings → API"))
        for i, (lab, var, hint) in enumerate(rows):
            tk.Label(inner, text=lab, bg=SURFACE, fg=INK, font=f.body, anchor="w").grid(row=1 + 2 * i, column=0, sticky="w", pady=(4, 0))
            ttk.Entry(inner, textvariable=var, width=70, font=f.body).grid(row=1 + 2 * i, column=1, sticky="we", padx=(12, 0), pady=(4, 0), ipady=2)
            tk.Label(inner, text=hint, bg=SURFACE, fg=MUTED, font=f.small, anchor="w").grid(row=2 + 2 * i, column=1, sticky="w", padx=(12, 0))
        inner.grid_columnconfigure(1, weight=1)
        btns = tk.Frame(inner, bg=SURFACE)
        btns.grid(row=8, column=1, sticky="e", pady=(10, 0))
        FlatButton(btns, "Zamknij", self.serwis_toggle_settings, "ghost", f.body, 14, 6).pack(side="right")
        FlatButton(btns, "Zapisz ustawienia", self.serwis_save, "dark", f.body, 14, 6).pack(side="right", padx=8)
        info = card(box, padx=16, pady=12)
        info.pack(fill="x", pady=(10, 0))
        tk.Label(info, text="Ważne w wersji beta", bg=SURFACE, fg=BLACK, font=f.label).pack(anchor="w")
        for line in ("• Tryb lokalny: dane są w folderze programu (data\\serwis_webview) – w panelu używaj „Zapisz kopię” "
                     "(np. raz w tygodniu).",
                     "• Przenosząc program na inny komputer, skopiuj cały folder razem z „data” albo wczytaj kopię w panelu.",
                     "• Naklejki z prawdziwym kodem QR drukuj dopiero po ustawieniu adresu strony dla klientów.",
                     "• Zakładka jest widoczna tylko u osób, które włączą ją w Ustawieniach na kanale beta."):
            tk.Label(info, text=line, bg=SURFACE, fg=INK, font=f.small, anchor="w", justify="left",
                     wraplength=900).pack(anchor="w", pady=1)

        # miejsce na panel
        self.serwis_host = tk.Frame(page, bg=SURFACE)
        self.serwis_host.pack(fill="both", expand=True)
        self.serwis_msg = tk.Label(self.serwis_host, text="", bg=SURFACE, fg=MUTED, font=f.body, justify="center")
        self.serwis_msg.place(relx=0.5, rely=0.4, anchor="center")
        self.serwis_host.bind("<Configure>", lambda e: self._serwis_fit())
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.serwis_refresh()

    def serwis_refresh(self):
        from serwis import serwis_qr
        cfg = load_config()
        m = "chmura (Supabase)" if serwis_qr.mode(cfg) == "cloud" else "tryb lokalny"
        base = (cfg.get("serwis_base") or "").strip()
        txt = f"{m}  ·  " + (f"kody QR → {base}" if base else "⚠ brak adresu strony dla klientów (QR)")
        if not self._serwis_hwnd:
            self._serwis_banner("idle", txt)
        else:
            self._serwis_banner("ok", txt)

    def _serwis_banner(self, kind, text):
        fg = {"ok": OK, "warn": WARN, "bad": RED}.get(kind, MUTED)
        self.serwis_banner.config(text=text, fg=fg)

    def _serwis_msg(self, text, kind="idle"):
        fg = {"warn": WARN, "bad": RED}.get(kind, MUTED)
        self.serwis_msg.config(text=text, fg=fg)
        self.serwis_msg.lift()

    def serwis_on_show(self):
        """Wywoływane przy wejściu na zakładkę: uruchamia panel albo go pokazuje."""
        from serwis import embed_win
        if self._serwis_settings_open:
            return
        proc = self._serwis_proc
        if self._serwis_hwnd and embed_win.alive(self._serwis_hwnd):
            embed_win.show(self._serwis_hwnd, True)
            self._serwis_fit()
            return
        if proc is None or proc.poll() is not None:
            self.serwis_start()

    def serwis_on_hide(self):
        from serwis import embed_win
        if self._serwis_hwnd:
            embed_win.show(self._serwis_hwnd, False)

    def serwis_start(self):
        import time
        from serwis import serwis_qr
        from serwis import serwis_window
        why = serwis_window.is_available()
        if why:
            self._serwis_msg(why + "\n\nPobierz instalator IntegraCRM-setup.exe z najnowszego wydania na GitHubie\n"
                             "i uruchom go – ustawienia i logowanie zostaną zachowane.", "warn")
            return
        cfg = load_config()
        try:
            if self.session:
                cfg["serwis_sso"] = True
                serwis_qr.write_token(self.session.access)
            serwis_qr.write_config(cfg)
            try:
                serwis_window.STATUS.unlink()
            except OSError:
                pass
            self._serwis_hwnd = 0
            self._serwis_gen += 1
            serwis_window.reset_log()
            self._serwis_proc = serwis_window.launch(embed=True)
            self._serwis_t0 = time.time()
            self._serwis_loaded_t = 0.0
            serwis_window.gui_log(f"start panelu #{self._serwis_gen}, pid {self._serwis_proc.pid}")
            self._stat("serwis_open")
            self._serwis_msg("Wczytywanie panelu…")
            gen = self._serwis_gen
            self.after(500, lambda: self._serwis_check_started(gen))
        except Exception as e:
            self._serwis_msg(f"Nie udało się uruchomić panelu:\n{e}", "bad")

    def serwis_stop(self):
        from serwis import serwis_window
        self._serwis_gen = getattr(self, "_serwis_gen", 0) + 1   # unieważnia zaplanowane sprawdzania
        proc = getattr(self, "_serwis_proc", None)
        if proc is not None:
            serwis_window.kill_tree(proc)   # razem z procesami Edge WebView2 – nic nie zostaje na pasku zadań
        self._serwis_proc = None
        self._serwis_hwnd = 0

    def serwis_restart(self):
        self.serwis_stop()
        if self._serwis_settings_open:
            self.serwis_toggle_settings()
        self.serwis_start()

    def _serwis_fit(self):
        from serwis import embed_win
        if self._serwis_hwnd:
            self.serwis_host.update_idletasks()
            embed_win.resize(self._serwis_hwnd, self.serwis_host.winfo_width(), self.serwis_host.winfo_height())

    def _serwis_check_started(self, gen):
        import time
        from serwis import embed_win
        from serwis import serwis_window
        proc = self._serwis_proc
        if proc is None or gen != self._serwis_gen:
            return
        st = serwis_window.read_status()
        state = st.get("state", "")
        waited = time.time() - self._serwis_t0
        code = proc.poll()
        if code is not None or state == "error":
            err = st.get("error") or f"kod zakończenia {code}"
            self._serwis_proc = None
            self._serwis_fail(err)
            return
        if state == "loaded":
            if not self._serwis_loaded_t:
                self._serwis_loaded_t = time.time()
            hwnd = embed_win.find_window(proc.pid, serwis_window.TITLE)
            if hwnd:
                serwis_window.gui_log(f"znaleziono okno panelu {hwnd:#x}, osadzam")
                self.serwis_host.update_idletasks()
                if embed_win.embed(hwnd, self.serwis_host.winfo_id(), self.serwis_host.winfo_width(),
                                   self.serwis_host.winfo_height()):
                    self._serwis_hwnd = hwnd
                    self._serwis_msg("")
                    if self.current_tab != "serwis" or self._serwis_settings_open:
                        embed_win.show(hwnd, False)
                    self.serwis_refresh()
                    serwis_window.gui_log("panel osadzony w zakładce")
                    self.after(2000, lambda: self._serwis_watch(gen))
                    return
                serwis_window.gui_log("osadzanie nie powiodło się")
            elif time.time() - self._serwis_loaded_t > 10:
                serwis_window.gui_log("panel wczytany, ale okna nie znaleziono: "
                                      + "; ".join(embed_win.list_windows(proc.pid)))
                self._serwis_fail("nie znaleziono okna panelu do osadzenia", kill=True)
                return
        if waited > 45:
            self._serwis_fail(f"przekroczony czas, etap: {state or 'start'}", kill=True)
            return
        label = {"": "uruchamianie…", "starting": "wczytywanie silnika…", "window": "tworzenie okna…",
                 "shown": "wczytywanie panelu…", "loaded": "osadzanie w programie…"}.get(state, state)
        self._serwis_msg(f"Wczytywanie panelu – {label}")
        self.after(400, lambda: self._serwis_check_started(gen))

    def _serwis_watch(self, gen):
        """Pilnuje, czy panel działa; gdy jego proces się zakończy – pokazuje komunikat."""
        from serwis import embed_win
        proc = self._serwis_proc
        if proc is None or gen != self._serwis_gen:   # po „Uruchom ponownie” stary strażnik kończy pracę
            return
        if proc.poll() is not None or not embed_win.alive(self._serwis_hwnd):
            self.serwis_stop()
            self._serwis_msg("Panel został zamknięty.\nKliknij „Uruchom ponownie” na pasku powyżej.", "warn")
            self.serwis_refresh()
            return
        self.after(2000, lambda: self._serwis_watch(gen))

    def _serwis_fail(self, err, kill=False):
        from serwis import serwis_window
        serwis_window.gui_log(f"błąd: {err}")
        if kill:
            self.serwis_stop()
        tail = serwis_window.log_tail(6)
        self._serwis_msg(f"Panel nie uruchomił się.\n\nPowód: {err}\n\n"
                         + (f"Dziennik (data\\serwis.log):\n{tail}\n\n" if tail else "")
                         + "Kliknij „Uruchom ponownie” na pasku powyżej.", "bad")

    def serwis_toggle_settings(self):
        from serwis import embed_win
        self._serwis_settings_open = not self._serwis_settings_open
        if self._serwis_settings_open:
            embed_win.show(self._serwis_hwnd, False)
            self.serwis_host.pack_forget()
            self.serwis_settings.pack(fill="both", expand=True)
            self.btn_sv_settings.config(text="✕  Zamknij ustawienia")
        else:
            self.serwis_settings.pack_forget()
            self.serwis_host.pack(fill="both", expand=True)
            self.btn_sv_settings.config(text="⚙  Ustawienia panelu")
            self.serwis_on_show()

    def _serwis_collect(self):
        from serwis import serwis_qr
        base, url, key = self.v_sv_base.get().strip(), self.v_sv_url.get().strip(), self.v_sv_key.get().strip()
        prob = serwis_qr.check_base(base) or serwis_qr.check_supabase(url, key)
        return {"serwis_base": base, "serwis_sb_url": url.rstrip("/"), "serwis_sb_key": key}, prob

    def serwis_save(self, quiet=False):
        from serwis import serwis_qr
        vals, prob = self._serwis_collect()
        if prob:
            messagebox.showwarning("SERWIS QR", prob)
            return False
        cfg = load_config()
        old_base = (cfg.get("serwis_base") or "").strip()
        if old_base and vals["serwis_base"] != old_base and not messagebox.askyesno(
                "SERWIS QR", "Zmieniasz adres strony dla klientów.\n\nNaklejki wydrukowane ze starym adresem "
                f"({old_base}) przestaną działać.\n\nZapisać nowy adres?"):
            return False
        changed = any(vals[k] != (cfg.get(k) or "").strip() for k in vals)
        cfg.update(vals)
        save_config(cfg)
        try:
            if self.session:
                cfg["serwis_sso"] = True
                serwis_qr.write_token(self.session.access)
            serwis_qr.write_config(cfg)
        except OSError as e:
            messagebox.showerror("SERWIS QR", f"Nie udało się zapisać ustawień panelu:\n{e}")
            return False
        self.serwis_refresh()
        if changed and self._serwis_proc is not None:   # panel musi wczytać nowe ustawienia
            self.serwis_stop()
        if not quiet:
            messagebox.showinfo("SERWIS QR", "Zapisano. Panel uruchomi się z nowymi ustawieniami po zamknięciu ustawień.")
        return True
