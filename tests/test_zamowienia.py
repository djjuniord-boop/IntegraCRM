"""ZAMÓWIENIA xPartner – odczyt XML (zamówienia, faktury, faktura KSeF), zakres dat, uprawnienia. Bez sieci."""
import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from oferty import zamowienia as Z  # noqa: E402

# przykłady w kształcie z dokumentacji xPartner (dane zmyślone)
XML_ZAM = b"""<?xml version="1.0" encoding="UTF-8"?><response><success>true</success><orders>
<order><orderXp>XP/1/2026</orderXp><orderErp>ZS 10/26</orderErp><currency>pln</currency><totalNetPrice>1200,50</totalNetPrice>
<createdAt>2026-11-01 10:00:00</createdAt><createdBy>Jan Test</createdBy><status>3</status><warehouseName>Magazyn A</warehouseName>
<deliveryPlace><name>Serwis</name><city>Miasto</city></deliveryPlace><products>
<product><lineNumber>1</lineNumber><productId>111</productId><productName>Opona A 205/55R16</productName><unit>szt</unit>
<quantity>4</quantity><quantityRemaining>4</quantityRemaining><quantityAvailable>2</quantityAvailable><unitNetPrice>300.125</unitNetPrice></product>
</products></order>
<order><orderXp>XP/2/2026</orderXp><totalNetPrice>500</totalNetPrice><createdAt>2026-11-03 09:00:00</createdAt><status>5</status><products/></order>
</orders></response>"""
XML_FAKTURY = b"""<response><success>true</success><invoices>
<invoice><documentNumber>FV0000001/26</documentNumber><documentDate>2026-10-01</documentDate><paymentMethod>przelew</paymentMethod><warehouse>A</warehouse></invoice>
<invoice><documentNumber>FV0000002/26</documentNumber><documentDate>2026-10-05</documentDate><paymentMethod>przelew</paymentMethod></invoice>
</invoices></response>"""
XML_FAKTURA = """<response><success>true</success><invoice><KsefNumber>KSEF-1</KsefNumber>
<Faktura xmlns="http://crd.gov.pl/wzor/2025/06/25/13775/"><Fa><KodWaluty>PLN</KodWaluty><P_1>2026-10-05</P_1><P_2>FV0000002/26</P_2>
<P_13_1>1000.00</P_13_1><P_14_1>230.00</P_14_1><P_15>1230.00</P_15>
<FaWiersz><NrWierszaFa>1</NrWierszaFa><P_7>Opona A</P_7><Indeks>111</Indeks><P_8A>szt</P_8A><P_8B>4</P_8B><P_9A>250</P_9A><P_11>1000</P_11><P_12>23</P_12></FaWiersz>
<Platnosc><TerminPlatnosci><Termin>2026-11-04</Termin></TerminPlatnosci><FormaPlatnosci>6</FormaPlatnosci></Platnosc>
<WarunkiTransakcji><Zamowienia><NrZamowienia>XP/1/2026</NrZamowienia></Zamowienia></WarunkiTransakcji></Fa></Faktura></invoice></response>""".encode()
XML_BLAD = b"<response><success>false</success><errors><error>Niepoprawny login</error></errors></response>"


def test_zamowienia_odczyt():
    z = Z.czytaj_zamowienia(Z.parsuj(XML_ZAM))
    assert [x["nr"] for x in z] == ["XP/2/2026", "XP/1/2026"]          # najnowsze pierwsze
    a = z[1]
    assert a["netto"] == 1200.5 and a["waluta"] == "PLN" and a["status_txt"] == "Oczekujące" and a["kto"] == "Jan Test"
    assert a["szt"] == 4 and a["do_wydania"] == 4 and a["pozycje"][0]["dostepne"] == 2 and a["pozycje"][0]["cena"] == 300.13
    assert a["dostawa"] == {"name": "Serwis", "city": "Miasto"}
    assert z[0]["status_txt"] == "Błąd" and z[0]["pozycje"] == []


