// Oferty opon – ekran telefonu. Logika jak w Panelu (app/oferty/index.html), silnik w silnik.js (Silnik.handle).
const $ = (s) => document.querySelector(s);
let CFG = {}, RES = null, VEH = [], SEL = new Set(), PAGE = {}, SORT = "", OID = null, ORABAT = "", CENY = {}, ULS = [], OSOBNO = null, ORABW = "", CENYW = {}, WYMS = [];
const F = { wet: "", rr: "", noise: "", hom: "", demo: "", txt: "" };
const PER = 20;
const zl = (x) => (+x || 0).toLocaleString("pl-PL", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " zł";
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
async function api(p, b) { const [code, body] = await Silnik.handle(p, b === undefined ? null : b); if (code >= 400) throw new Error((body && body.error) || "Błąd programu"); return body; }
function msg(el, t, e) { $(el).innerHTML = t ? `<div class="msg ${e ? "e" : "i"}">${esc(t)}</div>` : ""; }
function toast(t) { const el = $("#toast"); el.textContent = t; el.hidden = false; clearTimeout(toast._t); toast._t = setTimeout(() => (el.hidden = true), 2200); }
const LSx = { get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }, set(k, v) { try { localStorage.setItem(k, v); } catch (e) {} } };

// ------------------------------------------------ start, logowanie, zakładki
function pokaz(zalogowany) {
  $("#vLogin").hidden = zalogowany;
  for (const id of ["#top", "#tabs"]) $(id).hidden = !zalogowany;
  if (zalogowany) go(document.querySelector("#tabs button.on")); else { for (const v of ["#vOferta", "#vHist", "#vWyn", "#vZam", "#vUst"]) $(v).hidden = true; $("#selBar").hidden = true; }
}
async function startApp() {
  $("#lVer").textContent = "Wersja aplikacji: " + Aplikacja.wersja();
  if (!Aplikacja.zalogowany()) return pokaz(false);
  try {
    const p = await Aplikacja.start();
    $("#tUser").textContent = (p.name || p.email) + (p.role === "admin" ? " · administrator" : "");
    $("#kInfo").textContent = "Zalogowano: " + p.email + ". Wersja aplikacji: " + Aplikacja.wersja();
    const M = Aplikacja.moze;   // zakładki wg uprawnień (jak w Panelu)
    for (const v of ["vOferta", "vHist"]) document.querySelector(`#tabs button[data-v="${v}"]`).hidden = !M.oferty;
    document.querySelector('#tabs button[data-v="vWyn"]').hidden = !M.wyniki;
    document.querySelector('#tabs button[data-v="vZam"]').hidden = !M.zamowienia; $("#zbF").hidden = p.role !== "admin";
    $("#ustOferty").hidden = !M.oferty; $("#top .icon").hidden = !M.oferty;
    $("#tTitle").textContent = M.oferty ? "Oferty opon" : "Wyniki marży";
    const on = document.querySelector("#tabs button.on");
    if (!on || on.hidden) document.querySelectorAll("#tabs button").forEach((b) => b.classList.toggle("on", b === pierwszaZakladka()));
    pokaz(true); if (M.oferty) { await loadCfg(); if (!VEH.length) { addVeh({}); drawVeh(); } }
    sprawdzAkt(false);
  } catch (e) { pokaz(false); msg("#lMsg", e.message, 1); }
}
async function zaloguj() {
  const b = $("#bLogin"); b.disabled = true; msg("#lMsg", "Loguję…");
  try { await Aplikacja.login($("#lEmail").value, $("#lPass").value); $("#lPass").value = ""; msg("#lMsg", ""); await startApp(); }
  catch (e) { msg("#lMsg", e.message, 1); }
  b.disabled = false;
}
async function wyloguj() { if (!confirm("Wylogować z aplikacji?")) return; await Aplikacja.logout(); location.reload(); }
function go(b) {
  document.querySelectorAll("#tabs button").forEach((x) => x.classList.toggle("on", x === b));
  for (const v of ["vOferta", "vHist", "vWyn", "vZam", "vUst"]) $("#" + v).hidden = v !== b.dataset.v;
  updCnt();
  if (b.dataset.v === "vHist") loadHist();
  if (b.dataset.v === "vWyn") loadWyn();
  if (b.dataset.v === "vZam" && !ZD) zLoad();
  if (b.dataset.v === "vUst" && Aplikacja.moze.oferty) openCfg();
  window.scrollTo(0, 0);
}
async function sprawdzAkt(reczne) {
  const j = await Aplikacja.sprawdzAktualizacje();
  if (j && j.url) { const u = $("#upd"); u.innerHTML = `<span class="grow">Jest nowa wersja aplikacji ${esc(j.version)}.</span><button class="btn" onclick="Aplikacja.openUrl('${esc(j.url)}')">Aktualizuj</button>`; u.hidden = false; }
  else if (reczne) toast(j && j.blad ? "Nie udało się sprawdzić aktualizacji – sprawdź internet albo spróbuj później." : "Masz najnowszą wersję (" + Aplikacja.wersja() + ").");
}

// ------------------------------------------------ kryteria
const SEZ = [["Letnia", "letnie"], ["Zimowa", "zimowe"], ["Całoroczna", "całoroczne"]];  // wartości jak w silniku (sezon z xPartner)
const KL = [["PREMIUM", "premium"], ["MIDDLE", "średnia"], ["BUDGET", "budżet"]];
function drawChips() {
  $("#cSez").innerHTML = SEZ.map(([v, t]) => `<button class="chip sez" data-v="${v}" onclick="this.classList.toggle('on')">${t}</button>`).join("");
  $("#cKl").innerHTML = KL.map(([v, t]) => `<button class="chip kl" data-v="${v}" onclick="this.classList.toggle('on')">${t}</button>`).join("");
}
const chipVals = (c) => [...document.querySelectorAll("." + c + ".on")].map((x) => x.dataset.v);
const setChips = (c, l) => document.querySelectorAll("." + c).forEach((x) => x.classList.toggle("on", l.includes(x.dataset.v)));
let PROD = "";
function setProd(v) { PROD = v || ""; const n = PROD ? PROD.split(",").filter((x) => x.trim()).length : 0; $("#prodBtn").textContent = n ? (n <= 3 ? PROD : n + " producentów") + " ▾" : "Wszyscy producenci ▾"; }

// ------------------------------------------------ pojazdy (karty)
function addVeh(v) { VEH.push(Object.assign({ rej: "", pojazd: "", rozmiar: "", ilosc: 4, wymiana: false, typ: "osobowy", tpms: 0, przech: "" }, v)); }
function drawVeh() {
  const o = (a, b, c) => `<option value="${a}" ${c === a ? "selected" : ""}>${b}</option>`;
  $("#veh").innerHTML = VEH.map((v, i) => `<div class="veh">
    <div class="top"><b>${esc([v.pojazd, v.rej].filter(Boolean).join(" ") || "Pojazd " + (i + 1))}</b>${VEH.length > 1 ? `<button class="btn sec sm" onclick="VEH.splice(${i},1);drawVeh();reoffer()" aria-label="Usuń pojazd">✕</button>` : ""}</div>
    <div class="g">
      <label class="full">Rozmiar opony<input value="${esc(v.rozmiar)}" placeholder="205/55 R16" onchange="setVeh(${i},'rozmiar',this.value)"></label>
      <label>Pojazd<input value="${esc(v.pojazd)}" placeholder="np. Octavia" onchange="setVeh(${i},'pojazd',this.value,1)"></label>
      <label>Rejestracja<input value="${esc(v.rej)}" autocapitalize="characters" onchange="setVeh(${i},'rej',this.value.toUpperCase(),1)"></label>
      <label>Ilość opon<input type="number" inputmode="numeric" min="0" max="20" value="${v.ilosc}" onchange="setVeh(${i},'ilosc',+this.value||0)"></label>
      <label>Typ<select onchange="setVeh(${i},'typ',this.value)">${o("osobowy", "osobowy", v.typ)}${o("suv", "SUV / 4x4", v.typ)}${o("dostawczy", "dostawczy", v.typ)}</select></label>
      <label>Czujniki TPMS<input type="number" inputmode="numeric" min="0" max="8" value="${v.tpms || 0}" onchange="setVeh(${i},'tpms',+this.value||0)"></label>
      <label>Przechowalnia<select onchange="setVeh(${i},'przech',this.value)">${o("", "—", v.przech)}${o("opony", "opony", v.przech)}${o("kola", "koła z felgami", v.przech)}</select></label>
      <label class="chk full"><input type="checkbox" ${v.wymiana ? "checked" : ""} onchange="setVeh(${i},'wymiana',this.checked)">Wymiana (montaż i wyważenie)</label>
    </div></div>`).join("");
}
function setVeh(i, k, v, redraw) { VEH[i][k] = v; if (redraw) drawVeh(); reoffer(); }
const vehicles = () => VEH.map((v) => ({ ...v, rej: v.rej.trim(), pojazd: v.pojazd.trim(), rozmiar: v.rozmiar.trim(), nowe: v.ilosc > 0 })).filter((v) => v.rozmiar);
function keepOrClear() { if (VEH.length === 1 && !vehicles().length) VEH = []; }

