/* OFERTY OPON – silnik (JavaScript) dla aplikacji na Androida.
 * Wierne przeniesienie app/oferty/silnik.py (Panel). Przy zmianie logiki w Panelu – zmień też tutaj
 * i uruchom: node mobile/test/zgodnosc.mjs (porównuje wyniki obu wersji).
 * Zależności z zewnątrz (ustawia app.js):  Silnik.http(url) -> Promise<{status, text}>,
 *   Silnik.KONTO = {login, password, ustawienia, zapisz(dane)},  Silnik.HIST = {get, get_id, save, list, admin}
 */
(function (root) {
  "use strict";
  const S = {};
  S.API_URL = "https://xpartner.net.pl/index.php";
  S.KONTO = { login: "", password: "", ustawienia: {}, zapisz: null };
  S.HIST = null;
  S.http = null;

  const DEFAULT_CFG = {
    marza_proc: 5.0, vat_proc: 23.0,
    narzut_tryb: "procent",
    progi: [{ do: 400, kwota: 50 }, { do: 899, kwota: 70 }, { do: null, kwota: 90 }],
    min_stan: 50, propozycji_na_sezon: 1, tylko_standard: true,
    wymiana_kolo: { 13: 40, 14: 40, 15: 42, 16: 44, 17: 50, 18: 55, 19: 60, 20: 65, 21: 70, 22: 75 },
    wymiana_suv: { 15: 55, 16: 55, 17: 60, 18: 65, 19: 70, 20: 80, 21: 90, 22: 100 },
    wymiana_dost: { 14: 55, 15: 60, 16: 65, 17: 70 },
    tpms_cena: 150,
    przech_opony_do19: 120, przech_opony_pow19: 160, przech_kola_do19: 150, przech_kola_pow19: 200,
    kola_na_auto: 4, klasy_ver: 2,
    premium: ["BRIDGESTONE", "CONTINENTAL", "DUNLOP", "GOODYEAR", "METZELER", "MICHELIN", "NOKIAN", "PIRELLI", "PROMETEON", "TRELLEBORG", "VREDESTEIN", "YOKOHAMA"],
    srednie: ["BFGOODRICH", "TOYO", "ALLIANCE", "SOLIDEAL", "NEXEN", "MITAS", "MAXAM", "KUMHO", "HANKOOK", "GENERAL", "FULDA", "FIRESTONE", "FALKEN", "COOPER", "CAMSO", "UNIROYAL", "KLEBER"],
    budzet: ["SAILUN", "ROADX", "OPTIMO", "TRACMAX", "TRIANGLE", "FORTUNE", "WINDFORCE", "POWERTRAC", "DĘBICA", "BARUM", "GLOBGUM2", "KABAT", "KENDA", "LANVIGATOR", "MAXXIS", "PETLAS", "ROADHIKER", "STARMAXX", "TBBTIRES", "TRAXMAX", "TRAYAL", "TRAZANO", "VK TYRE", "APLUS"],
    podpis: "Latex Serwis", waznosc_dni: 7,
  };
  S.DEFAULT_CFG = DEFAULT_CFG;
  const clone = (o) => JSON.parse(JSON.stringify(o));

  S.load_cfg = function () {
    const cfg = clone(DEFAULT_CFG);
    const user = Object.assign({}, S.KONTO.ustawienia || {});
    if (user.klasy_ver !== DEFAULT_CFG.klasy_ver) for (const k of ["premium", "srednie", "budzet", "klasy_ver"]) delete user[k];
    for (const k of Object.keys(user)) if (k in DEFAULT_CFG) cfg[k] = user[k];
    cfg.login = S.KONTO.login || ""; cfg.password = S.KONTO.password || "";
    return cfg;
  };
  const bkey = (x) => String(x || "").toUpperCase().replace(/[^A-ZĄĆĘŁŃÓŚŹŻ0-9]/g, "");
  S.bkey = bkey;
  S.save_cfg = async function (cfg) {
    const dane = {};
    for (const k of Object.keys(DEFAULT_CFG)) if (k in cfg) dane[k] = cfg[k];
    if (S.KONTO.zapisz) await S.KONTO.zapisz(dane);
    S.KONTO.ustawienia = dane;
  };

  // ------------------------------------------------------------ API xPartner
  class ApiError extends Error {}
  S.ApiError = ApiError;

  function txt(el, tag) {
    const x = el.getElementsByTagName(tag)[0];
    return x && x.textContent ? x.textContent.trim() : "";
  }
  function parse_products(xml) {
    const doc = new DOMParser().parseFromString(xml, "text/xml");
    if (doc.getElementsByTagName("parsererror").length) throw new ApiError("Nieprawidłowa odpowiedź API (nie XML) – sprawdź login/hasło.");
    const rootEl = doc.documentElement;
    const kids = (tag) => [...rootEl.children].filter((e) => e.tagName === tag);
    const ok = (kids("success")[0] || kids("productsResult")[0] || { textContent: "" }).textContent.trim();
    const errs = [...doc.getElementsByTagName("error")].map((e) => e.textContent).filter(Boolean);
    if (ok.toLowerCase() !== "true") throw new ApiError(errs.join("; ") || "API zwróciło success=false (sprawdź login/hasło i uprawnienia subkonta)");
    const count = parseInt((kids("productsCount")[0] || {}).textContent || "0", 10) || 0;
    const out = [];
    for (const p of doc.getElementsByTagName("product")) {
      const attrs = {};
      for (const a of p.getElementsByTagName("attribute")) attrs[txt(a, "name")] = txt(a, "value");
      const mag = {};
      for (const i of p.getElementsByTagName("item")) mag[txt(i, "warehouseName")] = parseInt(txt(i, "quantity") || "0", 10) || 0;
      const num = (t) => { const v = parseFloat(txt(p, t).replace(",", ".")); return isNaN(v) ? 0 : v; };
      out.push({ id: parseInt(txt(p, "productId") || "0", 10) || 0, kod: txt(p, "manufacturerCode"), ean: txt(p, "ean"), foto: foto_of(p, attrs),
        pola: [...new Set([...p.children].map((c) => c.tagName))].sort(),
        nazwa: txt(p, "name"), ilosc: parseInt(txt(p, "quantity") || "0", 10) || 0, netto: num("netDiscountPrice"),
        brutto_zak: num("grossDiscountPrice"), netto_kat: num("netListPrice"), attrs, magazyny: mag });
    }
    return [count, out];
  }
  S.parse_products = parse_products;
  // zdjęcie opony, jeśli xPartner je podaje (jak _foto w silnik.py) – tylko https
  const FOTO_TAG = /image|photo|picture|img|zdj|foto/i, FOTO_URL = /^https:\/\/[^\s"'<>]+$/i;
  function foto_of(p, attrs) {
    for (const c of p.getElementsByTagName("*")) {
      if (!FOTO_TAG.test(c.tagName || "")) continue;
      for (const v0 of [c.textContent || "", ...[...c.attributes].map((a) => a.value)]) { const v = v0.trim(); if (FOTO_URL.test(v)) return v; }
    }
    for (const [k, v0] of Object.entries(attrs)) { const v = (v0 || "").trim(); if (FOTO_URL.test(v) && (FOTO_TAG.test(k) || /\.(jpe?g|png|webp)(\?|$)/i.test(v))) return v; }
    return "";
  }

  S.api_call = async function (cfg, params) {
    if (!cfg.login || !cfg.password)
      throw new ApiError("Twoje konto nie ma jeszcze loginu API xPartner – poproś administratora o wpisanie go (Panel → UŻYTKOWNICY → konto → xPartner).");
    const q = new URLSearchParams({ a: "b2b_xmlApi", login: cfg.login, pass: cfg.password, m: "productsList" });
    for (const [k, v] of Object.entries(params)) q.set(k, v === true ? "true" : v === false ? "false" : String(v));
    let r;
    try { r = await S.http(S.API_URL + "?" + q.toString()); }
    catch (e) { throw new ApiError("Brak połączenia z xPartner – sprawdź internet."); }
    if (!r || r.status >= 400 || r.status === 0) throw new ApiError("Brak połączenia z xPartner (kod " + (r ? r.status : "?") + ").");
    return parse_products(r.text);
  };

  // cechy tylko z pliku ofertowego (EPREL, śnieg, lód) – jak CECHY w silnik.py
  const CECHY = {}, CECHY_PLIKU = ["Kod EPREL", "Przyczepność na śniegu", "Przyczepność na lodzie", "Hałas"];
  function zapamietaj_cechy(it) {
    const a = it.attrs || {}, c = {};
    for (const k of CECHY_PLIKU) if (a[k]) c[k] = a[k];
    if (Object.keys(c).length) CECHY[it.id] = c;
  }
  S.CECHY = CECHY;
  async function search_size(cfg, size) {
    // jak w silnik.py: najpierw kopia pliku ofertowego xPartner, gdy brak / nieaktualna – API
    if (S.KONTO.katalog) { try { const items = await S.KONTO.katalog(size); if (items) { items.forEach(zapamietaj_cechy); return items; } } catch (e) { /* API */ } }
    let all = [], page = 0;
    while (page < 30) {
      const [count, items] = await S.api_call(cfg, { productName: size, resultsPerPage: 100, page });
      all = all.concat(items); page++;
      if (!items.length || all.length >= count) break;
    }
    return all;
  }
  async function get_product(cfg, pid) {
    const [, items] = await S.api_call(cfg, { productId: pid, showNotAvailable: true });
    return items[0] || null;
  }

  // ------------------------------------------------------------ rozmiary, cechy opon
  const SIZE_RE = /(\d{3})\s*\/\s*(\d{2})\s*Z?R\s*(\d{2})/i;
  const SIZE_LOOSE_SRC = String.raw`(?<!\d)(\d{3})\s*[/\\\-.x×, ]?\s*(\d{2})\s*(?:[/\\\-., ]|\s*Z?R\s*F?)?\s*(\d{2})(?:[.,]5)?(?!\d)`;
  const sizeLoose = () => new RegExp(SIZE_LOOSE_SRC, "gi");

  function find_sizes(t) {
    const out = [];
    for (const m of String(t || "").matchAll(sizeLoose())) {
      const w = +m[1], p = +m[2], r = +m[3];
      if (w >= 125 && w <= 355 && w % 5 === 0 && p >= 25 && p <= 85 && p % 5 === 0 && r >= 12 && r <= 24) {
        const s = `${w}/${p} R${r}`;
        if (!out.includes(s)) out.push(s);
      }
    }
    return out;
  }
  function norm_size(s) {
    const m = SIZE_RE.exec(s || "");
    if (m) return `${m[1]}/${m[2]} R${m[3]}`;
    const f = find_sizes(s);
    return f.length ? f[0] : null;
  }
  S.find_sizes = find_sizes; S.norm_size = norm_size;

  function season_of(p) {
    const s = (p.attrs.Sezon || "").toUpperCase();
    if (s.includes("ZIM")) return "Zimowa";
    if (s.includes("CAŁ") || s.includes("CAL") || s.includes("WIELO") || s.includes("ALL")) return "Całoroczna";
    if (s.includes("LET")) return "Letnia";
    const m = /^\S+\s+([ZWL])\d{3}\//.exec(p.nazwa);
    return ({ Z: "Zimowa", W: "Całoroczna", L: "Letnia" })[m ? m[1] : ""] || "?";
  }
  const producer_of = (p) => (p.attrs.Producent || p.nazwa.split(" ")[0]).toUpperCase();
  const KLASY = { PREMIUM: "premium", MIDDLE: "średnia", BUDGET: "budżetowa" };
  S.KLASY = KLASY;
  function klasa_of(p, cfg) {
    const k = (p.attrs.Klasa || "").toUpperCase();
    if (k.startsWith("PREM")) return "PREMIUM";
    if (["MIDDLE", "MEDIUM", "ŚREDNIA", "SREDNIA", "STANDARD", "QUALITY"].includes(k)) return "MIDDLE";
    if (["BUDGET", "ECONOMY", "EKONOMICZNA", "BUDŻETOWA", "BUDZETOWA", "ECO"].includes(k)) return "BUDGET";
    const prod = bkey(producer_of(p));
    if (cfg.premium.map(bkey).includes(prod)) return "PREMIUM";
    if ((cfg.srednie || []).map(bkey).includes(prod)) return "MIDDLE";
    return "BUDGET";
  }
  // jak str.title() w Pythonie: wielka litera po każdym znaku, który nie jest literą
  const title = (s) => String(s).toLowerCase().replace(/(^|[^a-ząćęłńóśźżéüöäß])([a-ząćęłńóśźżéüöäß])/g, (a, b, c) => b + c.toUpperCase());
  function model_of(p) {
    const m = p.attrs["Nazwa bieżnika"];
    if (m) return title(m);
    let n = p.nazwa.replace(/^\S+\s+[ZWL]?\d{3}\/\d{2}\s*Z?R\d{2}\s*/, "").replace(/\s+(DEMO|DOT\s?\d{4})\b/g, "");
    return title(n.replace(/\s+\d{2,3}[A-Z].*$/, ""));
  }
  function index_of(p) {
    const li = p.attrs["Indeks nośności"] || "", si = (p.attrs["Indeks prędkości"] || "").split("-")[0];
    const xl = /\bXL\b/.test(p.nazwa) ? " XL" : "";
    if (li && si) return li + si + xl;
    const m = /\b(\d{2,3}[A-Z])\b(\s+XL)?/.exec(p.nazwa);
    return m ? m[1] + (m[2] ? " XL" : "") : "";
  }
  function dot_of(p) {
    const d = p.attrs["Rok produkcji"] || "";
    const m = /DOT\s?(\d{4})/.exec(d || p.nazwa);
    return m ? m[1] : "";
  }
  function is_standard(p) {
    const s = (p.attrs.Struktura || "STANDARD").toUpperCase();
    return s === "STANDARD" && !/\b(RFT|SSR|R\/F|ROF|ZP|RUN ?FLAT|DSST|EMT)\b/.test(p.nazwa.toUpperCase());
  }
  const SEZ_ORDER = { Zimowa: 0, "Całoroczna": 1, Letnia: 2 }, KL_ORDER = { premium: 0, "średnia": 1, "budżetowa": 2 };
  function vkeyCmp(a, b) {
    const ka = (k) => { const p = k[0].split(" · "); return [SEZ_ORDER[p[0]] ?? 9, KL_ORDER[p[1] || ""] ?? 9, k[1]]; };
    const x = ka(a), y = ka(b);
    for (let i = 0; i < 3; i++) if (x[i] !== y[i]) return x[i] < y[i] ? -1 : 1;
    return 0;
  }
  S.leaflet_url = (pid, price) => S.API_URL + "?" + new URLSearchParams({ a: "b2b_products", m: "getPDF", pid, fp: 0, fn: 0, fb: 0, fs: 0, showc: 0, price: price.toFixed(2) }).toString();
  function vlabel(keys, key) {
    if (key[0] === "wszystkie") return "Propozycja " + (key[1] + 1);
    const multi = keys.filter((k) => k[0] === key[0]).length > 1;
    return key[0] + (multi ? " – propozycja " + (key[1] + 1) : "");
  }
  function doplata_progowa(cfg, zb) {
    const pr = (cfg.progi || []).filter((p) => p.do !== null && p.do !== "" && p.do !== undefined).sort((a, b) => +a.do - +b.do);
    const reszta = (cfg.progi || []).filter((p) => p.do === null || p.do === "" || p.do === undefined);
    for (const p of pr) if (zb <= +p.do + 0.004) return +(p.kwota || 0);
    return reszta.length ? +(reszta[0].kwota || 0) : pr.length ? +(pr[pr.length - 1].kwota || 0) : 0;
  }
  const r2 = (x) => Math.round((x + Number.EPSILON) * 100) / 100;
  const ceilZl = (x) => Math.ceil(r2(x) - 1e-9);
  function sell_price(cfg, netto) {
    const vat = 1 + cfg.vat_proc / 100;
    let cena;
    if (cfg.narzut_tryb === "kwota") { const b = r2(netto * vat); cena = b + doplata_progowa(cfg, b); }
    else cena = netto * (1 + cfg.marza_proc / 100) * vat;
    return ceilZl(cena);
  }
  S.sell_price = sell_price; S.doplata_progowa = doplata_progowa;

  const HOMOL = [["MO", /\bMOE?\b|\bMO1\b|\bMO-S\b/], ["AO", /\bAOE?\b|\bRO[12]\b|\bA8A\b/], ["*", /\*|\bBMW\b/], ["N", /\bN[0-9]\b/],
    ["VOL", /\bVOL\b/], ["T0", /\bT[0O][0-9]?\b/], ["J", /\bJLR\b|\bJ\b/], ["LR", /\bLR\b/], ["VW", /\bVW\b/], ["FR", /\b(FR|MFS|FP|RG)\b/]];
  S.HOMOL_NAZWY = { MO: "Mercedes (MO)", AO: "Audi (AO/RO)", "*": "BMW (*)", N: "Porsche (N0–N9)", VOL: "Volvo (VOL)", T0: "Tesla (T0)", J: "Jaguar (J)", LR: "Land Rover (LR)", VW: "VW", FR: "rant ochronny felgi" };
  function is_demo(p) {
    if (/\bDEMO\b/.test(p.nazwa.toUpperCase())) return true;
    return Object.entries(p.attrs).some(([k, v]) => (k + " " + v).toLowerCase().includes("demont") && !["", "NIE", "0", "FALSE"].includes(String(v).trim().toUpperCase()));
  }
  function homol_of(p) {
    const src = (p.nazwa.toUpperCase() + " " + (p.attrs.Homologacja || "").toUpperCase()).replace(new RegExp(SIZE_RE.source, "gi"), " ");
    return HOMOL.filter(([, rx]) => rx.test(src)).map(([k]) => k);
  }
  function enrich(cfg, p0) {
    const p = Object.assign({}, p0);
    Object.assign(p, { sezon: season_of(p), producent: producer_of(p), klasa: klasa_of(p, cfg), model: model_of(p), indeks: index_of(p),
      dot: dot_of(p), standard: is_standard(p), cena_brutto: sell_price(cfg, p.netto),
      etykieta: Object.fromEntries(["Opory toczenia", "Przyczepność na mokrej nawierzchni", "Hałas", "Poziom hałasu"].map((k) => [k, p.attrs[k] || ""])) });
    const nz = /(\d{2})/.exec(p.attrs["Poziom hałasu"] || "");
    Object.assign(p, { mokra: (p.attrs["Przyczepność na mokrej nawierzchni"] || "").trim().slice(0, 1).toUpperCase(),
      opory: (p.attrs["Opory toczenia"] || "").trim().slice(0, 1).toUpperCase(), halas: nz ? +nz[1] : 0, homol: homol_of(p), demo: is_demo(p) });
    p.model_oferta = p.model + (p.demo ? " – DEMO (opona z demontażu)" : "");
    return p;
  }
  S.enrich = enrich;

  // ------------------------------------------------------------ marki
  const MARKI_STALE = ["BRIDGESTONE", "CONTINENTAL", "DUNLOP", "GOODYEAR", "METZELER", "MICHELIN", "NOKIAN", "PIRELLI", "PROMETEON",
    "TRELLEBORG", "VREDESTEIN", "YOKOHAMA", "BFGOODRICH", "TOYO", "ALLIANCE", "SOLIDEAL", "NEXEN", "MITAS", "MAXAM",
    "KUMHO", "HANKOOK", "GENERAL", "FULDA", "FIRESTONE", "FALKEN", "COOPER", "CAMSO", "UNIROYAL", "KLEBER", "SAILUN",
    "ROADX", "OPTIMO", "TRACMAX", "TRIANGLE", "FORTUNE", "WINDFORCE", "POWERTRAC", "DĘBICA", "BARUM", "GLOBGUM2",
    "KABAT", "KENDA", "LANVIGATOR", "MAXXIS", "PETLAS", "ROADHIKER", "STARMAXX", "TBBTIRES", "TRAXMAX", "TRAYAL",
    "TRAZANO", "VK TYRE", "APLUS", "ANTEO", "ATF", "CHIŃSKIE", "COMPASAL", "CST", "CULTOR", "DEESTONE", "DELI",
    "DYNAMAXX", "GISLAVED", "GITI", "GT RADIAL", "KORMORAN", "LEAO", "LING LONG", "MARCHER", "MATADOR", "MONTANA",
    "NANKANG", "NEUMASTER", "PMT", "RIKEN", "ROSAVA", "SAVA", "STARCO", "TAURUS", "TECHSHIELD", "TIGAR", "VEE RUBBER",
    "VIKING", "SEMPERIT", "LASSA", "LAUFENN", "HIFLY", "GRIPMAX", "ZEETEX", "ROTALLA", "IMPERIAL", "MARSHAL",
    "GOODRIDE", "WESTLAKE", "MINERVA", "DAVANTI", "ARIVO", "LINGLONG", "STRIAL", "ORIUM", "NORDEXX"];
  S.MARKI_STALE = MARKI_STALE;
  const MARKI = new Set();
  const ALIAS = { GOODYEAR: "GOODYEAR", GOODYER: "GOODYEAR", GY: "GOODYEAR", DEBICA: "DĘBICA", BFG: "BFGOODRICH", CONTI: "CONTINENTAL",
    BRIDGE: "BRIDGESTONE", BS: "BRIDGESTONE", MICH: "MICHELIN", PIRA: "PIRELLI", LINGLONG: "LINGLONG", GTRADIAL: "GTRADIAL",
    VK: "VKTYRE", CHINSKIE: "CHIŃSKIE", CHINSKA: "CHIŃSKIE" };
  S.ucz_marki = function (cfg, nazwy) {
    for (const m of [].concat(MARKI_STALE, (cfg || {}).premium || [], (cfg || {}).srednie || [], (cfg || {}).budzet || [], nazwy || []))
      if (m && bkey(m).length >= 2) MARKI.add(bkey(m));
  };
  function odl(a, b, limit) {
    if (Math.abs(a.length - b.length) > limit) return limit + 1;
    const d = Array.from({ length: a.length + 1 }, (_, i) => [i].concat(Array(b.length).fill(0)));
    for (let j = 0; j <= b.length; j++) d[0][j] = j;
    for (let i = 1; i <= a.length; i++) for (let j = 1; j <= b.length; j++) {
      const c = a[i - 1] === b[j - 1] ? 0 : 1;
      d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + c);
      if (i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1]) d[i][j] = Math.min(d[i][j], d[i - 2][j - 2] + 1);
    }
    return d[a.length][b.length];
  }
  const NIE_MARKI = new Set(("ZIMA ZIMOWE LATO LETNIE OPONY OPONA PREMIUM SREDNIA ŚREDNIA BUDZET BUDŻET WYMIANA DEMO RUNFLAT TYLKO PRZECHOWALNIA " +
    "CZUJNIKI SZTUK OFERTA OFERTY TOYOTA OSOBOWY DOSTAWCZY KOMPLET FELGI FELGAMI SKODA OCTAVIA SUPERB FABIA KAMIQ KAROQ KODIAQ SCALA RAPID " +
    "ENYAQ VOLKSWAGEN PASSAT TIGUAN TOURAN GOLF POLO ARTEON TRANSPORTER CRAFTER CADDY AMAROK TAIGO TROC AUDI BMW MERCEDES SPRINTER VITO " +
    "VIANO YARIS COROLLA AURIS AVENSIS RAV4 CHR HILUX PROACE OPEL ASTRA CORSA INSIGNIA MOKKA VIVARO MOVANO ZAFIRA FORD FOCUS FIESTA " +
    "MONDEO KUGA TRANSIT CUSTOM PUMA RANGER RENAULT CLIO MEGANE CAPTUR KADJAR TRAFIC MASTER KANGOO DACIA DUSTER SANDERO LOGAN JOGGER " +
    "PEUGEOT PARTNER EXPERT BOXER CITROEN BERLINGO JUMPER JUMPY FIAT DUCATO DOBLO TIPO PANDA HYUNDAI TUCSON KONA I30 SANTA KIA CEED " +
    "SPORTAGE NIRO SORENTO PICANTO MAZDA HONDA CIVIC NISSAN QASHQAI JUKE XTRAIL NAVARA VOLVO SEAT LEON IBIZA ATECA ARONA CUPRA " +
    "FORMENTOR SUZUKI VITARA SWIFT MITSUBISHI OUTLANDER TESLA LEXUS JEEP SUBARU PORSCHE LAND ROVER MINI IVECO DAILY MAN SCANIA").split(" "));
  function brand_of_word(w) {
    if (!MARKI.size) S.ucz_marki();
    const k = bkey(ALIAS[bkey(w)] || w);
    if (k.length < 3 || NIE_MARKI.has(k)) return "";
    if (MARKI.has(k)) return k;
    if (k.length >= 4) {
      const hits = [...MARKI].filter((m) => m.startsWith(k)).sort();
      if (hits.length === 1) return hits[0];
      const lim = k.length <= 5 ? 1 : 2;
      const best = [...MARKI].filter((m) => m.length >= 4).map((m) => [odl(k, m, lim), m]).filter((b) => b[0] <= lim)
        .sort((a, b) => a[0] - b[0] || (a[1] < b[1] ? -1 : 1));
      if (best.length && (best.length === 1 || best[0][0] < best[1][0])) return best[0][1];
    }
    return "";
  }
  S.brand_of_word = brand_of_word;

  // ------------------------------------------------------------ rozpoznawanie zapytań
  function extras(t) {
    t = t.toLowerCase();
    const typ = /\bsuv\b|4x4|4 ?x ?4|terenow/.test(t) ? "suv" : /dostawcz|\bbus\b|\bvan\b/.test(t) ? "dostawczy" : "osobowy";
    const wym = /wymian|monta[żz]|przek[łl]ad/.test(t) && !/bez (wymiany|monta[żz]u)/.test(t);
    const m = /(\d)\s*(?:szt\.?\s*)?(?:czujnik[a-ząćęłńóśźż]*|tpms)|(?:czujnik[a-ząćęłńóśźż]*|tpms)\s*(?:x\s*)?(\d)\b/.exec(t);
    const tp = m ? +(m[1] || m[2]) : (/czujnik|tpms/.test(t) ? 4 : 0);
    let pr = "";
    if (/przechow/.test(t)) pr = /k[oó][łl]|felg/.test(t) ? "kola" : "opony";
    return { typ, wymiana: wym, tpms: Math.min(tp, 8), przech: pr };
  }
  const STOP = new Set("marka model rejestracja rozmiar wymaga nowych opon opony szt sztuk tak nie tylko wymiana wymianę wymiane auto samochód samochod pojazd i oraz x r zr nr rej".split(" "));
  const CRIT_RE = /^(demo|bez|suv|4x4|terenow[a-ząćęłńóśźż]*|dostawcz[a-ząćęłńóśźż]*|bus|van|czujnik[a-ząćęłńóśźż]*|tpms|przechow[a-ząćęłńóśźż]*|k[oó]ł|kola|koła|felg[a-ząćęłńóśźż]*|z|ze|wymian[a-ząćęłńóśźż]*|monta[żz][a-ząćęłńóśźż]*|przek[łl]ad[a-ząćęłńóśźż]*|premium|prem|[śs]redni[a-ząćęłńóśźż]*|middle|medium|bud[żz]et[a-ząćęłńóśźż]*|budget|ekonom[a-ząćęłńóśźż]*|tani[a-ząćęłńóśźż]*|zim[a-ząćęłńóśźż]*|letn[a-ząćęłńóśźż]*|lato|lecie|summer[a-ząćęłńóśźż]*|winter[a-ząćęłńóśźż]*|ca[łl]orok|pory|roku|ca[łl]oroczn[a-ząćęłńóśźż]*|wielosezon[a-ząćęłńóśźż]*|runflat|run-?flat|rft|ssr|klas[aey]?|półk[aią]|polk[aią]|sezon[a-ząćęłńóśźż]*|opony)$/i;
  const PLATE_RE = /(?<![A-Z0-9])([A-Z]{1,3})[ -]?([0-9][0-9A-Z]{2,5}|[A-Z]{0,2}[0-9][0-9A-Z]{1,4})(?![A-Z0-9])/g;
  const cap = (w) => (w.length <= 3 && /^[a-ząćęłńóśźż]+$/i.test(w)) || /\d/.test(w) ? w.toUpperCase() : w.charAt(0).toUpperCase() + w.slice(1);

  function parse_free_line(line) {
    const sizes = find_sizes(line);
    if (!sizes.length) return null;
    const up = line.toUpperCase();
    let rest = up.replace(sizeLoose(), " ");
    const q = /(?<!\d)(\d{1,2})\s*(SZT|OPON|SZTUK)/.exec(rest);
    let il = q ? +q[1] : 4;
    rest = rest.replace(/(?<!\d)\d{1,2}\s*(SZT|OPON|SZTUK)\.?/g, " ");
    const only_swap = /TYLKO\s+WYMIAN|\bNIE\b|BEZ OPON/.test(up);
    if (only_swap) il = 0;
    let reg = "";
    for (const m of rest.matchAll(PLATE_RE)) {
      const cand = m[1] + m[2];
      if ((/\d/.test(cand) && cand.length >= 4 && cand.length <= 8 && !/^\d+$/.test(m[2])) || (m[1].length >= 2 && cand.length >= 5)) {
        reg = cand; rest = rest.slice(0, m.index) + " " + rest.slice(m.index + m[0].length); break;
      }
    }
    const words = rest.split(/[\s,;/|\t]+/).filter((w) => w && !STOP.has(w.toLowerCase()) && !/^[\d.,]+$/.test(w) && !CRIT_RE.test(w) && !brand_of_word(w));
    const ex = extras(line);
    return { rej: reg, pojazd: words.map((w) => cap(w.toLowerCase())).join(" "), rozmiar: sizes[0], nowe: il > 0, ilosc: il,
      wymiana: ex.wymiana || only_swap, typ: ex.typ, tpms: ex.tpms, przech: ex.przech };
  }
  function parse_request_table(t) {
    const tokens = t.split(/[\t\r\n|;]+|\s{2,}/).map((x) => x.trim()).filter(Boolean);
    const recs = []; let cur = [];
    const reg_re = /^[A-Z]{1,3}[0-9][0-9A-Z]{2,6}$/;
    for (const tk of tokens) {
      cur.push(tk);
      if (["TAK", "NIE"].includes(tk.toUpperCase())) {
        const size = norm_size(cur.join(" "));
        const reg = (cur.find((x) => reg_re.test(x.replace(/ /g, "").toUpperCase()) && !SIZE_RE.test(x)) || "").replace(/ /g, "");
        if (size) {
          const words = cur.filter((x) => !(x.replace(/ /g, "") === reg || SIZE_RE.test(x) || ["TAK", "NIE"].includes(x.toUpperCase())
            || ["marka", "model", "rejestracja", "rozmiar", "wymaga nowych opon"].includes(x.toLowerCase()))).map(title);
          const tak = tk.toUpperCase() === "TAK";
          recs.push({ rej: reg.toUpperCase(), pojazd: words.slice(-2).join(" "), rozmiar: size, nowe: tak, ilosc: tak ? 4 : 0, wymiana: true });
        }
        cur = [];
      }
    }
    return recs;
  }
  S.parse_request_text = function (t) {
    const lines = t.split(/\r?\n/);
    if (!/(^|\s)(TAK|NIE)(\s|$)/m.test(t) || lines.filter((l) => l.trim()).length <= 1 || lines.some((l) => find_sizes(l).length && l.trim().split(/\s+/).length >= 3)) {
      const recs = t.split(/[\n;]+/).map(parse_free_line).filter(Boolean);
      if (recs.length) return recs;
    }
    return parse_request_table(t);
  };

  S.parse_quick = function (txt0) {
    const t = txt0.toLowerCase();
    const sizes = find_sizes(txt0);
    const q = /(?:^|\s)(\d{1,2})\s*(szt|opon|sztuk|x\b)/.exec(t) || /\bx\s*(\d{1,2})\b/.exec(t);
    const ilosc = q ? +q[1] : 4;
    const sezony = [];
    if (/(?<![a-ząćęłńóśźż])(zim|winter)/.test(t)) sezony.push("Zimowa");
    if (/(?<![a-ząćęłńóśźż])(ca[łl]oroczn|ca[łl]orok|wielosezon|all ?-?season|4 ?season|4 ?pory)/.test(t)) sezony.push("Całoroczna");
    if (/(?<![a-ząćęłńóśźż])(letn|lato|lecie|summer)/.test(t)) sezony.push("Letnia");
    const klasy = [];
    if (/premium|prem\b/.test(t)) klasy.push("PREMIUM");
    if (/[śs]redni|middle|medium/.test(t)) klasy.push("MIDDLE");
    if (/bud[żz]et|budget|ekonom|tani/.test(t)) klasy.push("BUDGET");
    const marki = [];
    const slowa = (t.match(/[a-ząćęłńóśźż][a-ząćęłńóśźż0-9\-.]*/g) || []).filter((w) => !sizeLoose().test(w));
    let i = 0;
    while (i < slowa.length) {
      let b;
      const b2 = i + 1 < slowa.length ? brand_of_word(slowa[i] + slowa[i + 1]) : "";
      if (b2 && MARKI.has(bkey(slowa[i] + slowa[i + 1]))) { b = b2; i += 2; } else { b = brand_of_word(slowa[i]); i += 1; }
      if (b && !marki.includes(b)) marki.push(b);
    }
    const ex = extras(t);
    const runflat = /run ?-?flat|\brft\b|\bssr\b|\bzp\b|\brof\b/.test(t);
    const pojazdy = sizes.map((s) => ({ rej: "", pojazd: "", rozmiar: s, ilosc, nowe: true, wymiana: ex.wymiana, typ: ex.typ, tpms: ex.tpms, przech: ex.przech }));
    const demo = /bez\s+demo/.test(t) ? "bez" : /\bdemo\b/.test(t) ? "tylko" : "";
    return { demo, pojazdy, sezony, klasy, runflat, producenci: marki.join(", ") };
  };

  // ------------------------------------------------------------ wyszukiwanie
  async function pool(items, n, fn) {
    const out = new Array(items.length); let next = 0;
    await Promise.all(Array.from({ length: Math.min(n, items.length) }, async () => {
      while (next < items.length) { const i = next++; out[i] = await fn(items[i]); }
    }));
    return out;
  }
  S.do_search = async function (cfg, req) {
    const sizes = [...new Set(req.pojazdy.filter((v) => v.nowe && norm_size(v.rozmiar)).map((v) => norm_size(v.rozmiar)))].sort();
    const sezony = req.sezony && req.sezony.length ? req.sezony : [""];
    const prod_f = (req.producenci || "").split(",").filter((x) => x.trim()).map(bkey);
    const klasy = req.klasy && req.klasy.length ? req.klasy : [""];
    const min_stan = parseInt(req.min_stan ?? cfg.min_stan, 10) || 0;
    const need = {};
    for (const v of req.pojazdy) if (v.nowe) { const s = norm_size(v.rozmiar); need[s] = (need[s] || 0) + (parseInt(v.ilosc, 10) || 4); }
    const found = await pool(sizes, 4, (s) => search_size(cfg, s));
    const res = {};
    sizes.forEach((s, si) => {
      const items = found[si].filter((p) => norm_size(p.nazwa) === s && p.netto > 0).map((p) => enrich(cfg, p));
      S.ucz_marki(null, items.map((p) => p.producent));
      res[s] = {};
      for (const sez of sezony) for (const klasa of klasy) {
        let lst = items.filter((p) => !sez || p.sezon === sez);
        if (req.tylko_runflat) lst = lst.filter((p) => !p.standard);
        if (prod_f.length) lst = lst.filter((p) => prod_f.some((x) => bkey(p.producent).startsWith(x)));
        if (klasa) lst = lst.filter((p) => p.klasa === klasa);
        lst = lst.map((p) => Object.assign({}, p, { ok_stan: p.ilosc >= Math.max(min_stan, need[s]) }));
        lst.sort((a, b) => (a.ok_stan === b.ok_stan ? a.netto - b.netto : a.ok_stan ? -1 : 1));
        const grp = [sez, KLASY[klasa] || klasa].filter(Boolean).join(" · ") || "wszystkie";
        res[s][grp] = lst;
      }
    });
    return { wyniki: res, potrzeba: need, zrodlo: (S.KONTO.katalog_info && S.KONTO.katalog_info()) || "xPartner na żywo (API)" };
  };

  // ------------------------------------------------------------ oferta
  const TYPY = { osobowy: "osobowy", suv: "SUV/4x4", dostawczy: "dostawczy" };
  const pl = (x) => (Math.round(x * 100) / 100).toFixed(2).replace(".", ",").replace(/\B(?=(\d{3})+(?!\d))/g, " ") + " zł";
  S.pl = pl;
  const total = (v) => v.opony + v.wymiana + (v.uslugi || 0);

  S.build_offer = async function (cfg, req) {
    const ids = [...new Set(Object.values(req.wybor).flatMap((g) => Object.values(g).flat()))].sort((a, b) => a - b);
    const got = await pool(ids, 4, (i) => get_product(cfg, i));
    const fresh = {};
    ids.forEach((pid, i) => { fresh[pid] = got[i] ? enrich(cfg, got[i]) : null; });
    let rab = parseFloat(req.rabat || 0); rab = isNaN(rab) ? 0 : Math.max(0, Math.min(90, rab));
    const over = {};
    for (const [k, v] of Object.entries(req.ceny || {})) if (String(v).trim() !== "" && String(v) !== "0") over[+k] = +v;
    for (const [pid, p] of Object.entries(fresh)) {
      if (!p) continue;
      let auto = sell_price(cfg, p.netto);
      if (rab) auto = ceilZl(auto * (1 - rab / 100));
      p.cena_auto = auto; p.cena_brutto = over[+pid] ?? auto; p.recznie = +pid in over;
    }
    const warnings = [], kola = parseInt(cfg.kola_na_auto, 10);
    const rows = [], variants = new Map(); // klucz "nazwa\u0001k"
    const keyOf = (a, k) => a + "\u0001" + k;
    const sep = !!req.osobno;
    req.pojazdy.forEach((v0, vi) => {
      let v = Object.assign({ rej: "", pojazd: "" }, v0);
      const s = norm_size(v.rozmiar) || v.rozmiar;
      const dm = /R(\d{2})/.exec(s); const dia = dm ? dm[1] : "16";
      const typ = v.typ || "osobowy";
      const cen = typ === "suv" ? cfg.wymiana_suv : typ === "dostawczy" ? cfg.wymiana_dost : cfg.wymiana_kolo;
      const n_kol = (parseInt(v.ilosc, 10) || 0) || kola;
      const wym = v.wymiana ? +(cen[dia] || 0) * n_kol : 0;
      if (v.wymiana && !cen[dia]) warnings.push(`Brak ceny wymiany dla ${v.rej || s} R${dia} (${TYPY[typ]}) – uzupełnij Ustawienia`);
      const n_tp = parseInt(v.tpms, 10) || 0;
      const tp_kw = r2(n_tp * +cfg.tpms_cena);
      const tp_op = n_tp ? `Czujniki TPMS ${n_tp} szt. × ${pl(+cfg.tpms_cena)}` : "";
      const pr = v.przech || "";
      let pr_kw = 0, pr_op = "";
      if (pr === "opony" || pr === "kola") {
        const big = +dia > 19;
        pr_kw = +cfg[`przech_${pr}_${big ? "pow19" : "do19"}`];
        pr_op = `Przechowalnia ${pr === "opony" ? "opon" : "kół z felgami"} (${big ? "powyżej" : "do"} R19)`;
      }
      v = Object.assign(v, { tpms_kw: tp_kw, tpms_op: tp_op, przech_kw: pr_kw, przech_op: pr_op, uslugi: tp_kw + pr_kw });
      if (!v.nowe) { rows.push(Object.assign({}, v, { rozmiar: s, rodzaj: v.wymiana ? "tylko wymiana" : "usługi", wymiana: wym, opony: 0, p: null, wariant: null })); return; }
      for (const [sez, lst] of Object.entries((req.wybor || {})[s] || {})) lst.forEach((pid, k) => {
        const p = fresh[pid];
        if (p && p.netto <= 0) { warnings.push(`${p.nazwa} – brak ceny w xPartner (niedostępna do zamówienia), pominięto`); return; }
        if (!p) { warnings.push(`Produkt ${pid} niedostępny w API`); return; }
        const q = parseInt(v.ilosc, 10) || 4;
        let name;
        if (sep) {
          const lab = (w) => [w.rej, w.pojazd].filter(Boolean).join(" ") || norm_size(w.rozmiar);
          let vl = [v.rej, v.pojazd].filter(Boolean).join(" ") || s;
          if (req.pojazdy.filter((w) => lab(w) === vl).length > 1) vl += ` (${vi + 1})`;
          name = vl + (sez === "wszystkie" ? "" : " · " + sez);
        } else name = sez;
        const key = keyOf(name, k);
        if (!variants.has(key)) variants.set(key, { key: [name, k] });
        rows.push(Object.assign({}, v, { rozmiar: s, rodzaj: p.sezon, p, ilosc: q, opony: r2(p.cena_brutto * q), wymiana: wym, wariant: key }));
      });
    });
    for (const [key, var_] of variants) {
      const mine = rows.filter((r) => r.wariant === key), bez = rows.filter((r) => !r.p);
      const sum = (a, f) => a.reduce((x, r) => x + r[f], 0);
      var_.opony = sum(mine, "opony");
      var_.wymiana = sum(mine, "wymiana") + sum(bez, "wymiana");
      var_.tpms_kw = sum(mine, "tpms_kw") + sum(bez, "tpms_kw");
      var_.przech_kw = sum(mine, "przech_kw") + sum(bez, "przech_kw");
      var_.uslugi = var_.tpms_kw + var_.przech_kw;
      var_.modele = [...new Set(mine.map((r) => title(r.p.producent) + " " + r.p.model))].sort();
    }
    if (!variants.size && rows.length) {
      const sum = (f) => rows.reduce((x, r) => x + r[f], 0);
      variants.set(keyOf("Usługi", 0), { key: ["Usługi", 0], opony: 0, wymiana: sum("wymiana"), tpms_kw: sum("tpms_kw"), przech_kw: sum("przech_kw"), uslugi: sum("uslugi"), modele: [] });
    }
    const need = {};
    for (const r of rows) if (r.p) need[r.p.id] = (need[r.p.id] || 0) + r.ilosc;
    for (const [pid, n] of Object.entries(need)) { const p = fresh[pid]; if (p && p.ilosc < n) warnings.push(`${p.nazwa} – na stanie ${p.ilosc} szt., potrzeba ${n}`); }
    const ordered = [...variants.values()].sort((a, b) => vkeyCmp(a.key, b.key));
    return { rows, variants: ordered, warnings };
  };

  S.email_text = function (cfg, req, rows, vars) {
    const kl = (req.klient || "").trim();
    const L = ["Dzień dobry,", "", "dziękujemy za zapytanie. W załączeniu przesyłamy ofertę na zakup i wymianę opon" + (kl ? " dla " + kl : "") + ".", ""];
    const keys = vars.map((v) => v.key);
    const per_car = rows.some((r) => r.p && (r.rej || r.pojazd));
    for (const v of vars) {
      const key = v.key[0] + "\u0001" + v.key[1];
      L.push("WARIANT: " + vlabel(keys, v.key).toUpperCase());
      const mine = rows.filter((r) => r.p && r.wariant === key);
      if (per_car) for (const r of mine) {
        const p = r.p, kto = [r.rej, r.pojazd].filter(Boolean).join(" ") || r.rozmiar;
        L.push(`• ${kto}: ${title(p.producent)} ${p.model_oferta} ${r.rozmiar} ${p.indeks} – ${pl(p.cena_brutto)} brutto/szt. × ${r.ilosc} = ${pl(r.opony)}`);
      } else {
        const seen = new Map();
        for (const r of mine) { const e = seen.get(r.p.id) || [r.p, r.rozmiar, 0]; e[2] += r.ilosc; seen.set(r.p.id, e); }
        for (const [p, s, q] of seen.values()) L.push(`• ${title(p.producent)} ${p.model_oferta} ${s} ${p.indeks} – ${pl(p.cena_brutto)} brutto/szt. × ${q} = ${pl(p.cena_brutto * q)}`);
      }
      const parts = [];
      if (v.opony) parts.push("Opony: " + pl(v.opony));
      if (v.wymiana) parts.push("Wymiana: " + pl(v.wymiana));
      if (v.tpms_kw) parts.push("Czujniki TPMS: " + pl(v.tpms_kw));
      if (v.przech_kw) parts.push("Przechowalnia: " + pl(v.przech_kw));
      L.push(parts.concat(["RAZEM: " + pl(total(v)) + " brutto"]).join(" | "));
      L.push("");
    }
    const us = rows.filter((r) => r.uslugi);
    if (us.length) {
      L.push("USŁUGI DODATKOWE");
      const seen = new Set();
      for (const r of us) {
        const k = r.rej + "|" + r.rozmiar; if (seen.has(k)) continue; seen.add(k);
        const kto = [r.pojazd, r.rej].filter(Boolean).join(" ") || r.rozmiar;
        if (r.tpms_kw) L.push(`• ${kto} – ${r.tpms_op} = ${pl(r.tpms_kw)}`);
        if (r.przech_kw) L.push(`• ${kto} – ${r.przech_op} = ${pl(r.przech_kw)}`);
      }
      L.push("");
    }
    L.push("GWARANCJA",
      "• Gwarancja producenta na wady fabryczne (materiałowe i produkcyjne) – standardowo do 5 lat od daty produkcji.",
      "• Nie obejmuje uszkodzeń mechanicznych (przebicia, przecięcia, uderzenia), jazdy na niewłaściwym ciśnieniu, złej geometrii ani naturalnego zużycia.",
      "• Reklamację zgłaszają Państwo w naszym serwisie z dowodem zakupu; oponę przekazujemy do oceny producenta.", "",
      `Ceny ważne ${cfg.waznosc_dni} dni, z zastrzeżeniem dostępności.`, "", "Z poważaniem,", cfg.podpis);
    return L.join("\n");
  };

  // ------------------------------------------------------------ historia (format zgodny z Panelem)
  const now = () => { const d = new Date(), p = (n) => String(n).padStart(2, "0"); return { d, p }; };
  S.nowy_oid = () => { const { d, p } = now(); return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}_${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}`; };
  const data_txt = () => { const { d, p } = now(); return `${p(d.getDate())}.${p(d.getMonth() + 1)}.${d.getFullYear()} ${p(d.getHours())}:${p(d.getMinutes())}`; };

  async function save_hist(req, summ) {
    if (!S.HIST) return;
    const oid = String(req.oid || S.nowy_oid()).replace(/[^0-9_]/g, "") || S.nowy_oid();
    const rec = { osobno: req.osobno, marza: req.marza, rabat: req.rabat, ceny: req.ceny || {}, oid, data: data_txt(), klient: req.klient || "",
      pojazdy: req.pojazdy || [], wybor: req.wybor || {}, sel: req.sel || [], warianty: summ, plik: "", zrodlo: "telefon", oddzial: req.oddzial || "" };
    const hay = (rec.klient + " " + rec.pojazdy.map((v) => (v.rej || "") + " " + (v.pojazd || "") + " " + (v.rozmiar || "")).join(" ") + " " + summ.flatMap((w) => w.modele).join(" ")).toLowerCase();
    await S.HIST.save(oid, rec.klient, rec, hay);
  }
  S.list_hist = async function (q) {
    const recs = S.HIST ? await S.HIST.list(q || "") : [];
    return recs.filter((row) => row.dane && row.dane.oid).map((row) => {
      const r = row.dane;
      return { id: row.id, kto: row.kto || row.owner || "", owner: row.owner || "", oid: r.oid, data: r.data, klient: r.klient || "",
        pojazdy: (r.pojazdy || []).map((v) => [v.rej, v.pojazd].filter(Boolean).join(" ") || v.rozmiar || "").join(", "),
        warianty: (r.warianty || []).map((w) => ({ wariant: w.wariant, modele: (w.modele || []).join(", "), razem: w.razem })),
        razem: Math.max(0, ...(r.warianty || []).map((w) => w.razem || 0)), zrodlo: r.zrodlo || "Panel" };
    });
  };

  // ------------------------------------------------------------ PDF oferty (jak pdf_dane/wypelnij w silnik.py)
  const OSTATNIA = {};
  const EU_KOLORY = [["A", "#00A651", "#fff"], ["B", "#4CB848", "#fff"], ["C", "#BFD730", "#111"], ["D", "#FFF200", "#111"], ["E", "#F7941D", "#fff"]];
  const KLASA_PDF = { PREMIUM: "PREMIUM", MIDDLE: "ŚREDNIA", BUDGET: "BUDŻET" };
  const esc = (v) => String(v).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  const reEsc = (t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const szukaj = (stos, k) => { for (let i = stos.length - 1; i >= 0; i--) { const c = stos[i]; if (c && typeof c === "object" && !Array.isArray(c) && k in c) return c[k]; } return null; };
  const pusty = (v) => !v || (Array.isArray(v) && !v.length);
  function wypelnij(tpl, ctx, stos0) {
    const stos = (stos0 || []).concat([ctx]), out = [], TAG = /\{\{(\{?)([#^/>]?)\s*([\w.]+)\s*\}?\}\}/g;
    let i = 0;
    for (;;) {
      TAG.lastIndex = i; const m = TAG.exec(tpl);
      if (!m) { out.push(tpl.slice(i)); break; }
      out.push(tpl.slice(i, m.index));
      const raw = m[1], typ = m[2], k = m[3];
      if (typ === "#" || typ === "^") {
        const zn = new RegExp("\\{\\{([#^/])\\s*" + reEsc(k) + "\\s*\\}\\}", "g");
        let glab = 1, j = m.index + m[0].length, koniec = j;
        while (glab) { zn.lastIndex = j; const n = zn.exec(tpl); if (!n) throw new Error("wzór: brak {{/" + k + "}}"); glab += n[1] === "/" ? -1 : 1; koniec = n.index; j = n.index + n[0].length; }
        const wn = tpl.slice(m.index + m[0].length, koniec), v = szukaj(stos, k);
        if (typ === "^") { if (pusty(v)) out.push(wypelnij(wn, {}, stos)); }
        else if (Array.isArray(v)) for (const e of v) out.push(wypelnij(wn, e && typeof e === "object" ? e : { ".": e }, stos));
        else if (v) out.push(wypelnij(wn, typeof v === "object" ? v : {}, stos));
        i = j; continue;
      }
      const v = szukaj(stos, k);
      out.push(v === null || v === undefined || v === false ? "" : raw ? String(v) : esc(v));
      i = m.index + m[0].length;
    }
    return out.join("");
  }
  S.wypelnij = wypelnij;
  S.wzor_pdf = function () {   // wzór + fragmenty z dołu pliku wstawione w {{>nazwa}} (jak w silnik.py)
    const cz = (root.PDF_WZOR || "").split(/<!--(\w+)-->/);
    let t = cz[0]; const frag = {};
    for (let i = 1; i < cz.length - 1; i += 2) frag[cz[i]] = cz[i + 1].trim();
    for (let n = 0; n < 3; n++) for (const [k, v] of Object.entries(frag)) t = t.split("{{>" + k + "}}").join(v);
    return t;
  };
  const skala = (lit) => EU_KOLORY.map(([l, k, t], i) => ({ l, kolor: k, tekst: t, szer: 34 + 9 * i, on: l === lit }));
  const p2 = (n) => String(n).padStart(2, "0");
  function data_oid(oid, dni) {
    let d = new Date(Date.UTC(+oid.slice(0, 4), +oid.slice(4, 6) - 1, +oid.slice(6, 8)));
    if (isNaN(d) || !/^\d{8}/.test(oid)) { const t = new Date(); d = new Date(Date.UTC(t.getFullYear(), t.getMonth(), t.getDate())); }
    d = new Date(d.getTime() + (dni || 0) * 864e5);
    return p2(d.getUTCDate()) + "." + p2(d.getUTCMonth() + 1) + "." + d.getUTCFullYear();
  }
  const g = (n) => String(n).replace(".", ",");
  S.pdf_dane = function (cfg, req, rows, pid, oddzial, kto, logo) {
    const R = rows.filter((r) => r.p && r.p.id === pid);
    if (!R.length) throw new Error("Tej opony nie ma w ofercie – wygeneruj ofertę ponownie.");
    if (!oddzial || !["nazwa", "adres", "tel"].every((k) => (oddzial[k] || "").trim())) throw new Error("Brak danych oddziału (nazwa, adres, telefon) – administrator uzupełnia je w Panelu: Ustawienia → Oddziały.");
    const p = R[0].p, vat = parseFloat(cfg.vat_proc || 23);
    let rab = parseFloat(req.rabat || 0); rab = isNaN(rab) ? 0 : Math.max(0, Math.min(90, rab));
    const przed_szt = p.recznie || !rab ? p.cena_brutto : sell_price(cfg, p.netto);
    const il = R.reduce((a, r) => a + (parseInt(r.ilosc, 10) || 0), 0);
    const poz = [{ nazwa: "Opona " + p.nazwa, q: il, j: "szt.", c: przed_szt }];
    const kola = parseInt(cfg.kola_na_auto, 10), wym = new Map();
    for (const r of R) if (r.wymiana) {
      const n = (parseInt(r.ilosc, 10) || 0) || kola, dia = (/R(\d{2})/.exec(r.rozmiar || "") || [null, ""])[1], typ = r.typ || "osobowy";
      const key = [dia, typ, r2(r.wymiana / n)].join("\u0001"); wym.set(key, (wym.get(key) || 0) + n);
    }
    for (const [key, n] of wym) { const [dia, typ, c] = key.split("\u0001"); poz.push({ nazwa: `Wymiana opon – demontaż, montaż, wyważenie (R${dia}${typ === "osobowy" ? "" : ", " + (TYPY[typ] || typ)})`, q: n, j: "szt.", c: +c }); }
    const n_tp = R.reduce((a, r) => a + (parseInt(r.tpms, 10) || 0), 0);
    if (n_tp) poz.push({ nazwa: "Czujnik ciśnienia TPMS (z montażem)", q: n_tp, j: "szt.", c: parseFloat(cfg.tpms_cena) });
    const dep = new Map();
    for (const r of R) if (r.przech_kw) { const key = r.przech_op + "\u0001" + r.przech_kw; dep.set(key, (dep.get(key) || 0) + 1); }
    for (const [key, n] of dep) { const [op, c] = key.split("\u0001"); poz.push({ nazwa: "Depozyt – " + op.slice(0, 1).toLowerCase() + op.slice(1) + ", 1 sezon", q: n, j: "kpl.", c: +c }); }
    const przed = r2(poz.reduce((a, x) => a + x.q * x.c, 0)), rabat_kw = r2((przed_szt - p.cena_brutto) * il);
    const brutto = r2(przed - rabat_kw), netto = r2(brutto / (1 + vat / 100)), oid = String(req.oid || "");
    const poj = [];
    for (const r of R) { const t = [(r.pojazd || "").trim(), (r.rej || "").trim().toUpperCase()].filter(Boolean).join(" · "); if (t && !poj.includes(t)) poj.push(t); }
    const cechy = Object.assign({}, CECHY[pid] || {}, Object.fromEntries(Object.entries(p.attrs || {}).filter(([, v]) => v)));
    const hk = (cechy["Hałas"] || "").trim().slice(0, 1).toUpperCase();
    const eprel = (cechy["Kod EPREL"] || "").replace(/\D/g, "").slice(0, 12);
    return {
      logo: logo || "", nr: oid.length >= 13 ? `OF/${oid.slice(0, 4)}/${oid.slice(4, 6)}/${oid.slice(6, 8)}-${oid.slice(9, 13)}` : "OF/" + oid,
      data: data_oid(oid, 0), wazna: data_oid(oid, parseInt(cfg.waznosc_dni || 7, 10)),
      o_nazwa: oddzial.nazwa || "", o_adres: oddzial.adres || "", o_tel: oddzial.tel || "", o_www: oddzial.www || "", o_email: oddzial.email || "",
      o_kom: (oddzial.kom || "").split(/[,;]/).map((t) => t.trim()).filter(Boolean).map((t) => ({ t })), xp_id: String(p.id || ""),
      klient: (req.klient || "").trim(), pojazd: poj.join(", "), kto: kto || "",
      tag: "OPONA " + (p.sezon || "").toUpperCase() + (KLASA_PDF[p.klasa] ? " · " + KLASA_PDF[p.klasa] : "") + (p.demo ? " · DEMO" : ""),
      tytul: p.nazwa, producent: p.producent || "", model: p.model || "", rozmiar: R[0].rozmiar || "", indeks: p.indeks || "", dot: p.dot || "",
      foto: p.foto || "", ean: p.ean || "", eu: !!(p.mokra || p.opory || p.halas) || !!eprel, ma_opory: !!p.opory, ma_mokra: !!p.mokra,
      skala_opory: skala(p.opory), skala_mokra: skala(p.mokra), halas: p.halas || "", halas_klasa: ["A", "B", "C"].includes(hk) ? hk : "",
      snieg: !!(cechy["Przyczepność na śniegu"] || "").trim(), lod: !!(cechy["Przyczepność na lodzie"] || "").trim(),
      eprel, eprel_img: eprel ? `https://eprel.ec.europa.eu/api/products/tyres/${eprel}/labels?format=PNG` : "",
      cena_szt: pl(p.cena_brutto), cena_szt_netto: pl(r2(p.cena_brutto / (1 + vat / 100))),
      pozycje: poz.map((x) => ({ nazwa: x.nazwa, ilosc: x.q + " " + x.j, cena: pl(x.c), wartosc: pl(r2(x.q * x.c)) })),
      rabat: rabat_kw > 0 ? g(rab) + "%" : "", przed: pl(przed), rabat_kw: pl(rabat_kw),
      netto: pl(netto), vat: pl(r2(brutto - netto)), vat_proc: g(vat), brutto: pl(brutto),
    };
  };
  S.pdf_html = (cfg, req, rows, pid, oddzial, kto, logo) => wypelnij(S.wzor_pdf(), S.pdf_dane(cfg, req, rows, pid, oddzial, kto, logo));
  S.polacz_strony = function (strony) {   // jak polacz_strony w silnik.py
    if (strony.length === 1) return strony[0];
    const glowa = strony[0].split("<body>")[0];
    const srodki = strony.map((h) => { const b = h.slice(h.indexOf("<body>") + 6); return b.slice(0, b.lastIndexOf("</body>")); });
    return glowa.replace("</head>", "<style>.page{break-after:page}.page:last-of-type{break-after:auto}</style></head>") + "<body>" + srodki.join("") + "</body></html>";
  };
  S.oddzial_oferty = function (req) {
    const moje = S.KONTO.oddzialy || [], dane = S.KONTO.oddzialy_dane || {};
    if (!moje.length) throw new Error("Twoje konto nie ma przypisanego oddziału – poproś administratora (Panel → UŻYTKOWNICY → konto → oddziały).");
    const o = moje.includes(req.oddzial) ? req.oddzial : moje[0];
    return [o, Object.assign({}, dane[o] || {}, { nazwa: (dane[o] || {}).nazwa || o })];
  };
  S.opis_pol = function (items) {
    if (!items.length) return "";
    const p = items[0], et = ["Opory toczenia", "Przyczepność na mokrej nawierzchni", "Poziom hałasu", "Hałas"].filter((k) => p.attrs[k]);
    return `\nZdjęcie opony: ${p.foto ? "TAK" : "brak"} · EAN: ${p.ean ? "TAK" : "brak"} · etykieta UE: ${et.join(", ") || "brak"}\nPola produktu: ${(p.pola || []).join(", ")}\nCechy: ${Object.keys(p.attrs).sort().join(", ")}`;
  };

  // ------------------------------------------------------------ polecenia (jak handle() w Panelu)
  const root_Z = () => (typeof window !== "undefined" ? window : globalThis).Zamowienia || require("./zamowienia.js");
  S.handle = async function (path, body) {
    const u = new URL(path, "http://x"), route = u.pathname, qs = u.searchParams;
    const cfg = S.load_cfg();
    S.ucz_marki(cfg);
    try {
      if (body === null || body === undefined) {
        if (route === "/api/cfg") { const c = Object.assign({}, cfg); c.login = cfg.login ? "tak" : ""; c.password = ""; c.marki_xp = MARKI_STALE; c.oddzialy = S.KONTO.oddzialy || []; c.oddzialy_dane = S.KONTO.oddzialy_dane || {}; return [200, c]; }
        if (route === "/api/zamowienia" || route === "/api/zamkniete" || route === "/api/faktury" || route === "/api/faktura") {
          if (!S.KONTO.zamowienia) return [403, { error: "Brak dostępu do zamówień – poproś administratora (UŻYTKOWNICY → moduł Zamówienia)." }];
          return await root_Z().handle(route, Object.fromEntries(qs.entries()), cfg, !!S.KONTO.admin, S.KONTO.oddzialy || []);
        }
        if (route === "/api/history") {
          if (qs.get("id")) { const r = S.HIST ? await S.HIST.get_id(qs.get("id")) : null; return r ? [200, r] : [404, { error: "Brak oferty" }]; }
          return [200, { lista: await S.list_hist(qs.get("q") || ""), admin: !!(S.HIST && S.HIST.admin) }];
        }
        return [404, { error: "404" }];
      }
      if (route === "/api/cfg") { for (const k of Object.keys(DEFAULT_CFG)) if (k in body) cfg[k] = body[k]; await S.save_cfg(cfg); return [200, { ok: true }]; }
      if (route === "/api/test") { const [count, items] = await S.api_call(cfg, { productName: "205/55 R16", resultsPerPage: 1 }); return [200, { ok: true, msg: `Połączono z xPartner. Przykładowe zapytanie zwróciło ${count} produktów.` + S.opis_pol(items) }]; }
      if (route === "/api/pdf") {
        if (!OSTATNIA.rows) return [400, { error: "Najpierw wygeneruj ofertę." }];
        const ids = (body.ids || [body.id || 0]).map((x) => +x || 0).slice(0, 30);   // jak w silnik.py
        for (const pid of ids) if (!CECHY[pid] && S.KONTO.katalog_cechy) { try { zapamietaj_cechy({ id: pid, attrs: (await S.KONTO.katalog_cechy(pid)) || {} }); } catch (e) { /* bez cech z pliku */ } }
        const [o, dane] = S.oddzial_oferty({ oddzial: body.oddzial || OSTATNIA.req.oddzial });
        const strony = ids.map((pid) => S.pdf_html(cfg, OSTATNIA.req, OSTATNIA.rows, pid, dane, S.KONTO.kto || "", body.logo || ""));
        return [200, { html: S.polacz_strony(strony), oddzial: o, stron: strony.length }];
      }
      if (route === "/api/quick") return [200, S.parse_quick(body.text || "")];
      if (route === "/api/parse") { const t = body.text || "", q = S.parse_quick(t); return [200, { pojazdy: S.parse_request_text(t), kryteria: { sezony: q.sezony, klasy: q.klasy, producenci: q.producenci, runflat: q.runflat } }]; }
      if (route === "/api/search") return [200, await S.do_search(cfg, body)];
      if (route === "/api/offer") {
        const { rows, variants, warnings } = await S.build_offer(cfg, body);
        OSTATNIA.req = body; OSTATNIA.rows = rows;
        if (!rows.length) return [400, { error: "Brak wybranych opon." }];
        const keys = variants.map((v) => v.key);
        const summ = variants.map((v) => ({ wariant: vlabel(keys, v.key), modele: v.modele, opony: r2(v.opony), wymiana: r2(v.wymiana),
          tpms: r2(v.tpms_kw), przech: r2(v.przech_kw), razem: r2(total(v)) }));
        const ul = [], seen = new Set();
        for (const r of rows) if (r.p && !seen.has(r.p.id)) { seen.add(r.p.id); ul.push({ id: r.p.id, nazwa: r.p.nazwa, cena: r.p.cena_brutto, auto: r.p.cena_auto, recznie: r.p.recznie, zakup: r.p.brutto_zak, url: S.leaflet_url(r.p.id, r.p.cena_brutto) }); }
        try { await save_hist(body, summ); } catch (e) { warnings.push("Nie zapisano oferty w historii: " + (e.message || e)); }
        return [200, { ulotki: ul, plik: "", oddzialy: S.KONTO.oddzialy || [], email: S.email_text(cfg, body, rows, variants), warianty: summ, uwagi: warnings }];
      }
    } catch (e) {
      if (e instanceof ApiError) return [502, { error: e.message }];
      return [500, { error: (e && e.message) || String(e) }];
    }
    return [404, { error: "404" }];
  };

  root.Silnik = S;
  if (typeof module !== "undefined") module.exports = S;
})(typeof window !== "undefined" ? window : globalThis);