def test_faktury_i_faktura_ksef():
    f = Z.czytaj_faktury(Z.parsuj(XML_FAKTURY))
    assert [x["nr"] for x in f] == ["FV0000002/26", "FV0000001/26"]
    d = Z.czytaj_fakture(Z.parsuj(XML_FAKTURA))
    assert (d["nr"], d["netto"], d["vat"], d["brutto"], d["ksef"]) == ("FV0000002/26", 1000.0, 230.0, 1230.0, "KSEF-1")
    assert d["termin"] == "2026-11-04" and d["forma"] == "przelew" and d["zamowienie"] == "XP/1/2026"
    assert d["pozycje"][0]["ilosc"] == 4 and d["pozycje"][0]["vat"] == "23"


def test_blad_xpartner():
    for dane in (XML_BLAD, b"<html>login"):
        try:
            Z.parsuj(dane)
            raise AssertionError("powinien być błąd")
        except Z.Blad:
            pass


def test_okres_faktur():
    dzis = datetime.date(2026, 11, 6)
    assert Z.okres("", "", dzis) == ("2026-10-07", "2026-11-06")
    assert Z.okres("2025-01-01", "2026-03-01", dzis) == ("2026-02-01", "2026-03-01")   # nie wcześniej niż 2026-02-01
    for od, do in (("2026-11-05", "2026-11-01"), ("zle", "")):
        try:
            Z.okres(od, do, dzis)
            raise AssertionError
        except Z.Blad:
            pass


def test_uprawnienia_i_bez_loginu():
    assert Z.handle("/api/faktury", {}, {}, admin=False)[0] == 403
    assert Z.handle("/api/faktura", {"nr": "x"}, {}, admin=True)[0] == 400
    k, j = Z.handle("/api/zamowienia", {}, {}, admin=False)   # brak loginu xPartner -> czytelny komunikat, bez sieci
    assert k == 502 and "loginu API" in j["error"]


def test_zamkniete_z_faktur():
    """Historia: faktury -> numery zamówień -> getOrder; duplikaty łączone, błędy liczone, zrealizowane zapamiętane."""
    zam_xml = lambda nr, st: ("<response><success>true</success><order><orderXp>%s</orderXp><orderErp>000000001/26</orderErp>"
                              "<createdAt>2026-10-0%s</createdAt><status>%d</status><products/></order></response>" % (nr, nr[-1], st)).encode()
    fa = lambda nr, zam: ("<response><success>true</success><invoice><Faktura><Fa><P_2>%s</P_2>%s</Fa></Faktura></invoice></response>"
                          % (nr, "".join("<WarunkiTransakcji><Zamowienia><NrZamowienia>%s</NrZamowienia></Zamowienia></WarunkiTransakcji>" % z for z in zam))).encode()
    odp = {("getInvoices", ""): XML_FAKTURY, ("getInvoice", "FV0000001/26"): fa("FV0000001/26", ["11111111111"]),
           ("getInvoice", "FV0000002/26"): fa("FV0000002/26", ["11111111111", "22222222222", "zly"]),
           ("getOrder", "11111111111"): zam_xml("11111111111", 6), ("getOrder", "22222222222"): XML_BLAD}
    wywolania = []

    def api(cfg, m, **p):
        k = (m, p.get("invoiceNumber") or p.get("orderXp") or "")
        wywolania.append(k)
        return Z.parsuj(odp[k])
    stare = Z.api_xml
    Z.api_xml = api
    Z._PAMIEC.clear()
    try:
        w = Z.zamkniete({"login": "t"}, "2026-10-01", "2026-10-31")
        # 2026-11-18: zamówienie, którego xPartner nie oddał, zostaje na liście z danymi z faktury (nic nie znika)
        nry = {z["nr"]: z for z in w["zamowienia"]}
        assert set(nry) == {"11111111111", "22222222222"} and w["bledy"] == 0 and w["bez_szczegolow"] == 1 and w["faktur"] == 2
        assert nry["11111111111"]["faktury"] == ["FV0000001/26", "FV0000002/26"]
        assert nry["22222222222"]["z_faktury"] is True and nry["22222222222"]["faktury"] == ["FV0000002/26"]
        assert Z.tylko_oddzialy([nry["22222222222"]], ["Latex Wrocław"]) == [nry["22222222222"]]   # z faktury konta pracownika
        n = len(wywolania)
        Z.zamkniete({"login": "t"}, "2026-10-01", "2026-10-31")
        assert ("getOrder", "11111111111") not in wywolania[n:]          # zrealizowane – z pamięci
    finally:
        Z.api_xml = stare


