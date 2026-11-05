const fs = require("fs");
const S = require("../www/silnik.js");
const inp = JSON.parse(fs.readFileSync(0, "utf8"));
const DB = inp.DB;
S.api_call = async (cfg, q) => {
  let it;
  if ("productId" in q) it = DB.filter((p) => p.id === +q.productId);
  else it = q.page ? [] : DB.filter((p) => p.nazwa.includes(q.productName || ""));
  return [it.length, it.map((p) => JSON.parse(JSON.stringify(p)))];
};
S.KONTO = { login: "x", password: "y", ustawienia: {}, zapisz: async () => {} };
S.HIST = { save: async () => {}, list: async () => [], get_id: async () => null };
(async () => {
  const cfg = S.load_cfg(); S.ucz_marki(cfg);
  const out = {
    quick: inp.TEKSTY.map(S.parse_quick), parse: inp.TEKSTY.map(S.parse_request_text),
    marki: inp.SLOWA.map(S.brand_of_word), sizes: inp.TEKSTY.map(S.find_sizes),
  };
  const keep = ["sezon", "producent", "klasa", "model", "indeks", "dot", "standard", "cena_brutto", "mokra", "halas", "homol", "demo", "model_oferta"];
  out.enrich = DB.map((p) => { const e = S.enrich(cfg, p); const o = {}; for (const k of keep) o[k] = e[k]; return o; });
  const cfg2 = Object.assign({}, cfg, { narzut_tryb: "kwota" });
  out.ceny = [100, 236.44, 300, 325.2, 344.10, 500, 731.0, 800].map((n) => [S.sell_price(cfg, n), S.sell_price(cfg2, n)]);
  out.search = [];
  for (const r of inp.reqs) { const w = (await S.do_search(cfg, r)).wyniki; const o = {}; for (const [s, d] of Object.entries(w)) { o[s] = {}; for (const [g, l] of Object.entries(d)) o[s][g] = l.map((p) => p.id); } out.search.push(o); }
  out.offer = [];
  for (const o of inp.offers) { const [c, r] = await S.handle("/api/offer", JSON.parse(JSON.stringify(o))); if (c !== 200) { out.offer.push({ err: r }); continue; }
    out.offer.push({ warianty: r.warianty, email: r.email, uwagi: r.uwagi, ulotki: r.ulotki.map((u) => [u.id, u.cena]) }); }
  process.stdout.write(JSON.stringify(out));
})().catch((e) => { console.error(e.stack); process.exit(1); });
