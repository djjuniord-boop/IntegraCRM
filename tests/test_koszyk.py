"""Testy KOSZYKA xPartner (zamawianie): XML zgodny z dokumentacją metody order, adresy, odpowiedź, uprawnienie – bez xPartner."""
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))
from oferty import koszyk as K, silnik as S, zamowienia as Z  # noqa: E402

# Przykład z dokumentacji xPartner (XML API → Zamówienia → order), z danymi zmyślonymi.
DOC = ('<?xml version="1.0" encoding="UTF-8"?><order><recipientId>8588</recipientId><deliveryPlaceId>9063</deliveryPlaceId>'
       '<document>Invoice</document><payment>Transfer</payment><comment></comment><extInvoiceDescription></extInvoiceDescription>'
       '<extOrderNumber>AY7091013</extOrderNumber><products><product><productId>93284</productId><quantity>2</quantity></product></products></order>')


def _zam(**kw):
    d = {"recipientId": 8588, "deliveryPlaceId": 9063, "numer": "AY7091013", "pozycje": [{"id": 93284, "ilosc": 2}]}
    d.update(kw)
    return d


def test_order_xml_identyczny_z_przykladem_dokumentacji():
    assert K.order_xml(_zam()) == DOC


def test_order_bez_ceny_faktura_przelew_zawsze():
    x = K.order_xml(_zam(document="Receipt", payment="Cash", pozycje=[{"id": 1, "ilosc": 4, "price": 1.0}]))
    r = ET.fromstring(x)
    assert r.findtext("document") == "Invoice" and r.findtext("payment") == "Transfer"
    assert "price" not in x and r.find("products/product/quantity").text == "4"


def test_order_nowy_adres_jednorazowy():
    x = K.order_xml(_zam(nowy_adres={"name": "Jan Nowak", "street": "ul. Pankiewicza 10/12A", "zipCode": "64-100", "city": "Leszno",
                                     "phone": "600100200", "vatin": "", "receivingPerson": "Jan"}))
    r = ET.fromstring(x)
    n = r.find("newDeliveryPlace")
    assert [c.tag for c in n] == ["recipientId", "name", "street", "zipCode", "city", "country", "vatin", "email", "phone", "receivingPerson"]
    assert n.findtext("recipientId") == "8588" and n.findtext("country") == "PL" and n.findtext("zipCode") == "64100"
    assert r.findtext("deliveryPlaceId") == "9063"   # wymagane także przy adresie jednorazowym
    assert [c.tag for c in r][-2:] == ["newDeliveryPlace", "products"]


def test_adres_limity_i_wymagane():
    for zly, txt in (({"name": "", "street": "a", "zipCode": "1", "city": "x"}, "Nazwa"),
                     ({"name": "a", "street": "x" * 36, "zipCode": "1", "city": "x"}, "Ulica")):
        try:
            K.order_xml(_zam(nowy_adres=zly))
            assert False
        except K.Blad as e:
            assert txt in str(e)


def test_pola_ascii_wzor_i_dlugosc():
    x = ET.fromstring(K.order_xml(_zam(numer="OF/2026/11/09-1141 Łódź_ż!" + "9" * 40, opis="DW 5444L – Kowalski, Żółć")))
    nr, op = x.findtext("extOrderNumber"), x.findtext("extInvoiceDescription")
    assert len(nr) <= 35 and nr.startswith("OF/2026/11/09-1141 Lodz z")
    assert op == "DW 5444L Kowalski Zolc"
    for v in (nr, op):
        assert K.WZOR_OPIS.match(v)


def test_uwagi_escape_i_limit():
    x = K.order_xml(_zam(uwagi="a<b & c"))
    assert ET.fromstring(x).findtext("comment") == "a<b & c"
    try:
        K.order_xml(_zam(uwagi="x" * 256))
        assert False
    except K.Blad:
        pass


def test_zle_ilosci_i_brak_adresu():
    for d in (_zam(pozycje=[]), _zam(pozycje=[{"id": 1, "ilosc": 0}]), _zam(pozycje=[{"id": 1, "ilosc": 500}]), _zam(deliveryPlaceId=0)):
        try:
            K.order_xml(d)
            assert False
        except K.Blad:
            pass


def test_wynik_kilka_zamowien_i_bledy():
    ok = (b"<response><success>true</success><orders><order><orderNo>1</orderNo><warehouseName>Ruda</warehouseName><orderXP>XP/1</orderXP>"
          b"<extOrderNumber>A</extOrderNumber></order><order><orderNo>2</orderNo><warehouseName>Opole</warehouseName><orderXP>XP/2</orderXP>"
          b"</order></orders><errors/></response>")
    z, uw = K.czytaj_wynik(ok)
    assert uw == []
    assert [x["nr"] for x in z] == ["XP/1", "XP/2"] and z[1]["magazyn"] == "Opole"
    zle = ("<response><success>false</success><errors><error>Wybrano nieodpowiednie miejsce dostawy.</error></errors></response>").encode()
    try:
        K.czytaj_wynik(zle)
        assert False
    except K.Blad as e:
        assert "miejsce dostawy" in str(e)