def test_zamkniete_pozycje_z_faktury():
    """Zamówienie zamknięte przychodzi z getOrder bez pozycji – pozycje bierzemy z jego faktury."""
    fa = XML_FAKTURA.replace(b"XP/1/2026", b"33333333333")
    odp = {"getInvoices": b"<response><success>true</success><invoices><invoice><documentNumber>FV0000002/26</documentNumber>"
                          b"<documentDate>2026-10-05</documentDate></invoice></invoices></response>",
           "getInvoice": fa,
           "getOrder": b"<response><success>true</success><order><orderXp>33333333333</orderXp><createdAt>2026-10-04</createdAt>"
                       b"<status>6</status><products/></order></response>"}
    stare = Z.api_xml
    Z.api_xml = lambda cfg, m, **p: Z.parsuj(odp[m])
    Z._PAMIEC.clear()
    try:
        z = Z.zamkniete({"login": "t"}, "2026-10-01", "2026-10-31")["zamowienia"][0]
        assert z["poz_z_faktury"] == "tak" and z["szt"] == 4 and z["pozycje"][0]["nazwa"] == "Opona A" and z["pozycje"][0]["id"] == 111
    finally:
        Z.api_xml = stare


def test_pracownik_widzi_swoj_oddzial():
    lista = [{"kto": "Detal Wrocław"}, {"kto": "Detal Opole"}, {"kto": ""}, {"kto": "Jan Kowalski"}]
    assert Z.tylko_oddzialy(lista, ["Latex Wrocław"]) == [{"kto": "Detal Wrocław"}]
    assert Z.tylko_oddzialy(lista, ["Latex Opole"]) == [{"kto": "Detal Opole"}]
    assert Z.tylko_oddzialy(lista, ["Stangum Opole"]) == [] and Z.tylko_oddzialy(lista, []) == []
    stare = Z._handle
    Z._handle = lambda *a: (200, {"zamowienia": lista, "czas": "x"})
    try:
        assert len(Z.handle("/api/zamowienia", {}, {}, admin=True, oddzialy=[])[1]["zamowienia"]) == 4
        assert [z["kto"] for z in Z.handle("/api/zamowienia", {}, {}, admin=False, oddzialy=["Latex Opole"])[1]["zamowienia"]] == ["Detal Opole"]
    finally:
        Z._handle = stare


def test_nietypowa_faktura_nie_psuje_historii():
    """Faktura bez sekcji Fa: liczona jako „nie pobrano”, reszta historii działa (wcześniej TypeError -> 500)."""
    import xml.etree.ElementTree as ET
    assert Z._pozycje_faktury(ET.fromstring("<r><invoice><Faktura><X/></Faktura></invoice></r>")) == []
    odp = {"getInvoices": XML_FAKTURY,
           "getInvoice": b"<response><success>true</success><invoice><Faktura><X/></Faktura></invoice></response>"}
    stare = Z.api_xml
    Z.api_xml = lambda cfg, m, **p: Z.parsuj(odp[m])
    Z._PAMIEC.clear()
    try:
        w = Z.zamkniete({"login": "t"}, "2026-10-01", "2026-10-31")
        # 2026-11-18: faktury bez numeru zamówienia też na liście (bez pozycji, gdy faktura nietypowa)
        assert [z["faktury"] for z in w["zamowienia"]] == [["FV0000002/26"], ["FV0000001/26"]] and w["faktur"] == 2
        assert all(z["bez_zamowienia"] and z["pozycje"] == [] for z in w["zamowienia"])
        k, j = Z.handle("/api/zamkniete", {"od": "2026-10-01", "do": "2026-10-31"}, {"login": "t"}, admin=False, oddzialy=["Latex Opole"])
        assert k == 200 and j["oddzialy"] == ["Latex Opole"] and j["ukryte"] == 0 and len(j["zamowienia"]) == 2
    finally:
        Z.api_xml = stare


