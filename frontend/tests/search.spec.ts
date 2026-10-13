import { test, expect, request as apiRequest, type APIRequestContext } from "@playwright/test";
import { Pool } from "pg";

const baseURL = process.env.TEST_BASE_URL!;
const database = process.env.AUTH_TEST_DATABASE_URL!;
if (new URL(database).pathname !== "/assistant_rag_test") throw new Error("Dedicated test database required");
const pool = new Pool({ connectionString: database, max: 2 });
test.beforeEach(async () => { await pool.query("DELETE FROM auth_rate_limit"); });
test.afterAll(async () => { await pool.end(); });

async function account(context: APIRequestContext, prefix: string) {
  const response = await context.post("/api/auth/sign-up/username", { headers: { origin: baseURL },
    data: { username: `${prefix}.t${Date.now()}${Math.floor(Math.random()*1000)}`, password: "Local search password 2026!" } });
  expect(response.status()).toBe(200);
}
async function upload(context: APIRequestContext, filename: string, text: string) {
  const bytes = Buffer.from(text);
  const response = await context.post("/api/v1/documents/uploads", { headers: { origin: baseURL },
    data: { filename, size_bytes: bytes.length, content_type: "text/plain" } });
  expect(response.status()).toBe(201);
  const reservation = await response.json();
  expect((await context.put(reservation.upload_url, { data: bytes,
    headers: { origin: baseURL, authorization: `Bearer ${reservation.upload_token}`, "content-type": "text/plain" } })).status()).toBe(204);
  expect((await context.post("/api/v1/documents", { headers: { origin: baseURL }, data: { upload_id: reservation.document.id } })).status()).toBe(202);
  await expect.poll(async () => (await (await context.get(`/api/v1/documents/${reservation.document.id}`)).json()).state, { timeout: 120000 }).toBe("ready");
  return reservation.document.id as string;
}
const facts = "Le lancement du projet Oriole a lieu le 12 décembre 2026 à Lyon. La démonstration dure vingt minutes.";