def test_adresy_z_getDeliveryData_tylko_wroclaw():
    xml = ("<response><success>true</success><recipients><recipient><recipientId>10</recipientId><name>LATEX</name><deliveryPlaces>"
           "<deliveryPlace><deliveryPlaceId>20</deliveryPlaceId><name>LATEX SERWIS WROCŁAW</name><street>Krakowska 1</street>"
           "<zipCode>50-001</zipCode><city>Wrocław</city></deliveryPlace><deliveryPlace><deliveryPlaceId>21</deliveryPlaceId>"
           "<name>LATEX SERWIS WROCLAW SERWIS_500</name><street>X 1</street><zipCode>45-001</zipCode><city>Opole</city></deliveryPlace>"
           "<deliveryPlace><deliveryPlaceId>22</deliveryPlaceId><name>LATEX OPOLE</name><street>KRAPKOWICKA 18A</street>"
           "<zipCode>45-001</zipCode><city>Opole</city></deliveryPlace></deliveryPlaces></recipient></recipients></response>")
    stary = Z.api_xml
    Z.api_xml = lambda cfg, m, **kw: Z.parsuj(xml.encode())
    try:
        a = K.adresy({}, ["Latex Wrocław"])
        assert K.adresy({}, ["Latex Opole"])[0]["deliveryPlaceId"] == 22
    finally:
        Z.api_xml = stary
    assert len(a) == 1 and a[0]["recipientId"] == 10 and a[0]["deliveryPlaceId"] == 20
    Z.api_xml = lambda cfg, m, **kw: Z.parsuj(xml.replace("Wrocław", "Opole").replace("WROCŁAW", "X").encode())
    try:
        K.adresy({}, ["Latex Wrocław"])
        assert False
    except K.Blad:
        pass
    finally:
        Z.api_xml = stary


def test_czesciowy_sukces_to_nie_blad():
    z, uw = K.czytaj_wynik(b"<response><success>false</success><orders><order><orderXP>XP/1</orderXP></order></orders>"
                           b"<errors><error>Brak w magazynie B</error></errors></response>")
    assert z[0]["nr"] == "XP/1" and "Brak w magazynie B" in uw


def test_odswiez_stan_za_maly():
    gp = lambda cfg, pid: {"nazwa": "X", "netto": 100.0, "brutto_zak": 123.0, "netto_kat": 150.0, "ilosc": 3, "magazyny": {"Opole": 3}}
    r = K.odswiez({}, [{"id": 1, "ilosc": 4}, {"id": 2, "ilosc": 2}], gp)
    assert not r[0]["ok"] and "3 szt" in r[0]["blad"] and r[1]["ok"]


def test_uprawnienie_zamawiania():
    stare = dict(S.KONTO)
    try:
        S.KONTO.update(admin=False, zamawianie=False)
        code, _ = S.handle("/api/koszyk/zamow", _zam())
        assert code == 403
        S.KONTO.update(zamawianie=True)
        code, r = S.handle("/api/koszyk/zamow", _zam(pozycje=[]))
        assert code == 400 and "pusty" in r["error"]
    finally:
        S.KONTO.clear(); S.KONTO.update(stare)


def test_zamow_wysyla_post_xml_po_sprawdzeniu_stanow():
    wyslane = {}
    stare = (K.wyslij, S.get_product, dict(S.KONTO))
    K.wyslij = lambda cfg, x: wyslane.setdefault("xml", x) and b"<response><success>true</success><orders><order><orderXP>XP/9</orderXP></order></orders></response>"
    S.get_product = lambda cfg, pid: {"netto": 10.0, "ilosc": 9, "nazwa": "X"}
    log = []
    S.KONTO.update(admin=True, dziennik=lambda *a: log.append(a))
    try:
        code, r = S.handle("/api/koszyk/zamow", _zam())
        assert code == 200 and r["zamowienia"][0]["nr"] == "XP/9" and wyslane["xml"] == DOC and log[0][1] == "XP/9"
        S.get_product = lambda cfg, pid: {"netto": 10.0, "ilosc": 1, "nazwa": "X"}
        wyslane.clear()
        code, r = S.handle("/api/koszyk/zamow", _zam())
        assert code == 409 and not wyslane
    finally:
        K.wyslij, S.get_product = stare[0], stare[1]
        S.KONTO.clear(); S.KONTO.update(stare[2])
