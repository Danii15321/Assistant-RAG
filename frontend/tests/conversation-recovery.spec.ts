import { test, expect, type APIRequestContext } from "@playwright/test";
import { Pool } from "pg";
import { randomUUID } from "node:crypto";

// This case isolates draft recovery in the UI; the other chat cases use real API/data/E5.
const baseURL = process.env.TEST_BASE_URL!;
const llmURL = process.env.TEST_LLM_URL!;
const db = process.env.AUTH_TEST_DATABASE_URL!;
if (new URL(db).pathname !== "/assistant_rag_test") throw new Error("Dedicated test database required");
const pool = new Pool({ connectionString: db, max: 2 });
const headers = { origin: baseURL };
const facts = "Le lancement du projet Oriole a lieu le 12 décembre 2026 à Lyon. La démonstration dure vingt minutes.";
test.beforeEach(async ({ request }) => {
  await pool.query("DELETE FROM auth_rate_limit");
  await request.post(llmURL + "/control", { data: { mode: "answered" } });
});
test.afterAll(async () => { await pool.end(); });
async function account(context: APIRequestContext, prefix: string) {
  expect((await context.post("/api/auth/sign-up/username", { headers, data: {
    username: `${prefix}.t${Date.now()}${Math.floor(Math.random() * 1000)}`, password: "Local conversation password 2026!",
  } })).status()).toBe(200);
}
async function create(context: APIRequestContext) {
  const result = await context.post("/api/v1/conversations", { headers });
  expect(result.status()).toBe(201); return (await result.json()).id as string;
}
async function calls(context: APIRequestContext) { return (await (await context.get(llmURL + "/control")).json()).calls; }


test("vérification d’un envoi inconnu réutilise son UUID et réinitialise l’accord", async ({ page }) => {
  test.setTimeout(180000); await account(page.request, "chatunknown");
  const documentId = randomUUID();
  await page.route("**/api/v1/documents", route => route.fulfill({ json: [{ id: documentId, filename: "oriole.txt", state: "ready" }] }));
  const id = await create(page.request); let firstPost = true; let failRead = false; const ids: string[] = [];
  await page.route(`**/api/v1/conversations/${id}/messages**`, async route => {
    if (route.request().method() === "POST") {
      ids.push(route.request().postDataJSON().request_id);
      if (firstPost) { firstPost = false; failRead = true; await route.abort("failed"); return; }
    } else if (failRead) { failRead = false; await route.abort("failed"); return; }
    if (route.request().method() === "POST") {
      const body = route.request().postDataJSON();
      await route.fulfill({ json: { id: randomUUID(), request_id: body.request_id, ordinal: 1,
        question: body.question, document_ids: body.document_ids, state: "answered", error_code: null,
        created_at: new Date().toISOString(), completed_at: new Date().toISOString(),
        answer: { state: "answered", answer: "Le lancement a lieu à Lyon. [S1]", provider_called: false,
          claims: [{ text: "Le lancement a lieu à Lyon.", evidence: [{ source_id: "S1", quote: "Lyon" }] }],
          sources: [{ source_id: "S1", document_id: documentId, text: facts, filename: "oriole.txt", kind: "line", start_number: 1, end_number: 1 }] } } });
      return;
    }
    await route.continue();
  });
  await page.goto(`/conversations/${id}`);
  await page.getByLabel("Votre question").fill(facts);
  await page.getByText("Documents à consulter", { exact: true }).click();
  await page.getByLabel("Périmètre de la réponse").selectOption("selection");
  await page.getByRole("checkbox", { name: "oriole.txt", exact: true }).check();
  await page.getByRole("checkbox", { name: /J’accepte l’envoi/ }).check();
  await page.getByRole("button", { name: "Envoyer ma question" }).click();
  await expect(page.getByRole("button", { name: "Vérifier l’envoi" })).toBeVisible();
  expect(await calls(page.request)).toBe(0);
  await page.getByRole("button", { name: "Vérifier l’envoi" }).click();
  await expect(page.locator(".answer-claims")).toContainText("Lyon", { timeout: 120000 });
  await expect(page.getByRole("checkbox", { name: /J’accepte l’envoi/ })).not.toBeChecked();
  await expect(page.getByLabel("Votre question")).toHaveValue("");
  await page.getByText("Documents à consulter", { exact: true }).click();
  await expect(page.getByRole("checkbox", { name: "oriole.txt", exact: true })).toBeChecked();
  await expect(page.getByRole("button", { name: "Envoyer ma question" })).toBeDisabled();
  expect(ids).toHaveLength(2); expect(new Set(ids).size).toBe(1);
  expect(await calls(page.request)).toBe(0);
  await expect(page.locator(".chat-exchange")).toHaveCount(1);
});
