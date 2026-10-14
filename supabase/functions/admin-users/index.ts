// IntegraCRM – operacje administratora na kontach (wymagają klucza service_role, dlatego na serwerze).
// Akcje: create {email, password, name, role, modules, branches}, set_password {email, password}, delete {email}
import { createClient } from "npm:@supabase/supabase-js@2.45.4";

const URL = Deno.env.get("SUPABASE_URL")!;
const ANON = Deno.env.get("SUPABASE_ANON_KEY")!;
const SERVICE = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

Deno.serve(async (req) => {
  if (req.method !== "POST") return json({ error: "Tylko POST" }, 405);
  const auth = req.headers.get("Authorization") ?? "";
  // 1. Kto pyta? Sprawdzamy w bazie jego tokenem – tylko aktywny admin.
  const asCaller = createClient(URL, ANON, { global: { headers: { Authorization: auth } } });
  const { data: isAdmin, error: e1 } = await asCaller.rpc("is_admin");
  if (e1 || isAdmin !== true) return json({ error: "Brak uprawnień administratora" }, 403);

  let b: Record<string, unknown>;
  try { b = await req.json(); } catch { return json({ error: "Nieprawidłowe dane" }, 400); }
  const email = String(b.email ?? "").trim().toLowerCase();
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) return json({ error: "Nieprawidłowy adres e-mail" }, 400);
  const password = String(b.password ?? "");
  const admin = createClient(URL, SERVICE, { auth: { persistSession: false } });

  const findUser = async () => {
    for (let page = 1; page < 50; page++) {
      const { data, error } = await admin.auth.admin.listUsers({ page, perPage: 200 });
      if (error) throw error;
      const u = data.users.find((x) => (x.email ?? "").toLowerCase() === email);
      if (u || data.users.length < 200) return u ?? null;
    }
    return null;
  };

  try {
    if (b.action === "create") {
      if (password.length < 8) return json({ error: "Hasło musi mieć co najmniej 8 znaków" }, 400);
      let u = await findUser();
      if (!u) {
        const { data, error } = await admin.auth.admin.createUser({ email, password, email_confirm: true });
        if (error) throw error;
        u = data.user;
      } else {
        const { error } = await admin.auth.admin.updateUserById(u.id, { password, ban_duration: "none" });
        if (error) throw error;
      }
      const { error } = await asCaller.rpc("admin_set_user", {
        p_email: email, p_name: String(b.name ?? ""), p_role: b.role === "admin" ? "admin" : "user",
        p_modules: (b.modules as string[]) ?? [], p_branches: (b.branches as string[]) ?? [], p_active: true,
      });
      if (error) throw error;
      await admin.from("app_users").update({ user_id: u!.id }).eq("email", email);
      return json({ ok: true });
    }
    if (b.action === "set_password") {
      if (password.length < 8) return json({ error: "Hasło musi mieć co najmniej 8 znaków" }, 400);
      const u = await findUser();
      if (!u) return json({ error: "Nie ma takiego konta" }, 404);
      const { error } = await admin.auth.admin.updateUserById(u.id, { password });
      if (error) throw error;
      return json({ ok: true });
    }
    if (b.action === "delete") {
      const { data: me } = await asCaller.rpc("me");
      if ((me?.email ?? "").toLowerCase() === email) return json({ error: "Nie możesz usunąć własnego konta" }, 400);
      const u = await findUser();
      if (u) {
        const { error } = await admin.auth.admin.deleteUser(u.id);
        if (error) throw error;
      }
      await admin.from("app_users").delete().eq("email", email);
      return json({ ok: true });
    }
    return json({ error: "Nieznana akcja" }, 400);
  } catch (e) {
    return json({ error: String((e as Error).message ?? e) }, 500);
  }
});