// ------------------------------------------------ szybkie polecenie, tekst
async function quick() {
  const b = $("#bQ"); b.disabled = true;
  try {
    const j = await api("/api/quick", { text: $("#quick").value });
    if (!j.pojazdy.length) throw new Error("Nie rozpoznałem rozmiaru opony (np. 205/55 R16).");
    VEH = []; j.pojazdy.forEach(addVeh); drawVeh();
    setChips("sez", j.sezony); setChips("kl", j.klasy); $("#rf").checked = j.runflat; setProd(j.producenci); F.demo = j.demo || "";
    msg("#qMsg", ""); await search();
  } catch (e) { msg("#qMsg", e.message, 1); }
  b.disabled = false;
}
async function parsePaste() {
  try {
    const j = await api("/api/parse", { text: $("#paste").value });
    if (!j.pojazdy.length) return msg("#qMsg", "Nie znalazłem rozmiaru opony w żadnej linii (np. 205/55 R16 albo 2055516).", 1);
    keepOrClear(); j.pojazdy.forEach(addVeh); drawVeh(); $("#paste").value = ""; $("#paste").closest("details").open = false;
    const k = j.kryteria;
    if (k.sezony.length) setChips("sez", k.sezony); if (k.klasy.length) setChips("kl", k.klasy);
    if (k.producenci) setProd(k.producenci); if (k.runflat) $("#rf").checked = true;
    toast("Wczytano pojazdów: " + j.pojazdy.length);
    if (k.sezony.length || k.klasy.length || k.producenci || k.runflat) search();
  } catch (e) { msg("#qMsg", e.message, 1); }
}

