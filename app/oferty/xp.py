"""Połączenie z API xPartner – przez pośrednika na serwerze (funkcja Supabase „xpartner”).

Hasło B2B nie trafia do komputera: okno.py ustawia POSREDNIK (zapytanie z tokenem programu), a funkcja na
serwerze dokłada login i hasło z sejfu i sprawdza uprawnienia (katalog / zamówienia / zamawianie).
Bez POSREDNIKA (testy, stare konfiguracje) – bezpośrednio z loginem i hasłem z cfg.
"""
import urllib.parse
import urllib.request

API_URL = "https://xpartner.net.pl/index.php"
POSREDNIK = None   # funkcja(m, params: dict, body: str|None, timeout: int) -> bytes; błąd -> Blad z polskim opisem


class Blad(Exception):
    """Błąd połączenia lub uprawnień – treść do pokazania użytkownikowi (bez loginu i hasła)."""


class BrakOdpowiedzi(Blad):
    """Zapytanie mogło dotrzeć do xPartner, ale nie ma odpowiedzi (ważne przy zamówieniu)."""


def zapytanie(cfg, m, params=None, body=None, timeout=30):
    """Surowa odpowiedź xPartner (XML) dla metody m."""
    params = {k: v for k, v in (params or {}).items() if v not in (None, "")}
    if POSREDNIK is not None:
        return POSREDNIK(m, params, body, timeout)
    if not cfg.get("login") or not cfg.get("password"):
        raise Blad("Twoje konto nie ma jeszcze loginu API xPartner – poproś administratora "
                   "(UŻYTKOWNICY → konto → xPartner).")
    q = {"a": "b2b_xmlApi", "login": cfg["login"], "pass": cfg["password"], "m": m}
    q.update(params)
    url = API_URL + "?" + urllib.parse.urlencode(q)
    if body is not None:
        req = urllib.request.Request(url, data=body.encode("utf-8"), method="POST",
                                     headers={"Content-Type": "application/xml", "User-Agent": "PanelLatexSerwis-Oferty"})
    else:
        req = urllib.request.Request(url, headers={"User-Agent": "PanelLatexSerwis-Oferty"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except Exception as e:   # bez treści błędu (adres z loginem i hasłem)
        raise BrakOdpowiedzi("Brak połączenia z xPartner: %s" % e.__class__.__name__)
