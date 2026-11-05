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
  A.profil = null;
  A.start = async function () {
    const me = await A.db("POST", "/rest/v1/rpc/me", {});
    const p = Array.isArray(me) ? me[0] : me;
    if (!p || !p.email) throw new Error("To konto jest nieaktywne albo nie ma dostępu do programu.");
    const admin = p.role === "admin";
    if (!admin && !(p.modules || []).includes("oferty")) throw new Error("Twoje konto nie ma dostępu do modułu Oferty opon – poproś administratora.");
    A.profil = p;
    const rows = (await A.db("GET", "/rest/v1/oferty_konta?select=xp_login,xp_haslo,ustawienia&email=eq." + encodeURIComponent(p.email.toLowerCase()))) || [];
    const r = rows[0] || {};
    Object.assign(S.KONTO, { login: r.xp_login || "", password: r.xp_haslo || "", ustawienia: r.ustawienia || {},
      zapisz: (dane) => A.db("POST", "/rest/v1/rpc/oferty_zapisz_ustawienia", { p: dane }) });
    let names = {};
    S.HIST = {
      admin,
      async get_id(id) { const x = (await A.db("GET", "/rest/v1/oferty?select=dane&id=eq." + (+id))) || []; return x[0] ? x[0].dane : null; },
      async save(oid, klient, dane, szukaj) {
        await A.db("POST", "/rest/v1/oferty?on_conflict=owner,oid", { oid, klient: klient || "", dane, szukaj: szukaj.slice(0, 2000), updated_at: new Date().toISOString() },
          "resolution=merge-duplicates,return=minimal");
      },
      async list(q) {
        q = (q || "").trim().toLowerCase().replace(/[*,()]/g, " ");
        const f = q ? "&or=(szukaj.ilike.*" + encodeURIComponent(q) + "*,owner.ilike.*" + encodeURIComponent(q) + "*)" : "";
        const rows = (await A.db("GET", "/rest/v1/oferty?select=id,owner,dane&order=updated_at.desc&limit=500" + f)) || [];
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
  A.wersja = () => (window.Native && window.Native.version ? window.Native.version() : "dev");
  A.sprawdzAktualizacje = async function () {
    try {
      const r = await A.http("https://github.com/djjuniord-boop/IntegraCRM/releases/download/aplikacja-android/aplikacja.json", "GET", {});
      if (r.status !== 200) return null;
      const j = JSON.parse(r.text), cur = A.wersja().split(".").map(Number), nw = String(j.version || "").split(".").map(Number);
      for (let i = 0; i < 3; i++) { if ((nw[i] || 0) > (cur[i] || 0)) return j; if ((nw[i] || 0) < (cur[i] || 0)) return null; }
    } catch (e) {}
    return null;
  };
})();
