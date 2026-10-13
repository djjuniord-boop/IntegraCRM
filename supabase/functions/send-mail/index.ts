// IntegraCRM – wysyłka maila z brakami z serwera (Gmail SMTP, hasło aplikacji w sekretach funkcji).
// Odbiorcy tylko z ustawień firmowych (app_config.crm) + nadawca jako kopia – funkcji nie da się użyć do spamu.
import { createClient } from "npm:@supabase/supabase-js@2.45.4";
import nodemailer from "npm:nodemailer@6.9.15";

const URL = Deno.env.get("SUPABASE_URL")!;
const ANON = Deno.env.get("SUPABASE_ANON_KEY")!;
const GMAIL_USER = Deno.env.get("GMAIL_USER") ?? "";
const GMAIL_PASS = (Deno.env.get("GMAIL_APP_PASSWORD") ?? "").replace(/\s/g, "");
const json = (b: unknown, s = 200) => new Response(JSON.stringify(b), { status: s, headers: { "Content-Type": "application/json" } });

Deno.serve(async (req) => {
  if (req.method !== "POST") return json({ error: "Tylko POST" }, 405);
  const sb = createClient(URL, ANON, { global: { headers: { Authorization: req.headers.get("Authorization") ?? "" } } });
  // najpierw: czy to aktywne konto programu (bez tego nic nie zdradzamy, nawet stanu konfiguracji)
  const { data: who } = await sb.rpc("me");
  if (!who || !(who as { email?: string }).email) return json({ error: "Brak dostępu – zaloguj się w programie" }, 401);
  if (!GMAIL_USER || !GMAIL_PASS) return json({ error: "Wysyłka z serwera nie jest skonfigurowana (brak sekretów GMAIL_USER / GMAIL_APP_PASSWORD)." }, 503);
  let b: Record<string, unknown>;
  try { b = await req.json(); } catch { return json({ error: "Nieprawidłowe dane" }, 400); }

  // MARŻA: gotowa wiadomość (HTML z wykresem) z kalkulatora – odbiorcy z listy MARŻA w ustawieniach firmowych
  if (b.action === "raw") {
    const { data: okm } = await sb.rpc("has_module", { m: "marza" });
    if (okm !== true) return json({ error: "Brak dostępu do modułu MARŻA" }, 403);
    const { data: rows } = await sb.from("app_config").select("value").eq("key", "crm");
    const mz = ((rows?.[0]?.value ?? {}) as { marza?: Record<string, { email: string }[]> }).marza ?? {};
    const ok = new Set(Object.values(mz).flat().map((r) => String(r.email).toLowerCase()));
    const rto = Array.isArray(b.to) ? (b.to as unknown[]).map((x) => String(x).trim().toLowerCase()) : [];
    const rbad = rto.filter((x) => !ok.has(x));
    if (!rto.length || rbad.length) return json({ error: `Adres spoza listy odbiorców MARŻY: ${rbad.join(", ")}` }, 400);
    let raw = String(b.raw ?? "");
    if (!raw || raw.length > 8_000_000) return json({ error: "Nieprawidłowa wiadomość" }, 400);
    // nagłówek „Od” zawsze z konta wysyłkowego serwera (silnik nie zna tego adresu)
    const cut = raw.search(/\r?\n\r?\n/);
    if (cut > 0) raw = raw.slice(0, cut).replace(/^From:[^\r\n]*(\r?\n[ \t][^\r\n]*)*/m, `From: Panel Wynikow LATEX <${GMAIL_USER}>`) + raw.slice(cut);
    const t = nodemailer.createTransport({ host: "smtp.gmail.com", port: 465, secure: true, auth: { user: GMAIL_USER, pass: GMAIL_PASS } });
    try {
      await t.sendMail({ envelope: { from: GMAIL_USER, to: rto }, raw });
    } catch (e) {
      return json({ error: `Gmail odrzucił wysyłkę: ${(e as Error).message}` }, 502);
    }
    return json({ ok: true, to: rto, from: GMAIL_USER });
  }

  // Kontrola CRM: mail z brakami
  const { data: ok } = await sb.rpc("has_module", { m: "crm" });
  if (ok !== true) return json({ error: "Brak dostępu do modułu Kontrola CRM" }, 403);
  const me = who as { email?: string };
  if (b.action === "status") return json({ ok: true, from: GMAIL_USER });
  const subject = String(b.subject ?? "").slice(0, 300);
  const text = String(b.body ?? "").slice(0, 50000);
  const to = Array.isArray(b.to) ? (b.to as unknown[]).map((x) => String(x).trim().toLowerCase()).filter(Boolean) : [];
  if (!subject || !text || !to.length) return json({ error: "Brak tematu, treści albo odbiorców" }, 400);

  // dozwoleni odbiorcy = ustawienia firmowe
  const { data: cfgRows } = await sb.from("app_config").select("value").eq("key", "crm");
  const cfg = (cfgRows?.[0]?.value ?? {}) as { recipients?: string[]; by_branch?: Record<string, string[]>; sender_name?: string };
  const allowed = new Set<string>([...(cfg.recipients ?? []), ...Object.values(cfg.by_branch ?? {}).flat()].map((x) => x.toLowerCase()));
  const bad = to.filter((x) => !allowed.has(x));
  if (bad.length) return json({ error: `Adres spoza listy odbiorców firmy: ${bad.join(", ")} – administrator ustawia ją w Ustawieniach.` }, 400);

  const userEmail = String(me?.email ?? "");
  const transport = nodemailer.createTransport({ host: "smtp.gmail.com", port: 465, secure: true, auth: { user: GMAIL_USER, pass: GMAIL_PASS } });
  try {
    await transport.sendMail({
      from: { name: cfg.sender_name || "Kontrola eksportu – Latex Serwis", address: GMAIL_USER },
      to, cc: b.cc_self && userEmail && !to.includes(userEmail.toLowerCase()) ? [userEmail] : undefined,
      replyTo: userEmail || undefined, subject, text,
    });
  } catch (e) {
    return json({ error: `Gmail odrzucił wysyłkę: ${(e as Error).message}` }, 502);
  }
  return json({ ok: true, to, from: GMAIL_USER });
});
