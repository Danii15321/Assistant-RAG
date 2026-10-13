import { test, expect, request as apiRequest, type APIRequestContext } from "@playwright/test";
import { Pool } from "pg";
import { readFileSync } from "node:fs";
import { randomUUID } from "node:crypto";

const baseURL = process.env.TEST_BASE_URL!;
const llmURL = process.env.TEST_LLM_URL!;
const db = process.env.AUTH_TEST_DATABASE_URL!;
if (new URL(db).pathname !== "/assistant_rag_test") throw new Error("Dedicated test database required");
const pool = new Pool({ connectionString: db, max: 2 });
const password = "Local conversation password 2026!";
const facts = "Le lancement du projet Oriole a lieu le 12 décembre 2026 à Lyon. La démonstration dure vingt minutes.";
const headers = { origin: baseURL };
test.beforeEach(async ({ request }) => {
  await pool.query("DELETE FROM auth_rate_limit");
  await pool.query("DELETE FROM generation_attempts");
  await pool.query("UPDATE generation_limits SET lease_token=NULL,lease_until=NULL,blocked_until=NULL");
  expect((await request.post(llmURL + "/control", { data: { mode: "answered" } })).ok()).toBe(true);
});
test.afterAll(async () => { await pool.end(); });
async function account(context: APIRequestContext, prefix: string) {
  expect((await context.post("/api/auth/sign-up/username", { headers, data: {
    username: `${prefix}.t${Date.now()}${Math.floor(Math.random() * 1000)}`, password,
  } })).status()).toBe(200);
}
async function upload(context: APIRequestContext, filename = "oriole.txt", bytes = Buffer.from(facts), content_type = "text/plain") {
  const reserve = await context.post("/api/v1/documents/uploads", { headers, data: { filename, size_bytes: bytes.length, content_type } });
  expect(reserve.status()).toBe(201); const value = await reserve.json();
  expect((await context.put(value.upload_url, { data: bytes, headers: { ...headers, authorization: `Bearer ${value.upload_token}`, "content-type": content_type } })).status()).toBe(204);
  expect((await context.post("/api/v1/documents", { headers, data: { upload_id: value.document.id } })).status()).toBe(202);
  await expect.poll(async () => (await (await context.get(`/api/v1/documents/${value.document.id}`)).json()).state, { timeout: 120000 }).toBe("ready");
  return value.document.id as string;
}
async function create(context: APIRequestContext) {
  const result = await context.post("/api/v1/conversations", { headers });
  expect(result.status()).toBe(201); return (await result.json()).id as string;
}
const input = () => ({ request_id: randomUUID(), question: facts, allow_external_processing: true });
async function calls(context: APIRequestContext) { return (await (await context.get(llmURL + "/control")).json()).calls; }

