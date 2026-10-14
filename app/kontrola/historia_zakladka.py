"""Zakładka HISTORIA: wspólna historia sprawdzeń z bazy."""
import os
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from ui import BG, BLACK, FlatButton, MUTED, RED, SURFACE, card
try:
    from kontrola import history
except Exception:   # pragma: no cover – stare .exe bez bibliotek historii
    history = None


class HistoriaMixin:
    """Zakładka HISTORIA: wspólna historia sprawdzeń z bazy.
    Część klasy okna programu (App) – metody korzystają z jej pól (self.*)."""

    def _build_history(self, page):
        f = self.fonts
        top = tk.Frame(page, bg=BG)
        top.pack(fill="x", pady=(0, 10))
        tk.Label(top, text="Historia sprawdzeń", bg=BG, fg=BLACK, font=f.h1).pack(side="left")
        FlatButton(top, "Otwórz w Excelu", self.open_history_file, "ghost", f.body, 14, 6).pack(side="right")
        FlatButton(top, "Odśwież", self.refresh_history, "ghost", f.body, 14, 6).pack(side="right", padx=8)
        box = card(page, padx=2, pady=2)
        box.pack(fill="both", expand=True)
        cols = ("data", "kto", "plik", "integra", "crm", "brakuje", "mail")
        s = ttk.Style(self)
        s.configure("H.Treeview", font=f.body, rowheight=26, background=SURFACE, fieldbackground=SURFACE)
        s.configure("H.Treeview.Heading", font=f.label, background=BG)
        s.map("H.Treeview", background=[("selected", RED)], foreground=[("selected", "white")])
        self.hist_tree = ttk.Treeview(box, columns=cols, show="headings", style="H.Treeview")
        for c, t, w in (("data", "Data", 130), ("kto", "Kto / oddział", 280), ("plik", "Plik PDF", 170),
                        ("integra", "Integra", 70),
                        ("crm", "CRM", 60), ("brakuje", "Brakuje w CRM", 260), ("mail", "Mail wysłany do", 200)):
            self.hist_tree.heading(c, text=t, anchor="w")
            self.hist_tree.column(c, width=w, anchor="w")
        sb = ttk.Scrollbar(box, command=self.hist_tree.yview)
        self.hist_tree.config(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.hist_tree.pack(fill="both", expand=True)
        tk.Label(page, text="Numery zgłoszone już wcześniej są oznaczane przy kolejnych sprawdzeniach "
                 "(„zgłoszony …”), żeby nie wysyłać ich ponownie bez potrzeby.",
                 bg=BG, fg=MUTED, font=f.small, wraplength=900, justify="left").pack(anchor="w", pady=(8, 0))
        # wątek dopiero po starcie pętli okna – after() z wątku przed mainloop gubi wynik (pusta historia)
        self.after(0, self.refresh_history)

    def refresh_history(self):
        if history is None:
            return

        def work():   # historia może być w bazie – pobieranie w tle
            try:
                rows = history.read_all()
            except Exception as e:
                rows = [{"data": "", "plik_pdf": f"Nie udało się wczytać historii: {e}"}]
            try:
                self.after(0, self._show_history, rows)
            except RuntimeError:   # okno zamknięte albo pętla okna jeszcze nie działa
                pass
        threading.Thread(target=work, daemon=True).start()

    def _show_history(self, rows):
        t = self.hist_tree
        t.delete(*t.get_children())
        for r in reversed(rows):
            who = " · ".join(x for x in (r.get("kto", ""), r.get("oddzialy", "")) if x)
            t.insert("", "end", values=(r.get("data", ""), who or "—", r.get("plik_pdf", ""), r.get("integra", ""),
                                        r.get("crm", ""), r.get("brakuje", "") or "—",
                                        r.get("mail_wyslany_do", "") or "—"))

    def open_history_file(self):
        if history is None:
            return
        import tempfile
        out = os.path.join(tempfile.gettempdir(), "IntegraCRM-historia.csv")

        def work():
            try:
                history.export_csv(out)
                os.startfile(out)   # Windows: otwiera w Excelu
            except Exception as e:
                self.after(0, lambda err=str(e): messagebox.showinfo("Historia", f"Nie udało się otworzyć historii:\n{err}"))
        threading.Thread(target=work, daemon=True).start()
