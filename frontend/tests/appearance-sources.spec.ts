import { test, expect } from "@playwright/test";
import { Pool } from "pg";
const db = process.env.AUTH_TEST_DATABASE_URL!;
if (new URL(db).pathname !== "/assistant_rag_test") throw new Error("Dedicated test database required");
const pool = new Pool({ connectionString: db, max: 2 });
test.use({ actionTimeout: 10000 });
test.beforeEach(async ({ page }) => {
  await pool.query("DELETE FROM auth_rate_limit");
  const response = await page.request.post("/api/auth/sign-up/username", { headers: { origin: process.env.TEST_BASE_URL! }, data: {
    username: `design.t${Date.now()}`, password: "Local design password 2026!",
  } });
  expect(response.status()).toBe(200);
});
test.afterAll(async () => { await pool.end(); });

test("apparence persistante et thème système réactif", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "dark" });
  await page.goto("/settings");
  await expect(page.getByRole("heading", { name: "Paramètres", exact: true })).toBeVisible();
  await expect(page.getByRole("radio", { name: "Système", exact: true })).toBeChecked();
  const background = () => page.locator("body").evaluate(el => getComputedStyle(el).backgroundColor);
  const dark = await background();
  await page.getByRole("radio", { name: "Clair", exact: true }).check();
  const light = await background();
  expect(light).not.toBe(dark);
  await page.reload();
  await expect(page.getByRole("radio", { name: "Clair", exact: true })).toBeChecked();
  expect(await background()).toBe(light);
  await page.getByRole("radio", { name: "Sombre", exact: true }).check();
  expect(await background()).toBe(dark);
  await page.screenshot({ path: test.info().outputPath("settings-dark.png"), fullPage: true });
  await page.getByRole("radio", { name: "Système", exact: true }).check();
  await page.emulateMedia({ colorScheme: "light" });
  await expect.poll(background).toBe(light);
  await page.screenshot({ path: test.info().outputPath("settings-light.png"), fullPage: true });
  expect(await page.evaluate(() => Object.values(localStorage))).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

const doc = "00000000-0000-4000-8000-000000000001";
const conversation = "00000000-0000-4000-8000-000000000002";
const quote = "La livraison prend deux à cinq jours ouvrés.";
test("cartes de sources, panneau exact, clavier et document privé", async ({ page }) => {
  await page.route("**/api/v1/documents**", route => route.fulfill({ json: route.request().url().includes("/extraction") ? [{ ordinal: 1, kind: "page", number: 3, text: quote }] : [{ id: doc, filename: "livraison.pdf", extension: "pdf", size_bytes: 2048, state: "ready", unit_count: 3, chunk_count: 1, embedded_count: 1 }] }));
  await page.route("**/api/v1/conversations**", route => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/messages")) return route.fulfill({ json: [{ id: "exchange-one", ordinal: 1, question: "Quels sont les délais de livraison ?", created_at: "2026-10-14T08:42:00Z", state: "answered", document_ids: null,
      answer: { state: "answered", answer: quote, claims: [{ text: "Comptez deux à cinq jours ouvrés.", evidence: [{ source_id: "S1", quote }] }], sources: [{ source_id: "S1", document_id: doc, filename: "livraison.pdf", kind: "page", start_number: 3, end_number: 3, text: quote + " Les commandes sont préparées après paiement.", status: "available" }], provider_called: true } }] });
    return route.fulfill({ json: path.endsWith(conversation) ? { id: conversation, title: "Délais de livraison" } : [{ id: conversation, title: "Délais de livraison" }] });
  });
  await page.emulateMedia({ colorScheme: "dark" });
  await page.goto(`/conversations/${conversation}`);
  const card = page.getByRole("button", { name: "Vérifier la source S1" });
  await expect(card).toContainText("livraison.pdf");
  await expect(card).toContainText("Page 3");
  await expect(card).toContainText(quote);
  await card.click();
  const drawer = page.getByRole("dialog", { name: "Sources de la réponse" });
  await expect(drawer).toBeVisible();
  await expect(drawer.locator("blockquote")).toHaveText(quote);
  await expect(drawer.locator("pre")).toContainText("Les commandes sont préparées après paiement.");
  await expect(drawer.getByRole("link", { name: "Voir le document" })).toHaveAttribute("href", `/library?document=${doc}`);
  await page.screenshot({ path: test.info().outputPath("chat-sources-dark.png"), fullPage: true });
  await page.keyboard.press("Escape");
  await expect(drawer).toHaveCount(0);
  await expect(card).toBeFocused();
  await page.getByRole("link", { name: "[S1]" }).click();
  await expect(drawer).toBeVisible();
  await drawer.getByRole("button", { name: "Fermer les sources" }).click();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await card.click();
  await drawer.getByRole("link", { name: "Voir le document" }).click();
  await expect(page).toHaveURL(new RegExp(`/library\\?document=${doc}`));
  await expect(page.getByRole("heading", { name: "Texte extrait · livraison.pdf" })).toBeVisible();
  await expect(page.locator(".extracted-unit pre")).toHaveText(quote);
});

test("bibliothèque filtrable par nom et format", async ({ page }) => {
  await page.route("**/api/v1/documents?limit=50", route => route.fulfill({ json: [
    { id: doc, filename: "Livraison.pdf", extension: "pdf", size_bytes: 2048, state: "ready", unit_count: 3, chunk_count: 1, embedded_count: 1 },
    { id: "two", filename: "Notes.txt", extension: "txt", size_bytes: 1024, state: "ready", unit_count: 1, chunk_count: 1, embedded_count: 1 },
  ] }));
  await page.goto("/library");
  await expect(page.locator("[data-document-id]")).toHaveCount(2);
  await page.getByRole("button", { name: "PDF (1)", exact: true }).click();
  await expect(page.locator("[data-document-id]")).toHaveCount(1);
  await page.getByLabel("Rechercher un document").fill("inexistant");
  await expect(page.getByText("Aucun document ne correspond à ces filtres.")).toBeVisible();
  await page.getByLabel("Rechercher un document").clear();
  await page.getByRole("button", { name: "Tous (2)", exact: true }).click();
  await expect(page.locator("[data-document-id]")).toHaveCount(2);
  await page.emulateMedia({ colorScheme: "dark" });
  await page.screenshot({ path: test.info().outputPath("documents-dark.png"), fullPage: true });
});
