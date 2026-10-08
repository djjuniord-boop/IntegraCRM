"""Integra 7 ↔ CRM: kontrola eksportu zleceń po numerach rejestracyjnych (okno programu)."""
import json
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

import extract
import mailer
import paths
import plates
import updater
from version import CHANGELOG, DEFAULT_UPDATE_SOURCE, RELEASED, VERSION

NAVY, ORANGE = "#22517D", "#E8621A"
DEFAULTS = {
    "gmail_user": "",
    "gmail_app_password": "",
    "recipients": [],
    "tesseract_cmd": "",       # puste = automatycznie (folder programu / Program Files)
    "update_source": "",       # puste = DEFAULT_UPDATE_SOURCE z version.py
}

HELP_TEXT = (
    "Jak używać\n"
    "1. Wybierz raport PDF z Integra 7.\n"
    "2. W CRM zrób wycinek ekranu (Win+Shift+S), wróć tutaj i naciśnij Ctrl+V.\n"
    "3. Kliknij „Sprawdź”. Jeśli czegoś brakuje w CRM, program przygotuje mail.\n"
    "4. Kliknij „Wyślij maila” (treść możesz wcześniej poprawić).\n\n"
    "Liczy się tylko numer rejestracyjny – status i pozostałe kolumny są pomijane.\n"
    "Przy każdym starcie program sam sprawdza, czy jest nowa wersja, i aktualizuje się."
)


def load_config() -> dict:
    cfg = dict(DEFAULTS)
    if paths.CONFIG_PATH.exists():
        cfg.update(json.loads(paths.CONFIG_PATH.read_text(encoding="utf-8")))
    return cfg


def save_config(cfg: dict) -> None:
    paths.DATA_DIR.mkdir(parents=True, exist_ok=True)
    paths.CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


def update_source(cfg: dict) -> str:
    return (cfg.get("update_source") or "").strip() or DEFAULT_UPDATE_SOURCE


def changelog_text() -> str:
    out = []
    for e in CHANGELOG:
        out.append(f"Wersja {e['version']}  ({e['date']})")
        out += [f"  • {c}" for c in e["changes"]]
        out.append("")
    return "\n".join(out)


