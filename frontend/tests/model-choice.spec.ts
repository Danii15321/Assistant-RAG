import { test, expect } from "@playwright/test";
import { Pool } from "pg";
const db = process.env.AUTH_TEST_DATABASE_URL!;
if (new URL(db).pathname !== "/assistant_rag_test") throw new Error("Dedicated test database required");
const pool = new Pool({ connectionString: db, max: 2 });
test.afterAll(async () => { await pool.end(); });

test("Groq par défaut, consentement par fournisseur et choix conservé dans l’envoi", async ({ page }) => {
  await pool.query("DELETE FROM auth_rate_limit");
  expect((await page.request.post("/api/auth/sign-up/username", { headers: { origin: process.env.TEST_BASE_URL! }, data: { username: `models.t${Date.now()}`, password: "Local models password 2026!" } })).ok()).toBe(true);
  await page.route("**/api/v1/models", route => route.fulfill({ json: { models: [
    { id: "groq", label: "Groq · gratuit", available: true },
    { id: "gpt-6-luna", label: "GPT-6 Luna", available: true },
    { id: "gpt-6.1-sol", label: "GPT-6.1 Sol", available: false, reason: "Clé OpenAI à configurer" },
  ], remaining_microusd: 900000, limit_microusd: 1000000 } }));
  await page.route("**/api/v1/documents**", route => route.fulfill({ json: [{ id: "doc", filename: "notes.txt", state: "ready" }] }));
  let sent: Record<string, unknown> | undefined;
  await page.route("**/api/v1/conversations**", route => {
    if (route.request().method() === "POST" && route.request().url().endsWith("/messages")) {
      sent = route.request().postDataJSON();
      return route.fulfill({ status: 429, json: { code: "openai_budget_exhausted" } });
    }
    if (route.request().url().includes("/messages")) return route.fulfill({ json: [] });
    return route.fulfill({ json: route.request().method() === "POST" ? { id: "00000000-0000-4000-8000-000000000002", title: "Essai" } : [] });
  });
  await page.goto("/conversations");
  const model = page.getByLabel("Modèle de réponse");
  await expect(model).toHaveValue("groq");
  await page.getByLabel("Votre question").fill("Une question sur le document ?");
  const consent = page.getByRole("checkbox", { name: /J’accepte l’envoi/ });
  await consent.check();
  await model.selectOption("gpt-6-luna");
  await expect(consent).not.toBeChecked();
  await expect(page.getByRole("checkbox", { name: /J’accepte l’envoi à OpenAI/ })).toBeVisible();
  await expect(page.getByRole("button", { name: "Envoyer ma question" })).toBeDisabled();
  // Playwright actionability does not classify <option>; check its native disabled property.
  await expect(model.locator('option[value="gpt-6.1-sol"]')).toHaveJSProperty("disabled", true);
  await expect(page.getByText(/0,90.*1,00/)).toBeVisible();
  await consent.check();
  await page.getByRole("button", { name: "Envoyer ma question" }).click();
  await expect.poll(() => sent?.model).toBe("gpt-6-luna");
  await expect(page.getByRole("alert").filter({ hasText: "plafond" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: test.info().outputPath("openai-model-choice.png"), fullPage: true });
});


test("une discussion rouverte conserve le modèle choisi après un échec", async ({ page }) => {
  await pool.query("DELETE FROM auth_rate_limit");
  expect((await page.request.post("/api/auth/sign-up/username", { headers: { origin: process.env.TEST_BASE_URL! }, data: { username: `resume.t${Date.now()}`, password: "Local models password 2026!" } })).ok()).toBe(true);
  const id = "00000000-0000-4000-8000-000000000002";
  await page.route("**/api/v1/models", route => route.fulfill({ json: { models: [{ id: "groq", label: "Groq", available: true }, { id: "gpt-6-luna", label: "GPT-6 Luna", available: true }] } }));
  await page.route("**/api/v1/documents**", route => route.fulfill({ json: [] }));
  await page.route("**/api/v1/conversations**", route => route.fulfill({ json: route.request().url().includes("/messages") ? [{ id: "exchange", request_id: "request", ordinal: 1, model: "gpt-6-luna", question: "Une question", state: "failed", error_code: "service_unavailable", document_ids: null, answer: null, created_at: "2026-10-14T12:00:00Z" }] : route.request().url().endsWith(id) ? { id, title: "Une question" } : [] }));
  await page.goto(`/conversations/${id}`);
  await expect(page.getByLabel("Modèle de réponse")).toHaveValue("gpt-6-luna");
  await expect(page.getByRole("checkbox", { name: /J’accepte l’envoi à OpenAI/ })).not.toBeChecked();
  await page.reload();
  await expect(page.getByLabel("Modèle de réponse")).toHaveValue("gpt-6-luna");
  await page.getByRole("button", { name: "Nouvelle discussion", exact: true }).click();
  await expect(page.getByLabel("Modèle de réponse")).toHaveValue("groq");
});
