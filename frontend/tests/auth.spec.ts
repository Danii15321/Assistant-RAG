import { test, expect, request as apiRequest, type APIRequestContext } from "@playwright/test";
import { Pool } from "pg";
import { betterAuth } from "better-auth";
import { authOptions } from "../src/lib/auth-options";

const databaseURL = process.env.AUTH_TEST_DATABASE_URL;
if (!databaseURL || new URL(databaseURL).pathname !== "/assistant_rag_test") {
  throw new Error("Authentication tests require the isolated assistant_rag_test database.");
}
const pool = new Pool({ connectionString: databaseURL, max: 2 });
const baseURL = process.env.TEST_BASE_URL!;
const sdk = betterAuth(authOptions(pool, baseURL, process.env.TEST_AUTH_SECRET!));
test.beforeEach(async () => { await pool.query("DELETE FROM auth_rate_limit"); });
test.afterAll(async () => { await pool.end(); });

async function signUp(context: APIRequestContext, username: string) {
  const response = await context.post("/api/auth/sign-up/username", {
    headers: { origin: baseURL }, data: { username, password },
  });
  expect(response.status()).toBe(200);
  expect(await response.json()).toEqual({ ok: true });
}
async function mintToken(context: APIRequestContext) {
  const cookies = (await context.storageState()).cookies;
  const headers = new Headers({ cookie: cookies.map(c => `${c.name}=${c.value}`).join("; ") });
  return (await sdk.api.getToken({ headers })).token;
}

const password = "Local test password 2026!";

