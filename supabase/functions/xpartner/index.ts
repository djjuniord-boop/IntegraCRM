// IntegraCRM – pośrednik API xPartner. Hasło B2B nie trafia do komputerów: funkcja czyta je z Vault
// (service_role) i sama wywołuje xPartner. Uprawnienia sprawdza baza tokenem użytkownika:
//   katalog (productsList, getProduct)                       – moduł „oferty”
//   zamówienia i faktury (getOpenOrders, getOrder, getInvoices, getInvoice) – „zamowienia” albo „zamawianie”
//   adresy dostawy i zamówienie (getDeliveryData, order)     – „zamawianie”
// (has_module zwraca true dla administratora). Zamówienie zapisuje się w Dzienniku zmian po stronie serwera.
// Znane ograniczenie: faktury i zamówienia innych oddziałów filtruje jeszcze program (zamowienia.py) – serwer
// sprawdza tylko moduł; przeniesienie tego filtra na serwer – w kolejnym etapie.
// Wejście: POST {m, params?: {klucz: wartość}, body?: "XML zamówienia"}. Wyjście: surowa odpowiedź XML xPartner
// albo JSON {error} (4xx/5xx).
import { createClient } from "npm:@supabase/supabase-js@2.45.4";

const URL = Deno.env.get("SUPABASE_URL")!;
const ANON = Deno.env.get("SUPABASE_ANON_KEY")!;
const SERVICE = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const API = "https://xpartner.net.pl/index.php";
const json = (b: unknown, s = 200) =>
  new Response(JSON.stringify(b), { status: s, headers: { "Content-Type": "application/json; charset=utf-8" } });

const METODY: Record<string, string[][]> = {   // każda grupa: wystarczy jeden moduł z listy; wszystkie grupy wymagane
  productsList: [["oferty"]],
  getProduct: [["oferty"]],
  getOpenOrders: [["oferty"], ["zamowienia", "zamawianie"]],
  getOrder: [["oferty"], ["zamowienia", "zamawianie"]],
  getInvoices: [["oferty"], ["zamowienia", "zamawianie"]],
  getInvoice: [["oferty"], ["zamowienia", "zamawianie"]],
  getDeliveryData: [["oferty"], ["zamawianie"]],
  order: [["oferty"], ["zamawianie"]],
};
const KLUCZ = /^[A-Za-z][A-Za-z0-9_]{0,40}$/;

Deno.serve(async (req) => {
  if (req.method !== "POST") return json({ error: "Tylko POST" }, 405);
  const auth = req.headers.get("Authorization") ?? "";
  const asUser = createClient(URL, ANON, { global: { headers: { Authorization: auth } } });
  const { data: who } = await asUser.rpc("me");
  const email = String((who as { email?: string } | null)?.email ?? "").toLowerCase();
  if (!email) return json({ error: "Brak dostępu – zaloguj się w programie" }, 401);

  let b: Record<string, unknown>;
  try { b = await req.json(); } catch { return json({ error: "Nieprawidłowe dane" }, 400); }
  const m = String(b.m ?? "");
  if (!Object.hasOwn(METODY, m)) return json({ error: "Niedozwolona operacja xPartner" }, 400);
  const grupy = METODY[m];
  for (const grupa of grupy) {
    let ok = false;
    for (const mod of grupa) {
      const { data } = await asUser.rpc("has_module", { m: mod });
      if (data === true) { ok = true; break; }
    }
    if (!ok) return json({ error: m === "order" || m === "getDeliveryData"
      ? "Brak uprawnienia do zamawiania w xPartner – poproś administratora."
      : "Brak dostępu do tej części xPartner – poproś administratora." }, 403);
  }

  const q = new URLSearchParams();
  const params = (b.params && typeof b.params === "object") ? b.params as Record<string, unknown> : {};
  for (const [k, v] of Object.entries(params)) {
    if (!KLUCZ.test(k) || ["a", "m", "login", "pass"].includes(k)) return json({ error: "Nieprawidłowy parametr" }, 400);
    if (v === null || v === undefined || v === "") continue;
    q.set(k, String(v).slice(0, 200));
  }
  const xml = m === "order" ? String(b.body ?? "") : "";
  if (m === "order" && (!xml || xml.length > 200_000)) return json({ error: "Nieprawidłowe zamówienie" }, 400);

  const admin = createClient(URL, SERVICE, { auth: { persistSession: false } });
  const { data: konto, error: e1 } = await admin.rpc("xpartner_dane", { p_email: email });
  const k = (Array.isArray(konto) ? konto[0] : konto) as { login?: string; haslo?: string } | null;
  if (e1) return json({ error: "Nie udało się odczytać konta xPartner z bazy." }, 500);
  if (!k?.login || !k?.haslo) {
    return json({ error: "Twoje konto nie ma jeszcze loginu API xPartner – poproś administratora (UŻYTKOWNICY → konto → xPartner)." }, 400);
  }
  const url = `${API}?${new URLSearchParams({ a: "b2b_xmlApi", login: k.login, pass: k.haslo, m })}&${q}`;

  const ctl = new AbortController();
  const stop = setTimeout(() => ctl.abort(), m === "order" ? 70_000 : 45_000);
  let odp: Response;
  let dane: Uint8Array;
  try {   // limit czasu obejmuje też odczyt treści odpowiedzi
    odp = await fetch(url, m === "order"
      ? { method: "POST", body: xml, headers: { "Content-Type": "application/xml", "User-Agent": "PanelLatexSerwis-Oferty" }, signal: ctl.signal }
      : { headers: { "User-Agent": "PanelLatexSerwis-Oferty" }, signal: ctl.signal });
    dane = new Uint8Array(await odp.arrayBuffer());
  } catch (e) {
    if (m === "order") await dziennik(admin, email, "brak odpowiedzi – sprawdzić w xPartner", { blad: (e as Error).name });
    return json({ error: `Brak połączenia z xPartner (${(e as Error).name})` }, 502);
  } finally {
    clearTimeout(stop);
  }
  if (m === "order") {
    const txt = new TextDecoder().decode(dane);
    const nr = [...txt.matchAll(/<order(?:XP|Xp|No)>([^<]{1,40})</g)].map((x) => x[1]);
    // szczegóły od programu (pozycje, adres, numer własny) – tylko jako opis, przycięte; numery i konto ustala serwer
    let opis: unknown = null;
    try {
      const t = JSON.stringify(b.dziennik ?? null);
      opis = t && t.length <= 4000 ? JSON.parse(t) : { uwaga: "szczegóły pominięte (za długie)" };
    } catch { opis = null; }
    await dziennik(admin, email, nr.length ? nr.join(", ") : "bez numeru",
                   { http: odp.status, numery: nr, znakow: xml.length, szczegoly: opis });
  }
  return new Response(dane, { status: 200, headers: { "Content-Type": "application/xml; charset=utf-8", "X-Xpartner-Status": String(odp.status) } });
});

async function dziennik(admin: ReturnType<typeof createClient>, email: string, label: string, detail: Record<string, unknown>) {
  try {
    await admin.from("audit_log").insert({ email, action: "zamówienie", entity: "xPartner (serwer)", label: label.slice(0, 200), detail });
  } catch { /* dziennik nie zatrzymuje zamówienia */ }
}
