// IntegraCRM – pośrednik API wheel-size.com (dobór felg i opon po aucie). Klucz API nie trafia do komputerów:
// funkcja czyta go z sekretu WHEELSIZE_API_KEY. Dostęp: zalogowany użytkownik z modułem „dobor” (sprawdza baza).
// Wejście: POST {m: "makes"|"models"|..., params: {...}}. Wyjście: JSON z wheel-size albo {error}.
// Dozwolone tylko metody odczytu z listy i parametry z listy; region domyślnie eudm (Europa).
// Dzienny limit planu API: przed zapytaniem ws_licznik_dodaj(e-mail) kluczem serwera (baza liczy dzień, osobę, odmawia po limicie z app_config
// 'wheel_size'); odpowiedź dostaje pole _licznik {suma, limit} – Panel ostrzega przy 80% (od 2026-11-27).
import { createClient } from "npm:@supabase/supabase-js@2.45.4";

const URL = Deno.env.get("SUPABASE_URL")!;
const ANON = Deno.env.get("SUPABASE_ANON_KEY")!;
const SERVICE = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const KEY = Deno.env.get("WHEELSIZE_API_KEY") ?? "";
const API = "https://api.wheel-size.com/v2/";
const json = (b: unknown, s = 200) =>
  new Response(JSON.stringify(b), { status: s, headers: { "Content-Type": "application/json; charset=utf-8" } });

const METODY: Record<string, string> = {   // tylko to, czego używa Panel (płatny plan – nic ponad potrzebę)
  makes: "makes/", models: "models/", years: "years/", generations: "generations/",
  modifications: "modifications/", by_model: "search/by_model/",
};
const PARAMY = new Set(["make", "model", "year", "generation", "modification", "region"]);
Deno.serve(async (req) => {
  if (req.method !== "POST") return json({ error: "Tylko POST" }, 405);
  if (!KEY) return json({ error: "Brak klucza wheel-size w ustawieniach serwera." }, 500);
  const asUser = createClient(URL, ANON, { global: { headers: { Authorization: req.headers.get("Authorization") ?? "" } } });
  const { data: who } = await asUser.rpc("me");
  const email = String((who as { email?: string } | null)?.email ?? "").toLowerCase();
  if (!email) return json({ error: "Brak dostępu – zaloguj się w programie" }, 401);
  const { data: ok } = await asUser.rpc("has_module", { m: "dobor" });
  if (ok !== true) return json({ error: "Brak dostępu do doboru po aucie – poproś administratora." }, 403);
  let b: Record<string, unknown>;
  try { b = await req.json(); } catch { return json({ error: "Nieprawidłowe dane" }, 400); }
  const m = String(b.m ?? "");
  if (!Object.hasOwn(METODY, m)) return json({ error: "Niedozwolona operacja" }, 400);
  const q = new URLSearchParams();
  const params = (b.params && typeof b.params === "object") ? b.params as Record<string, unknown> : {};
  for (const [k, v] of Object.entries(params)) {
    if (!PARAMY.has(k)) return json({ error: "Nieprawidłowy parametr " + k.slice(0, 30) }, 400);
    if (v === null || v === undefined || v === "") continue;
    q.set(k, String(v).slice(0, 80));
  }
  if (!q.has("region") && !q.has("modification")) q.set("region", "eudm");
  const admin = createClient(URL, SERVICE, { auth: { persistSession: false } });
  const { data: lic, error: eLic } = await admin.rpc("ws_licznik_dodaj", { p_email: email });
  if (eLic) return json({ error: "Nie udało się sprawdzić dziennego limitu zapytań." }, 500);
  const L = lic as { ok: boolean; suma: number; limit: number };
  if (!L.ok) return json({ error: `Wyczerpany dzienny limit doboru po aucie (${L.suma} z ${L.limit}) – spróbuj jutro albo poproś administratora.`, licznik: L }, 429);
  q.set("user_key", KEY);
  const ctl = new AbortController();
  const stop = setTimeout(() => ctl.abort(), 20_000);
  try {
    const odp = await fetch(API + METODY[m] + "?" + q, { headers: { "Accept": "application/json", "User-Agent": "PanelLatexSerwis" }, signal: ctl.signal });
    const txt = await odp.text();
    if (!odp.ok) return json({ error: "wheel-size odpowiedział " + odp.status, szczegoly: txt.replaceAll(KEY, "***").slice(0, 300) }, 502);
    let out: unknown;
    try { out = JSON.parse(txt); } catch { return json({ error: "wheel-size: nieczytelna odpowiedź" }, 502); }
    if (out && typeof out === "object" && !Array.isArray(out)) (out as Record<string, unknown>)._licznik = { suma: L.suma, limit: L.limit };
    return json(out);
  } catch (e) {
    return json({ error: "Brak połączenia z wheel-size (" + (e as Error).name + ")" }, 502);
  } finally { clearTimeout(stop); }
});
