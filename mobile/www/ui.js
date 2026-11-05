// Oferty opon – ekran telefonu. Logika jak w Panelu (app/oferty/index.html), silnik w silnik.js (Silnik.handle).
const $ = (s) => document.querySelector(s);
let CFG = {}, RES = null, VEH = [], SEL = new Set(), PAGE = {}, SORT = "", OID = null, ORABAT = "", CENY = {}, ULS = [], OSOBNO = null;
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
  if (zalogowany) go(document.querySelector("#tabs button.on")); else { for (const v of ["#vOferta", "#vHist", "#vUst"]) $(v).hidden = true; $("#selBar").hidden = true; }
}
async function startApp() {
  $("#lVer").textContent = "Wersja aplikacji: " + Aplikacja.wersja();
  if (!Aplikacja.zalogowany()) return pokaz(false);
  try {
    const p = await Aplikacja.start();
    $("#tUser").textContent = (p.name || p.email) + (p.role === "admin" ? " · administrator" : "");
    $("#kInfo").textContent = "Zalogowano: " + p.email + ". Wersja aplikacji: " + Aplikacja.wersja();
    pokaz(true); await loadCfg(); if (!VEH.length) { addVeh({}); drawVeh(); }
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
  for (const v of ["vOferta", "vHist", "vUst"]) $("#" + v).hidden = v !== b.dataset.v;
  updCnt();
  if (b.dataset.v === "vHist") loadHist();
  if (b.dataset.v === "vUst") openCfg();
  window.scrollTo(0, 0);
}
async function sprawdzAkt(reczne) {
  const j = await Aplikacja.sprawdzAktualizacje();
  if (j && j.url) { const u = $("#upd"); u.innerHTML = `<span class="grow">Jest nowa wersja aplikacji ${esc(j.version)}.</span><button class="btn" onclick="Aplikacja.openUrl('${esc(j.url)}')">Aktualizuj</button>`; u.hidden = false; }
  else if (reczne) toast("Masz najnowszą wersję (" + Aplikacja.wersja() + ").");
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
    RES = await api("/api/search", req); SEL = new Set(); PAGE = {}; OID = newOid(); ORABAT = ""; CENY = {}; OSOBNO = null;
    if (req.sezony.length || req.klasy.length || req.producenci.trim())
      for (const [s, g] of Object.entries(RES.wyniki)) for (const [z, l] of Object.entries(g)) l.filter((p) => p.ok_stan).slice(0, 1).forEach((p) => SEL.add(s + "|" + z + "|" + p.id));
    $("#outCard").hidden = true; render(); msg("#sMsg", ""); $("#resCard").hidden = false; $("#resCard").scrollIntoView({ behavior: "smooth" });
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
function setC(id, v) { v = String(v).replace(",", ".").trim(); if (v === "" || +v <= 0) delete CENY[id]; else CENY[id] = Math.ceil(+v); reoffer(); }
async function offer(quiet) {
  const b = $("#bO"); b.disabled = true; if (!quiet) msg("#oMsg", "Odświeżam ceny i stany w xPartner…");
  try {
    const wybor = {}; SEL.forEach((k) => { const [s, z, id] = k.split("|"); ((wybor[s] ??= {})[z] ??= []).push(+id); });
    if (!OID) OID = newOid();
    if (OSOBNO === null) { const V = vehicles().filter((v) => v.nowe); OSOBNO = V.length > 1 && !V.some((v) => v.rej || v.pojazd); }
    const j = await api("/api/offer", { osobno: OSOBNO, oid: OID, sel: [...SEL], klient: $("#klient").value, pojazdy: vehicles(), wybor, marza: "", rabat: ORABAT, ceny: CENY });
    ULS = j.ulotki;
    msg("#oMsg", j.uwagi.length ? "⚠ " + j.uwagi.join("\n⚠ ") : quiet ? "" : "Zapisano w historii.", j.uwagi.length > 0);
    $("#sum").innerHTML = j.warianty.map((v) => `<div class="vcard"><div class="t">${esc(v.wariant)}</div><div class="m">${esc(v.modele.join(", "))}</div>
      <div class="l"><span>Opony</span><span>${zl(v.opony)}</span></div>${v.wymiana ? `<div class="l"><span>Wymiana</span><span>${zl(v.wymiana)}</span></div>` : ""}
      ${v.tpms ? `<div class="l"><span>Czujniki TPMS</span><span>${zl(v.tpms)}</span></div>` : ""}${v.przech ? `<div class="l"><span>Przechowalnia</span><span>${zl(v.przech)}</span></div>` : ""}
      <div class="tot"><span>RAZEM brutto</span><b>${zl(v.razem)}</b></div></div>`).join("");
    $("#ul").innerHTML = '<div class="lbl">Ulotki PDF dla klienta (otwierają się w przeglądarce zalogowanej do xPartner)</div>' +
      j.ulotki.map((u) => `<button class="ulk" data-u="${esc(u.url)}" onclick="Aplikacja.openUrl(this.dataset.u)"><span>📄 ${esc(u.nazwa)}</span><b>${zl(u.cena)}</b></button>`).join("");
    $("#email").value = j.email; drawEdit();
    const first = $("#outCard").hidden; $("#outCard").hidden = false; if (!quiet || first) $("#outCard").scrollIntoView({ behavior: "smooth" });
  } catch (e) { msg("#oMsg", e.message, 1); $("#outCard").hidden = false; }
  b.disabled = false;
}
function drawEdit() {
  const o = (a, b, c) => `<option value="${a}" ${c === a ? "selected" : ""}>${b}</option>`;
  const V = VEH.map((v, i) => [v, i]).filter(([v]) => v.rozmiar.trim());
  $("#edit").innerHTML = `<details class="edit"><summary class="lbl" style="margin:0;min-height:40px;display:flex;align-items:center">✏️ Zmień warunki, ceny, ilości</summary>
    <div class="r"><label class="tgl"><input type="checkbox" ${OSOBNO ? "checked" : ""} onchange="OSOBNO=this.checked;reoffer()"><span>Osobna oferta dla każdego pojazdu / rozmiaru</span></label>
    <label class="fld">Rabat dla klienta %<input type="number" inputmode="decimal" step="0.5" min="0" max="90" placeholder="0" value="${esc(ORABAT)}" onchange="ORABAT=this.value;reoffer()"></label></div>` +
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
  RES = null; SEL = new Set(); PAGE = {}; OID = null; ORABAT = ""; CENY = {}; OSOBNO = null; $("#res").innerHTML = ""; $("#resCard").hidden = true; $("#outCard").hidden = true;
  ["#sMsg", "#oMsg", "#qMsg"].forEach((x) => msg(x, "")); updCnt(); go(document.querySelector('#tabs button[data-v="vOferta"]'));
}

// ------------------------------------------------ historia
let HL = [], HADM = false;
async function loadHist() {
  $("#hl").innerHTML = '<p class="muted" style="padding:0 6px">Wczytuję…</p>';
  try { const j = await api("/api/history?q=" + encodeURIComponent($("#hq").value)); HL = j.lista; HADM = j.admin; }
  catch (e) { $("#hl").innerHTML = ""; return msg("#hfil", e.message, 1); }
  const osoby = [...new Set(HL.map((h) => h.kto))].sort(), cur = $("#hk") ? $("#hk").value : "";
  $("#hfil").innerHTML = HADM ? `<label class="fld">Osoba<select id="hk" onchange="drawHist()"><option value="">wszyscy (${HL.length})</option>${osoby.map((o) => `<option ${o === cur ? "selected" : ""}>${esc(o)}</option>`).join("")}</select></label>` : "";
  drawHist();
}
function drawHist() {
  const k = HADM && $("#hk") ? $("#hk").value : "", L = HL.filter((h) => !k || h.kto === k);
  let sum = "";
  if (HADM && L.length) {
    const by = {};
    for (const h of L) { const o = (by[h.kto] ??= { n: 0, kl: new Set(), wart: 0 }); o.n++; if (h.klient) o.kl.add(h.klient); o.wart += h.razem || 0; }
    sum = '<div class="card"><div class="lbl" style="margin-top:0">Podsumowanie</div><table class="sum"><tr><th>Kto</th><th class="num">Ofert</th><th class="num">Klientów</th><th class="num">Wartość</th></tr>' +
      Object.entries(by).sort((a, b) => b[1].n - a[1].n).map(([o, v]) => `<tr><td><b>${esc(o)}</b></td><td class="num">${v.n}</td><td class="num">${v.kl.size}</td><td class="num">${zl(v.wart)}</td></tr>`).join("") + "</table></div>";
  }
  $("#hl").innerHTML = sum + (L.length ? L.map((h) => `<div class="hrow"><div class="d">${esc(h.data)}${HADM ? " · " + esc(h.kto) : ""}${h.zrodlo === "telefon" ? " · 📱" : ""}</div>
    <div class="k">${esc(h.klient || "—")}</div><div class="small muted">${esc(h.pojazdy)}</div>
    <div class="w">${h.warianty.map((w) => `${esc(w.modele || w.wariant)} – <b>${zl(w.razem)}</b>`).join("<br>")}</div>
    <div class="row"><button class="btn sec sm" onclick="restoreHist(${+h.id})">Otwórz i odśwież ceny</button></div></div>`).join("") : '<p class="muted" style="padding:0 6px">Brak zapisanych ofert.</p>');
}
async function restoreHist(id) {
  try {
    const r = await api("/api/history?id=" + id);
    go(document.querySelector('#tabs button[data-v="vOferta"]'));
    $("#klient").value = r.klient || ""; VEH = []; (r.pojazdy || []).forEach(addVeh); if (!VEH.length) addVeh({}); drawVeh();
    SEL = new Set(r.sel && r.sel.length ? r.sel : Object.entries(r.wybor || {}).flatMap(([s, g]) => Object.entries(g).flatMap(([z, l]) => l.map((i) => s + "|" + z + "|" + i))));
    RES = null; $("#res").innerHTML = '<p class="muted">Oferta z historii (' + esc(r.data) + '). Aby wybrać inne opony, użyj „Szukaj w xPartner”.</p>'; $("#resCard").hidden = false;
    ORABAT = r.rabat ?? ""; CENY = r.ceny || {}; OSOBNO = r.osobno ?? null; OID = newOid(); $("#outCard").hidden = true; updCnt(); await offer();
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

// Przycisk „wstecz” Androida: zamyka arkusz, potem wraca do zakładki Oferta.
window.onBack = function () {
  if (!$("#sheet").hidden) { closeSheet(); return true; }
  const b = document.querySelector("#tabs button.on");
  if (b && b.dataset.v !== "vOferta" && !$("#tabs").hidden) { go(document.querySelector('#tabs button[data-v="vOferta"]')); return true; }
  return false;
};

drawChips();
startApp();