test("parcours inscription import chat suivi source reprise et effacement privé", async ({ page }) => {
  test.setTimeout(240000);
  const username = `chat.t${Date.now()}${Math.floor(Math.random() * 1000)}`;
  await page.goto("/sign-up");
  await page.getByLabel("Nom d’utilisateur").fill(username);
  await page.getByLabel("Mot de passe", { exact: true }).fill(password);
  await page.getByLabel("Confirmer le mot de passe").fill(password);
  await page.getByRole("button", { name: "Créer mon compte" }).click();
  await expect(page).toHaveURL(/\/conversations$/);
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: "Ajouter des documents" }).click();
  await (await chooser).setFiles({ name: "oriole.txt", mimeType: "text/plain", buffer: Buffer.from(facts) });
  await expect(page.getByText("1 document prêt", { exact: true })).toBeVisible({ timeout: 120000 });
  const doc = (await (await page.request.get("/api/v1/documents")).json())[0].id;
  await page.getByLabel("Votre question").fill(facts);
  await expect(page.getByRole("button", { name: "Envoyer ma question" })).toBeDisabled();
  await page.getByRole("checkbox", { name: /J’accepte l’envoi/ }).check();
  await page.getByRole("button", { name: "Envoyer ma question" }).click();
  await expect(page.locator(".answer-claims")).toContainText("Lyon", { timeout: 120000 });
  await expect(page).toHaveURL(/\/conversations\/[a-f0-9-]+$/);
  const conversation = page.url().split("/").pop();
  await page.getByRole("link", { name: "[S1]" }).click();
  await expect(page.getByRole("dialog", { name: "Sources de la réponse" })).toBeVisible();
  await expect(page.locator(".answer-source pre")).toHaveText(facts);
  await page.screenshot({ path: test.info().outputPath("conversation-private.png"), fullPage: true });
  await page.getByRole("button", { name: "Fermer les sources" }).click();
  await expect(page.getByRole("checkbox", { name: /J’accepte l’envoi/ })).not.toBeChecked();
  await page.getByLabel("Votre question").fill("Et dans quelle ville ?");
  await page.getByRole("checkbox", { name: /J’accepte l’envoi/ }).check();
  await page.getByRole("button", { name: "Envoyer ma question" }).click();
  await expect(page.locator(".answer-claims")).toHaveCount(2, { timeout: 120000 });
  await page.reload();
  await expect(page.locator(".chat-exchange")).toHaveCount(2);
  expect(await calls(page.request)).toBe(2);
  const anchors = await page.locator(".answer-claims a").evaluateAll(links => links.map(link => link.getAttribute("href")));
  expect(new Set(anchors).size).toBe(2);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect(await page.evaluate(() => Object.values(localStorage))).toEqual([]);
  if (await page.getByRole("button", { name: "Ouvrir le panneau latéral" }).isVisible()) await page.getByRole("button", { name: "Ouvrir le panneau latéral" }).click();
  await page.getByRole("button", { name: "Se déconnecter" }).click();
  await expect(page).toHaveURL(/\/sign-in$/);
  expect((await page.request.get(`/api/v1/conversations/${conversation}/messages`)).status()).toBe(401);
  await page.getByLabel("Nom d’utilisateur").fill(username);
  await page.getByLabel("Mot de passe", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Se connecter" }).click();
  await expect(page).toHaveURL(/\/conversations$/);
  await page.goto(`/conversations/${conversation}`);
  await expect(page.locator(".chat-exchange")).toHaveCount(2);
  expect((await page.request.delete(`/api/v1/documents/${doc}`, { headers })).status()).toBe(202);
  await page.reload();
  await expect(page.getByText(/Source supprimée · Les extraits/)).toHaveCount(2);
  await expect(page.locator(".answer-source pre, .answer-source blockquote")).toHaveCount(0);
  await expect(page.locator(".answer-claims")).toHaveCount(2);
  expect(await calls(page.request)).toBe(2);
  const disposable = await create(page.request);
  await page.goto("/conversations");
  if (await page.getByRole("button", { name: "Ouvrir le panneau latéral" }).isVisible()) await page.getByRole("button", { name: "Ouvrir le panneau latéral" }).click();
  await page.getByRole("button", { name: "Supprimer la conversation Nouvelle conversation", exact: true }).click();
  await page.getByRole("button", { name: "Confirmer la suppression" }).click();
  await expect(page.locator(".sidebar-history li")).toHaveCount(1);
  expect((await page.request.get(`/api/v1/conversations/${disposable}/messages`)).status()).toBe(404);
  expect((await page.request.get(`/api/v1/conversations/${conversation}/messages`)).status()).toBe(200);
  expect((await pool.query("SELECT count(*)::int AS count FROM generation_attempts")).rows[0].count).toBe(2);
});

test("double envoi sérialisé identifiant stable isolation et suppression pendant Groq", async ({ page }) => {
  test.setTimeout(180000); await account(page.request, "chatlease"); await upload(page.request);
  const id = await create(page.request); const body = input();
  await page.request.post(llmURL + "/control", { data: { mode: "pause" } });
  const response = page.request.post(`/api/v1/conversations/${id}/messages`, { headers, data: body, timeout: 180000 });
  await expect.poll(() => calls(page.request), { timeout: 120000 }).toBe(1);
  const duplicate = await page.request.post(`/api/v1/conversations/${id}/messages`, { headers, data: body });
  expect(duplicate.status()).toBe(202); expect((await duplicate.json()).state).toBe("pending");
  expect((await page.request.post(`/api/v1/conversations/${id}/messages`, { headers, data: input() })).status()).toBe(409);
  expect((await page.request.post(`/api/v1/conversations/${id}/messages`, { headers, data: { ...body, question: "Autre" } })).status()).toBe(409);
  const bob = await apiRequest.newContext({ baseURL });
  try {
    await account(bob, "chatbob");
    expect(await (await bob.get("/api/v1/conversations")).json()).toEqual([]);
    for (const route of [`/${id}`, `/${id}/messages`]) expect((await bob.get("/api/v1/conversations" + route)).status()).toBe(404);
    expect((await bob.post(`/api/v1/conversations/${id}/messages`, { headers, data: body })).status()).toBe(404);
    expect((await bob.delete(`/api/v1/conversations/${id}`, { headers })).status()).toBe(404);
  } finally { await bob.dispose(); }
  expect((await page.request.delete(`/api/v1/conversations/${id}`, { headers })).status()).toBe(204);
  await page.request.post(llmURL + "/control", { data: { release: true } });
  expect((await response).status()).toBe(409); expect(await calls(page.request)).toBe(1);
});

