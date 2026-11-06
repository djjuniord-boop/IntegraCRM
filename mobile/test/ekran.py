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
def route(r):
    u, m = r.request.url, r.request.method
    if "/auth/v1/token" in u: return r.fulfill(json={"access_token": "a", "refresh_token": "r", "expires_in": 3600, "user": {"email": "test@firma.pl"}})
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
        assert "RAZEM" in pg.inner_text("#sum"); assert len(pg.input_value("#email")) > 50
        # PDF oferty: admin ma oba oddziały -> wybór; PDF z danymi wybranego oddziału
        # „;0” na końcu: Playwright wywołałby funkcję, gdyby była ostatnim wyrażeniem (wtedy __pdf powstaje bez kliknięcia)
        pg.evaluate("window.__pdf=null;Aplikacja.pdf=async(h,n)=>{window.__pdf={h,n};return{ok:true}};0")
        pg.select_option("#ul select", "Latex Opole"); pg.locator("#ul .ulk").first.click(); pg.wait_for_function("window.__pdf && window.__pdf.h")
        h = pg.evaluate("window.__pdf.h")
        assert "LATEX SERWIS OPOLE" in h and "77 474 80 89" in h and "WROCŁAW" not in h and "DO ZAPŁATY BRUTTO" in h and "Wymiana opon" in h, h[:300]
        assert pg.evaluate("window.__pdf.n").startswith("Oferta ")
        assert 'src="logo.png"' in h, "PDF bez logo"
        (OUT / f"{name}_pdf.html").write_text(h, encoding="utf-8")
        pg.click("#edit summary"); pg.locator("#edit input[type=number]").nth(0).fill("10"); pg.locator("#edit input[type=number]").nth(0).dispatch_event("change")
        pg.wait_for_timeout(900); shot("5_edycja"); wide()
        pg.click("#prodBtn" ) if False else None
        pg.click("text=⚙ Filtry"); pg.wait_for_selector("#sheet:not([hidden])"); shot("6_filtry"); pg.click("#sheet .btn.grow >> nth=1")
        pg.click("#prodBtn"); pg.wait_for_selector("#pBody label"); shot("7_producenci"); wide(); pg.click("text=Zastosuj")
        pg.click("#tabs button[data-v=vHist]"); pg.wait_for_selector(".hrow"); shot("8_historia"); wide()
        pg.click("#tabs button[data-v=vUst]"); pg.check("input[value=kwota]"); shot("9_ustawienia"); wide()
        pg.click("text=Zapisz ustawienia"); pg.wait_for_selector("#cMsg .msg"); assert "Zapisano" in pg.inner_text("#cMsg"), pg.inner_text("#cMsg")
        pg.click("#tabs button[data-v=vWyn]"); pg.wait_for_selector("#wBody .wtop"); shot("10_wyniki"); wide()
        assert "Wrocław" in pg.inner_text("#wOdd") and "Opole" in pg.inner_text("#wOdd"), "admin widzi oba oddziały"
        assert "41%" in pg.inner_text("#wBody .pct"), pg.inner_text("#wBody .pct")
        pg.click("#wOdd button >> text=Opole"); assert "33%" in pg.inner_text("#wBody .pct")
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
        PROF["p"] = {"email": "test@firma.pl", "name": "Jan Testowy", "role": "admin", "modules": ["oferty"], "branches": []}
        ctx.close()
    b.close()
print("błędy JS:", errs or "brak"); print("zrzuty:", OUT)
sys.exit(1 if errs else 0)
