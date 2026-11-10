"""Zakładka DZIŚ: kafle wg uprawnień i teksty z danych (bez okna)."""
import datetime

from _wspolne import temp_data  # noqa: F401 – ustawia ścieżkę do app/

PL = datetime.timezone(datetime.timedelta(hours=1))
TERAZ = datetime.datetime(2026, 11, 10, 9, 0, tzinfo=PL)


def test_kafle_wg_uprawnien():
    from dzis.zakladka import kafle_konta
    assert kafle_konta(lambda m: m in ("crm", "historia")) == ["kontrola"]          # 1 kafel – bez zakładki DZIŚ
    assert kafle_konta(lambda m: m == "wyniki") == ["wyniki"]
    assert kafle_konta(lambda m: m in ("marza", "serwis")) == ["wyniki", "marza", "serwis"]
    assert kafle_konta(lambda m: True) == ["kontrola", "wyniki", "marza", "oferty", "serwis"]


def test_teksty_kontroli_i_marzy():
    from dzis.zakladka import kiedy, tekst_kontroli, tekst_marzy
    assert kiedy(TERAZ.replace(hour=6, minute=40), TERAZ) == "dziś 06:40"
    assert kiedy(TERAZ - datetime.timedelta(days=1), TERAZ) == "wczoraj 09:00"
    assert tekst_kontroli(None) == ("Nie ma jeszcze sprawdzeń.", "brak")
    t, st = tekst_kontroli({"created_at": "2026-11-10T07:12:00+00:00", "missing": ["DW1", "DW2"], "mail_to": ""}, TERAZ)
    assert "brakowało 2 numerów" in t and "NIE wysłany" in t and st == "uwaga"
    t, st = tekst_kontroli({"created_at": "2026-11-10T07:12:00+00:00", "missing": [], "mail_to": ""}, TERAZ)
    assert "wszystko było w CRM" in t and st == "ok"
    t, st = tekst_marzy([{"branch": "wroclaw", "updated_at": "2026-11-10T05:40:00+00:00"},
                         {"branch": "opole", "updated_at": "2026-11-06T05:40:00+00:00"}], TERAZ)
    assert "Wrocław: dziś" in t and "od 4 dni bez aktualizacji" in t and st == "uwaga"
    assert tekst_marzy([], TERAZ)[1] == "uwaga"