test("échec conservé replay sans appel abstention et corpus vide persistants", async ({ page }) => {
  test.setTimeout(180000); await account(page.request, "chatfailure"); await upload(page.request);
  const id = await create(page.request); const body = input();
  await page.request.post(llmURL + "/control", { data: { mode: "invalid" } });
  expect((await page.request.post(`/api/v1/conversations/${id}/messages`, { headers, data: body })).status()).toBe(502);
  const replay = await page.request.post(`/api/v1/conversations/${id}/messages`, { headers, data: body });
  expect(replay.status()).toBe(200); const failed = await replay.json();
  expect(failed.state).toBe("failed"); expect(failed.answer).toBeNull(); expect(failed.question).toBe(facts);
  expect(await calls(page.request)).toBe(1);
  await page.goto(`/conversations/${id}`);
  await expect(page.getByText(/Échange échoué/)).toBeVisible();
  await page.request.post(llmURL + "/control", { data: { mode: "absent" } });
  const absent = await page.request.post(`/api/v1/conversations/${id}/messages`, { headers, data: input() });
  expect(absent.status()).toBe(200); expect((await absent.json()).state).toBe("insufficient_context");
  await page.request.post("/api/auth/sign-out", { headers, data: {} });
  await account(page.request, "chatempty"); const empty = await create(page.request);
  const result = await page.request.post(`/api/v1/conversations/${empty}/messages`, { headers, data: { request_id: randomUUID(), question: "Question sans document" } });
  expect(result.status()).toBe(200); expect((await result.json()).answer.provider_called).toBe(false);
  expect(await calls(page.request)).toBe(1);
});

for (const mutation of ["source", "session"] as const) test(`historique sans réponse après révocation de ${mutation}`, async ({ page }) => {
  test.setTimeout(180000); await account(page.request, `chatrace${mutation}`); const doc = await upload(page.request);
  const id = await create(page.request);
  await page.goto(`/conversations/${id}`);
  await page.getByLabel("Votre question").fill(facts);
  await page.getByRole("checkbox", { name: /J’accepte l’envoi/ }).check();
  await page.request.post(llmURL + "/control", { data: { mode: "pause" } });
  await page.getByRole("button", { name: "Envoyer ma question" }).click();
  await expect.poll(() => calls(page.request), { timeout: 120000 }).toBe(1);
  if (mutation === "source") expect((await page.request.delete(`/api/v1/documents/${doc}`, { headers })).status()).toBe(202);
  else expect((await page.request.post("/api/auth/sign-out", { headers, data: {} })).status()).toBe(200);
  await page.request.post(llmURL + "/control", { data: { release: true } });
  if (mutation === "source") {
    await expect(page.getByText(/Échange échoué/)).toBeVisible();
    const messages = await (await page.request.get(`/api/v1/conversations/${id}/messages`)).json();
    expect(messages[0].answer).toBeNull(); expect(messages[0].error_code).toBe("source_unavailable");
  } else await expect(page).toHaveURL(/\/sign-in\?expired=1$/);
  await expect(page.locator(".answer-claims")).toHaveCount(0);
});

test("suivi Q28 Iris recherche E5 réelle depuis historique serveur et sélection mémorisée", async ({ page }) => {
  test.setTimeout(180000); await account(page.request, "chatiris");
  const doc = await upload(page.request, "atelier-rag.pdf", readFileSync("/corpus/atelier-rag.pdf"), "application/pdf");
  const id = await create(page.request);
  await page.request.post(llmURL + "/control", { data: { mode: "iris" } });
  for (const [question, expected] of [["Quelle taille de passages utilise l’atelier Iris ?", "220 tokens"], ["Et à combien s’élève le chevauchement ?", "40 tokens"]]) {
    const response = await page.request.post(`/api/v1/conversations/${id}/messages`, { headers, data: { request_id: randomUUID(), question, document_ids: [doc], allow_external_processing: true }, timeout: 180000 });
    expect(response.status()).toBe(200); const exchange = await response.json();
    expect(exchange.state).toBe("answered"); expect(exchange.answer.answer).toContain(expected);
    expect(exchange.document_ids).toEqual([doc]);
    expect(exchange.answer.sources.every((source: { document_id: string }) => source.document_id === doc)).toBe(true);
  }
  await page.goto(`/conversations/${id}`);
  await expect(page.locator(".chat-exchange")).toHaveCount(2);
  await expect(page.locator(".answer-claims").last()).toContainText("40 tokens");
  expect(await calls(page.request)).toBe(2);
});


test("réponse réseau perdue retrouvée dans l’historique sans double appel", async ({ page }) => {
  test.setTimeout(180000); await account(page.request, "chatnetwork"); await upload(page.request);
  const id = await create(page.request); let posts = 0;
  await page.route(`**/api/v1/conversations/${id}/messages`, async route => {
    if (route.request().method() !== "POST") { await route.continue(); return; }
    posts += 1;
    const response = await route.fetch(); expect(response.status()).toBe(200);
    await route.abort("failed");
  });
  await page.goto(`/conversations/${id}`);
  await page.getByLabel("Votre question").fill(facts);
  await page.getByRole("checkbox", { name: /J’accepte l’envoi/ }).check();
  await page.getByRole("button", { name: "Envoyer ma question" }).click();
  await expect(page.locator(".answer-claims")).toContainText("Lyon", { timeout: 120000 });
  expect(posts).toBe(1); expect(await calls(page.request)).toBe(1);
  await page.reload();
  await expect(page.locator(".chat-exchange")).toHaveCount(1);
  expect(await calls(page.request)).toBe(1);
});

