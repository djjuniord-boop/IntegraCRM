"""Zakładka OFERTY OPON: okno modułu (osobny proces WebView2) osadzone w zakładce – jak panel SERWIS QR."""
import time
import tkinter as tk
from ui import BLACK, FlatButton, LINE, MUTED, OK, RED, SURFACE, WARN, WARN_BG


class OfertyMixin:
    """Część klasy okna programu (App) – metody korzystają z jej pól (self.*)."""

    def _build_oferty(self, page):
        f = self.fonts
        self._of_proc = None
        self._of_hwnd = 0
        self._of_gen = 0
        page.configure(padx=0, pady=0)
        bar = tk.Frame(page, bg=SURFACE, padx=16, pady=6, highlightthickness=1, highlightbackground=LINE)
        bar.pack(fill="x")
        tk.Label(bar, text="Oferty opon (xPartner)", bg=SURFACE, fg=BLACK, font=f.label).pack(side="left")
        tk.Label(bar, text=" BETA ", bg=WARN_BG, fg=WARN, font=f.small).pack(side="left", padx=8)
        self.of_banner = tk.Label(bar, text="", bg=SURFACE, fg=MUTED, font=f.small, anchor="w")
        self.of_banner.pack(side="left", padx=(8, 0), fill="x", expand=True)
        FlatButton(bar, "Uruchom ponownie", self.oferty_restart, "ghost", f.small, 10, 3).pack(side="right")
        self.of_host = tk.Frame(page, bg=SURFACE)
        self.of_host.pack(fill="both", expand=True)
        self.of_msg = tk.Label(self.of_host, text="", bg=SURFACE, fg=MUTED, font=f.body, justify="center")
        self.of_msg.place(relx=0.5, rely=0.4, anchor="center")
        self.of_host.bind("<Configure>", lambda e: self._of_fit())

    def _of_say(self, text, kind="idle"):
        self.of_msg.config(text=text, fg={"warn": WARN, "bad": RED}.get(kind, MUTED))
        self.of_msg.lift()

    def oferty_on_show(self):
        from serwis import embed_win
        if self._of_hwnd and embed_win.alive(self._of_hwnd):
            embed_win.show(self._of_hwnd, True)
            self._of_fit()
            return
        if self._of_proc is None or self._of_proc.poll() is not None:
            self.oferty_start()

    def oferty_on_hide(self):
        from serwis import embed_win
        if getattr(self, "_of_hwnd", 0):
            embed_win.show(self._of_hwnd, False)

    def oferty_start(self):
        from oferty import okno
        from serwis import serwis_qr, serwis_window
        why = serwis_window.is_available()
        if why:
            self._of_say(why + "\n\nPobierz instalator IntegraCRM-setup.exe z najnowszego wydania na GitHubie.", "warn")
            return
        try:
            if self.session:
                serwis_qr.write_token(self.session.access)   # ten sam plik tokenu co SERWIS QR (odświeżany co 30 min)
            okno.reset_log()
            self._of_hwnd = 0
            self._of_gen += 1
            self._of_proc = okno.launch(embed=True)
            self._of_t0 = time.time()
            self._of_loaded = 0.0
            self._stat("oferty_open")
            self._of_say("Wczytywanie ofert…")
            gen = self._of_gen
            self.after(500, lambda: self._of_check(gen))
        except Exception as e:
            self._of_say(f"Nie udało się uruchomić modułu:\n{e}", "bad")

    def oferty_stop(self):
        from serwis import serwis_window
        self._of_gen = getattr(self, "_of_gen", 0) + 1
        proc = getattr(self, "_of_proc", None)
        if proc is not None:
            serwis_window.kill_tree(proc)
        self._of_proc = None
        self._of_hwnd = 0

    def oferty_restart(self):
        self.oferty_stop()
        self.oferty_start()

    def _of_fit(self):
        from serwis import embed_win
        if self._of_hwnd:
            self.of_host.update_idletasks()
            embed_win.resize(self._of_hwnd, self.of_host.winfo_width(), self.of_host.winfo_height())

    def _of_check(self, gen):
        from oferty import okno
        from serwis import embed_win
        proc = self._of_proc
        if proc is None or gen != self._of_gen:
            return
        st = okno.read_status()
        state = st.get("state", "")
        if proc.poll() is not None or state == "error":
            self._of_proc = None
            return self._of_fail(st.get("error") or f"kod zakończenia {proc.poll()}")
        if state == "loaded":
            if not self._of_loaded:
                self._of_loaded = time.time()
            hwnd = embed_win.find_window(proc.pid, okno.TITLE)
            if hwnd:
                self.of_host.update_idletasks()
                if embed_win.embed(hwnd, self.of_host.winfo_id(), self.of_host.winfo_width(), self.of_host.winfo_height()):
                    self._of_hwnd = hwnd
                    self._of_say("")
                    if self.current_tab != "oferty":
                        embed_win.show(hwnd, False)
                    self.of_banner.config(text="połączono z bazą · ceny i stany na żywo z xPartner", fg=OK)
                    okno.gui_log("okno osadzone w zakładce")
                    self.after(2000, lambda: self._of_watch(gen))
                    return
            elif time.time() - self._of_loaded > 10:
                return self._of_fail("nie znaleziono okna modułu do osadzenia", kill=True)
        if time.time() - self._of_t0 > 45:
            return self._of_fail(f"przekroczony czas, etap: {state or 'start'}", kill=True)
        self.after(400, lambda: self._of_check(gen))

    def _of_watch(self, gen):
        from serwis import embed_win
        if self._of_proc is None or gen != self._of_gen:
            return
        if self._of_proc.poll() is not None or not embed_win.alive(self._of_hwnd):
            self.oferty_stop()
            self._of_say("Moduł został zamknięty.\nKliknij „Uruchom ponownie” na pasku powyżej.", "warn")
            return
        self.after(2000, lambda: self._of_watch(gen))

    def _of_fail(self, err, kill=False):
        from oferty import okno
        okno.gui_log(f"błąd: {err}")
        if kill:
            self.oferty_stop()
        tail = okno.log_tail(6)
        self._of_say(f"Moduł ofert nie uruchomił się.\n\nPowód: {err}\n\n"
                     + (f"Dziennik (data\\oferty.log):\n{tail}\n\n" if tail else "")
                     + "Kliknij „Uruchom ponownie” na pasku powyżej.", "bad")
