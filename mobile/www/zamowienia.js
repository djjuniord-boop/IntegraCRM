// ZAMÓWIENIA xPartner – port app/oferty/zamowienia.py (te same wyniki; pilnuje mobile/test/zgodnosc.py). Tylko odczyt.
(function (root) {
  const Z = {};
  const STATUSY = { 1: "W kolejce", 2: "Przesłane", 3: "Oczekujące", 4: "Wczytane", 5: "Błąd", 6: "Zrealizowane" };
  const FAKTURA_NR = /^[A-Z]{2}\d{7}\/\d{2}$/, FAKTURY_OD = "2026-02-01";
  const FORMY = { 1: "gotówka", 2: "karta", 3: "bon", 4: "czek", 5: "kredyt", 6: "przelew", 7: "mobilna" };
  class Blad extends Error {}
  const lok = (el) => (el.localName || el.nodeName || "").replace(/^.*:/, "");
  const dzieci = (el) => (el ? [...el.children] : []);
  const dz = (el, n) => dzieci(el).find((c) => lok(c) === n) || null;
  const t = (el, n) => { const c = dz(el, n); return c ? (c.textContent || "").trim() : ""; };
  const gr = (x) => Math.trunc(x * 100 + (x >= 0 ? 0.5 : -0.5)) / 100;   // jak _gr w zamowienia.py
  const f2 = (v) => { const x = parseFloat(String(v).replace(",", ".")); return isNaN(x) ? 0 : gr(x); };
  const i0 = (v) => { const x = parseFloat(String(v).replace(",", ".")); return isNaN(x) ? 0 : Math.trunc(x); };
  const wszystkie = (el, n) => (el ? [...el.getElementsByTagName("*")].filter((c) => lok(c) === n) : []);

  Z.parsuj = function (tekst) {
    const doc = new DOMParser().parseFromString(tekst, "text/xml");
    if (doc.getElementsByTagName("parsererror").length) throw new Blad("Nieprawidłowa odpowiedź xPartner (nie XML) – sprawdź login/hasło.");
    const r = doc.documentElement, ok = (t(r, "success") || t(r, "productResult")).toLowerCase();
    const bledy = wszystkie(dz(r, "errors"), "error").map((e) => (e.textContent || "").trim()).filter(Boolean);
    if (ok === "false" || (bledy.length && ok !== "true")) throw new Blad("xPartner: " + (bledy.join("; ") || "operacja nieudana"));
    return r;
  };
  Z.api_xml = async function (cfg, metoda, params) {
    if (!cfg.login || !cfg.password) throw new Blad("Twoje konto nie ma jeszcze loginu API xPartner – poproś administratora (UŻYTKOWNICY → konto → xPartner).");
    const q = new URLSearchParams({ a: "b2b_xmlApi", login: cfg.login, pass: cfg.password, m: metoda });
    for (const [k, v] of Object.entries(params || {})) if (v !== null && v !== undefined && v !== "") q.set(k, v);
    let r;
    try { r = await root.Silnik.http("https://xpartner.net.pl/index.php?" + q.toString()); } catch (e) { r = null; }
    if (!r || !r.status || r.status >= 400) throw new Blad("Brak połączenia z xPartner (kod " + (r ? r.status : "?") + ").");
    return Z.parsuj(r.text);
  };
  const adres = (el) => { const o = {}; if (el) for (const k of ["name", "street", "zipCode", "city", "receivingPerson"]) if (t(el, k)) o[k] = t(el, k); return o; };
  Z.czytaj_zamowienia = function (r) {
    const out = wszystkie(dz(r, "orders"), "order").map((o) => {
      const st = i0(t(o, "status"));
      const poz = wszystkie(dz(o, "products"), "product").map((p) => ({ lp: i0(t(p, "lineNumber")), id: i0(t(p, "productId")), nazwa: t(p, "productName"),
        jedn: t(p, "unit") || "szt", ilosc: i0(t(p, "quantity")), zostalo: i0(t(p, "quantityRemaining")), dostepne: i0(t(p, "quantityAvailable")), cena: f2(t(p, "unitNetPrice")) }));
      return { nr: t(o, "orderXp"), nr_erp: t(o, "orderErp"), nr_zew: t(o, "extOrderNumber"), waluta: (t(o, "currency") || "pln").toUpperCase(),
        netto: f2(t(o, "totalNetPrice")), data: t(o, "createdAt"), kto: t(o, "createdBy"), wazne_do: t(o, "expirationDate"), status: st,
        status_txt: STATUSY[st] || String(st || "?"), magazyn: t(o, "warehouseName"), komentarz: t(o, "comment"),
        odbiorca: adres(dz(o, "recipient")), dostawa: adres(dz(o, "deliveryPlace")), pozycje: poz,
        szt: poz.reduce((a, x) => a + x.ilosc, 0), do_wydania: poz.reduce((a, x) => a + x.zostalo, 0) };
    });
    return out.sort((a, b) => (a.data < b.data ? 1 : a.data > b.data ? -1 : 0));
  };
  Z.czytaj_faktury = function (r) {
    const out = wszystkie(dz(r, "invoices"), "invoice").map((x) => ({ nr: t(x, "documentNumber"), data: t(x, "documentDate"), platnosc: t(x, "paymentMethod"), magazyn: t(x, "warehouse") }));
    const k = (x) => [x.data, x.nr];
    return out.sort((a, b) => { const A = k(a), B = k(b); return A[0] !== B[0] ? (A[0] < B[0] ? 1 : -1) : A[1] < B[1] ? 1 : A[1] > B[1] ? -1 : 0; });
  };
  Z.czytaj_fakture = function (r) {
    const fak = [...r.getElementsByTagName("*")].find((c) => lok(c) === "Faktura");
    if (!fak) throw new Blad("Brak faktury w odpowiedzi xPartner.");
    const fa = dz(fak, "Fa"), dzf = dzieci(fa);
    const suma = (re) => gr(dzf.filter((c) => re.test(lok(c))).reduce((a, c) => a + f2(c.textContent), 0));
    const plat = dz(fa, "Platnosc"), zam = [...fa.getElementsByTagName("*")].find((c) => lok(c) === "NrZamowienia");
    const poz = dzf.filter((c) => lok(c) === "FaWiersz").map((w) => ({ lp: i0(t(w, "NrWierszaFa")), nazwa: t(w, "P_7"), indeks: t(w, "Indeks"), jedn: t(w, "P_8A"),
      ilosc: f2(t(w, "P_8B")), cena: f2(t(w, "P_9A")), wartosc: f2(t(w, "P_11")), vat: t(w, "P_12") }));
    const forma = plat ? t(plat, "FormaPlatnosci") : "";
    return { nr: t(fa, "P_2"), data: t(fa, "P_1"), wz: t(fa, "WZ"), ksef: t(dz(r, "invoice"), "KsefNumber"), netto: suma(/^P_13_\d+$/), vat: suma(/^P_14_\d+$/),
      brutto: f2(t(fa, "P_15")), waluta: t(fa, "KodWaluty") || "PLN", termin: plat ? t(dz(plat, "TerminPlatnosci"), "Termin") : "",
      forma: plat ? FORMY[forma] || forma : "", zamowienie: zam ? (zam.textContent || "").trim() : "", pozycje: poz };
  };
  const iso = (d) => d.getUTCFullYear() + "-" + String(d.getUTCMonth() + 1).padStart(2, "0") + "-" + String(d.getUTCDate()).padStart(2, "0");
  const dzien = (s) => { if (!/^\d{4}-\d{2}-\d{2}$/.test(s)) return null; const d = new Date(s + "T00:00:00Z"); return isNaN(d) ? null : d; };
  Z.okres = function (od, dO, dzis) {
    const t0 = dzis ? dzien(dzis) : (() => { const n = new Date(); return new Date(Date.UTC(n.getFullYear(), n.getMonth(), n.getDate())); })();
    const d2 = dO ? dzien(dO) : t0; if (!d2) throw new Blad("Zła data „do” (RRRR-MM-DD).");
    let d1 = od ? dzien(od) : new Date(d2.getTime() - 30 * 864e5); if (!d1) throw new Blad("Zła data „od” (RRRR-MM-DD).");
    d1 = new Date(Math.max(d1.getTime(), dzien(FAKTURY_OD).getTime(), d2.getTime() - 366 * 864e5));
    if (d1 > d2) throw new Blad("Data „od” jest późniejsza niż „do”.");
    return [iso(d1), iso(d2)];
  };
  Z.handle = async function (route, q, cfg, admin) {
    try {
      if (route === "/api/zamowienia") {
        const z = Z.czytaj_zamowienia(await Z.api_xml(cfg, "getOpenOrders"));
        return [200, { zamowienia: z, czas: new Date().toLocaleTimeString("pl-PL", { hour: "2-digit", minute: "2-digit" }) }];
      }
      if ((route === "/api/faktury" || route === "/api/faktura") && !admin) return [403, { error: "Faktury widzi administrator." }];
      if (route === "/api/faktury") {
        const [od, dO] = Z.okres(q.od || "", q.do || "");
        return [200, { faktury: Z.czytaj_faktury(await Z.api_xml(cfg, "getInvoices", { documentDateFrom: od, documentDateTo: dO })), od, do: dO }];
      }
      if (route === "/api/faktura") {
        const nr = (q.nr || "").trim().toUpperCase();
        if (!FAKTURA_NR.test(nr)) return [400, { error: "Zły numer faktury." }];
        return [200, Z.czytaj_fakture(await Z.api_xml(cfg, "getInvoice", { invoiceNumber: nr }))];
      }
    } catch (e) { if (e instanceof Blad) return [502, { error: e.message }]; throw e; }
    return [404, { error: "Nie znaleziono" }];
  };
  root.Zamowienia = Z;
  if (typeof module !== "undefined") module.exports = Z;
})(typeof window !== "undefined" ? window : globalThis);
