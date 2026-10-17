// IntegraCRM – zapasowe źródło aktualizacji: pośredniczy w pobieraniu plików z GitHub Releases
// dla komputerów, z których GitHub jest nieosiągalny (np. sieć w serwisie). Tylko pliki z repozytorium
// programu, tylko version.json i paczka integra-x.y.z.zip (sha256 sprawdza program).
const REPO = "https://github.com/djjuniord-boop/IntegraCRM/releases";
const FILE = /^(version\.json|integra-\d+\.\d+\.\d+\.zip)$/;

Deno.serve(async (req) => {
  if (req.method !== "GET") return new Response("Tylko GET", { status: 405 });
  // …/aktualizacje/<kanal>/<plik>, kanal: latest (oficjalny) albo beta
  const parts = new URL(req.url).pathname.split("/").filter(Boolean);
  const [kanal, plik] = parts.slice(-2);
  if (!FILE.test(plik ?? "") || !["latest", "beta"].includes(kanal ?? "")) return new Response("Nie znaleziono", { status: 404 });
  const src = kanal === "beta" ? `${REPO}/download/kanal-beta/${plik}` : `${REPO}/latest/download/${plik}`;
  const r = await fetch(src, { redirect: "follow" });
  if (!r.ok) return new Response(`GitHub: ${r.status}`, { status: 502 });
  return new Response(r.body, {
    headers: { "Content-Type": plik.endsWith(".zip") ? "application/zip" : "application/json", "Cache-Control": "no-store" },
  });
});