def test_kto_zamowil_z_dziennika():
    """2026-11-18: przy zamówieniu imię i nazwisko osoby z Panelu (funkcja w bazie zamowienia_kto); brak funkcji = jak dotąd."""
    from oferty import zamowienia as Z
    stare = (Z.KTO, Z.JA)
    try:
        Z.KTO = lambda nry: [{"nr": "25354046318", "email": "RKolano@x.pl", "kto": "Rafał Kolano"}] if "25354046318" in nry else []
        Z.JA = lambda: "rkolano@x.pl"
        zam = [{"nr": "25354046318", "nr_zew": ""}, {"nr": "1", "nr_zew": ""}]
        assert Z.dopisz_kto(zam) is True
        assert (zam[0]["zamowil"], zam[0]["zamowil_email"], zam[1]["zamowil"]) == ("Rafał Kolano", "rkolano@x.pl", "")
        def zle(nry):
            raise RuntimeError("404 – brak funkcji")
        Z.KTO = zle
        zam = [{"nr": "25354046318", "nr_zew": ""}]
        assert Z.dopisz_kto(zam) is False and zam[0]["zamowil"] == ""
    finally:
        Z.KTO, Z.JA = stare


def test_pamiec_zamowien_na_dysku():
    """Faktury i zamówienia zrealizowane zapisane w data/ – po ponownym uruchomieniu nie pytamy o nie xPartner."""
    import tempfile, os
    d = tempfile.mkdtemp()
    stare = (Z.PLIK_PAMIECI, Z.api_xml)
    try:
        Z.PLIK_PAMIECI = os.path.join(d, "zamowienia_pamiec.json")
        Z._PAMIEC.clear(); Z._PAMIEC[("t", "F", "FV0000001/26")] = (["11111111111"], [{"id": 1}])
        Z._PAMIEC[("t", "Z", "11111111111")] = {"nr": "11111111111", "status": 6}
        Z._pamiec_zapisz()
        Z._PAMIEC.clear(); Z._wczytana[0] = False
        Z._pamiec_wczytaj()
        assert Z._PAMIEC[("t", "F", "FV0000001/26")] == (["11111111111"], [{"id": 1}])
        assert Z._PAMIEC[("t", "Z", "11111111111")]["status"] == 6
        assert not os.path.exists(Z.PLIK_PAMIECI + ".tmp")
    finally:
        Z.PLIK_PAMIECI, Z.api_xml = stare
        Z._PAMIEC.clear(); Z._wczytana[0] = False


def test_faktura_bez_numeru_zamowienia_na_liscie():
    """2026-11-18: faktura bez numeru zamówienia (zakup telefoniczny / w hurtowni) też jest w „Zrealizowanych”."""
    fa = XML_FAKTURA if isinstance(XML_FAKTURA, bytes) else XML_FAKTURA.encode()
    odp = {"getInvoices": XML_FAKTURY, "getInvoice": fa}
    stare = Z.api_xml
    Z.api_xml = lambda cfg, m, **p: Z.parsuj(odp[m])
    Z._PAMIEC.clear()
    try:
        w = Z.zamkniete({"login": "t"}, "2026-10-01", "2026-10-31")
        fk = sorted(z["faktury"][0] for z in w["zamowienia"] if z.get("bez_zamowienia"))
        assert w["bez_zamowienia"] == 2 and fk == ["FV0000001/26", "FV0000002/26"], w
        z1 = next(z for z in w["zamowienia"] if z["faktury"] == ["FV0000001/26"])
        assert z1["magazyn"] == "A" and z1["szt"] == 4 and Z.tylko_oddzialy([z1], ["Latex Wrocław"]) == [z1]
    finally:
        Z.api_xml = stare
        Z._PAMIEC.clear()
