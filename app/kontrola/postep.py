"""Postęp sprawdzania (koło w zakładce KONTROLA) – z linii „Szczegółów” wyliczamy ułamek 0..1. Bez okna."""

# kolejne kroki sprawdzania: początek linii → postęp po tym kroku (odczyt PDF/OCR trwa najdłużej)
KROKI = (
    ("PDF z Integry", 0.05),        # start odczytu PDF (przy skanie – OCR, koło się kręci)
    ("zakres raportu", 0.45),
    ("Raport z CRM", 0.50),
    ("Porównuję", 0.65),
    ("⚠", 0.70),
    ("Historia", 0.80),
    ("Statystyki", 0.88),
    ("Przygotowuję e-mail", 0.95),
    ("Gotowe", 1.0),
)


def postep(line, cur=0.0):
    """Nowy postęp po linii `line` (nigdy mniejszy niż `cur`). Linia z liczbą numerów („  12: …”)
    kończy odczyt PDF (0.45), a druga – odczyt raportu CRM (0.60)."""
    s = (line or "").strip()
    nowy = cur
    for pocz, fr in KROKI:
        if s.startswith(pocz):
            nowy = fr
            break
    else:
        head = s.split(":", 1)[0]
        if head.isdigit() and ":" in s:
            nowy = 0.45 if cur < 0.45 else 0.60 if cur < 0.60 else cur
    return max(cur, min(1.0, nowy))


def rodzaj_wyniku(res=None, error=False):
    """'ok' (jest dobrze) | 'warn' (ostrzeżenie, do weryfikacji) | 'bad' (braki w CRM albo błąd) – znak na kole po sprawdzeniu."""
    if error or res is None:
        return "bad"
    if not res.get("integra") or not res.get("crm") or res.get("no_overlap"):
        return "warn"
    if res.get("missing"):
        return "bad"    # są braki – czerwony ✖, tak jak baner z wynikiem
    if res.get("uncertain") or res.get("warnings"):
        return "warn"
    return "ok"
