"""Test ekranu aplikacji w Chromium jak na telefonie (dane testowe, bez sieci).
Uruchom: python3 mobile/test/ekran.py <katalog_na_zrzuty>"""
import json, sys, os
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app")); sys.path.insert(0, str(ROOT / "tests"))
import test_oferty as T
T._setup()
from playwright.sync_api import sync_playwright
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "zrzuty"); OUT.mkdir(parents=True, exist_ok=True)
DB = json.dumps(T.DB, default=str)
SB = "https://nlrwulrtaocuemfmlfav.supabase.co"
saved = []
PROF = {"p": {"email": "test@firma.pl", "name": "Jan Testowy", "role": "admin", "modules": ["oferty"], "branches": []}}
import datetime as _dt
_t = _dt.date.today(); _p = (_t.replace(day=1) - _dt.timedelta(days=1))
MONTHS = [{"branch": b, "year": _t.year, "month": _t.month, "label": "Bieżący", "target": 300000, "done": d, "holidays": [], "updated_at": _t.isoformat() + "T08:00:00+00:00"}
          for b, d in (("wroclaw", 123456), ("opole", 98000))] + \
         [{"branch": "wroclaw", "year": _p.year, "month": _p.month, "label": "Poprzedni", "target": 280000, "done": 291000, "holidays": []}]
RUNS = [{"branch": "wroclaw", "done": 40000 * i, "run_at": _t.replace(day=i).isoformat() + "T10:00:00+00:00"} for i in range(1, min(_t.day, 4))]
# DEPOZYT – zmyślony spis (bez prawdziwych numerów): 1200 pozycji = 2 strony po 1000, dwa sezony
import random as _r
_r.seed(7)
DEP = [{"id": i, "branch": "Latex Wrocław", "sezon": "ZIMA 2026/27" if i % 6 else "LATO 2026", "nr": "XX%04d%s" % (i, "ABCDE"[i % 5]),
        "lok": "%s%d.%d" % ("KM"[i % 2], i % 40 + 1, i % 4 + 1), "marka": ["Testowa", "Próbna", "Ćwiczebna Źdźbło"][i % 3], "marka2": "kombi" if i % 7 == 0 else "",
        "ilosc": "" if i % 3 else "2", "rodzaj": "LATO?" if i % 11 == 0 else "", "uwagi": "chyba XY%04dZ" % i if i % 13 == 0 else "",
        "komentarz": "felgi alu, żółta naklejka" if i % 17 == 0 else "", "przywiezione": i % 4 == 0,
        "przywiezione_at": (_dt.datetime.now(_dt.timezone.utc).isoformat() if i % 8 == 0 else None) if i % 4 == 0 else None,
        "przywiezione_kto": "Magazynier Testowy" if i % 8 == 0 else None, "zmieniono": "2026-11-25T08:00:00+00:00"} for i in range(1, 1201)]
DEP_ZM = []   # zmiany „z innego telefonu” – zwracane przy odświeżaniu
def dep_route(r, u, m):
    import urllib.parse as up
    q = dict(up.parse_qsl(up.urlparse(u).query))
    if "depozyt_ustawienia" in u: return r.fulfill(json=[{"branch": "Latex Wrocław", "sezon_domyslny": "ZIMA 2026/27", "ukryte_sezony": [], "trasa": []}])
    if "rpc/depozyt_zmien" in u:
        b = json.loads(r.request.post_data); p = next(x for x in DEP if x["id"] == b["p_id"])
        if b["p_pole"] == "przywiezione" and b["p_wartosc"] == "0" and PROF["p"]["role"] != "admin":
            return r.fulfill(status=400, json={"message": "Cofnąć „przywiezione” może tylko administrator"})
        if b["p_pole"] == "przywiezione":
            p.update(przywiezione=b["p_wartosc"] == "1", przywiezione_at=_dt.datetime.now(_dt.timezone.utc).isoformat() if b["p_wartosc"] == "1" else None, przywiezione_kto=PROF["p"]["name"])
        else:
            p[b["p_pole"]] = b["p_wartosc"]
        p["zmieniono"] = _dt.datetime.now(_dt.timezone.utc).isoformat(); return r.fulfill(json=p)
    if "zmieniono" in q:
        return r.fulfill(json=[z for z in DEP_ZM if z["zmieniono"] > q["zmieniono"].replace("gt.", "")])
    off, lim = int(q.get("offset", 0)), int(q.get("limit", 1000))
    return r.fulfill(json=DEP[off:off + lim])
