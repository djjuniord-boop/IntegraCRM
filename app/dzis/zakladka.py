"""DZIŚ: ekran startowy. Kafle tylko dla modułów konta; dane wczytywane w tle (zasada z CLAUDE.md: wątek nie
dotyka okna – wynik przez self.after). Zakładka jest pierwsza, gdy konto ma co najmniej dwa kafle."""
import datetime
import threading
import tkinter as tk

from ui import BG, BLACK, FlatButton, INK, LINE, MUTED, OK, RED, SURFACE, WARN, card, odmiana, opis_bledu
from version import VERSION

DNI = ["poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela"]
ODSWIEZ_MS = 5 * 60 * 1000


def kafle_konta(can) -> list:
    """Klucze kafli dla konta (can = funkcja uprawnień)."""
    out = []
    if can("crm"):
        out.append("kontrola")
    if can("wyniki") or can("marza"):
        out.append("wyniki")
    if can("marza"):
        out.append("marza")
    if can("oferty"):
        out.append("oferty")
    if can("serwis"):
        out.append("serwis")
    return out


def _czas(iso):
    try:
        return datetime.datetime.fromisoformat(str(iso).replace("Z", "+00:00")).astimezone()
    except (TypeError, ValueError):
        return None


def kiedy(t, teraz=None) -> str:
    """„dziś 06:40”, „wczoraj 15:20”, „3.11 15:20”."""
    if t is None:
        return "—"
    teraz = teraz or datetime.datetime.now().astimezone()
    d = (teraz.date() - t.date()).days
    dzien = "dziś" if d == 0 else "wczoraj" if d == 1 else f"{t.day}.{t.month:02d}"
    return f"{dzien} {t:%H:%M}"


def tekst_kontroli(row, teraz=None):
    """Kafel KONTROLA z ostatniego sprawdzenia (wiersz tabeli checks) → (opis, stan)."""
    if not row:
        return "Nie ma jeszcze sprawdzeń.", "brak"
    brak = len(row.get("missing") or [])
    t = kiedy(_czas(row.get("created_at")), teraz)
    if not brak:
        return f"Ostatnie sprawdzenie: {t} – wszystko było w CRM.", "ok"
    mail = "e-mail wysłany" if row.get("mail_to") else "e-mail NIE wysłany"
    return f"Ostatnie sprawdzenie: {t} – brakowało {brak} {odmiana(brak, 'numeru', 'numerów', 'numerów')}, {mail}.", \
        "ok" if row.get("mail_to") else "uwaga"


def tekst_marzy(rows, teraz=None):
    """Kafel MARŻA: ostatnia aktualizacja każdego oddziału → (opis, stan). Starsza niż 1 dzień = uwaga."""
    teraz = teraz or datetime.datetime.now().astimezone()
    ost = {}
    for r in rows or []:
        t = _czas(r.get("updated_at"))
        if t and (r.get("branch") not in ost or t > ost[r["branch"]]):
            ost[r["branch"]] = t
    if not ost:
        return "Brak aktualizacji w bazie.", "uwaga"
    nazwy = {"wroclaw": "Wrocław", "opole": "Opole"}
    linie, stan = [], "ok"
    for b, t in sorted(ost.items()):
        dni = (teraz.date() - t.date()).days
        if dni > 1 and teraz.weekday() != 6:
            stan = "uwaga"
        linie.append(f"{nazwy.get(b, b)}: {kiedy(t, teraz)}" + (f" (od {dni} dni bez aktualizacji)" if dni > 1 else ""))
    return "Ostatnia aktualizacja – " + ";  ".join(linie), stan


