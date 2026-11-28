const fs = require("fs");
const inp = JSON.parse(fs.readFileSync(0, "utf8"));
globalThis.PDF_WZOR = inp.WZOR; globalThis.PDF_POROWNANIE = inp.POROWNANIE;
const S = require("../www/silnik.js");
const DB = inp.DB;
S.api_call = async (cfg, q) => {
  let it;
  if ("productId" in q) it = DB.filter((p) => p.id === +q.productId);
  else it = q.page ? [] : DB.filter((p) => p.nazwa.includes(q.productName || ""));
  return [it.length, it.map((p) => JSON.parse(JSON.stringify(p)))];
};
S.KONTO = { login: "x", password: "y", ustawienia: {}, zapisz: async () => {}, oddzialy: ["Latex Wrocław"], oddzialy_dane: inp.ODDZ, kto: "Test" };
S.HIST = { save: async () => {}, list: async () => [], get_id: async () => null };
(async () => {
  const cfg = S.load_cfg(); S.ucz_marki(cfg);
  const out = {
    quick: inp.TEKSTY.map(S.parse_quick), parse: inp.TEKSTY.map(S.parse_request_text),
    marki: inp.SLOWA.map(S.brand_of_word), sizes: inp.TEKSTY.map(S.find_sizes),
  };
  const keep = ["sezon", "producent", "klasa", "model", "indeks", "dot", "standard", "cena_brutto", "mokra", "halas", "homol", "demo", "model_oferta", "nosnosc", "predkosc", "rant", "homol_kod"];
  out.enrich = DB.map((p) => { const e = S.enrich(cfg, p); const o = {}; for (const k of keep) o[k] = e[k]; return o; });
  const cfg2 = Object.assign({}, cfg, { narzut_tryb: "kwota" });
  out.ceny = [100, 236.44, 300, 325.2, 344.10, 500, 731.0, 800].map((n) => [S.sell_price(cfg, n), S.sell_price(cfg2, n)]);
  out.search = [];
  for (const r of inp.reqs) { const w = (await S.do_search(cfg, r)).wyniki; const o = {}; for (const [s, d] of Object.entries(w)) { o[s] = {}; for (const [g, l] of Object.entries(d)) o[s][g] = l.map((p) => p.id); } out.search.push(o); }
  out.offer = []; out.pdf = [];
  for (const o of inp.offers) { const [c, r] = await S.handle("/api/offer", JSON.parse(JSON.stringify(o))); if (c !== 200) { out.offer.push({ err: r }); continue; }
    out.offer.push({ warianty: r.warianty, uwagi: r.uwagi, ulotki: r.ulotki.map((u) => [u.id, u.cena, u.szt]) });
    for (const u of r.ulotki) { const [c2, r2] = await S.handle("/api/pdf", { id: u.id, logo: "logo.png" }); out.pdf.push(r2.html || null); }
    if (r.ulotki.length > 1) out.pdf.push((await S.handle("/api/pdf", { ids: r.ulotki.map((u) => u.id), logo: "logo.png" }))[1].html || null);
    if (r.ulotki.length >= 2 && r.ulotki.length <= 3) out.pdf.push((await S.handle("/api/pdf", { ids: r.ulotki.map((u) => u.id), porownanie: 1, logo: "logo.png" }))[1].html || null);
    out.offer[out.offer.length - 1].snap = S.snap_ofert(S._ostatnia().rows);
    out.offer[out.offer.length - 1].zmiany = S.zmiany_ofert([{ id: 1, nazwa: "A", cena: 1, ilosc: 99 }, { id: 999, nazwa: "B", cena: 5, ilosc: 1 }], S._ostatnia().rows); }
  for (const k of Object.keys(S.CECHY)) delete S.CECHY[k];
  S.KONTO.katalog = async (sz) => (sz === "205/55 R16" ? [JSON.parse(JSON.stringify(inp.PLIK))] : null);
  S.KONTO.katalog_info = () => "z pliku";
  const [, rs] = await S.handle("/api/search", { pojazdy: [{ rozmiar: "205/55 R16", ilosc: 4, nowe: true }], sezony: ["Zimowa"] });
  out.plik_search = [rs.zrodlo, Object.fromEntries(Object.entries(rs.wyniki["205/55 R16"]).map(([g, l]) => [g, l.map((p) => p.id)]))];
  await S.handle("/api/offer", { oid: "20261106_090000", pojazdy: [{ rozmiar: "205/55 R16", ilosc: 4, nowe: true, wymiana: true }], wybor: { "205/55 R16": { x: [inp.PLIK.id] } } });
  out.plik_pdf = [(await S.handle("/api/pdf", { id: inp.PLIK.id, logo: "logo.png" }))[1].html];
  out.homol = inp.HOM.map((a) => [S.homol_cecha({ attrs: a }), S.enrich(cfg, { nazwa: "205/55 R16 91V NA0 TEST", attrs: a, netto: 1 }).homol]);
  out.gwiazdka = inp.GW.map(([n, a]) => S.enrich(cfg, { nazwa: n, attrs: a, netto: 1 }).homol);
  S.KONTO.katalog_produkt = async (k) => (k === String(inp.PLIK.id) || k === (inp.PLIK.ean || "-") ? [JSON.parse(JSON.stringify(inp.PLIK))] : []);
  out.kod = []; for (const t of [String(inp.PLIK.id), "ABC123456789", "xyz"]) out.kod.push((await S.handle("/api/quick", { text: t }))[1]);
  out.cfg = [];
  for (const [adm, odd] of [[false, ["Latex Wrocław"]], [true, ["Latex Wrocław"]], [false, ["Latex Opole"]]]) {
    const zap = [];
    Object.assign(S.KONTO, { admin: adm, oddzialy_konta: odd, ceny_oddz: JSON.parse(JSON.stringify(inp.CENY_ODDZ)), ustawienia: { marza_proc: 20, tpms_cena: 50 },
      zapisz_ceny: async (o, d) => zap.push([o, d]), zapisz: async (d) => zap.push(["osobiste", d.marza_proc, d.tpms_cena, d.vat_proc]) });
    const c = (await S.handle("/api/cfg", null))[1];
    await S.handle("/api/cfg", { marza_proc: 40, tpms_cena: 120, vat_proc: 23 });
    out.cfg.push([c.marza_proc, c.tpms_cena, c.wymiana_kolo["16"], c.ceny_oddzial, c.ceny_edycja, zap]);
  }
  process.stdout.write(JSON.stringify(out));
})().catch((e) => { console.error(e.stack); process.exit(1); });