def route(r):
    u, m = r.request.url, r.request.method
    if "/auth/v1/token" in u: return r.fulfill(json={"access_token": "a", "refresh_token": "r", "expires_in": 3600, "user": {"email": "test@firma.pl"}})
    if "/rest/v1/depozyt" in u or "rpc/depozyt" in u: return dep_route(r, u, m)
    if "app_config" in u and "oferty_ceny" in u: return r.fulfill(json=[{"value": {"Latex Wrocław": {"tpms_cena": 25}}}])
    if "/rpc/me" in u: return r.fulfill(json=[PROF["p"]])
    if "marza_months" in u: return r.fulfill(json=MONTHS)
    if "marza_results" in u: return r.fulfill(json=RUNS)
    if "app_config" in u and "oddzialy" in u: return r.fulfill(json=[{"value": {"Latex Wrocław": {"nazwa": "LATEX SERWIS WROCŁAW", "adres": "ul. Krakowska 54a, 50-425 Wrocław", "tel": "71 341 30 60"},
                                                                            "Latex Opole": {"nazwa": "LATEX SERWIS OPOLE", "adres": "ul. Krapkowicka 18A, 45-732 Opole", "tel": "77 474 80 89"}}}])
    if "oferty_konta" in u: return r.fulfill(json=[{"xp_login": "x", "xp_haslo": "y", "ustawienia": {}}])
    if "/rest/v1/oferty" in u and m == "POST": saved.append(r.request.post_data); return r.fulfill(status=201, body="")
    if "/rest/v1/oferty" in u: return r.fulfill(json=[{"id": 7, "owner": "test@firma.pl", "dane": json.loads(saved[-1])["dane"]}] if saved else [])
    if "app_users" in u: return r.fulfill(json=[{"email": "test@firma.pl", "name": "Jan Testowy"}])
    if "rpc/oferty_moje_haslo" in u: return r.fulfill(json="y")
    if "rpc/oferty_zapisz" in u: return r.fulfill(json=None)
    return r.fulfill(status=404, body="")
