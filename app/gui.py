"""IntegraCRM – okno główne programu (rdzeń).

Moduły (każdy ma README.md): kontrola/ (Kontrola CRM + Historia), marza/ (MARŻA), serwis/ (SERWIS QR),
uzytkownicy/ (Użytkownicy i dziennik). Wspólne: ui.py (wygląd), konfig.py (ustawienia), cloud.py (baza),
logowanie.py, ustawienia.py, updater.py. Mapa całości: CLAUDE.md w głównym folderze repozytorium.
"""
import os
import threading
import tkinter as tk
from tkinter import messagebox, ttk
import cloud
import paths
import updater
from version import CHANGELOG, RELEASED, VERSION
from ui import ASSETS, BG, BLACK, FlatButton, Fonts, INK, LINE, MUTED, RED, SURFACE, card, set_icon, step_badge
from konfig import COMPANY, load_config, migrate_config, save_config, update_source
from ustawienia import SettingsDialog
from logowanie import login_flow
try:
    from kontrola import history
except Exception:   # pragma: no cover – stare .exe bez bibliotek historii
    history = None
try:
    import stats
except Exception:   # pragma: no cover
    stats = None
try:
    import dnd
except Exception:   # pragma: no cover
    dnd = None
from kontrola.historia_zakladka import HistoriaMixin
from kontrola.zakladka import KontrolaMixin
from marza.zakladka import MarzaMixin
from serwis.zakladka import SerwisMixin
from uzytkownicy.zakladka import UzytkownicyMixin


STATS_INFO = ("Program wysyła anonimowe statystyki użycia: losowy identyfikator instalacji, wersję, "
              "rodzaj zdarzenia (uruchomienie, sprawdzenie, wysłany mail, błąd) i same liczby "
              "(ile numerów, ile braków, czas sprawdzenia). Nie wysyła numerów rejestracyjnych, adresów e-mail, "
              "haseł, nazw plików ani treści maili. Można to wyłączyć w Ustawieniach.")

HELP_STEPS = [
    ("Raport z Integra 7", "Przeciągnij plik PDF na okno programu albo kliknij „Wybierz PDF”."),
    ("Dane z CRM", "Najlepiej: w CRM w „Listy kontrolne” pobierz raport .xlsx i przeciągnij go na okno "
                   "(albo „Raport z CRM (.xlsx)…”). Zaznacz serwisy do sprawdzenia: Latex Wrocław, "
                   "Latex Opole, Stangum Opole – wybór jest zapamiętywany. Można też wkleić wycinek "
                   "tabeli (Win+Shift+S, potem Ctrl+V)."),
    ("Sprawdź", "Program porówna numery rejestracyjne. Status i inne kolumny są pomijane."),
    ("Wyślij maila", "Jeśli czegoś brakuje, mail jest gotowy – możesz go poprawić i wysłać."),
]


