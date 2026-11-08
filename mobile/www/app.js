/* Aplikacja „Oferty opon” (Android): logowanie Supabase (to samo konto co Panel), most do Androida, baza. */
(function () {
  "use strict";
  const SB = "https://nlrwulrtaocuemfmlfav.supabase.co";
  const ANON = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5scnd1bHJ0YW9jdWVtZm1sZmF2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTE4ODY2NTYsImV4cCI6MjEwNzQ2MjY1Nn0.F6Qd7vvYuDZs4Opt_4dnOPmPpsKB8rzAZ5iF47h6gtk";   // klucz publiczny (jak w app/cloud.py) – dostęp chronią zasady RLS w bazie
  const S = window.Silnik;
  const A = (window.Aplikacja = {});
  const LS = { get: (k) => { try { return localStorage.getItem(k); } catch (e) { return null; } },
               set: (k, v) => { try { v == null ? localStorage.removeItem(k) : localStorage.setItem(k, v); } catch (e) {} } };

  // ---------- HTTP: natywnie przez Androida (bez ograniczeń CORS), w przeglądarce testowej – fetch
  let seq = 0; const waiting = {};
  window.__httpDone = function (id, status, text) { const w = waiting[id]; if (w) { delete waiting[id]; w({ status, text }); } };
  A.http = function (url, method, headers, body) {
    method = method || "GET";
    if (window.Native && window.Native.http) {
      const id = "h" + (++seq);
      return new Promise((ok) => { waiting[id] = ok; window.Native.http(id, method, url, JSON.stringify(headers || {}), body == null ? "" : body); });
    }
    return fetch(url, { method, headers: headers || {}, body: body == null ? undefined : body }).then(async (r) => ({ status: r.status, text: await r.text() }), () => ({ status: 0, text: "" }));
  };
  S.http = (url) => A.http(url, "GET", { "User-Agent": "LatexOferty-Android" });

  // ---------- sesja
  let ses = null; try { ses = JSON.parse(LS.get("sesja") || "null"); } catch (e) {}
  A.zalogowany = () => !!(ses && ses.refresh);
  A.email = () => (ses && ses.email) || "";
  async function auth(body, grant) {
    const r = await A.http(SB + "/auth/v1/token?grant_type=" + grant, "POST", { apikey: ANON, "Content-Type": "application/json" }, JSON.stringify(body));
    let j = {}; try { j = JSON.parse(r.text || "{}"); } catch (e) {}
    if (r.status === 0) throw new Error("Brak połączenia z internetem.");
    if (r.status >= 400) throw new Error(grant === "password" ? "Nieprawidłowy e-mail lub hasło." : "Sesja wygasła – zaloguj się ponownie.");
    ses = { access: j.access_token, refresh: j.refresh_token, email: (j.user && j.user.email || "").toLowerCase(), exp: Date.now() + (j.expires_in || 3600) * 1000 - 60000 };
    LS.set("sesja", JSON.stringify(ses));
  }
  A.login = (email, haslo) => auth({ email: email.trim(), password: haslo }, "password");
  A.logout = async () => { try { if (ses) await A.http(SB + "/auth/v1/logout", "POST", { apikey: ANON, Authorization: "Bearer " + ses.access }, ""); } catch (e) {} ses = null; LS.set("sesja", null); S.KONTO.zapisz = null; };
  async function token() {
    if (!ses) throw new Error("Zaloguj się.");
    if (Date.now() > (ses.exp || 0)) await auth({ refresh_token: ses.refresh }, "refresh_token");
    return ses.access;
  }
  A.db = async function (method, path, body, prefer) {
    const h = { apikey: ANON, Authorization: "Bearer " + (await token()), "Content-Type": "application/json", Prefer: prefer || "return=representation" };
    let r = await A.http(SB + path, method, h, body == null ? null : JSON.stringify(body));
    if (r.status === 401) { await auth({ refresh_token: ses.refresh }, "refresh_token"); h.Authorization = "Bearer " + ses.access; r = await A.http(SB + path, method, h, body == null ? null : JSON.stringify(body)); }
    if (r.status === 0) throw new Error("Brak połączenia z serwerem.");
    let j = null; try { j = r.text ? JSON.parse(r.text) : null; } catch (e) {}
    if (r.status >= 400) throw new Error((j && (j.message || j.msg)) || "Błąd serwera (" + r.status + ")");
    return j;
  };

  // ---------- profil, konto xPartner, historia (te same tabele co Panel)
  A.profil = null; A.moze = {};
  A.wyniki = async function () {   // jak Panel: miesiące + aktualizacje od początku poprzedniego miesiąca
    const d = new Date(), od = new Date(d.getFullYear(), d.getMonth() - 1, 1);
    const ods = od.getFullYear() + "-" + String(od.getMonth() + 1).padStart(2, "0") + "-01";
    const months = (await A.db("GET", "/rest/v1/marza_months?select=*&order=year.desc,month.desc")) || [];
    const runs = (await A.db("GET", "/rest/v1/marza_results?select=branch,month_label,done,target,run_at&run_at=gte." + ods + "&order=run_at.asc")) || [];
    return { months, runs };
  };
  A.start = async function () {
    const me = await A.db("POST", "/rest/v1/rpc/me", {});
    const p = Array.isArray(me) ? me[0] : me;
    if (!p || !p.email) throw new Error("To konto jest nieaktywne albo nie ma dostępu do programu.");
    const admin = p.role === "admin", mod = p.modules || [];
    // zakładki jak w Panelu: OFERTY OPON – moduł „oferty”; WYNIKI – moduł „wyniki” albo „marza” (dane i tak pilnuje baza)
    A.moze = { oferty: admin || mod.includes("oferty"), wyniki: admin || mod.includes("wyniki") || mod.includes("marza"), zamowienia: admin || mod.includes("zamowienia") };
    if (!A.moze.oferty && !A.moze.wyniki && !A.moze.zamowienia) throw new Error("Twoje konto nie ma dostępu do Ofert opon, Wyników ani Zamówień – poproś administratora.");
    A.profil = p;
    S.KONTO.admin = admin; S.KONTO.zamowienia = A.moze.zamowienia;
    if (!A.moze.oferty && !A.moze.zamowienia) return p;
    // oddział na PDF: z konta (nie do zmiany przez pracownika); dane oddziałów wpisuje administrator w Panelu
    let odd = {};
    try { const c = (await A.db("GET", "/rest/v1/app_config?key=eq.oddzialy&select=value")) || []; odd = (c[0] && c[0].value) || {}; } catch (e) {}
    Object.assign(S.KONTO, { oddzialy: admin ? Object.keys(odd) : (p.branches || []), oddzialy_dane: odd, kto: p.name || p.email });
    const rows = (await A.db("GET", "/rest/v1/oferty_konta?select=*&email=eq." + encodeURIComponent(p.email.toLowerCase()))) || [];
    const r = rows[0] || {};
    // hasło xPartner: z zaszyfrowanego sejfu przez funkcję bazy (tylko własne); przed etapem 2 – jawna kolumna
    let haslo = "";
    try { haslo = (await A.db("POST", "/rest/v1/rpc/oferty_moje_haslo", {})) || ""; } catch (e) { haslo = r.xp_haslo || ""; }
    Object.assign(S.KONTO, { login: r.xp_login || "", password: typeof haslo === "string" ? haslo : "", ustawienia: r.ustawienia || {},
      zapisz: (dane) => A.db("POST", "/rest/v1/rpc/oferty_zapisz_ustawienia", { p: dane }) });
    // wyszukiwanie w kopii pliku ofertowego xPartner (tabela xp_oferta) – jak Katalog w okno.py
    const K = { stan: null, t: 0, uzyty: false };
    const swiezy = async () => {
      if (Date.now() - K.t > 120000) {
        try { const c = (await A.db("GET", "/rest/v1/app_config?key=eq.xp_oferta_stan&select=value")) || []; K.stan = (c[0] && c[0].value) || null; } catch (e) { K.stan = null; }
        K.t = Date.now();
      }
      const t = K.stan && Date.parse(K.stan.czas);
      return !!t && Date.now() - t < 3 * 3600 * 1000 && (K.stan.ile || 0) > 0;
    };
    S.KONTO.katalog = async (size) => {
      const m = /^(\d{3})\/(\d{2}) R(\d{2})/.exec(size || "");
      if (!m || !(await swiezy())) { K.uzyty = false; return null; }
      const rows = (await A.db("GET", `/rest/v1/xp_oferta?select=dane&szer=eq.${m[1]}&profil=eq.${m[2]}&sred=eq.${m[3]}&limit=5000`)) || [];
      K.uzyty = true;
      return rows.map((x) => x.dane).filter((d) => d && typeof d === "object");
    };
    S.KONTO.katalog_cechy = async (pid) => {
      const rows = (await A.db("GET", "/rest/v1/xp_oferta?select=dane&id=eq." + (+pid || 0))) || [];
      return (rows[0] && rows[0].dane && rows[0].dane.attrs) || {};
    };
    S.KONTO.katalog_info = () => K.uzyty ? "Oferta xPartner z godz. " + new Date(K.stan.czas).toLocaleTimeString("pl-PL", { hour: "2-digit", minute: "2-digit" }) + " (kopia co 30 min; ceny w ofercie – na żywo)" : "";
    let names = {};
    S.HIST = {
      admin,
      get me() { return A.email(); },
      async get_id(id) { const x = (await A.db("GET", "/rest/v1/oferty?select=dane&id=eq." + (+id))) || []; return x[0] ? x[0].dane : null; },
      async save(oid, klient, dane, szukaj) {
        await A.db("POST", "/rest/v1/oferty?on_conflict=owner,oid", { oid, klient: klient || "", dane, szukaj: szukaj.slice(0, 2000), updated_at: new Date().toISOString() },
          "resolution=merge-duplicates,return=minimal");
      },
      async link(oid, dane) { return await A.db("POST", "/rest/v1/rpc/oferty_link", { p_oid: oid, p_dane: dane }); },
      async status(oid, st) { await A.db("POST", "/rest/v1/rpc/oferty_status", { p_oid: oid, p_status: st }, "return=minimal"); },
      async list(q) {
        q = (q || "").trim().toLowerCase().replace(/[*,()]/g, " ");
        const f = q ? "&or=(szukaj.ilike.*" + encodeURIComponent(q) + "*,owner.ilike.*" + encodeURIComponent(q) + "*)" : "";
        let rows;
        try { rows = (await A.db("GET", "/rest/v1/oferty?select=id,owner,dane,status,status_at,link_at,link_otwarta,klient_odp&order=updated_at.desc&limit=500" + f)) || []; }
        catch (e) { rows = (await A.db("GET", "/rest/v1/oferty?select=id,owner,dane&order=updated_at.desc&limit=500" + f)) || []; }
        if (admin && !Object.keys(names).length) { try { for (const u of (await A.db("GET", "/rest/v1/app_users?select=email,name")) || []) names[u.email.toLowerCase()] = u.name || ""; } catch (e) {} }
        for (const r of rows) r.kto = names[(r.owner || "").toLowerCase()] || r.owner || "";
        return rows;
      },
    };
    return p;
  };

  // ---------- Android: udostępnianie, linki, wersja
  A.share = (text, title) => { if (window.Native && window.Native.share) window.Native.share(text, title || "Oferta"); else if (navigator.share) navigator.share({ text, title }); else navigator.clipboard.writeText(text); };
  A.openUrl = (u) => { if (!/^https:\/\//.test(u)) return; if (window.Native && window.Native.openUrl) window.Native.openUrl(u); else window.open(u, "_blank"); };
  // PDF oferty: Android tworzy plik i otwiera „Udostępnij”; w przeglądarce (testy) – podgląd strony
  let pdfOk = null;
  window.__pdfDone = (ok, m) => { const f = pdfOk; pdfOk = null; if (f) f(ok, m); };
  A.pdf = (html, nazwa) => new Promise((ok) => {
    if (window.Native && window.Native.pdf) { pdfOk = (o, m) => ok({ ok: o, msg: m }); window.Native.pdf(html, nazwa); }
    else { const w = window.open("", "_blank"); if (w) { w.document.write(html); w.document.close(); } ok({ ok: true, msg: "podgląd" }); }
  });
  A.pdfOtworz = (n) => { if (window.Native && window.Native.pdfOtworz) window.Native.pdfOtworz(n); };
  A.pdfWyslij = (n) => { if (window.Native && window.Native.pdfWyslij) window.Native.pdfWyslij(n); };
  A.wersja = () => (window.Native && window.Native.version ? window.Native.version() : "dev");
  A.sprawdzAktualizacje = async function () {
    try {
      const r = await A.http("https://github.com/djjuniord-boop/IntegraCRM/releases/download/aplikacja-android/aplikacja.json", "GET", {});
      if (r.status !== 200) return { blad: true };
      const j = JSON.parse(r.text), cur = A.wersja().split(".").map(Number), nw = String(j.version || "").split(".").map(Number);
      for (let i = 0; i < 3; i++) { if ((nw[i] || 0) > (cur[i] || 0)) return j; if ((nw[i] || 0) < (cur[i] || 0)) return null; }
    } catch (e) { return { blad: true }; }
    return null;  // null = masz najnowszą, {blad} = nie udało się sprawdzić, {version,url} = jest nowa
  };
})();