errs = []
with sync_playwright() as p:
    b = p.chromium.launch()
    for name, dev in [("360", {"viewport": {"width": 360, "height": 740}, "device_scale_factor": 1, "is_mobile": True, "has_touch": True}),
                      ("412", {"viewport": {"width": 412, "height": 915}, "device_scale_factor": 1, "is_mobile": True, "has_touch": True})]:
        saved.clear()
        ctx = b.new_context(**dev); pg = ctx.new_page()
        pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda c: c.type == "error" and "404" not in c.text and errs.append(c.text))
        pg.route(SB + "/**", route); pg.route("https://github.com/**", lambda r: r.fulfill(status=404, body=""))
        pg.goto((ROOT / "mobile/www/index.html").as_uri())
        pg.evaluate("db=>{const D=JSON.parse(db);Silnik.api_call=async(c,p)=>p.productId?[1,D.filter(x=>String(x.productId||x.id)==String(p.productId)).slice(0,1)]:[D.length,D]}", DB)
        def shot(n): pg.screenshot(path=str(OUT / f"{name}_{n}.png"), full_page=True)
        def wide():  # nic nie wystaje poza ekran
            w = pg.evaluate("document.documentElement.scrollWidth"); assert w <= dev["viewport"]["width"], f"przewijanie w bok: {w}"
        shot("1_login"); wide()
        pg.fill("#lEmail", "test@firma.pl"); pg.fill("#lPass", "x"); pg.click("#bLogin"); pg.wait_for_selector("#vOferta:not([hidden])")
        shot("2_oferta"); wide()
        pg.fill("#quick", "skoda octavia 2055516 dw5444lw z wymianą 4 czujniki"); pg.click("#bQ"); pg.wait_for_selector("#resCard:not([hidden]) .prod")
        shot("3_wyniki"); wide()
        # sezon i klasa z polecenia muszą zadziałać jak w Panelu (błąd 1.0.0: „zimowe” pokazywało też letnie)
        pg.fill("#quick", "2055516 zimowe premium"); pg.click("#bQ"); pg.wait_for_timeout(500)
        g = pg.inner_text("#res .grp"); assert "Zimowa" in g and "wszystkie" not in g, g
        assert pg.locator(".sez.on").count() == 1 and pg.locator(".kl.on").count() == 1, "chipy nie zaznaczone"
        assert all("Zimowa" in t for t in pg.locator(".prod .t2").all_inner_texts()), "w wynikach są inne sezony"
        pg.fill("#quick", "skoda octavia 2055516 dw5444lw z wymianą 4 czujniki"); pg.click("#bQ"); pg.wait_for_timeout(500)
        pg.locator(".prod input").first.check(); pg.locator(".prod input").nth(1).check()
        assert pg.is_visible("#selBar"), "brak paska Generuj"
        pg.click("#bO"); pg.wait_for_selector("#outCard:not([hidden]) .vcard")
        shot("4_oferta"); wide()
        assert "RAZEM" in pg.inner_text("#sum") and pg.locator("#email").count() == 0, "oferta bez treści e-maila (jak Panel)"
        # PDF oferty: admin ma oba oddziały -> wybór; PDF z danymi wybranego oddziału
        # „;0” na końcu: Playwright wywołałby funkcję, gdyby była ostatnim wyrażeniem (wtedy __pdf powstaje bez kliknięcia)
        pg.evaluate("window.__pdf=null;Aplikacja.pdf=async(h,n)=>{window.__pdf={h,n};return{ok:true}};0")
        pg.select_option("#ul select", "Latex Opole"); pg.locator("#ul .ulk").first.click(); pg.wait_for_function("window.__pdf && window.__pdf.h")
        h = pg.evaluate("window.__pdf.h")
        assert "LATEX SERWIS OPOLE" in h and "77 474 80 89" in h and "WROCŁAW" not in h and "DO ZAPŁATY BRUTTO" in h and "Wymiana opon" in h, h[:300]
        assert pg.evaluate("window.__pdf.n").startswith("Oferta ")
        assert 'src="logo.png"' in h, "PDF bez logo"
        (OUT / f"{name}_pdf.html").write_text(h, encoding="utf-8")
        pg.evaluate("window.__pdf=null;0"); pg.click("text=w jednym PDF"); pg.wait_for_function("window.__pdf && window.__pdf.h")
        hw = pg.evaluate("window.__pdf.h"); assert hw.count('<div class="page">') == 2 and "wszystkie 2" in pg.evaluate("window.__pdf.n"), "wszystkie w jednym"
        pg.click("#edit summary"); pg.locator("#edit input[type=number]").nth(0).fill("10"); pg.locator("#edit input[type=number]").nth(0).dispatch_event("change")
        pg.wait_for_timeout(900); shot("5_edycja"); wide()
        pg.click("#prodBtn" ) if False else None
        pg.click("text=⚙ Filtry"); pg.wait_for_selector("#sheet:not([hidden])"); shot("6_filtry"); pg.click("#sheet .btn.grow >> nth=1")
        pg.click("#prodBtn"); pg.wait_for_selector("#pBody label"); shot("7_producenci"); wide(); pg.click("text=Zastosuj")
        pg.click("#tabs button[data-v=vHist]"); pg.wait_for_selector(".hrow"); shot("8_historia"); wide()
        pg.click("#tabs button[data-v=vUst]"); pg.check("input[value=kwota]"); shot("9_ustawienia"); wide()
        assert "Obsługa TPMS" in pg.inner_text("#vUst"), "TPMS jako obsługa czujnika"
        pg.click("text=Zapisz ustawienia"); pg.wait_for_selector("#cMsg .msg"); assert "Zapisano" in pg.inner_text("#cMsg"), pg.inner_text("#cMsg")
        pg.click("#tabs button[data-v=vWyn]"); pg.wait_for_selector("#wBody .wtop"); shot("10_wyniki"); wide()
        assert "Wrocław" in pg.inner_text("#wOdd") and "Opole" in pg.inner_text("#wOdd"), "admin widzi oba oddziały"
        assert "41%" in pg.inner_text("#wBody .pct"), pg.inner_text("#wBody .pct")
        pg.click("#wOdd button >> text=Opole"); assert "33%" in pg.inner_text("#wBody .pct")
        # DEPOZYT (admin): wybór oddziału, sezon domyślny, bez wyszukania najwyżej 50 kart
        pg.click("#tabs button[data-v=vDep]"); pg.wait_for_selector("#dL .dk")
        assert pg.is_visible("#dOdd") and pg.input_value("#dSez") == "ZIMA 2026/27", pg.input_value("#dSez")
        assert pg.locator("#dL .dk").count() == 50 and not pg.is_visible("#dLista"), pg.locator("#dL .dk").count()
        assert "wszystkie 1000" in pg.inner_text("#dCnt").replace("\n", " "), pg.inner_text("#dCnt")
        shot("12_depozyt"); wide()
        pg.fill("#dq", "xx0O07c"); pg.wait_for_timeout(400)   # literówka O/0 – i tak znajdzie
        assert pg.locator("#dL .dk").count() >= 1 and "XX0007C" in pg.inner_text("#dL .dk >> nth=0"), pg.inner_text("#dL")
        pg.fill("#dq", "XX0001B"); pg.wait_for_timeout(400); assert "XX0001B" in pg.inner_text("#dL .dnr >> nth=0") and "literówka" not in pg.inner_text("#dL .dnr >> nth=0")
        K1 = "#dL .dk[data-id='1']"
        pg.click(K1 + " .dok"); pg.wait_for_selector(K1 + ".jest"); t = pg.inner_text(K1 + " .dst"); assert "przywiezione" in t and "Jan Testowy" in t, t
        shot("13_depozyt_przywiezione"); wide()
        pg.click(K1 + " >> text=Zmień lokalizację"); pg.fill("#dEd", "k99.9"); pg.click("#sheet >> text=Zapisz"); pg.wait_for_function("document.querySelector(\"#dL .dk[data-id='1'] .dlok\").textContent==='K99.9'")
        pg.click(K1 + " >> text=Komentarz"); pg.fill("#dEd", "Opony z łańcuchami – źle opisane"); shot("14_depozyt_komentarz"); pg.click("#sheet >> text=Zapisz")
        pg.wait_for_selector(K1 + " .dkom")
        pg.once("dialog", lambda d: d.accept()); pg.click(K1 + " >> text=Cofnij przywiezione"); pg.wait_for_selector(K1 + " .dok")   # admin może cofnąć
        # zmiana z innego telefonu – po 10 s podmienia się sama (tylko zmiany po „zmieniono”)
        x = next(d for d in DEP if d["id"] == 25); x2 = dict(x, lok="KZMIANA", zmieniono="2099-01-01T00:00:00+00:00"); DEP_ZM.append(x2)
        pg.fill("#dq", "XX0025A"); pg.wait_for_timeout(300); pg.evaluate("depOdswiez()"); pg.wait_for_function("(document.querySelector(\"#dL .dk[data-id='25'] .dlok\")||{}).textContent==='KZMIANA'")
        DEP_ZM.clear(); x.update(lok=x["lok"])
        ctx.close()
        # handlowiec: tylko WYNIKI, oddział Wrocław – bez zakładek ofert, bez ustawień ofert
        PROF["p"] = {"email": "h@firma.pl", "name": "Handlowiec", "role": "user", "modules": ["wyniki"], "branches": ["Latex Wrocław"]}
        ctx = b.new_context(**dev); pg = ctx.new_page()
        pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda c: c.type == "error" and "404" not in c.text and errs.append(c.text))
        pg.route(SB + "/**", route); pg.route("https://github.com/**", lambda r: r.fulfill(status=404, body=""))
        pg.goto((ROOT / "mobile/www/index.html").as_uri())
        pg.fill("#lEmail", "h@firma.pl"); pg.fill("#lPass", "x"); pg.click("#bLogin"); pg.wait_for_selector("#vWyn:not([hidden]) .wtop")
        vis = [x for x in pg.locator("#tabs button").all() if x.is_visible()]
        assert [x.get_attribute("data-v") for x in vis] == ["vWyn", "vUst"], [x.get_attribute("data-v") for x in vis]
        assert "Opole" not in pg.inner_text("#wOdd") and pg.inner_text("#tTitle") == "Wyniki marży"
        shot("11_handlowiec"); wide()
        pg.click("#tabs button[data-v=vUst]"); assert not pg.is_visible("#ustOferty") and pg.is_visible("text=Wyloguj")
        ctx.close()
        # magazynier: tylko moduł „depozyt” – widzi samą zakładkę Depozyt; cofnięcie – komunikat bazy
        PROF["p"] = {"email": "m@firma.pl", "name": "Magazynier Testowy", "role": "user", "modules": ["depozyt"], "branches": ["Latex Wrocław"]}
        ctx = b.new_context(**dev); pg = ctx.new_page()
        pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda c: c.type == "error" and "404" not in c.text and "400" not in c.text and errs.append(c.text))
        pg.route(SB + "/**", route); pg.route("https://github.com/**", lambda r: r.fulfill(status=404, body=""))
        pg.goto((ROOT / "mobile/www/index.html").as_uri())
        pg.fill("#lEmail", "m@firma.pl"); pg.fill("#lPass", "x"); pg.click("#bLogin"); pg.wait_for_selector("#vDep:not([hidden]) .dk")
        vis = [x.get_attribute("data-v") for x in pg.locator("#tabs button").all() if x.is_visible()]
        assert vis == ["vDep", "vUst"], vis
        assert not pg.is_visible("#dOdd") and pg.inner_text("#tTitle") == "Depozyt opon"
        pg.select_option("#dFil", "tak"); pg.fill("#dq", "XX0004E"); pg.wait_for_timeout(400)
        pg.once("dialog", lambda d: d.accept()); pg.click("#dL .dk[data-id='4'] >> text=Cofnij przywiezione"); pg.wait_for_selector("#dMsg .msg.e")
        assert "tylko administrator" in pg.inner_text("#dMsg"), pg.inner_text("#dMsg")
        shot("15_magazynier"); wide()
        pg.select_option("#dSez", "LATO 2026"); pg.fill("#dq", ""); pg.select_option("#dFil", ""); pg.wait_for_timeout(300); shot("16_magazynier_lato"); wide()
        PROF["p"] = {"email": "test@firma.pl", "name": "Jan Testowy", "role": "admin", "modules": ["oferty"], "branches": []}
        ctx.close()
    b.close()
print("błędy JS:", errs or "brak"); print("zrzuty:", OUT)
sys.exit(1 if errs else 0)