// Real credentials, database, cookies, server bridge and FastAPI: no auth mocks.
test("inscription, compte privé, déconnexion et reconnexion", async ({ page }) => {
  const unique = `${Date.now()}${String(Math.floor(Math.random() * 10000)).padStart(4, "0")}`;
  const username = `alice${unique}`.padEnd(62, "a") + ".b";
  await page.goto("/sign-up");
  await page.getByLabel("Nom d’utilisateur").fill(username);
  await page.getByLabel("Mot de passe", { exact: true }).fill(password);
  await page.getByLabel("Confirmer le mot de passe").fill(password);
  await page.getByRole("button", { name: "Créer mon compte" }).click();
  await expect(page).toHaveURL(/\/library$/);
  await expect(page.getByRole("heading", { name: "Ma bibliothèque" })).toBeVisible();
  await expect(page.getByText(username, { exact: true })).toBeVisible();
  const profile = await page.request.get("/api/v1/users/me");
  expect(profile.status()).toBe(200);
  const id = (await profile.json()).id;
  expect(id).toMatch(/^[a-f0-9-]{36}$/);
  const cookies = await page.context().cookies();
  const session = cookies.find((cookie) => cookie.name.endsWith("session_token"));
  expect(session?.httpOnly).toBe(true);
  expect(session?.sameSite).toBe("Lax");
  await page.screenshot({ path: test.info().outputPath("library.png"), fullPage: true });
  await page.getByRole("button", { name: "Se déconnecter" }).click();
  await expect(page).toHaveURL(/\/sign-in$/);
  expect((await page.request.get("/api/v1/users/me")).status()).toBe(401);
  await page.getByLabel("Nom d’utilisateur").fill(username.toUpperCase());
  await page.getByLabel("Mot de passe", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Se connecter" }).click();
  await expect(page).toHaveURL(/\/library$/);
  expect((await (await page.request.get("/api/v1/users/me")).json()).id).toBe(id);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect(await page.evaluate(() => Object.values(localStorage))).toEqual([]);
  const jwt = await mintToken(page.request);
  const claims = JSON.parse(Buffer.from(jwt.split(".")[1], "base64url").toString());
  await pool.query(`UPDATE auth_session SET "expiresAt" = CURRENT_TIMESTAMP - interval '1 second' WHERE id = $1`, [claims.sid]);
  await page.reload();
  await expect(page).toHaveURL(/\/sign-in$/);
});

test("pages privées inaccessibles sans session", async ({ page }) => {
  for (const path of ["/library", "/search", "/conversations", "/conversations/00000000-0000-0000-0000-000000000001"]) {
    await page.goto(path);
    await expect(page).toHaveURL(/\/sign-in$/);
  }
  expect((await page.request.get("/api/v1/users/me")).status()).toBe(401);
  expect((await page.request.get("/api/v1/conversations")).status()).toBe(401);
});


test("deux comptes isolés, JWT réel révoqué et session expirée", async () => {
  const alice = await apiRequest.newContext({ baseURL });
  const bob = await apiRequest.newContext({ baseURL });
  const direct = await apiRequest.newContext({ baseURL: process.env.TEST_API_URL });
  try {
    const marker = `${Date.now()}${Math.floor(Math.random() * 1000)}`;
    await signUp(alice, `alice.t${marker}`);
    await signUp(bob, `bob.t${marker}`);
    const a = await (await alice.get("/api/v1/users/me")).json();
    const b = await (await bob.get("/api/v1/users/me")).json();
    expect(a.id).not.toBe(b.id);
    expect((await alice.get(`/api/v1/users/${a.id}`)).status()).toBe(200);
    const inaccessible = await alice.get(`/api/v1/users/${b.id}`);
    const absent = await alice.get("/api/v1/users/00000000-0000-0000-0000-000000000001");
    expect(inaccessible.status()).toBe(404);
    expect(await inaccessible.json()).toEqual(await absent.json());
    const jwt = await mintToken(alice);
    const headers = { authorization: `Bearer ${jwt}` };
    expect((await direct.get("/api/v1/users/me", { headers })).status()).toBe(200);
    expect((await direct.get("/api/v1/users/me")).status()).toBe(401);
    expect((await direct.get("/api/v1/users/me", { headers: { authorization: "Bearer tampered" } })).status()).toBe(401);
    expect((await alice.post("/api/auth/sign-out", { headers: { origin: baseURL }, data: {} })).status()).toBe(200);
    expect((await direct.get("/api/v1/users/me", { headers })).status()).toBe(401);
    const bobJwt = await mintToken(bob);
    const claims = JSON.parse(Buffer.from(bobJwt.split(".")[1], "base64url").toString());
    expect(Object.keys(claims).sort()).toEqual(["aud", "exp", "iat", "iss", "sid", "sub"].sort());
    expect(claims.exp - claims.iat).toBe(300);
    await pool.query(`UPDATE auth_session SET "expiresAt" = CURRENT_TIMESTAMP - interval '1 second' WHERE id = $1`, [claims.sid]);
    expect((await bob.get("/api/v1/users/me")).status()).toBe(401);
    expect((await direct.get("/api/v1/users/me", { headers: { authorization: `Bearer ${bobJwt}` } })).status()).toBe(401);
    const stored = await pool.query('SELECT password FROM auth_account WHERE "userId" = $1', [claims.sub]);
    expect(stored.rows[0].password).not.toBe(password);
    expect(stored.rows[0].password.length).toBeGreaterThan(64);
    const keys = await pool.query('SELECT "privateKey" FROM auth_jwks');
    for (const key of keys.rows) expect(key.privateKey).not.toContain('"d":');
  } finally { await Promise.all([alice.dispose(), bob.dispose(), direct.dispose()]); }
});

test("validation, origines, chemins interdits et limite de connexion", async () => {
  const context = await apiRequest.newContext({ baseURL });
  try {
    const username = `carol.t${Date.now()}`;
    const badOrigin = await context.post("/api/auth/sign-up/username", {
      headers: { origin: "https://attacker.invalid" }, data: { username, password },
    });
    expect(badOrigin.status()).toBe(403);
    for (const input of [{ username: "sanspoint", password }, { username, password: "short" }]) {
      expect((await context.post("/api/auth/sign-up/username", { headers: { origin: baseURL }, data: input })).status()).toBe(400);
    }
    for (const path of ["/sign-up/email", "/sign-in/email", "/sign-in/social", "/sign-jwt", "/forget-password"]) {
      expect((await context.post(`/api/auth${path}`, { headers: { origin: baseURL }, data: {} })).status()).toBe(404);
    }
    for (const path of ["/token", "/get-session"]) {
      expect((await context.get(`/api/auth${path}`)).status()).toBe(404);
    }
    expect((await context.post("/api/auth/sign-up/username", {
      headers: { origin: baseURL, "content-type": "application/json" }, data: "{broken-json",
    })).status()).toBe(400);
    expect((await context.post("/api/auth/sign-up/username", {
      headers: { origin: baseURL }, data: { username, password: "a".repeat(5000) },
    })).status()).toBe(413);
    await signUp(context, username);
    const duplicate = await context.post("/api/auth/sign-up/username", {
      headers: { origin: baseURL }, data: { username: username.toUpperCase(), password },
    });
    expect(duplicate.ok()).toBe(false);
    await context.post("/api/auth/sign-out", { headers: { origin: baseURL }, data: {} });
    let lastStatus = 0;
    for (let attempt = 0; attempt < 11; attempt++) {
      const response = await context.post("/api/auth/sign-in/username", {
        headers: { origin: baseURL, "x-forwarded-for": `203.0.113.${attempt + 1}` },
        data: { username, password: "incorrect password" },
      });
      lastStatus = response.status();
      expect(response.ok()).toBe(false);
      expect(await response.text()).not.toContain("accounts.invalid");
    }
    expect(lastStatus).toBe(429);
  } finally { await context.dispose(); }
});