# ---------- okno główne: rdzeń + zakładki modułów ----------
class App(KontrolaMixin, HistoriaMixin, MarzaMixin, SerwisMixin, UzytkownicyMixin, tk.Tk):
    """Okno programu. Zakładki są w modułach (kontrola/, marza/, serwis/, uzytkownicy/) jako klasy *Mixin;
    tutaj: start, układ okna, zakładki wg uprawnień, aktualizacje, obsługa błędów."""
    def __init__(self, session=None):
        super().__init__()
        self.session = session   # zalogowany użytkownik (rola, moduły, oddziały)
        migrate_config()
        if session and history is not None:   # historia i rejestr zgłoszeń – wspólne, w bazie
            history.SESSION = session
            try:
                from marza import runner as _mr
                _mr.SESSION = session
            except Exception:
                pass
            if stats is not None:
                stats.SESSION = session
            try:
                COMPANY.update(session.company())
            except Exception:
                pass

            def _sync():
                try:
                    n = history.migrate_local()
                    history.reported(refresh=True)
                    if n:
                        self.after(0, lambda: self.say(f"Przeniesiono do bazy {n} pozycji (stara historia "
                                                       "i zgłoszone numery)."))
                        self.after(0, self.refresh_history)
                except Exception:
                    pass
            threading.Thread(target=_sync, daemon=True).start()
        if session:   # SERWIS QR korzysta z tej samej bazy co logowanie
            try:
                _c = load_config()
                if not _c.get("serwis_sb_url"):
                    _c.update(serwis_sb_url=cloud.URL, serwis_sb_key=cloud.ANON_KEY)
                    _c.setdefault("serwis_base", "")
                    if not _c.get("serwis_base"):
                        _c["serwis_base"] = "https://djjuniord-boop.github.io/IntegraCRM/"
                    save_config(_c)
            except Exception:
                pass
        self.fonts = Fonts(self)
        self.title(f"Latex Serwis – kontrola eksportu zleceń  v{VERSION}")
        self.geometry("1000x820")
        try:
            self.state("zoomed")   # Windows: pełny ekran roboczy – więcej miejsca na wynik i mail
        except tk.TclError:
            pass
        self.minsize(860, 680)
        self.configure(bg=BG)
        set_icon(self)
        self._style()
        self.pdf_path = tk.StringVar()
        self.crm_img = None
        self.crm_rows = None     # raport .xlsx z „Listy kontrolne”
        self.crm_file = ""
        self.branch_vars = {}
        self._thumb = None
        self._logo = None
        self.result = None
        self.hist_index = None
        self._build()
        self.dnd_ok = dnd.enable(self, self.on_drop) if dnd else False
        self.bind("<Control-v>", self._on_ctrl_v)
        self.bind("<Control-V>", self._on_ctrl_v)
        shot = os.environ.get("INTEGRA_SHOT")   # tryb zrzutów ekranu (kontrola wyglądu w GitHub Actions)
        if shot:
            self.after(2500, self._screenshots, shot)
            return
        _c = load_config()
        if not self.session and not (_c["gmail_user"] and _c["gmail_app_password"]):   # po zalogowaniu maile wysyła serwer
            self.after(400, lambda: SettingsDialog(self))
        self.after(900, lambda: self.check_updates(manual=False))
        if self.session:
            self.after(30 * 60 * 1000, self._keep_session)
        self._stat("start")

    def _screenshots(self, out_dir):
        try:
            self._screenshots_inner(out_dir)
        except Exception:
            import traceback
            with open(f"{out_dir}/error.txt", "w", encoding="utf-8") as fh:
                fh.write(traceback.format_exc())
        finally:
            os._exit(0)

    def _simulate_drop(self, path):
        """Test: wysyła do okna komunikat WM_DROPFILES, jak przy upuszczeniu pliku z Eksploratora."""
        import ctypes
        import struct
        data = path.encode("utf-16-le") + b"\0\0\0\0"
        header = struct.pack("<IiiII", 20, 0, 0, 0, 1)        # DROPFILES: pFiles=20, pt, fNC, fWide=1
        k32 = ctypes.windll.kernel32
        k32.GlobalAlloc.restype = ctypes.c_void_p
        k32.GlobalLock.restype = ctypes.c_void_p
        k32.GlobalLock.argtypes = [ctypes.c_void_p]
        k32.GlobalUnlock.argtypes = [ctypes.c_void_p]
        h = k32.GlobalAlloc(0x0042, len(header) + len(data))   # GHND
        ptr = k32.GlobalLock(h)
        ctypes.memmove(ptr, header + data, len(header) + len(data))
        k32.GlobalUnlock(h)
        u32 = ctypes.windll.user32
        u32.PostMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]
        u32.PostMessageW(self.winfo_id(), 0x0233, h, 0)

    def _screenshots_inner(self, out_dir):
        from PIL import ImageGrab

        def grab(win, name):
            win.update()
            x, y = win.winfo_rootx(), win.winfo_rooty()
            ImageGrab.grab((x, y, x + win.winfo_width(), y + win.winfo_height())).save(f"{out_dir}/{name}.png")
        self.lift()
        self.attributes("-topmost", True)
        with open(f"{out_dir}/dnd.txt", "w", encoding="utf-8") as fh:
            fh.write(f"enable={self.dnd_ok}\n")
        if self.dnd_ok:
            self._simulate_drop(r"C:\Raporty\Integra zakończone 09.10.pdf")
            import time
            t_end = time.time() + 1.5
            while time.time() < t_end:
                self.update()
                time.sleep(0.05)
        grab(self, "1-kontrola")
        with open(f"{out_dir}/dnd.txt", "a", encoding="utf-8") as fh:
            fh.write(f"pdf_after_drop={self.pdf_path.get()}\n")
        self.set_chips(["DW12345", "WE7A071"], [("DX7806F", "DX78O6F")])
        self.set_banner("bad", "✖  W CRM brakuje 2 i 1 do weryfikacji z 12 zleceń. Mail jest gotowy.")
        self.subject.set("Brak zleceń w CRM – prośba o eksport")
        self.mail_body.insert("1.0", "Dzień dobry,\n\nw CRM brakuje zleceń o numerach: DW12345, WE7A071.\n")
        self.btn_send.set_enabled(True)
        grab(self, "2-wynik")
        mw = self.edit_mail_big()
        mw.attributes("-topmost", True)
        grab(mw, "6-mail-duzy")
        mw.destroy()
        self.show_tab("help")
        grab(self, "3-pomoc")
        self.show_tab("hist")
        grab(self, "5-historia")
        if "marza" in self.pages:
            self.show_tab("marza")
            grab(self, "7-marza")
        if "serwis" in self.pages:
            import time
            self.show_tab("serwis")
            t_end = time.time() + 60
            while time.time() < t_end and not self._serwis_hwnd:
                self.update()
                time.sleep(0.1)
            for _ in range(20):
                self.update()
                time.sleep(0.1)
            with open(f"{out_dir}/serwis_embed.txt", "w", encoding="utf-8") as fh:
                fh.write(f"embedded={bool(self._serwis_hwnd)}\nmsg={self.serwis_msg.cget('text')}\n")
            grab(self, "8-serwis")
            self.show_tab("hist")
            self.update()
            time.sleep(0.5)
            grab(self, "8b-serwis-ukryty")
            self.serwis_stop()
        d = SettingsDialog(self)
        d.attributes("-topmost", True)
        grab(d, "4-ustawienia")

    def _style(self):
        s = ttk.Style(self)
        try:
            s.theme_use("clam")
        except tk.TclError:
            pass
        f = self.fonts
        s.configure("TEntry", fieldbackground=SURFACE, bordercolor=LINE, lightcolor=LINE,
                    darkcolor=LINE, padding=4)
        s.map("TEntry", bordercolor=[("focus", RED)], lightcolor=[("focus", RED)])
        s.configure("TCheckbutton", background=SURFACE, foreground=INK, font=f.body)
        s.map("TCheckbutton", background=[("active", SURFACE)], indicatorcolor=[("selected", RED)])
        s.configure("Vertical.TScrollbar", background="#DDDDDD", troughcolor=BG, bordercolor=BG,
                    arrowcolor=MUTED, lightcolor="#DDDDDD", darkcolor="#DDDDDD")

    # ---------- układ ----------
    def _build(self):
        f = self.fonts
        head = tk.Frame(self, bg=SURFACE, padx=22, pady=8)
        head.pack(fill="x")
        logo_ok = False
        try:
            if (ASSETS / "logo.png").exists():
                self._logo = tk.PhotoImage(file=str(ASSETS / "logo.png"))
                tk.Label(head, image=self._logo, bg=SURFACE).pack(side="left")
                logo_ok = True
        except tk.TclError:
            pass
        if not logo_ok:
            tk.Label(head, text="LATEX", bg=SURFACE, fg=RED, font=(f.family, 20, "bold")).pack(side="left")
        titles = tk.Frame(head, bg=SURFACE)
        titles.pack(side="left", padx=(18, 0))
        tk.Label(titles, text="Kontrola eksportu zleceń", bg=SURFACE, fg=BLACK, font=f.h1).pack(anchor="w")
        tk.Label(titles, text=f"Integra 7 → CRM   ·   wersja {VERSION}", bg=SURFACE, fg=MUTED,
                 font=f.small).pack(anchor="w")
        FlatButton(head, "⚙  Ustawienia", lambda: SettingsDialog(self), "ghost", f.body, 14, 7).pack(side="right")
        if self.session:
            FlatButton(head, "Wyloguj", self.logout, "ghost", f.body, 14, 7).pack(side="right", padx=(0, 8))
            who = self.session.profile.get("name") or self.session.email
            tk.Label(head, text=f"{who}\n{'administrator' if self.session.is_admin else 'użytkownik'}",
                     bg=SURFACE, fg=MUTED, font=f.small, justify="right").pack(side="right", padx=12)
        tk.Frame(self, bg=RED, height=4).pack(fill="x")

        # zakładki jako przyciski (czytelniejsze niż systemowy Notebook)
        tabs = tk.Frame(self, bg=BLACK)
        tabs.pack(fill="x")
        self.pages, self.tab_btns = {}, {}
        holder = tk.Frame(self, bg=BG)
        holder.pack(fill="both", expand=True)
        shot = bool(os.environ.get("INTEGRA_SHOT"))
        can = (lambda m: shot or self.session.can(m)) if self.session else (lambda m: True)
        tab_list = []
        if can("crm"):
            tab_list += [("main", "KONTROLA"), ("hist", "HISTORIA")]
        if can("marza"):
            tab_list.append(("marza", "MARŻA"))
        if can("serwis"):
            tab_list.append(("serwis", "SERWIS QR  β"))
        if self.session and self.session.is_admin:
            tab_list.append(("users", "UŻYTKOWNICY"))
        tab_list.append(("help", "POMOC I WERSJE"))
        self.current_tab = tab_list[0][0]
        for key, label in tab_list:
            b = tk.Label(tabs, text=label, bg=BLACK, fg="#BBBBBB", font=f.label, padx=20, pady=9,
                         cursor="hand2")
            b.pack(side="left")
            b.bind("<Button-1>", lambda e, k=key: self.show_tab(k))
            self.tab_btns[key] = b
            self.pages[key] = tk.Frame(holder, bg=BG, padx=22, pady=10)
        if "main" in self.pages:
            self._build_main(self.pages["main"])
            self._build_history(self.pages["hist"])
        else:   # bez modułu kontroli – elementy używane przez inne funkcje okna
            self._build_main(tk.Frame(self))
            self._build_history(tk.Frame(self))
        self._build_help(self.pages["help"])
        if "users" in self.pages:
            self._build_users(self.pages["users"])
        if "marza" in self.pages:
            self._build_marza(self.pages["marza"])
        if "serwis" in self.pages:
            try:
                self._build_serwis(self.pages["serwis"])
            except Exception as e:   # beta nie może zablokować reszty programu
                tk.Label(self.pages["serwis"], text=f"Nie udało się wczytać zakładki SERWIS QR: {e}",
                         bg=BG, fg=RED, font=self.fonts.body).pack(anchor="w")
        self.show_tab(self.current_tab)

    def logout(self):
        if not messagebox.askyesno("Wyloguj", "Wylogować się? Program zostanie zamknięty."):
            return
        try:
            self.session.logout()
        except Exception:
            pass
        self._on_close() if hasattr(self, "_on_close") else self.destroy()

    def _on_close(self):
        self.serwis_stop()
        try:
            from serwis import serwis_qr
            serwis_qr.clear_token()
        except Exception:
            pass
        self.destroy()

    def _keep_session(self):
        """Co 30 min odświeża logowanie (token ważny ok. 1 godz.) i przekazuje go panelowi SERWIS QR."""
        def work():
            try:
                self.session.refresh()
                if cloud.SESSION_FILE.exists():
                    cloud.remember(self.session)
                from serwis import serwis_qr
                if serwis_qr.TOKEN_FILE.exists():
                    serwis_qr.write_token(self.session.access)
            except Exception:
                pass
        threading.Thread(target=work, daemon=True).start()
        self.after(30 * 60 * 1000, self._keep_session)

    def show_tab(self, key):
        for k, p in self.pages.items():
            p.pack_forget()
            self.tab_btns[k].config(fg="#BBBBBB", bg=BLACK)
        self.current_tab = key
        self.pages[key].pack(fill="both", expand=True)
        self.tab_btns[key].config(fg="white", bg=RED)
        if "serwis" in self.pages and hasattr(self, "serwis_host"):
            try:
                if key == "serwis":
                    self.after(50, self.serwis_on_show)
                else:
                    self.serwis_on_hide()
            except Exception:
                pass

    def _build_help(self, page):
        f = self.fonts
        top = card(page, padx=18, pady=14)
        top.pack(fill="x")
        tk.Label(top, text=f"Wersja {VERSION}", bg=SURFACE, fg=BLACK, font=f.h1).pack(anchor="w")
        tk.Label(top, text=f"wydana {RELEASED}", bg=SURFACE, fg=MUTED, font=f.small).pack(anchor="w")
        self.upd_status = tk.Label(top, text="", bg=SURFACE, fg=INK, font=f.body, anchor="w", justify="left")
        self.upd_status.pack(fill="x", pady=(8, 8))
        r = tk.Frame(top, bg=SURFACE)
        r.pack(anchor="w")
        self.btn_update = FlatButton(r, "Sprawdź aktualizacje", lambda: self.check_updates(manual=True),
                                     "primary", f.body, 14, 6)
        self.btn_update.pack(side="left")
        if self.session is None or self.session.is_admin:   # cofnięcie wersji tylko administrator
            FlatButton(r, "Przywróć poprzednią wersję", self.rollback, "ghost", f.body, 14, 6).pack(side="left", padx=8)

        tk.Label(top, text="Prywatność: " + STATS_INFO, bg=SURFACE, fg=MUTED, font=f.small,
                 wraplength=880, justify="left").pack(anchor="w", pady=(10, 0))
        how = card(page, padx=18, pady=14)
        how.pack(fill="x", pady=12)
        tk.Label(how, text="Jak używać", bg=SURFACE, fg=BLACK, font=f.h2).pack(anchor="w", pady=(0, 8))
        for i, (t, d) in enumerate(HELP_STEPS, 1):
            row = tk.Frame(how, bg=SURFACE)
            row.pack(fill="x", pady=3)
            step_badge(row, i, f).pack(side="left", anchor="n")
            tx = tk.Frame(row, bg=SURFACE)
            tx.pack(side="left", padx=10, fill="x")
            tk.Label(tx, text=t, bg=SURFACE, fg=BLACK, font=f.label).pack(anchor="w")
            tk.Label(tx, text=d, bg=SURFACE, fg=INK, font=f.body, wraplength=780, justify="left").pack(anchor="w")

        log = card(page, padx=18, pady=14)
        log.pack(fill="both", expand=True)
        tk.Label(log, text="Historia zmian", bg=SURFACE, fg=BLACK, font=f.h2).pack(anchor="w", pady=(0, 6))
        box = tk.Text(log, font=f.body, wrap="word", relief="flat", bg=SURFACE, fg=INK, padx=2)
        sb = ttk.Scrollbar(log, command=box.yview)
        box.config(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        box.pack(fill="both", expand=True)
        box.tag_config("ver", font=f.label, foreground=RED, spacing1=8)
        box.tag_config("date", foreground=MUTED, font=f.small)
        for e in CHANGELOG:
            box.insert("end", f"Wersja {e['version']}", "ver")
            box.insert("end", f"   {e['date']}\n", "date")
            for ch in e["changes"]:
                box.insert("end", f"  •  {ch}\n")
        box.config(state="disabled")

    def copy_text(self, text, info=None):
        self.clipboard_clear()
        self.clipboard_append(text)
        self.copy_info.config(text=info or f"✔ Skopiowano: {text}")
        self.after(3000, lambda: self.copy_info.config(text=""))

    def _text_window(self, title, content, editable=False, on_save=None):
        f = self.fonts
        w = tk.Toplevel(self)
        w.title(title)
        w.geometry("900x620")
        w.configure(bg=SURFACE)
        w.transient(self)
        set_icon(w)
        tk.Frame(w, bg=RED, height=4).pack(fill="x")
        bar = tk.Frame(w, bg=SURFACE, padx=14, pady=10)
        bar.pack(side="bottom", fill="x")
        box = tk.Frame(w, bg=SURFACE, padx=14, pady=10)
        box.pack(fill="both", expand=True)
        t = tk.Text(box, font=f.mono if not editable else (f.family, 11), wrap="word", bg=SURFACE, fg=INK,
                    relief="flat", highlightthickness=1, highlightbackground=LINE, padx=10, pady=8)
        sb = ttk.Scrollbar(box, command=t.yview)
        t.config(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        t.pack(fill="both", expand=True)
        t.insert("1.0", content)
        if not editable:
            t.config(state="disabled")
        FlatButton(bar, "Kopiuj całość", lambda: self.copy_text(t.get("1.0", "end").strip(), "✔ Skopiowano tekst"),
                   "ghost", f.body, 12, 5).pack(side="left")
        if editable:
            def save():
                on_save(t.get("1.0", "end").strip())
                w.destroy()
            FlatButton(bar, "Zapisz zmiany", save, "primary", f.label, 16, 5).pack(side="right")
            FlatButton(bar, "Anuluj", w.destroy, "ghost", f.body, 12, 5).pack(side="right", padx=8)
        else:
            FlatButton(bar, "Zamknij", w.destroy, "dark", f.body, 14, 5).pack(side="right")
        t.focus_set()
        return w

    # ---------- aktualizacje ----------
    def set_update_status(self, text):
        self.upd_status.config(text=text)

    def check_updates(self, manual: bool):
        src = update_source(load_config())
        if not src:
            self.set_update_status("Aktualizacje wyłączone – nie ustawiono źródła (Ustawienia).")
            if manual:
                messagebox.showinfo("Aktualizacje", "Nie ustawiono źródła aktualizacji.\nWpisz je w Ustawieniach.")
            return
        self.set_update_status("Sprawdzam aktualizacje…")
        threading.Thread(target=self._update_worker, args=(src, manual), daemon=True).start()

    def _update_worker(self, src, manual):
        try:
            m, newer = updater.check(src)
            self.after(0, self._update_checked, m, newer, manual, None)
        except Exception as e:
            if manual:
                self._report(e, "sprawdzanie aktualizacji")
            self.after(0, self._update_checked, None, False, manual, e)

    def _update_checked(self, m, newer, manual, err):
        if err:
            import urllib.error
            if isinstance(err, urllib.error.HTTPError):
                why = (f"serwer aktualizacji odpowiedział błędem {err.code} – spróbuj później; jeśli to się "
                       "powtarza, zgłoś administratorowi")
            elif isinstance(err, OSError):
                why = "brak połączenia ze źródłem aktualizacji – sprawdź internet i spróbuj później"
            elif isinstance(err, ValueError):
                why = "nieprawidłowy opis aktualizacji na serwerze – zgłoś administratorowi"
            else:
                why = str(err)
            self.set_update_status(f"Nie udało się sprawdzić aktualizacji: {why}")
            if manual:
                messagebox.showerror("Aktualizacje", f"Nie udało się sprawdzić aktualizacji:\n{why}")
            return
        if not newer:
            self.set_update_status(f"✔ Masz najnowszą wersję ({VERSION}).")
            if manual:
                messagebox.showinfo("Aktualizacje", f"Masz najnowszą wersję ({VERSION}).")
            return
        notes = "\n".join("• " + n for n in m.get("notes", []))
        messagebox.showinfo("Aktualizacja", f"Dostępna nowa wersja {m['version']}.\n"
                            "Program zaktualizuje się teraz i uruchomi ponownie.\n\n" + notes)
        self.set_update_status(f"Aktualizuję do wersji {m['version']}…")
        self.btn_update.set_enabled(False)
        threading.Thread(target=self._apply_worker, args=(m,), daemon=True).start()

    def _apply_worker(self, m):
        try:
            updater.apply(m)
            self.after(0, self._restart)
        except Exception as e:
            self._report(e, "instalacja aktualizacji")
            self.after(0, self._apply_failed, e)

    def _restart(self):
        self.destroy()
        updater.restart()

    def _apply_failed(self, e):
        self.btn_update.set_enabled(True)
        self.set_update_status(f"Aktualizacja nie powiodła się: {e}")
        messagebox.showerror("Aktualizacja", f"Aktualizacja nie powiodła się:\n{e}\n\n"
                             f"Program działa dalej w wersji {VERSION}.")

    def rollback(self):
        if not updater.has_backup():
            messagebox.showinfo("Przywracanie", "Brak zapisanej poprzedniej wersji.")
            return
        if not messagebox.askyesno("Przywracanie", "Przywrócić poprzednią wersję programu?\n"
                                   "Program uruchomi się ponownie."):
            return
        try:
            updater.rollback(pin=True)
        except Exception as e:
            self._report(e, "przywracanie wersji")
            messagebox.showerror("Przywracanie", f"Nie udało się przywrócić:\n{e}")
            return
        self._restart()

    def _report(self, exc, where):
        if stats is not None:
            try:
                stats.report_exception(exc, where, load_config())
            except Exception:
                pass

    def report_callback_exception(self, exc, val, tb):
        """Nieobsłużony błąd w oknie: zapis do data/error.log, zgłoszenie i komunikat zamiast cichej awarii."""
        import datetime
        import traceback
        try:
            paths.DATA_DIR.mkdir(parents=True, exist_ok=True)
            with open(paths.LOG_PATH, "a", encoding="utf-8") as f:
                f.write(f"\n[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}]\n"
                        + "".join(traceback.format_exception(exc, val, tb)))
        except OSError:
            pass
        self._report(val, "okno programu")
        try:
            messagebox.showerror("Błąd", f"Wystąpił nieoczekiwany błąd:\n{val}\n\nZostał zapisany i zgłoszony autorowi.")
        except Exception:
            pass

    def _stat(self, name, **values):
        if stats is not None:
            try:
                stats.event(name, load_config(), **values)
            except Exception:
                pass

    def on_drop(self, files):
        """Upuszczone pliki: PDF → krok 1, obraz → krok 2 (na zakładce MARŻA – raporty marży)."""
        if getattr(self, "current_tab", "") == "marza":
            self.marza_add(files)
            return
        used = False
        for fp in files:
            low = fp.lower()
            if low.endswith(".pdf"):
                self.set_pdf(fp)
                used = True
            elif low.endswith((".xlsx", ".csv")):
                self.set_report(fp)
                used = True
            elif low.endswith((".png", ".jpg", ".jpeg", ".bmp")):
                try:
                    from PIL import Image
                    self.set_image(Image.open(fp))
                    used = True
                except Exception as e:
                    messagebox.showerror("Obraz", f"Nie udało się otworzyć obrazu:\n{e}")
        if not used:
            messagebox.showinfo("Przeciągnij plik", "Przeciągnij raport PDF z Integry, raport .xlsx z CRM albo obraz (zrzut z CRM).")

    # ---------- logika ----------
    def say(self, text):
        """Bezpieczne z wątku roboczego – dopisuje linię do „Szczegółów”."""
        def _do():
            self.log.insert("end", text + "\n")
            self.log.see("end")
        self.after(0, _do)

    def ui(self, fn, *a):
        self.after(0, fn, *a)




def main():
    if os.environ.get("INTEGRA_SELFTEST"):   # test bez okna (GitHub Actions)
        import selftest
        os._exit(selftest.run(os.environ["INTEGRA_SELFTEST"]))
    try:  # ostrzejszy tekst na ekranach z powiększeniem
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    if os.environ.get("INTEGRA_SHOT"):   # zrzuty ekranu w GitHub Actions – bez logowania
        App(None).mainloop()
        return
    sess = login_flow()
    if sess is None:
        return
    App(sess).mainloop()

# Nazwy używane przez testy i starsze odwołania (gui.SettingsDialog, gui.UserDialog …)
from marza.okna import MarzaFilesWindow, MarzaRecipientsDialog, MarzaResultsWindow  # noqa: E402
from uzytkownicy.okna import AuditWindow, UserDialog  # noqa: E402

__all__ = ["App", "main", "login_flow", "SettingsDialog", "UserDialog", "AuditWindow",
           "MarzaRecipientsDialog", "MarzaResultsWindow", "MarzaFilesWindow"]
