import { randomUUID } from "node:crypto";
import { appURL } from "./app-url";
import { auth } from "./auth";
import { normalizeUsername, usernamePattern } from "./auth-options";

const readPaths = new Set(["/jwks"]);
const writePaths = new Set(["/sign-up/username", "/sign-in/username", "/sign-out"]);
const json = (status: number, message: string) => Response.json({ message }, {
  status, headers: { "cache-control": "no-store" },
});
class BodyTooLarge extends Error {}

async function readBody(request: Request): Promise<string> {
  const reader = request.body?.getReader();
  if (!reader) return "{}";
  const chunks: Uint8Array[] = [];
  let size = 0;
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    size += value.length;
    if (size > 4096) { await reader.cancel(); throw new BodyTooLarge(); }
    chunks.push(value);
  }
  return Buffer.concat(chunks).toString("utf8");
}

export async function handleAuth(request: Request): Promise<Response> {
  const url = new URL(request.url);
  const path = url.pathname.slice("/api/auth".length);
  if (!(request.method === "GET" ? readPaths : writePaths).has(path)) return json(404, "Route inconnue.");
  // Fixed shared bucket: independent of client-controlled forwarded headers.
  // Deliberately global for this small, zero-budget demonstration.
  const headers = new Headers(request.headers);
  for (const name of ["x-forwarded-for", "x-real-ip", "x-vercel-forwarded-for", "forwarded"]) headers.delete(name);
  headers.set("x-forwarded-for", "127.0.0.1");
  try {
    let body: string | undefined;
    if (request.method === "POST") {
      if (request.headers.get("origin") !== new URL(appURL()).origin) {
        return json(403, "Origine refusée.");
      }
      body = await readBody(request);
      if (path !== "/sign-out") {
        const input: unknown = JSON.parse(body);
        if (!input || typeof input !== "object" || !("username" in input) || !("password" in input)
            || typeof input.username !== "string" || typeof input.password !== "string") {
          return json(400, "Identifiants invalides.");
        }
        const name = normalizeUsername(input.username);
        if (name.length > 64 || !usernamePattern.test(name) || input.password.length > 128
            || (path === "/sign-up/username" && input.password.length < 12)) {
          return json(400, "Utilisez prenom.nom et un mot de passe de 12 à 128 caractères.");
        }
        // Better Auth requires an email internally; no personal address is collected or used.
        body = JSON.stringify(path === "/sign-up/username"
          ? { username: name, name, email: `${randomUUID()}@accounts.invalid`, password: input.password }
          : { username: name, password: input.password });
        if (path === "/sign-up/username") url.pathname = "/api/auth/sign-up/email";
      } else body = "{}";
      headers.set("content-type", "application/json");
      headers.delete("content-length");
    }
    const result = await auth.handler(new Request(url, { method: request.method, headers, body }));
    const outputHeaders = new Headers(result.headers);
    outputHeaders.delete("content-length");
    outputHeaders.set("cache-control", "no-store");
    outputHeaders.delete("set-auth-jwt");
    // Session tokens and SDK-only identifiers never need to reach application JavaScript.
    if (result.ok && path !== "/jwks") {
      return new Response(JSON.stringify({ ok: true }), { status: result.status, headers: outputHeaders });
    }
    if (!result.ok) {
      return new Response(JSON.stringify({ message: result.status === 429
        ? "Trop de tentatives. Réessayez dans une minute."
        : path === "/sign-up/username" ? "Création impossible. Vérifiez les champs ou choisissez un autre nom."
        : "Nom d’utilisateur ou mot de passe incorrect." }), { status: result.status, headers: outputHeaders });
    }
    return result;
  } catch (error) {
    if (error instanceof BodyTooLarge) return json(413, "Requête trop volumineuse.");
    if (error instanceof SyntaxError) return json(400, "Requête invalide.");
    return json(503, "Connexion indisponible. Réessayez dans un instant.");
  }
}
