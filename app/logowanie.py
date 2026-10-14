"""Okno logowania przy starcie (konto w Supabase) i wymuszenie minimalnej wersji programu."""
import threading
import tkinter as tk
from tkinter import messagebox
import cloud
import updater
from version import VERSION
from ui import ASSETS, BG, BLACK, FlatButton, Fonts, INK, MUTED, RED, SURFACE, card, set_icon
from konfig import load_config, update_source


# ---------- logowanie (zawsze online) ----------
def _version_ok(sess) -> bool:
    """Wersja programu nie starsza niż minimalna ustawiona przez administratora."""
    try:
        need = sess.min_version()
    except cloud.CloudError:
        return True
    return not need or updater._ver(VERSION) >= updater._ver(need)


def _force_update(root):
    """Za stara wersja: próba aktualizacji; inaczej komunikat i koniec."""
    try:
        m, newer = updater.check(update_source(load_config()))
        if newer:
            messagebox.showinfo("Aktualizacja", f"Wymagana nowsza wersja programu. Instaluję {m['version']}…",
                                parent=root)
            updater.apply(m)
            updater.restart()
    except Exception:
        pass
    messagebox.showerror("Aktualizacja", "Ta wersja programu jest za stara i nie może się połączyć.\n"
                         "Pobierz najnowszą paczkę IntegraCRM z GitHuba.", parent=root)


def login_flow():
    """Okno logowania. Zwraca zalogowaną sesję (z profilem) albo None (zamknięto okno)."""
    root = tk.Tk()
    root.title(f"Latex Serwis – logowanie  v{VERSION}")
    root.configure(bg=BG)
    root.resizable(False, False)
    set_icon(root)
    fonts = Fonts(root)
    result = {"s": None}

    def finish(sess):
        if not _version_ok(sess):
            _force_update(root)
            root.destroy()
            return
        result["s"] = sess
        root.destroy()

    # 1. zapamiętana sesja – bez wpisywania hasła (ale zawsze z weryfikacją na serwerze)
    email0, tok = cloud.remembered()
    if tok:
        try:
            s = cloud.Session.from_refresh(tok)
            s.load_profile(VERSION)
            cloud.remember(s)
            root.withdraw()
            root.after(0, finish, s)
            root.mainloop()
            return result["s"]
        except cloud.CloudError as e:
            if "połączenia" in str(e):
                messagebox.showerror("Brak internetu", str(e), parent=root)
            cloud.forget()

    box = card(root, padx=34, pady=26)
    box.pack(padx=30, pady=30)
    try:
        if (ASSETS / "logo.png").exists():
            root._logo = tk.PhotoImage(file=str(ASSETS / "logo.png"))
            tk.Label(box, image=root._logo, bg=SURFACE).pack(pady=(0, 10))
    except tk.TclError:
        pass
    tk.Label(box, text="Zaloguj się", bg=SURFACE, fg=BLACK, font=fonts.h1).pack(anchor="w")
    tk.Label(box, text="Konto zakłada administrator programu.", bg=SURFACE, fg=MUTED,
             font=fonts.small).pack(anchor="w", pady=(0, 12))
    v_email, v_pass, v_rem = tk.StringVar(value=email0), tk.StringVar(), tk.BooleanVar(value=True)
    for label, var, show in (("E-mail", v_email, None), ("Hasło", v_pass, "•")):
        tk.Label(box, text=label, bg=SURFACE, fg=INK, font=fonts.label).pack(anchor="w")
        e = tk.Entry(box, textvariable=var, show=show, width=34, font=fonts.body, relief="solid", bd=1)
        e.pack(anchor="w", ipady=4, pady=(2, 10))
        if (label == "E-mail") == (not email0):
            e.focus_set()
    tk.Checkbutton(box, text="Zapamiętaj mnie na tym komputerze", variable=v_rem, bg=SURFACE,
                   activebackground=SURFACE, font=fonts.small).pack(anchor="w")
    msg = tk.Label(box, text="", bg=SURFACE, fg=RED, font=fonts.small, wraplength=300, justify="left")
    msg.pack(anchor="w", pady=(8, 4))
    btn = FlatButton(box, "ZALOGUJ", lambda: go(), "primary", fonts.btn)
    btn.pack(fill="x", pady=(4, 0))

    def go():
        if not v_email.get().strip() or not v_pass.get():
            msg.config(text="Wpisz e-mail i hasło.")
            return
        btn.set_enabled(False, "Łączę…")
        msg.config(text="")
        email, pw, rem = v_email.get().strip(), v_pass.get(), v_rem.get()

        def work():
            try:
                s = cloud.Session.login(email, pw)
                s.load_profile(VERSION)
                if rem:
                    cloud.remember(s)
                else:
                    cloud.forget()
                root.after(0, finish, s)
            except cloud.CloudError as e:
                root.after(0, lambda err=str(e): (msg.config(text=err), btn.set_enabled(True, "ZALOGUJ")))
        threading.Thread(target=work, daemon=True).start()

    root.bind("<Return>", lambda e: go())
    root.mainloop()
    return result["s"]