// ------------------------------------------------ wyszukiwanie i lista opon
const newOid = () => { const d = new Date(), p = (n) => String(n).padStart(2, "0"); return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}_${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}`; };
async function search() {
  const b = $("#bS"); b.disabled = true; msg("#sMsg", "Szukam w xPartner…");
  try {
    const req = { pojazdy: vehicles(), sezony: chipVals("sez"), klasy: chipVals("kl"), producenci: PROD, min_stan: +$("#minstan").value, tylko_runflat: $("#rf").checked };
    if (!req.pojazdy.some((v) => v.nowe)) throw new Error("Wpisz rozmiar opony i ilość większą od 0.");
    RES = await api("/api/search", req); SEL = new Set(); PAGE = {}; OID = newOid(); ORABAT = ""; CENY = {}; ORABW = ""; CENYW = {}; OSOBNO = null;
    if (req.sezony.length || req.klasy.length || req.producenci.trim())
      for (const [s, g] of Object.entries(RES.wyniki)) for (const [z, l] of Object.entries(g)) l.filter((p) => p.ok_stan).slice(0, 1).forEach((p) => SEL.add(s + "|" + z + "|" + p.id));
    $("#outCard").hidden = true; render(); msg("#sMsg", RES.zrodlo || ""); $("#resCard").hidden = false; $("#resCard").scrollIntoView({ behavior: "smooth" });
  } catch (e) { msg("#sMsg", e.message, 1); }
  b.disabled = false;
}
const lab = (x) => (x ? x.charCodeAt(0) : 99);
const SK = { producent: (p) => p.producent, klasa: (p) => ({ PREMIUM: 0, MIDDLE: 1, BUDGET: 2 }[p.klasa] ?? 3), dot: (p) => -(+p.dot || 0), mokra: (p) => lab(p.mokra), halas: (p) => p.halas || 99, stan: (p) => -p.ilosc, cena: (p) => p.cena_brutto };
function sorted(l) { if (!SORT) return l; const d = SORT[0] === "-" ? -1 : 1, k = SORT.replace("-", ""), f = SK[k] || SK[k.replace("dot", "dot")]; const sgn = k === "dot" || k === "stan" ? 1 : d;
  return [...l].sort((a, b) => { const x = f(a), y = f(b); return (x < y ? -1 : x > y ? 1 : 0) * sgn; }); }
function filt(l) {
  const n = +F.noise || 0, t = F.txt.trim().toUpperCase();
  return l.filter((p) => (!F.wet || (p.mokra && p.mokra <= F.wet)) && (!F.rr || (p.opory && p.opory <= F.rr)) && (!n || (p.halas && p.halas <= n)) && (!F.hom || p.homol.includes(F.hom)) &&
    (!F.demo || (F.demo === "tylko") === !!p.demo) && (!t || (p.nazwa + " " + p.model + " " + p.indeks + " " + p.id).toUpperCase().includes(t)));
}
function render() {
  if (!RES) return;
  const fc = Object.values(F).filter(Boolean).length; $("#fCnt").textContent = fc ? " (" + fc + ")" : "";
  let h = "", gi = 0;
  for (const [s, bySez] of Object.entries(RES.wyniki)) for (const [sez, all] of Object.entries(bySez)) {
    const g = gi++, l = sorted(filt(all)), pages = Math.max(1, Math.ceil(l.length / PER)), pg = Math.min(PAGE[g] || 0, pages - 1); PAGE[g] = pg;
    h += `<div class="grp" id="g_${g}">${esc(s)} · ${esc(sez)} <span class="tag">potrzeba ${RES.potrzeba[s]} szt.</span><span class="tag">${l.length}${l.length !== all.length ? " z " + all.length : ""} poz.</span></div>`;
    if (!l.length) { h += '<p class="muted">Brak opon spełniających kryteria.</p>'; continue; }
    for (const p of l.slice(pg * PER, pg * PER + PER)) {
      const key = s + "|" + sez + "|" + p.id;
      const et = [p.mokra && "mokra " + p.mokra, p.opory && "opory " + p.opory, p.halas && p.halas + " dB"].filter(Boolean).join(" · ");
      h += `<label class="prod ${p.ok_stan ? "" : "bad"}"><span class="ck"><input type="checkbox" data-k="${esc(key)}" onchange="tog(this)" ${SEL.has(key) ? "checked" : ""}></span>
        <span class="b"><div class="t1">${esc(p.producent)} ${esc(p.model)}${p.demo ? ' <span class="demo">DEMO</span>' : ""}</div>
        <div class="t2"><span>${esc(p.sezon)}</span><span>${esc(p.indeks)}</span><span>${esc(p.klasa)}</span>${p.dot ? `<span>DOT ${esc(p.dot)}</span>` : ""}${et ? `<span>${esc(et)}</span>` : ""}${p.homol.filter((x) => x !== "FR").length ? `<span>${esc(p.homol.filter((x) => x !== "FR").join(" "))}</span>` : ""}<span class="muted">ind. ${p.id}</span></div></span>
        <span class="pr"><b>${zl(p.cena_brutto)}</b><small class="${p.ok_stan ? "ok" : ""}">stan ${p.ilosc}</small><br><small class="buy">zakup ${zl(p.brutto_zak)}</small></span></label>`;
    }
    if (pages > 1) h += `<div class="pager"><button class="btn sec sm" ${pg ? "" : "disabled"} onclick="pg(${g},-1)">◀ poprzednie</button><span class="small">${pg + 1} / ${pages}</span><button class="btn sec sm" ${pg < pages - 1 ? "" : "disabled"} onclick="pg(${g},1)">następne ▶</button></div>`;
  }
  $("#res").innerHTML = h; updCnt();
}
function pg(g, d) { PAGE[g] = (PAGE[g] || 0) + d; render(); document.getElementById("g_" + g)?.scrollIntoView({ block: "start" }); }
function tog(c) { c.checked ? SEL.add(c.dataset.k) : SEL.delete(c.dataset.k); updCnt(); }
function updCnt() { const on = !$("#vOferta").hidden && SEL.size > 0; $("#selBar").hidden = !on; $("#bO").textContent = "📄 Generuj ofertę (" + SEL.size + ")"; }
function hideBuy(v) { const on = v === undefined ? !document.body.classList.contains("hidebuy") : !!v; document.body.classList.toggle("hidebuy", on); LSx.set("hidebuy", on ? "1" : ""); }
if (LSx.get("hidebuy")) document.body.classList.add("hidebuy");

// ------------------------------------------------ arkusze: producenci, filtry
function openSheet(h) { $("#sheetBody").innerHTML = h; $("#sheet").hidden = false; }
function closeSheet() { $("#sheet").hidden = true; }
let PSEL = new Set(), PMORE = {};
const PG = [["PREMIUM", "#0B5ED7"], ["MIDDLE", "#F5A000"], ["BUDGET", "#111"]];
const bk = (x) => String(x || "").toUpperCase().replace(/[^A-ZĄĆĘŁŃÓŚŹŻ0-9]/g, "");
function brandGroups() {
  const g = { PREMIUM: new Set(CFG.premium || []), MIDDLE: new Set(CFG.srednie || []), BUDGET: new Set(CFG.budzet || []) };
  const known = new Set([...g.PREMIUM, ...g.MIDDLE, ...g.BUDGET].map(bk));
  for (const m of CFG.marki_xp || []) if (!known.has(bk(m))) { known.add(bk(m)); g.BUDGET.add(m); }
  if (RES) for (const gr of Object.values(RES.wyniki)) for (const l of Object.values(gr)) for (const p of l) if (!known.has(bk(p.producent))) { known.add(bk(p.producent)); (g[p.klasa] || g.BUDGET).add(p.producent); }
  return g;
}
function openProd() {
  PSEL = new Set(PROD.split(",").map((x) => x.trim().toUpperCase()).filter(Boolean)); PMORE = {};
  openSheet(`<div class="h" id="pTitle"></div><input id="pSearch" placeholder="Szukaj producenta…" oninput="drawProd()"><div id="pBody"></div>
    <div class="row" style="margin-top:12px;position:sticky;bottom:0;background:#fff;padding-top:8px"><button class="btn sec grow" onclick="PSEL.clear();drawProd()">Wszyscy</button><button class="btn grow" onclick="setProd([...PSEL].join(', '));closeSheet()">Zastosuj</button></div>`);
  drawProd();
}
function drawProd() {
  const q = $("#pSearch").value.trim().toUpperCase(), g = brandGroups(); let h = "";
  for (const [k, col] of PG) {
    let l = [...g[k]].sort((a, b) => a.localeCompare(b, "pl")); if (q) l = l.filter((b) => b.includes(q)); if (!l.length) continue;
    const all = l.every((b) => PSEL.has(b)), lim = q || PMORE[k] ? l.length : 20;
    h += `<label class="pgrp" style="border-color:${col}"><input type="checkbox" ${all ? "checked" : ""} data-g="${k}" onchange="grpProd(this.dataset.g,this.checked)"> ${k}</label><div class="pgrid">` +
      l.slice(0, lim).map((b) => `<label><input type="checkbox" ${PSEL.has(b) ? "checked" : ""} data-b="${esc(b)}" onchange="this.checked?PSEL.add(this.dataset.b):PSEL.delete(this.dataset.b);drawTitle()">${esc(b)}</label>`).join("") + "</div>" +
      (l.length > lim ? `<button class="btn sec sm" data-g="${k}" onclick="PMORE[this.dataset.g]=1;drawProd()">Więcej (${l.length - lim}) ▾</button>` : "");
  }
  $("#pBody").innerHTML = h || "<p>Brak producentów.</p>"; drawTitle();
}
function grpProd(k, on) { const q = $("#pSearch").value.trim().toUpperCase(); [...brandGroups()[k]].filter((b) => !q || b.includes(q)).forEach((b) => (on ? PSEL.add(b) : PSEL.delete(b))); drawProd(); }
function drawTitle() { $("#pTitle").textContent = "Producenci (" + (PSEL.size ? "wybrano " + PSEL.size : "wszyscy") + ")"; }
const HOM = { MO: "Mercedes (MO)", AO: "Audi (AO/RO)", "*": "BMW (*)", N: "Porsche (N0–N9)", VOL: "Volvo (VOL)", T0: "Tesla (T0)", J: "Jaguar (J)", LR: "Land Rover (LR)", VW: "VW", FR: "rant ochronny felgi" };
function openFil() {
  const have = new Set(); if (RES) for (const g of Object.values(RES.wyniki)) for (const l of Object.values(g)) for (const p of l) p.homol.forEach((h) => have.add(h));
  const o = (v, t, c) => `<option value="${esc(v)}" ${c === v ? "selected" : ""}>${esc(t)}</option>`;
  const abc = (cur) => o("", "dowolne", cur) + ["A", "B", "C", "D", "E"].map((x) => o(x, x + " lub lepsze", cur)).join("");
  openSheet(`<div class="h">Filtry</div>
    <label class="fld">Szukaj w nazwie / indeksie<input id="f_txt" value="${esc(F.txt)}"></label>
    <div class="row2"><label class="fld">Hamowanie na mokrym<select id="f_wet">${abc(F.wet)}</select></label>
    <label class="fld">Opory toczenia<select id="f_rr">${abc(F.rr)}</select></label>
    <label class="fld">Hałas maks. (dB)<input id="f_noise" type="number" inputmode="numeric" value="${esc(F.noise)}"></label>
    <label class="fld">Homologacja<select id="f_hom">${o("", "dowolna", F.hom)}${[...have].map((h) => o(h, HOM[h] || h, F.hom)).join("")}</select></label></div>
    <label class="fld">Opony DEMO<select id="f_demo">${o("", "wszystkie", F.demo)}${o("bez", "bez DEMO", F.demo)}${o("tylko", "tylko DEMO", F.demo)}</select></label>
    <div class="row" style="margin-top:14px"><button class="btn sec grow" onclick="for(const k in F)F[k]='';PAGE={};render();closeSheet()">Wyczyść</button><button class="btn grow" onclick="applyFil()">Pokaż</button></div>`);
}
function applyFil() { for (const k of Object.keys(F)) F[k] = $("#f_" + k).value; PAGE = {}; render(); closeSheet(); }

// ------------------------------------------------ oferta
let RT = null;
function reoffer() { if ($("#outCard").hidden || !SEL.size) return; clearTimeout(RT); RT = setTimeout(() => offer(true), 400); }
function setW(k, v) { v = String(v).replace(",", ".").trim(); if (v === "" || isNaN(+v) || +v < 0) delete CENYW[k]; else CENYW[k] = Math.ceil(+v); reoffer(); }
function setC(id, v) { v = String(v).replace(",", ".").trim(); if (v === "" || +v <= 0) delete CENY[id]; else CENY[id] = Math.ceil(+v); reoffer(); }
async function offer(quiet) {
  const b = $("#bO"); b.disabled = true; if (!quiet) msg("#oMsg", "Odświeżam ceny i stany w xPartner…");
  try {
    const wybor = {}; SEL.forEach((k) => { const [s, z, id] = k.split("|"); ((wybor[s] ??= {})[z] ??= []).push(+id); });
    if (!OID) OID = newOid();
    if (OSOBNO === null) { const V = vehicles().filter((v) => v.nowe); OSOBNO = V.length > 1 && !V.some((v) => v.rej || v.pojazd); }
    const j = await api("/api/offer", { oddzial: OODD, osobno: OSOBNO, oid: OID, sel: [...SEL], klient: $("#klient").value, pojazdy: vehicles(), wybor, marza: "", rabat: ORABAT, ceny: CENY, rabat_wym: ORABW, ceny_wym: CENYW, porownaj: HSNAP || undefined });
    ULS = j.ulotki; WYMS = j.wymiany || [];
    $("#zmBox").innerHTML = j.zmiany && j.zmiany.length ? `<div class="msg w"><b>⚠ Od zapisania (${esc(HDATA)}) zmieniło się w xPartner:</b>${j.zmiany.map((z) => `<div>• ${esc(z.nazwa)}: <b style="color:${z.w_gore ? "#b00012" : "#1b6b2a"}">${esc(z.co)}</b></div>`).join("")}<div class="small">Oferta ma już aktualne ceny i stany.</div></div>` : "";
    msg("#oMsg", j.uwagi.length ? "⚠ " + j.uwagi.join("\n⚠ ") : quiet ? "" : "Zapisano w historii.", j.uwagi.length > 0);
    $("#sum").innerHTML = j.warianty.map((v) => `<div class="vcard"><div class="t">${esc(v.wariant)}</div><div class="m">${esc(v.modele.join(", "))}</div>
      <div class="l"><span>Opony</span><span>${zl(v.opony)}</span></div>${v.wymiana ? `<div class="l"><span>Wymiana</span><span>${zl(v.wymiana)}</span></div>` : ""}
      ${v.tpms ? `<div class="l"><span>Czujniki TPMS</span><span>${zl(v.tpms)}</span></div>` : ""}${v.przech ? `<div class="l"><span>Przechowalnia</span><span>${zl(v.przech)}</span></div>` : ""}
      <div class="tot"><span>RAZEM brutto</span><b>${zl(v.razem)}</b></div></div>`).join("");
    drawUl();
    $("#email").value = j.email; drawEdit();
    const first = $("#outCard").hidden; $("#outCard").hidden = false; if (!quiet || first) $("#outCard").scrollIntoView({ behavior: "smooth" });
  } catch (e) { msg("#oMsg", e.message, 1); $("#outCard").hidden = false; }
  b.disabled = false;
}
let OODD = "", HSNAP = null, HDATA = "";
function drawUl() {
  const od = CFG.oddzialy || []; if (!od.includes(OODD)) OODD = od[0] || "";
  $("#ul").innerHTML = '<div class="lbl">PDF oferty dla klienta – jeden model opony, każda usługa osobno</div>' +
    (od.length > 1 ? `<label class="fld" style="margin-top:0">Oddział na PDF<select onchange="OODD=this.value">${od.map((o) => `<option ${o === OODD ? "selected" : ""}>${esc(o)}</option>`).join("")}</select></label>` : "") +
    (od.length ? "" : '<div class="msg e">Twoje konto nie ma przypisanego oddziału – PDF nie powstanie. Poproś administratora.</div>') +
    (ULS.length > 1 ? `<button class="btn wide" style="margin-top:6px" onclick="pdfOferta(this, true)">📄 Wszystkie (${ULS.length}) w jednym PDF</button>` : "") +
    ULS.map((u) => `<button class="ulk" data-id="${u.id}" data-n="${esc(u.nazwa)}" onclick="pdfOferta(this)"><span>📄 ${esc(u.nazwa)}</span><b>${zl(u.cena)}</b></button>`).join("") +
    (ULS.length >= 2 && ULS.length <= 3 ? `<button class="btn sec wide" style="margin-top:6px" onclick="pdfOferta(this, 2)">⚖ Porównanie ${ULS.length} opon (1 strona)</button>` : "") +
    `<button class="btn wide" style="margin-top:10px" onclick="linkKlient(this)">🔗 Link dla klienta (SMS)</button><div id="linkBox"></div>`;
}
async function linkKlient(b) {
  b.disabled = true; $("#linkBox").innerHTML = '<p class="muted small">Tworzę link…</p>';
  try {
    const j = await api("/api/link", { oddzial: OODD });
    $("#linkBox").innerHTML = `<div class="msg ok">Oferta ważna do ${esc(j.wazna)} (status „Wysłana”).<div class="small" style="word-break:break-all;margin:6px 0">${esc(j.url)}</div>
      <div class="row"><a class="btn grow" href="sms:?body=${encodeURIComponent(j.sms)}">✉ Wyślij SMS</a><button class="btn sec grow" data-t="${esc(j.sms)}" onclick="kopiuj(this)">📋 Kopiuj</button></div></div>`;
  } catch (e) { $("#linkBox").innerHTML = `<div class="msg e">${esc(e.message)}</div>`; }
  b.disabled = false;
}
function kopiuj(b) { const t = b.dataset.t; (navigator.clipboard ? navigator.clipboard.writeText(t) : Promise.reject()).then(() => toast("Skopiowano."), () => toast("Nie udało się skopiować.")); }
async function pdfOferta(b, wszystkie) {
  b.disabled = true; toast("Tworzę PDF…");
  try {
    // logo z plików aplikacji (PDF ładuje się z android_asset/www); „wszystkie” – jeden plik, strona na oponę
    const j = await api("/api/pdf", wszystkie ? { ids: ULS.map((u) => u.id), porownanie: wszystkie === 2 ? 1 : 0, oddzial: OODD, logo: "logo.png" } : { id: +b.dataset.id, oddzial: OODD, logo: "logo.png" });
    const r = await Aplikacja.pdf(j.html, "Oferta " + (OID || "") + " " + (wszystkie === 2 ? "porownanie" : wszystkie ? "wszystkie " + ULS.length : b.dataset.n));
    if (!r.ok) msg("#oMsg", r.msg, 1);
    else if (window.Native) pdfGotowy(r.msg);
  } catch (e) { msg("#oMsg", e.message, 1); }
  b.disabled = false;
}
function pdfGotowy(plik) {   // PDF gotowy w telefonie: najpierw podgląd albo od razu wysyłka
  const d = document.createElement("div"); d.className = "pdfwyb";
  d.innerHTML = `<div class="card"><b>PDF gotowy</b><div class="small muted" style="word-break:break-all;margin:4px 0 10px">${esc(plik)}</div>
    <div class="row"><button class="btn grow" data-a="o">👁 Otwórz</button><button class="btn sec grow" data-a="w">📤 Wyślij</button></div>
    <button class="btn sec wide" style="margin-top:8px" data-a="x">Zamknij</button></div>`;
  d.onclick = (e) => { const a = e.target.dataset && e.target.dataset.a; if (!a && e.target !== d) return;
    if (a === "o") Aplikacja.pdfOtworz(plik); if (a === "w") Aplikacja.pdfWyslij(plik); d.remove(); };
  document.body.appendChild(d);
}
function drawEdit() {
  const o = (a, b, c) => `<option value="${a}" ${c === a ? "selected" : ""}>${b}</option>`;
  const V = VEH.map((v, i) => [v, i]).filter(([v]) => v.rozmiar.trim());
  $("#edit").innerHTML = `<details class="edit"><summary class="lbl" style="margin:0;min-height:40px;display:flex;align-items:center">✏️ Zmień warunki, ceny, ilości</summary>
    <div class="r"><label class="tgl"><input type="checkbox" ${OSOBNO ? "checked" : ""} onchange="OSOBNO=this.checked;reoffer()"><span>Osobna oferta dla każdego pojazdu / rozmiaru</span></label>
    <label class="fld">Rabat na opony %<input type="number" inputmode="decimal" step="0.5" min="0" max="90" placeholder="0" value="${esc(ORABAT)}" onchange="ORABAT=this.value;reoffer()"></label>
    <label class="fld">Rabat na wymianę %<input type="number" inputmode="decimal" step="1" min="0" max="100" placeholder="0" value="${esc(ORABW)}" onchange="ORABW=this.value;reoffer()"></label></div>` +
    WYMS.map((w) => `<div class="r"><div class="nm">${esc(w.opis)} <span class="small">(za 1 koło)</span></div><div class="small">cennik ${zl(w.cennik)}${+ORABW ? " · po rabacie " + zl(w.auto) : ""}</div>
      <div class="row"><input class="pr-in grow ${w.recznie ? "man" : ""}" type="number" inputmode="numeric" min="0" step="1" placeholder="własna cena wymiany (zł/koło)" value="${w.recznie ? w.cena : ""}" data-k="${esc(w.klucz)}" onchange="setW(this.dataset.k,this.value)">${w.recznie ? `<button class="btn sec" data-k="${esc(w.klucz)}" onclick="setW(this.dataset.k,'')">↺</button>` : ""}</div></div>`).join("") +
    ULS.map((u) => `<div class="r"><div class="nm">${esc(u.nazwa)}</div><div class="small"><span class="buy">zakup ${zl(u.zakup)} · </span>wyliczona ${zl(u.auto)}${u.cena < u.zakup ? ' · <b style="color:#b00012">⚠ poniżej zakupu</b>' : ""}</div>
      <div class="row"><input class="pr-in grow ${u.recznie ? "man" : ""}" type="number" inputmode="numeric" min="1" step="1" placeholder="własna cena (zł/szt.)" value="${u.recznie ? u.cena : ""}" onchange="setC(${u.id},this.value)">${u.recznie ? `<button class="btn sec" onclick="setC(${u.id},'')">↺</button>` : ""}</div></div>`).join("") +
    V.map(([v, i]) => `<div class="r"><div class="nm">${esc([v.pojazd, v.rej].filter(Boolean).join(" ") || "Pojazd " + (i + 1))} <span class="tag">${esc(v.rozmiar)}</span></div>
      <div class="row2"><label class="fld">Ilość opon<input type="number" inputmode="numeric" min="0" value="${v.ilosc}" onchange="setVeh(${i},'ilosc',+this.value||0);drawVeh()"></label>
      <label class="fld">TPMS<input type="number" inputmode="numeric" min="0" max="8" value="${v.tpms || 0}" onchange="setVeh(${i},'tpms',+this.value||0);drawVeh()"></label>
      <label class="fld">Przechowalnia<select onchange="setVeh(${i},'przech',this.value);drawVeh()">${o("", "—", v.przech)}${o("opony", "opony", v.przech)}${o("kola", "koła", v.przech)}</select></label>
      <label class="tgl"><input type="checkbox" ${v.wymiana ? "checked" : ""} onchange="setVeh(${i},'wymiana',this.checked);drawVeh()"><span>Wymiana</span></label></div></div>`).join("") + "</details>";
  const d = $("#edit details"); if (drawEdit.open) d.open = true; d.addEventListener("toggle", () => (drawEdit.open = d.open));
}
function copyMail() { const t = $("#email").value; (navigator.clipboard ? navigator.clipboard.writeText(t) : Promise.reject()).then(() => toast("Skopiowano."), () => { $("#email").select(); document.execCommand("copy"); toast("Skopiowano."); }); }
function nowaOferta() {
  if (SEL.size && !confirm("Wyczyścić bieżącą ofertę? (zapisana jest w Historii)")) return;
  for (const id of ["#klient", "#paste", "#quick"]) $(id).value = "";
  VEH = []; addVeh({}); drawVeh(); setChips("sez", []); setChips("kl", []); $("#rf").checked = false; setProd(""); $("#minstan").value = CFG.min_stan;
  for (const k in F) F[k] = "";
  RES = null; SEL = new Set(); PAGE = {}; OID = null; HSNAP = null; $("#zmBox").innerHTML = ""; ORABAT = ""; CENY = {}; ORABW = ""; CENYW = {}; OSOBNO = null; $("#res").innerHTML = ""; $("#resCard").hidden = true; $("#outCard").hidden = true;
  ["#sMsg", "#oMsg", "#qMsg"].forEach((x) => msg(x, "")); updCnt(); go(document.querySelector('#tabs button[data-v="vOferta"]'));
}

// ------------------------------------------------ historia
let HL = [], HADM = false, ME = "";
const STATUSY = { nowa: "Nowa", wyslana: "Wysłana", przyjeta: "Przyjęta", odrzucona: "Odrzucona", zamowiona: "Zamówiona" };
async function setStatus(oid, st, sel) { sel.disabled = true; try { await api("/api/status", { oid, status: st }); toast("Zapisano status."); loadHist(); } catch (e) { toast(e.message); sel.disabled = false; } }
async function loadHist() {
  $("#hl").innerHTML = '<p class="muted" style="padding:0 6px">Wczytuję…</p>';
  try { const j = await api("/api/history?q=" + encodeURIComponent($("#hq").value)); HL = j.lista; HADM = j.admin; ME = j.me || ""; }
  catch (e) { $("#hl").innerHTML = ""; return msg("#hfil", e.message, 1); }
  const osoby = [...new Set(HL.map((h) => h.kto))].sort(), cur = $("#hk") ? $("#hk").value : "";
  const cs = $("#hs") ? $("#hs").value : "", nOd = HL.filter((h) => h.oddzwon && h.owner === ME).length;
  $("#hfil").innerHTML = (HADM ? `<label class="fld">Osoba<select id="hk" onchange="drawHist()"><option value="">wszyscy (${HL.length})</option>${osoby.map((o) => `<option ${o === cur ? "selected" : ""}>${esc(o)}</option>`).join("")}</select></label>` : "") +
    `<label class="fld">Status<select id="hs" onchange="drawHist()"><option value="">wszystkie</option><option value="oddzwon" ${cs === "oddzwon" ? "selected" : ""}>📞 do oddzwonienia (${nOd})</option>${Object.entries(STATUSY).map(([k, v]) => `<option value="${k}" ${cs === k ? "selected" : ""}>${v}</option>`).join("")}</select></label>`;
  drawHist();
}
function drawHist() {
  const k = HADM && $("#hk") ? $("#hk").value : "", st = $("#hs") ? $("#hs").value : "";
  const L = HL.filter((h) => (!k || h.kto === k) && (!st || (st === "oddzwon" ? h.oddzwon : h.status === st)));
  let sum = "";
  if (L.length) {
    const by = {};
    for (const h of L) { const o = (by[h.kto] ??= { n: 0, kl: new Set(), wart: 0, wys: 0, prz: 0 }); o.n++; if (h.klient) o.kl.add(h.klient); o.wart += h.razem || 0; if (h.status !== "nowa") o.wys++; if (h.status === "przyjeta" || h.status === "zamowiona") o.prz++; }
    sum = '<div class="card"><div class="lbl" style="margin-top:0">Podsumowanie</div><table class="sum"><tr><th>Kto</th><th class="num">Ofert</th><th class="num">Wartość</th><th class="num">Przyjęte</th></tr>' +
      Object.entries(by).sort((a, b) => b[1].n - a[1].n).map(([o, v]) => `<tr><td><b>${esc(o)}</b></td><td class="num">${v.n}</td><td class="num">${zl(v.wart)}</td><td class="num">${v.wys ? Math.round(100 * v.prz / v.wys) + "%" : "—"}</td></tr>`).join("") + "</table></div>";
  }
  $("#hl").innerHTML = sum + (L.length ? L.map((h) => `<div class="hrow"><div class="d">${esc(h.data)}${HADM ? " · " + esc(h.kto) : ""}${h.zrodlo === "telefon" ? " · 📱" : ""}</div>
    <div class="k">${esc(h.klient || "—")}</div><div class="small muted">${esc(h.pojazdy)}</div>
    <div class="w">${h.warianty.map((w) => `${esc(w.modele || w.wariant)} – <b>${zl(w.razem)}</b>`).join("<br>")}</div>
    <div class="row" style="margin-top:6px">${h.owner === ME ? `<select class="sm" data-oid="${esc(h.oid)}" onchange="setStatus(this.dataset.oid,this.value,this)">${Object.entries(STATUSY).map(([s, n]) => `<option value="${s}" ${h.status === s ? "selected" : ""}>${n}</option>`).join("")}</select>` : `<span class="st">${esc(STATUSY[h.status] || h.status)}</span>`}
      ${h.oddzwon ? '<span class="st" style="background:#fff3cd;color:#7a5900">📞 oddzwoń</span>' : ""}${h.link ? `<span class="small muted">🔗${h.otwarta ? " 👁 otwarty" : " nieotwarty"}</span>` : ""}</div>
    ${h.odp ? `<div class="msg ok small">✅ <b>${esc(h.odp.wybor)}</b>${h.odp.tel ? ` · <a href="tel:${esc(String(h.odp.tel).replace(/[^0-9+]/g, ""))}">☎ ${esc(h.odp.tel)}</a>` : ""}${h.odp.uwagi ? `<br>„${esc(h.odp.uwagi)}”` : ""}</div>` : ""}
    <div class="row"><button class="btn sec sm" onclick="restoreHist(${+h.id})">Otwórz i odśwież ceny</button></div></div>`).join("") : '<p class="muted" style="padding:0 6px">Brak zapisanych ofert.</p>');
}
async function restoreHist(id) {
  try {
    const r = await api("/api/history?id=" + id);
    go(document.querySelector('#tabs button[data-v="vOferta"]'));
    $("#klient").value = r.klient || ""; VEH = []; (r.pojazdy || []).forEach(addVeh); if (!VEH.length) addVeh({}); drawVeh();
    SEL = new Set(r.sel && r.sel.length ? r.sel : Object.entries(r.wybor || {}).flatMap(([s, g]) => Object.entries(g).flatMap(([z, l]) => l.map((i) => s + "|" + z + "|" + i))));
    RES = null; $("#res").innerHTML = '<p class="muted">Oferta z historii (' + esc(r.data) + '). Aby wybrać inne opony, użyj „Szukaj w xPartner”.</p>'; $("#resCard").hidden = false;
    ORABAT = r.rabat ?? ""; CENY = r.ceny || {}; ORABW = r.rabat_wym ?? ""; CENYW = r.ceny_wym || {}; if (r.oddzial) OODD = r.oddzial; OSOBNO = r.osobno ?? null; HSNAP = r.snap && r.snap.length ? r.snap : null; HDATA = r.data || ""; OID = newOid(); $("#outCard").hidden = true; updCnt(); await offer();
  } catch (e) { toast(e.message); }
}

// ------------------------------------------------ ustawienia
async function loadCfg() {
  CFG = await api("/api/cfg");
  try { $("#wzor").textContent = CFG.narzut_tryb === "kwota" ? "cena = zakup brutto + " + (CFG.progi || []).map((p) => (p.do == null ? "powyżej" : "do " + p.do + " zł") + ": " + p.kwota + " zł").join(", ") : "cena = zakup netto + " + CFG.marza_proc + "% + VAT"; } catch (e) {}
  if ($("#minstan").value === "") $("#minstan").value = CFG.min_stan;
  if (!CFG.login) msg("#qMsg", "Twoje konto nie ma jeszcze loginu API xPartner – poproś administratora o wpisanie go w Panelu (UŻYTKOWNICY → konto → xPartner).", 1);
}
let WT = {}, WCUR = "wymiana_kolo", PROGI = [];
function readW() { WT[WCUR] = Object.fromEntries([...document.querySelectorAll("#c_wym input")].filter((i) => i.value !== "").map((i) => [i.dataset.d, +i.value])); }
function drawW() { const W = WT[WCUR] || {}; $("#c_wym").innerHTML = Array.from({ length: 12 }, (_, i) => String(i + 12)).map((d) => `<div class="w"><b>R${d}</b><input type="number" inputmode="numeric" min="0" data-d="${d}" value="${W[d] ?? ""}" placeholder="—"><small>${W[d] != null ? "×4 = " + W[d] * 4 : "brak"}</small></div>`).join(""); }
function wTab(b) { readW(); WCUR = b.dataset.t; document.querySelectorAll("#wtabs button").forEach((x) => x.classList.toggle("on", x === b)); drawW(); }
function drawProgi() {
  const k = document.querySelector("input[name=ntryb]:checked")?.value || "procent"; $("#lblMarza").style.visibility = k === "procent" ? "" : "hidden";
  if (k !== "kwota") return ($("#progiBox").innerHTML = "");
  $("#progiBox").innerHTML = '<div class="progi"><div class="pr small muted"><span>Zakup brutto do (zł)</span><span>Doliczyć (zł)</span><span></span></div>' +
    PROGI.map((p, i) => `<div class="pr"><input type="number" inputmode="numeric" min="0" value="${p.do ?? ""}" placeholder="powyżej" onchange="PROGI[${i}].do=this.value===''?null:+this.value"><input type="number" inputmode="numeric" min="0" value="${p.kwota ?? ""}" onchange="PROGI[${i}].kwota=+this.value"><button class="btn sec sm" onclick="PROGI.splice(${i},1);drawProgi()">✕</button></div>`).join("") +
    '</div><button class="btn sec sm" style="margin-top:6px" onclick="PROGI.splice(Math.max(0,PROGI.length-1),0,{do:null,kwota:0});drawProgi()">+ próg</button><p class="hint">Puste „do” = wszystkie droższe. Cena = zakup brutto + kwota, w górę do pełnych zł.</p>';
}
function openCfg() {
  for (const k of ["marza_proc", "vat_proc", "min_stan", "kola_na_auto", "waznosc_dni", "podpis", "tpms_cena", "przech_opony_do19", "przech_opony_pow19", "przech_kola_do19", "przech_kola_pow19"]) $("#c_" + k).value = CFG[k] ?? "";
  WT = { wymiana_kolo: { ...CFG.wymiana_kolo }, wymiana_suv: { ...CFG.wymiana_suv }, wymiana_dost: { ...CFG.wymiana_dost } }; WCUR = "wymiana_kolo";
  document.querySelectorAll("#wtabs button").forEach((b) => b.classList.toggle("on", b.dataset.t === WCUR)); drawW();
  $("#c_premium").value = (CFG.premium || []).join(", "); PROGI = JSON.parse(JSON.stringify(CFG.progi || []));
  document.querySelectorAll("input[name=ntryb]").forEach((r) => (r.checked = r.value === (CFG.narzut_tryb || "procent"))); drawProgi(); msg("#cMsg", "");
}
async function saveCfg() {
  const c = { podpis: $("#c_podpis").value };
  for (const k of ["marza_proc", "vat_proc", "min_stan", "kola_na_auto", "waznosc_dni"]) c[k] = +$("#c_" + k).value;
  readW(); Object.assign(c, WT);
  for (const k of ["tpms_cena", "przech_opony_do19", "przech_opony_pow19", "przech_kola_do19", "przech_kola_pow19"]) c[k] = +$("#c_" + k).value || 0;
  c.narzut_tryb = document.querySelector("input[name=ntryb]:checked")?.value || "procent";
  c.progi = PROGI.filter((p) => p.kwota !== undefined && p.kwota !== "").map((p) => ({ do: p.do === null || p.do === "" ? null : +p.do, kwota: +p.kwota }));
  c.premium = $("#c_premium").value.split(",").map((s) => s.trim().toUpperCase()).filter(Boolean);
  try { await api("/api/cfg", c); await loadCfg(); msg("#cMsg", "Zapisano."); return true; } catch (e) { msg("#cMsg", e.message, 1); return false; }
}
async function testApi() { if (!(await saveCfg())) return; msg("#cMsg", "Łączę…"); try { const j = await api("/api/test", {}); msg("#cMsg", j.msg); } catch (e) { msg("#cMsg", e.message, 1); } }

// ------------------------------------------------ wyniki marży (tylko podgląd; dane i uprawnienia z bazy)
function pierwszaZakladka() { return [...document.querySelectorAll("#tabs button")].find((b) => !b.hidden); }
let WD = null, WB = null, WCZAS = 0;
async function loadWyn(force, cicho) {
  const odd = Wyniki.oddzialy(Aplikacja.profil);
  if (!odd.length) { $("#wOdd").innerHTML = ""; return ($("#wBody").innerHTML = '<div class="msg e">Twoje konto nie ma przypisanego oddziału z wynikami marży (Wrocław albo Opole). Skontaktuj się z administratorem.</div>'); }
  if (!WB || !odd.includes(WB)) WB = odd[0];
  if (WD && !force && Date.now() - WCZAS < 5 * 60 * 1000) return drawWyn();
  if (!WD) $("#wBody").innerHTML = '<p class="muted">Wczytuję wyniki…</p>';
  try { WD = await Aplikacja.wyniki(); WCZAS = Date.now(); drawWyn(); if (force && !cicho) toast("Odświeżono."); }
  catch (e) { if (!WD) $("#wBody").innerHTML = '<div class="msg e">Nie udało się wczytać wyników. Sprawdź internet i kliknij „Odśwież”.</div>'; else if (!cicho) toast("Nie udało się odświeżyć: " + e.message); }
}
function drawWyn() {
  const odd = Wyniki.oddzialy(Aplikacja.profil), names = Object.fromEntries(Wyniki.ODDZIALY), zl = Wyniki.zl;
  const dane = (k) => ({ months: WD.months.filter((m) => m.branch === k), runs: WD.runs.filter((r) => r.branch === k) });
  $("#wOdd").innerHTML = odd.length > 1 ? odd.map((k) => `<button class="${k === WB ? "on" : ""}" onclick="WB='${k}';drawWyn()">${names[k]}</button>`).join("") : `<button class="on">${names[odd[0]]}</button>`;
  $("#wObie").innerHTML = odd.length > 1 ? odd.map((k) => { const m = Wyniki.wybierz_miesiac(dane(k).months), s = m && Wyniki.podsumowanie(m); return `${names[k]}: <b>${s && s.pct !== null ? Math.round(s.pct) + "% celu" : "brak danych"}</b>`; }).join(" · ") : "";
  const d = dane(WB), m = Wyniki.wybierz_miesiac(d.months);
  if (!m) return ($("#wBody").innerHTML = `<p class="muted">Brak wyników dla oddziału ${names[WB]} – pojawią się po najbliższej aktualizacji MARŻY.</p>`);
  const s = Wyniki.podsumowanie(m), pts = Wyniki.punkty_wykresu(m, d.runs);
  const plan = s.biezacy && s.plan_dzis !== null ? `▲ plan na dziś ${zl(s.plan_dzis)} · dzień roboczy ${s.dzien_dzis || Math.min(s.dni_minelo + 1, s.dni_all)} z ${s.dni_all}` : s.cel === null ? "brak celu w kalkulatorze" : "";
  const kiedy = s.updated_at ? new Date(s.updated_at).toLocaleString("pl-PL", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "";
  const tile = (t, v, c) => `<div class="tile"><small>${t}</small><b ${c ? `style="color:${c}"` : ""}>${v}</b></div>`;
  const tc = s.tempo === null ? "" : s.tempo >= 100 ? "var(--ok)" : "var(--red)";
  const rows = Wyniki.poprzednie(d.months, m);
  $("#wBody").innerHTML = `<div class="wtop"><div class="mies">${esc(names[WB])} · ${esc(s.label)}${s.biezacy ? "" : " (ostatni miesiąc z wynikami)"}</div>
    <div class="row" style="align-items:flex-end;justify-content:space-between"><div><div class="zr">ZROBIONE</div><div class="kw">${zl(s.zrobione)}</div>
    <div class="cel">cel ${zl(s.cel)}${m.target_pending ? " ✎ czeka na Excel" : ""}</div></div><div style="text-align:right"><div class="pct">${s.pct !== null ? Math.round(s.pct) + "%" : "—"}</div><div class="cel">realizacji celu</div></div></div>
    <div class="wbar"><i style="width:${s.pct !== null ? Math.min(s.pct, 100) : 0}%"></i>${s.biezacy && s.cel && s.plan_dzis !== null ? `<b style="left:calc(${Math.min(s.plan_dzis / s.cel, 1) * 100}% - 1px)"></b>` : ""}</div>
    <div class="pl">${esc(plan)}</div></div>
    <div class="tiles">${tile("Brakuje do celu", zl(s.brakuje))}${tile("Potrzeba dziennie", s.biezacy ? zl(s.potrzeba_dziennie) : "—", "var(--red)")}
    ${tile("Średnio dziennie dotąd", zl(s.srednio_dziennie))}${tile("Prognoza na koniec", s.biezacy ? zl(s.prognoza) : "—")}
    ${tile("Tempo wobec planu", s.tempo !== null ? Math.round(s.tempo) + "%" : "—", tc)}${tile("Zostało dni roboczych", s.biezacy ? s.dni_zostalo : "—")}</div>
    <div class="card chart"><div class="lbl" style="margin-top:0">Plan i wykonanie (narastająco) <span style="color:var(--red)">■ wykonanie</span> · — plan</div>${wykres(s, pts)}
    ${pts.length < 3 ? '<p class="hint">Wykres uzupełnia się przy każdej aktualizacji MARŻY.</p>' : ""}</div>
    <div class="card"><div class="lbl" style="margin-top:0">Poprzednie miesiące</div>${rows.length ? '<table class="hist"><tr><th>Miesiąc</th><th>Zrobione</th><th>Cel</th><th>%</th></tr>' + rows.map((r) => {
      const p = Wyniki.podsumowanie(r); return `<tr><td>${esc(p.label)}${r.manual ? " <small class=muted>(ręcznie)</small>" : ""}</td><td>${zl(p.zrobione)}</td><td>${zl(p.cel)}${r.target_pending ? " ✎" : ""}</td><td class="${p.pct === null ? "" : p.pct >= 100 ? "ok" : "bad"}">${p.pct !== null ? Math.round(p.pct) + "%" : "—"}</td></tr>`; }).join("") + "</table>" : '<p class="muted">Brak.</p>'}</div>
    <p class="hint" style="padding:0 4px">${kiedy ? "Zaktualizowano " + kiedy + ". " : ""}Tylko podgląd – cele zmienia administrator w Panelu.</p>`;
}
function wykres(s, pts) {
  if (!s.dni_all) return "";
  const w = 340, h = 190, L = 48, R = 8, T = 8, B = 20, top = Math.max(s.cel || 0, ...pts.map((p) => p[1]), 1) * 1.08;
  const X = (i) => L + ((w - L - R) * i) / s.dni_all, Y = (v) => T + (h - T - B) * (1 - v / top);
  const k = (v) => (v >= 1000 ? Math.round(v / 1000) + " tys." : Math.round(v));
  let g = "";
  for (let i = 0; i <= 4; i++) { const v = (top * i) / 4; g += `<line x1="${L}" x2="${w - R}" y1="${Y(v)}" y2="${Y(v)}" stroke="#E4E4E4"/><text x="${L - 4}" y="${Y(v) + 3}" text-anchor="end" font-size="9" fill="#7A7A7A">${k(v)}</text>`; }
  g += `<text x="${L}" y="${h - 4}" font-size="9" fill="#7A7A7A">1. dzień</text><text x="${w - R}" y="${h - 4}" font-size="9" fill="#7A7A7A" text-anchor="end">${s.dni_all}. dzień rob.</text>`;
  if (s.cel) g += `<line x1="${X(0)}" y1="${Y(0)}" x2="${X(s.dni_all)}" y2="${Y(s.cel)}" stroke="#141414" stroke-width="1.5" stroke-dasharray="5 4"/>`;
  if (pts.length) {
    g += `<polyline fill="none" stroke="#E30613" stroke-width="2.5" points="${[[0, 0], ...pts].map(([i, v]) => X(i) + "," + Y(v)).join(" ")}"/>`;
    g += pts.map(([i, v]) => `<circle cx="${X(i)}" cy="${Y(v)}" r="3.5" fill="#E30613" stroke="#fff" stroke-width="1.5"/>`).join("");
  }
  return `<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="Wykres wykonania narastająco">${g}</svg>`;
}
setInterval(() => { if (!$("#vWyn").hidden && document.visibilityState === "visible") loadWyn(true, true); }, 5 * 60 * 1000);

// Przycisk „wstecz” Androida: zamyka arkusz, potem wraca do zakładki Oferta.
window.onBack = function () {
  if (!$("#sheet").hidden) { closeSheet(); return true; }
  const b = document.querySelector("#tabs button.on");
  const p = pierwszaZakladka();
  if (b && p && b !== p && !$("#tabs").hidden) { go(p); return true; }
  return false;
};

drawChips();
startApp();

// ------------------------------------------------ zamówienia xPartner (tylko podgląd; faktury – administrator)
let ZD = null, ZH = null, ZT = "z";
const zIso = (d) => d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
function zKto() { const D = ZT === "h" ? ZH : ZD; if (!D) return; const k = [...new Set(D.zamowienia.map((z) => z.kto).filter(Boolean))].sort(); let zap = ""; try { zap = localStorage.getItem("zam_kto") || ""; } catch (e) {}
  $("#zkto").innerHTML = '<option value="">wszyscy</option>' + k.map((x) => `<option>${esc(x)}</option>`).join(""); if (k.includes(zap)) $("#zkto").value = zap; }
const zzl = (v) => Number(v || 0).toLocaleString("pl-PL", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " zł";
function zTab(b) { ZT = b.dataset.z; document.querySelectorAll("#zTabs button").forEach((x) => x.classList.toggle("on", x === b)); $("#zZ").hidden = ZT === "f"; $("#zF").hidden = ZT !== "f"; $("#zDaty").hidden = ZT !== "h";
  if (ZT === "f" && !$("#fL").innerHTML) zFak();
  else if (ZT === "h" && !ZH) { const d = new Date(); $("#hdo").value = zIso(d); d.setDate(d.getDate() - 30); $("#hod").value = zIso(d); zLoad(); }
  else if (ZT !== "f") { zKto(); zDraw(); } }
async function zLoad(force) {
  if (ZT === "f") return zFak();
  const h = ZT === "h";
  $("#zL").innerHTML = h ? '<p class="muted">Szukam zamówień po fakturach… (pierwszy raz może potrwać kilkanaście sekund)</p>' : '<p class="muted">Wczytuję zamówienia…</p>'; $("#zSum").innerHTML = "";
  const [k, j] = await Silnik.handle(h ? "/api/zamkniete?od=" + encodeURIComponent($("#hod").value) + "&do=" + encodeURIComponent($("#hdo").value) : "/api/zamowienia", null);
  if (k !== 200) { if (h) ZH = null; else ZD = null; $("#zL").innerHTML = `<p class="err">${esc(j.error || "Błąd")}</p>`; return; }
  if (h) { ZH = j; $("#hod").value = j.od; $("#hdo").value = j.do; } else ZD = j;
  zKto(); zDraw(); if (force) toast("Odświeżono (" + j.czas + ").");
}
function zDraw() {
  const D = ZT === "h" ? ZH : ZD; if (!D) return; 
  const q = $("#zq").value.trim().toLowerCase(), kto = $("#zkto").value, st = ZT === "h" && $("#zst").value === "otw" ? "" : $("#zst").value;
  const l = D.zamowienia.filter((z) => (!kto || z.kto === kto) && (!st || (st === "otw" ? z.status !== 6 : String(z.status) === st)) &&
    (!q || [z.nr, z.nr_erp, z.kto, z.komentarz, ...z.pozycje.map((p) => p.nazwa)].join(" ").toLowerCase().includes(q)));
  const bl = l.filter((z) => z.status === 5).length;
  $("#zSum").innerHTML = `${l.length} zamówień · ${l.reduce((a, z) => a + z.szt, 0)} szt. · do wydania ${l.reduce((a, z) => a + z.do_wydania, 0)} szt. · ${zzl(l.reduce((a, z) => a + z.netto, 0))} netto` + (bl ? ` · <b class="err">błędy: ${bl}</b>` : "") + (D.oddzialy ? ` · tylko oddział: ${esc(D.oddzialy.join(", ") || "brak – poproś administratora")}` + (D.ukryte ? ` (innych: ${D.ukryte})` : "") : "") + (ZT === "h" ? ` · faktur: ${D.faktur}` + (D.bledy ? ` · <b class="err">nie pobrano: ${D.bledy}</b>` : "") : "");
  $("#zL").innerHTML = l.length ? l.map((z) => `<div class="card zk${z.status === 5 ? " zerr" : ""}"><div class="row"><b class="grow">${esc(z.nr)}${z.nr_erp ? " · " + esc(z.nr_erp) : ""}</b><span class="st s${z.status}">${esc(z.status_txt)}</span></div>
    <div class="small muted">${esc(z.data)}${z.kto ? " · " + esc(z.kto) : ""}${z.magazyn ? " · " + esc(z.magazyn) : ""} · <b>${zzl(z.netto)}</b> netto</div>
    ${z.pozycje.map((p) => `<div class="zp"><span class="grow">${esc(p.nazwa)}</span><span>${p.ilosc} szt.${p.zostalo ? ` · do wydania ${p.zostalo}` : ""}${p.zostalo && p.dostepne < p.zostalo ? ` · <b class="err">dostępne ${p.dostepne}</b>` : ""}</span></div>`).join("")}
    ${z.komentarz ? `<div class="small muted">💬 ${esc(z.komentarz)}</div>` : ""}${z.poz_z_faktury ? `<div class="small muted">Pozycje z faktury${z.poz_z_faktury === "wspolna" ? " (faktura obejmuje kilka zamówień)" : ""}</div>` : ""}${z.faktury && z.faktury.length ? `<div class="small muted">🧾 ${z.faktury.map(esc).join(", ")}</div>` : ""}</div>`).join("") : '<p class="muted">Brak zamówień' + (ZT === "h" ? " na fakturach z tego okresu" : "") + ".</p>";
}
async function zFak() {
  $("#fL").innerHTML = '<p class="muted">Wczytuję faktury…</p>';
  const [k, j] = await Silnik.handle("/api/faktury?od=" + encodeURIComponent($("#fod").value) + "&do=" + encodeURIComponent($("#fdo").value), null);
  if (k !== 200) { $("#fL").innerHTML = `<p class="err">${esc(j.error || "Błąd")}</p>`; return; }
  $("#fod").value = j.od; $("#fdo").value = j.do;
  $("#fL").innerHTML = j.faktury.length ? j.faktury.map((f) => `<div class="card zk" data-nr="${esc(f.nr)}" onclick="zFakSz(this, this.dataset.nr)"><div class="row"><b class="grow">${esc(f.nr)}</b><span class="small">${esc(f.data)}</span></div><div class="small muted">${esc(f.platnosc)}${f.magazyn ? " · " + esc(f.magazyn) : ""}</div><div class="fs"></div></div>`).join("") : '<p class="muted">Brak faktur w tym okresie.</p>';
}
async function zFakSz(el, nr) {
  const d = el.querySelector(".fs"); if (d.innerHTML) { d.innerHTML = ""; return; }
  d.innerHTML = '<p class="muted small">Wczytuję…</p>';
  const [k, f] = await Silnik.handle("/api/faktura?nr=" + encodeURIComponent(nr), null);
  if (k !== 200) { d.innerHTML = `<p class="err small">${esc(f.error || "Błąd")}</p>`; return; }
  d.innerHTML = f.pozycje.map((p) => `<div class="zp"><span class="grow">${esc(p.nazwa)}</span><span>${p.ilosc} × ${zzl(p.cena)}</span></div>`).join("") +
    `<div class="small" style="margin-top:6px">Netto ${zzl(f.netto)} · VAT ${zzl(f.vat)} · <b>brutto ${zzl(f.brutto)}</b>${f.termin ? " · termin " + esc(f.termin) : ""}${f.zamowienie ? " · zam. " + esc(f.zamowienie) : ""}</div>`;
}