class SettingsDialog(tk.Toplevel):
    """Konfiguracja maila, OCR i aktualizacji – zapisywana do data/config.json."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Ustawienia")
        self.resizable(False, False)
        self.configure(bg="white", padx=16, pady=14)
        self.transient(parent)
        self.grab_set()
        cfg = load_config()

        self.v_user = tk.StringVar(value=cfg["gmail_user"])
        self.v_pass = tk.StringVar(value=cfg["gmail_app_password"])
        self.v_to = tk.StringVar(value=", ".join(cfg["recipients"]))
        self.v_tess = tk.StringVar(value=cfg["tesseract_cmd"])
        self.v_upd = tk.StringVar(value=cfg["update_source"])

        def row(r, label, var, show=None):
            tk.Label(self, text=label, bg="white", anchor="w").grid(row=r, column=0, sticky="w", pady=4)
            e = ttk.Entry(self, textvariable=var, width=48, show=show)
            e.grid(row=r, column=1, pady=4, padx=(8, 0))
            return e

        row(0, "Konto Gmail (nadawca)", self.v_user)
        self.pass_entry = row(1, "Hasło aplikacji Google", self.v_pass, show="•")
        row(2, "Odbiorcy (po przecinku)", self.v_to)
        row(3, "Tesseract (puste = auto)", self.v_tess)
        row(4, "Źródło aktualizacji", self.v_upd)

        self.show = tk.BooleanVar()
        ttk.Checkbutton(self, text="Pokaż hasło", variable=self.show,
                        command=lambda: self.pass_entry.config(show="" if self.show.get() else "•")
                        ).grid(row=5, column=1, sticky="w", padx=8)

        hint = ("Hasło aplikacji to 16 znaków z konta Google (to nie jest zwykłe hasło do Gmaila):\n"
                "Konto Google → Bezpieczeństwo → Weryfikacja dwuetapowa → Hasła aplikacji.\n"
                "Źródło aktualizacji: adres do version.json albo folder (np. sieciowy).")
        tk.Label(self, text=hint, bg="white", fg="#555", justify="left").grid(
            row=6, column=0, columnspan=2, sticky="w", pady=(8, 10))

        btns = tk.Frame(self, bg="white")
        btns.grid(row=7, column=0, columnspan=2, sticky="e")
        ttk.Button(btns, text="Wyślij test", command=self.test).pack(side="left", padx=4)
        ttk.Button(btns, text="Zapisz", command=self.save).pack(side="left", padx=4)
        ttk.Button(btns, text="Anuluj", command=self.destroy).pack(side="left")

    def collect(self) -> dict:
        return {
            "gmail_user": self.v_user.get().strip(),
            "gmail_app_password": self.v_pass.get().strip(),
            "recipients": [x.strip() for x in self.v_to.get().split(",") if x.strip()],
            "tesseract_cmd": self.v_tess.get().strip(),
            "update_source": self.v_upd.get().strip(),
        }

    def save(self):
        save_config(self.collect())
        self.destroy()

    def test(self):
        cfg = self.collect()
        try:
            mailer.send("Test – Integra 7 ↔ CRM",
                        "To jest wiadomość testowa z programu kontroli eksportu zleceń.", cfg)
            messagebox.showinfo("Test", "Mail testowy wysłany.", parent=self)
        except Exception as e:
            messagebox.showerror("Test", f"Nie udało się wysłać:\n{e}", parent=self)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"Integra 7 ↔ CRM – kontrola eksportu   v{VERSION}")
        self.geometry("840x800")
        self.configure(bg="white")
        self.pdf_path = tk.StringVar()
        self.crm_img = None
        self._thumb = None
        self.result = None
        self._build()
        self.bind("<Control-v>", lambda e: self.paste())
        _c = load_config()
        if not (_c["gmail_user"] and _c["gmail_app_password"]):
            self.after(300, lambda: SettingsDialog(self))
        self.after(800, lambda: self.check_updates(manual=False))

    # ---------- układ ----------
    def _build(self):
        bar = tk.Frame(self, bg=NAVY)
        bar.pack(fill="x")
        tk.Label(bar, text="Kontrola eksportu zleceń do CRM", bg=NAVY, fg="white",
                 font=("Segoe UI", 15, "bold"), pady=12).pack(side="left", padx=16)
        tk.Label(bar, text=f"v{VERSION}", bg=NAVY, fg="#b9cde0",
                 font=("Segoe UI", 10)).pack(side="left")
        tk.Button(bar, text="⚙ Ustawienia", bg=NAVY, fg="white", relief="flat",
                  activebackground="#1a4165", activeforeground="white",
                  command=lambda: SettingsDialog(self)).pack(side="right", padx=12)

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)
        main = tk.Frame(nb, bg="white", padx=16, pady=12)
        help_ = tk.Frame(nb, bg="white", padx=16, pady=12)
        nb.add(main, text="  Kontrola  ")
        nb.add(help_, text="  Pomoc  ")
        self._build_main(main)
        self._build_help(help_)

    def _build_main(self, body):
        tk.Label(body, text="1. Raport z Integra 7 (PDF)", bg="white",
                 font=("Segoe UI", 10, "bold")).pack(anchor="w")
        row = tk.Frame(body, bg="white")
        row.pack(fill="x", pady=(2, 10))
        ttk.Entry(row, textvariable=self.pdf_path).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Wybierz…", command=self.pick_pdf).pack(side="left", padx=(6, 0))

        tk.Label(body, text="2. Raport z CRM – wklej wycinek ekranu (Ctrl+V)", bg="white",
                 font=("Segoe UI", 10, "bold")).pack(anchor="w")
        row2 = tk.Frame(body, bg="white")
        row2.pack(fill="x", pady=(2, 4))
        ttk.Button(row2, text="Wklej ze schowka", command=self.paste).pack(side="left")
        ttk.Button(row2, text="Wczytaj z pliku…", command=self.pick_img).pack(side="left", padx=6)
        self.img_info = tk.Label(row2, text="nic nie wklejono", bg="white", fg="#777")
        self.img_info.pack(side="left", padx=8)
        self.preview = tk.Label(body, bg="#f4f4f4", height=7, text="(podgląd wklejonego wycinka)",
                                fg="#999", relief="solid", bd=1)
        self.preview.pack(fill="x", pady=(0, 10))

        btnrow = tk.Frame(body, bg="white")
        btnrow.pack(fill="x", pady=(0, 8))
        self.btn_check = tk.Button(btnrow, text="Sprawdź", bg=ORANGE, fg="white", relief="flat",
                                   font=("Segoe UI", 12, "bold"), pady=8, command=self.check)
        self.btn_check.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.btn_send = tk.Button(btnrow, text="Wyślij maila", bg=NAVY, fg="white", relief="flat",
                                  font=("Segoe UI", 12, "bold"), pady=8, command=self.send_mail)
        self.btn_send.pack(side="left", fill="x", expand=True)

        tk.Label(body, text="Wynik", bg="white", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.log = scrolledtext.ScrolledText(body, height=7, font=("Consolas", 10))
        self.log.pack(fill="x", pady=(2, 8))

        tk.Label(body, text="Treść maila (możesz edytować przed wysłaniem)", bg="white",
                 font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.subject = tk.StringVar()
        ttk.Entry(body, textvariable=self.subject).pack(fill="x", pady=(2, 4))
        self.mail_body = scrolledtext.ScrolledText(body, height=9, font=("Segoe UI", 10))
        self.mail_body.pack(fill="both", expand=True)

    def _build_help(self, f):
        tk.Label(f, text=f"Integra 7 ↔ CRM   wersja {VERSION}  ({RELEASED})", bg="white",
                 font=("Segoe UI", 13, "bold"), fg=NAVY).pack(anchor="w")
        self.upd_status = tk.Label(f, text="", bg="white", fg="#555", anchor="w", justify="left")
        self.upd_status.pack(fill="x", pady=(4, 6))
        row = tk.Frame(f, bg="white")
        row.pack(fill="x", pady=(0, 10))
        self.btn_update = ttk.Button(row, text="Sprawdź aktualizacje",
                                     command=lambda: self.check_updates(manual=True))
        self.btn_update.pack(side="left")
        ttk.Button(row, text="Przywróć poprzednią wersję", command=self.rollback).pack(side="left", padx=6)

        tk.Label(f, text=HELP_TEXT, bg="white", justify="left", anchor="w",
                 wraplength=760).pack(fill="x", pady=(0, 10))
        tk.Label(f, text="Lista zmian", bg="white", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        box = scrolledtext.ScrolledText(f, font=("Segoe UI", 10), wrap="word")
        box.pack(fill="both", expand=True, pady=(2, 0))
        box.insert("1.0", changelog_text())
        box.config(state="disabled")

    # ---------- aktualizacje ----------
    def set_update_status(self, text):
        self.upd_status.config(text=text)

    def check_updates(self, manual: bool):
        src = update_source(load_config())
        if not src:
            self.set_update_status("Aktualizacje wyłączone – nie ustawiono źródła (Ustawienia).")
            if manual:
                messagebox.showinfo("Aktualizacje", "Nie ustawiono źródła aktualizacji.\n"
                                    "Wpisz je w Ustawieniach.")
            return
        self.set_update_status("Sprawdzam aktualizacje…")
        threading.Thread(target=self._update_worker, args=(src, manual), daemon=True).start()

    def _update_worker(self, src, manual):
        try:
            m, newer = updater.check(src)
            self.after(0, self._update_checked, m, newer, manual, None)
        except Exception as e:
            self.after(0, self._update_checked, None, False, manual, e)

    def _update_checked(self, m, newer, manual, err):
        if err:
            self.set_update_status(f"Nie udało się sprawdzić aktualizacji: {err}")
            if manual:
                messagebox.showerror("Aktualizacje", f"Nie udało się sprawdzić aktualizacji:\n{err}")
            return
        if not newer:
            self.set_update_status(f"Masz najnowszą wersję ({VERSION}).")
            if manual:
                messagebox.showinfo("Aktualizacje", f"Masz najnowszą wersję ({VERSION}).")
            return
        notes = "\n".join("• " + n for n in m.get("notes", []))
        messagebox.showinfo("Aktualizacja",
                            f"Dostępna nowa wersja {m['version']}.\n"
                            "Program zaktualizuje się teraz i uruchomi ponownie.\n\n" + notes)
        self.set_update_status(f"Aktualizuję do wersji {m['version']}…")
        self.btn_update.config(state="disabled")
        threading.Thread(target=self._apply_worker, args=(m,), daemon=True).start()

    def _apply_worker(self, m):
        try:
            updater.apply(m)
            self.after(0, self._restart)
        except Exception as e:
            self.after(0, self._apply_failed, e)

    def _restart(self):
        self.destroy()
        updater.restart()

    def _apply_failed(self, e):
        self.btn_update.config(state="normal")
        self.set_update_status(f"Aktualizacja nie powiodła się: {e}")
        messagebox.showerror("Aktualizacja", f"Aktualizacja nie powiodła się:\n{e}\n\n"
                             f"Program działa dalej w wersji {VERSION}.")

    def rollback(self):
        if not updater.has_backup():
            messagebox.showinfo("Przywracanie", "Brak zapisanej poprzedniej wersji.")
            return
        if not messagebox.askyesno("Przywracanie",
                                   "Przywrócić poprzednią wersję programu?\n"
                                   "Program uruchomi się ponownie."):
            return
        try:
            updater.rollback(pin=True)
        except Exception as e:
            messagebox.showerror("Przywracanie", f"Nie udało się przywrócić:\n{e}")
            return
        self._restart()

    # ---------- pliki / schowek ----------
    def pick_pdf(self):
        p = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf")])
        if p:
            self.pdf_path.set(p)

    def pick_img(self):
        p = filedialog.askopenfilename(filetypes=[("Obrazy", "*.png *.jpg *.jpeg *.bmp")])
        if p:
            from PIL import Image
            self.set_image(Image.open(p))

    def paste(self):
        img = extract.image_from_clipboard()
        if img is None:
            messagebox.showwarning("Schowek", "W schowku nie ma obrazu.\n"
                                   "Zrób wycinek ekranu (Win+Shift+S) i wklej ponownie.")
            return
        self.set_image(img)

    def set_image(self, img):
        from PIL import ImageTk
        self.crm_img = img.copy()
        th = img.copy()
        th.thumbnail((760, 140))
        self._thumb = ImageTk.PhotoImage(th)
        self.preview.config(image=self._thumb, text="", height=th.height)
        self.img_info.config(text=f"wklejono obraz {img.width}×{img.height} px", fg="#2a7a2a")

    # ---------- logika ----------
    def say(self, text):
        self.log.insert("end", text + "\n")
        self.log.see("end")

    def check(self):
        if not self.pdf_path.get():
            messagebox.showwarning("Brak PDF", "Wybierz raport PDF z Integry.")
            return
        if self.crm_img is None:
            messagebox.showwarning("Brak wycinka", "Wklej wycinek ekranu z CRM (Ctrl+V).")
            return
        self.btn_check.config(state="disabled")
        self.log.delete("1.0", "end")
        threading.Thread(target=self._check_work, daemon=True).start()

    def _check_work(self):
        try:
            tess = paths.find_tesseract(load_config().get("tesseract_cmd", ""))
            self.say("Czytam PDF z Integry…")
            integra = plates.extract_plates(extract.text_from_pdf(self.pdf_path.get(), tess))
            self.say(f"  znaleziono {len(integra)}: {', '.join(integra) or '—'}")
            self.say("Czytam wycinek z CRM (OCR)…")
            texts = extract.ocr_variants(self.crm_img, tess)
            crm_main = plates.extract_crm_plates(texts[0])
            crm = list(crm_main)
            for t in texts[1:]:  # dodatkowe przebiegi OCR – poprawiają przekręcone znaki
                for p in plates.extract_crm_plates(t):
                    if p not in crm:
                        crm.append(p)
            self.say(f"  znaleziono {len(crm_main)}: {', '.join(crm_main) or '—'}")

            self.result = None
            if not integra:
                self.say("\n⚠ W PDF z Integry nie znaleziono żadnego numeru rejestracyjnego.\n"
                         "Nie mogę potwierdzić, że wszystko jest w CRM – sprawdź, czy to właściwy plik.")
                return
            if not crm:
                self.say("\n⚠ Na wycinku z CRM nie odczytano żadnego numeru.\n"
                         "Zrób wycinek tabeli z kolumną „Rejestracja” i wklej ponownie.")
                return

            missing, uncertain = plates.compare(integra, crm)
            self.result = (missing, uncertain)
            if not missing and not uncertain:
                self.say("\n✔ Jest dobrze – wszystkie zlecenia z Integry są w CRM.")
                self.subject.set("")
                self.mail_body.delete("1.0", "end")
                return
            self.say(f"\nBrakuje w CRM: {', '.join(missing) or '—'}")
            for a, b in uncertain:
                self.say(f"Do weryfikacji: {a} ↔ {b}")
            subj, body = mailer.compose(missing, uncertain)
            self.subject.set(subj)
            self.mail_body.delete("1.0", "end")
            self.mail_body.insert("1.0", body)
            self.say("\nMail przygotowany – sprawdź treść i kliknij „Wyślij maila”.")
        except Exception as e:
            self.say(f"\n✖ Błąd: {e}")
        finally:
            self.btn_check.config(state="normal")

    def send_mail(self):
        if not self.result or not (self.result[0] or self.result[1]):
            messagebox.showinfo("Wyślij maila", "Nie ma czego wysyłać – najpierw kliknij „Sprawdź”, "
                                "a mail przygotuje się tylko wtedy, gdy czegoś brakuje.")
            return
        cfg = load_config()
        if not (cfg["gmail_user"] and cfg["gmail_app_password"] and cfg["recipients"]):
            messagebox.showwarning("Ustawienia", "Uzupełnij konfigurację maila.")
            SettingsDialog(self)
            return
        if not messagebox.askyesno("Wyślij maila",
                                   f"Wysłać do: {', '.join(cfg['recipients'])}?"):
            return
        try:
            mailer.send(self.subject.get(), self.mail_body.get("1.0", "end").strip(), cfg)
            self.say(f"✔ Wysłano do: {', '.join(cfg['recipients'])}")
        except Exception as e:
            self.say(f"✖ Nie udało się wysłać: {e}")


def main():
    try:  # ostrzejszy tekst na ekranach z powiększeniem
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    App().mainloop()