class DzisMixin:
    """Zakładka DZIŚ (część klasy okna App)."""

    def _build_dzis(self, page):
        f = self.fonts
        s = self.session
        imie = ((s.profile.get("name") if s else "") or "").split(" ")[0]
        dzis = datetime.date.today()
        top = tk.Frame(page, bg=BG)
        top.pack(fill="x", pady=(4, 12))
        tk.Label(top, text=f"Dzień dobry{', ' + imie if imie else ''}", bg=BG, fg=BLACK, font=f.h1).pack(side="left")
        tk.Label(top, text=f"   {DNI[dzis.weekday()]} {dzis.day}.{dzis.month:02d}.{dzis.year}"
                           + (f"   ·   {', '.join(s.branches())}" if s and not s.is_admin else ""),
                 bg=BG, fg=MUTED, font=f.body).pack(side="left", pady=(6, 0))
        FlatButton(top, f"Wersja {VERSION} – co nowego", lambda: self.show_tab("help"), "ghost", f.small, 10, 4
                   ).pack(side="right")
        FlatButton(top, "Odśwież", self.dzis_odswiez, "ghost", f.small, 10, 4).pack(side="right", padx=8)

        siatka = tk.Frame(page, bg=BG)
        siatka.pack(fill="both", expand=True)
        can = (lambda m: s.can(m)) if s else (lambda m: True)
        self.dzis_kafle = {}
        opisy = {
            "kontrola": ("Kontrola CRM", "Sprawdź dzisiejsze zlecenia", "main"),
            "wyniki": ("Wyniki marży", "Szczegóły wyników", "wyniki"),
            "marza": ("Marża – aktualizacja", "Aktualizuj marżę", "marza"),
            "oferty": ("Oferty opon", "Otwórz oferty", "oferty"),
            "serwis": ("Serwis QR", "Otwórz historię serwisową", "serwis"),
        }
        klucze = [k for k in kafle_konta(can) if opisy[k][2] in self.pages]
        for i, k in enumerate(klucze):
            tytul, przycisk, zakladka = opisy[k]
            ramka = card(siatka)
            ramka.grid(row=i // 3, column=i % 3, sticky="nsew", padx=6, pady=6)
            pasek = tk.Frame(ramka, bg=LINE, width=5)   # pasek stanu: zielony – w porządku, czerwony – do zrobienia
            pasek.pack(side="left", fill="y")
            c = tk.Frame(ramka, bg=SURFACE, padx=16, pady=12)
            c.pack(side="left", fill="both", expand=True)
            tk.Label(c, text=tytul, bg=SURFACE, fg=BLACK, font=f.h2).pack(anchor="w")
            txt = tk.Label(c, text="Wczytuję…" if k in ("kontrola", "wyniki", "marza") else
                           {"oferty": "Oferta dla klienta w kilka kliknięć: rozmiar, sezon, ilość.",
                            "serwis": "Historia serwisowa aut i naklejki QR."}[k],
                           bg=SURFACE, fg=INK, font=f.body, justify="left", anchor="w", wraplength=380)
            txt.pack(anchor="w", fill="x", pady=(6, 10))
            FlatButton(c, przycisk, lambda z=zakladka: self.show_tab(z), "primary" if i == 0 else "dark",
                       f.body, 14, 6).pack(anchor="w", side="bottom")
            self.dzis_kafle[k] = (txt, pasek)
        for col in range(min(3, max(1, len(klucze)))):
            siatka.columnconfigure(col, weight=1, uniform="k")
        self.dzis_admin = tk.Label(page, text="", bg=BG, fg=MUTED, font=f.small, anchor="w")
        if s and s.is_admin:
            self.dzis_admin.pack(fill="x", pady=(8, 0))
        self.dzis_ladowanie = False
        self.dzis_job = None
        self.after(300, self.dzis_odswiez)

    def _dzis_stan(self, klucz, tekst, stan):
        if klucz not in self.dzis_kafle:
            return
        txt, pasek = self.dzis_kafle[klucz]
        txt.config(text=tekst, fg=RED if stan == "blad" else INK)
        pasek.config(bg={"ok": OK, "uwaga": RED, "blad": WARN}.get(stan, LINE))

    def dzis_odswiez(self):
        if getattr(self, "dzis_ladowanie", False) or self.session is None or not getattr(self, "dzis_kafle", None):
            return
        self.dzis_ladowanie = True
        s, kafle = self.session, set(self.dzis_kafle)
        oddzialy = self.wyniki_oddzialy() if "wyniki" in kafle else []

        def work():
            wynik = {}
            if "kontrola" in kafle:
                try:
                    r = s.call("GET", "/rest/v1/checks?select=created_at,missing,mail_to&order=created_at.desc&limit=1")
                    wynik["kontrola"] = tekst_kontroli((r or [None])[0])
                except Exception as e:
                    wynik["kontrola"] = (opis_bledu(e), "blad")
            if kafle & {"wyniki", "marza"}:
                try:
                    rows = s.call("GET", "/rest/v1/marza_months?select=*&order=year.desc,month.desc") or []
                    if "wyniki" in kafle:
                        wynik["wyniki"] = self._dzis_wyniki(rows, oddzialy)
                    if "marza" in kafle:
                        wynik["marza"] = tekst_marzy(rows)
                except Exception as e:
                    for k in kafle & {"wyniki", "marza"}:
                        wynik[k] = (opis_bledu(e), "blad")
            admin = ""
            if s.is_admin:
                try:
                    from uzytkownicy.zakladka import pracuje_teraz
                    n = sum(1 for u in s.list_users() if pracuje_teraz(u.get("last_active")))
                    admin = f"Pracuje teraz w programie: {n} {odmiana(n, 'osoba', 'osoby', 'osób')}."
                except Exception:
                    admin = ""
            try:
                self.after(0, self._dzis_pokaz, wynik, admin)
            except RuntimeError:   # okno zamknięte
                pass
        threading.Thread(target=work, daemon=True).start()

    @staticmethod
    def _dzis_wyniki(rows, oddzialy):
        from wyniki import dane
        nazwy = dict(dane.ODDZIALY)
        linie, stan = [], "ok"
        for b in oddzialy:
            row = dane.wybierz_miesiac([r for r in rows if r.get("branch") == b])
            if not row:
                continue
            p = dane.podsumowanie(row)
            pct = f"{p['pct']:.0f}% celu" if p["pct"] is not None else "brak celu"
            plan = dane.zl(p["plan_dzis"]).replace(" ", "\u00a0") if p["biezacy"] and p["plan_dzis"] else ""
            linie.append(f"{nazwy.get(b, b)} ({p['label']}): {pct}" + (f", plan na dziś {plan}" if plan else ""))
            if p["tempo"] is not None and p["tempo"] < 100:
                stan = "uwaga"
        return ("\n".join(linie) or "Brak wyników w bazie.", stan if linie else "brak")

    def _dzis_pokaz(self, wynik, admin):
        self.dzis_ladowanie = False
        for k, (t, st) in wynik.items():
            self._dzis_stan(k, t, st)
        if admin:
            self.dzis_admin.config(text=admin)
        if self.dzis_job:
            try:
                self.after_cancel(self.dzis_job)
            except tk.TclError:
                pass
        self.dzis_job = self.after(ODSWIEZ_MS, self.dzis_odswiez)