test("recherche E5 réelle, sélection, sources consultables et isolation", async ({ page }) => {
  test.setTimeout(180000);
  const bob = await apiRequest.newContext({ baseURL });
  try {
    await account(page.request, "searchalice"); await account(bob, "searchbob");
    const alpha = await upload(page.request, "alpha.txt", facts);
    const beta = await upload(page.request, "beta.txt", "La maquette Bételgeuse est présentée à Bordeaux le 2 janvier 2027.");
    const foreign = await upload(bob, "confidentiel-bob.txt", facts + " Confidentiel Bob.");
    await page.goto("/library");
    if (await page.getByRole("button", { name: "Ouvrir le panneau latéral" }).isVisible()) await page.getByRole("button", { name: "Ouvrir le panneau latéral" }).click();
    await page.getByRole("link", { name: "Explorer les passages" }).click();
    await page.getByLabel("Votre question").fill(facts);
    await page.getByRole("button", { name: "Rechercher les passages" }).click();
    await expect(page.locator(".search-hit").first()).toBeVisible({ timeout: 120000 });
    await page.locator(".search-hit").first().getByText("Lire le passage", { exact: true }).click();
    await expect(page.locator(".search-hit pre").first()).toHaveText(facts);
    await expect(page.locator(".search-hit").first().getByRole("heading")).toContainText("alpha.txt");
    await expect(page.getByText("Confidentiel Bob.", { exact: false })).toHaveCount(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    expect(await page.evaluate(() => Object.values(localStorage))).toEqual([]);
    await page.screenshot({ path: test.info().outputPath("search-private.png"), fullPage: true });
    await page.getByLabel("Documents à consulter").selectOption("selection");
    await page.getByRole("button", { name: "Rechercher les passages" }).click();
    await expect(page.getByRole("region", { name: "Rechercher dans mes documents" }).getByRole("alert")).toHaveText("Choisissez au moins un document.");
    await page.getByRole("checkbox", { name: "beta.txt" }).check();
    const limited = await page.request.post("/api/v1/search", { headers: { origin: baseURL }, data: { question: facts, document_ids: [beta] } });
    expect(limited.status()).toBe(200);
    for (const hit of (await limited.json()).hits) expect(hit.document_id).toBe(beta);
    const ranked = await page.request.post("/api/v1/search", { headers: { origin: baseURL }, data: { question: facts + " Confidentiel Bob.", top_k: 1 } });
    const result = await ranked.json(); expect(result.hits).toHaveLength(1);
    expect(result.hits[0].document_id).toBe(alpha);
    expect(result.hits[0]).not.toHaveProperty("embedding");
    expect(result.context_tokens).toBeLessThanOrEqual(1500);
    expect(ranked.headers()["cache-control"]).toBe("no-store");
    for (const id of [foreign, "00000000-0000-0000-0000-000000000000"]) {
      expect((await page.request.post("/api/v1/search", { headers: { origin: baseURL }, data: { question: facts, document_ids: [id] } })).status()).toBe(404);
    }
    if (await page.getByRole("button", { name: "Ouvrir le panneau latéral" }).isVisible()) await page.getByRole("button", { name: "Ouvrir le panneau latéral" }).click();
    await page.getByRole("button", { name: "Se déconnecter" }).click();
    await expect(page).toHaveURL(/sign-in/);
    expect((await page.request.post("/api/v1/search", { headers: { origin: baseURL }, data: { question: facts } })).status()).toBe(401);
  } finally { await bob.dispose(); }
});

test("corpus vide, questions bornées, sélection invalide et origine refusée", async ({ page }) => {
  expect((await page.request.post("/api/v1/search", { data: { question: "Question" } })).status()).toBe(401);
  await page.goto("/search"); await expect(page).toHaveURL(/sign-in/);
  await account(page.request, "emptysearch");
  const response = await page.request.post("/api/v1/search", { headers: { origin: baseURL }, data: { question: "Question" } });
  expect(response.status()).toBe(200); expect((await response.json()).status).toBe("empty_corpus");
  for (const data of [{question:" "},{question:"x".repeat(1001)}, {question:"Question",document_ids:[]},
    {question:"Question",owner_id:"forged"},{question:"Question",top_k:11}]) {
    expect((await page.request.post("/api/v1/search", { headers: { origin: baseURL }, data })).status()).toBe(422);
  }
  expect((await page.request.post("/api/v1/search", { headers: { origin: "https://attacker.invalid" }, data: { question: "Question" } })).status()).toBe(403);
  expect((await page.request.post("/api/v1/search", { headers: { origin: baseURL }, data: "x".repeat(16385) })).status()).toBe(413);
  await page.goto("/search"); await expect(page.getByText(/Aucun document prêt/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Rechercher les passages" })).toBeDisabled();
});

test("erreur de recherche visible, nouvelle tentative réelle et absence de correspondance", async ({ page }) => {
  test.setTimeout(180000);
  await account(page.request, "searchretry");
  await upload(page.request, "projet.txt", facts);
  await page.goto("/search"); await page.getByLabel("Votre question").fill(facts);
  await page.route("**/api/v1/search", route => route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ code: "search_timeout" }) }));
  await page.getByRole("button", { name: "Rechercher les passages" }).click();
  await expect(page.getByRole("region", { name: "Rechercher dans mes documents" }).getByRole("alert")).toContainText("délai autorisé");
  await page.unroute("**/api/v1/search");
  await page.getByRole("button", { name: "Rechercher les passages" }).click();
  await expect(page.locator(".search-hit").first()).toBeVisible({ timeout: 120000 });
  await page.getByLabel("Votre question").fill("Comment préparer une tarte aux pommes à la cannelle ?");
  await page.getByRole("button", { name: "Rechercher les passages" }).click();
  await expect(page.getByText("Aucun passage suffisamment proche de votre question.")).toBeVisible({ timeout: 120000 });
});
