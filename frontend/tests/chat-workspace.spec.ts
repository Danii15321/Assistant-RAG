import { test, expect } from "@playwright/test";
import { Pool } from "pg";

test.use({ actionTimeout: 15000 });

const db = process.env.AUTH_TEST_DATABASE_URL!;
if (new URL(db).pathname !== "/assistant_rag_test") throw new Error("Dedicated test database required");
const pool = new Pool({ connectionString: db, max: 2 });
test.beforeEach(async () => { await pool.query("DELETE FROM auth_rate_limit"); });
test.afterAll(async () => { await pool.end(); });

test("le chat est l’entrée, import multiple via plus et brouillon conservé", async ({ page }) => {
  test.setTimeout(180000);
  await page.goto("/sign-up");
  await page.getByLabel("Nom d’utilisateur").fill(`workspace.t${Date.now()}`);
  await page.getByLabel("Mot de passe", { exact: true }).fill("Local workspace password 2026!");
  await page.getByLabel("Confirmer le mot de passe").fill("Local workspace password 2026!");
  await page.getByRole("button", { name: "Créer mon compte" }).click();
  await expect(page).toHaveURL(/\/conversations$/);
  await expect(page.getByRole("heading", { name: "Par où commence-t-on ?" })).toBeVisible();
  await page.screenshot({ path: test.info().outputPath("chat-empty.png"), fullPage: true });
  await page.getByLabel("Votre question").fill("Quel est le sujet de ces notes ?");
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: "Ajouter des documents" }).click();
  await (await chooser).setFiles([
    { name: "premier.txt", mimeType: "text/plain", buffer: Buffer.from("Le projet Oriole est présenté à Lyon.") },
    { name: "refus.csv", mimeType: "text/csv", buffer: Buffer.from("erreur") },
    { name: "second.txt", mimeType: "text/plain", buffer: Buffer.from("La présentation du projet Oriole dure vingt minutes.") },
  ]);
  await expect(page.getByText(/refus.csv.*PDF textuel/)).toBeVisible();
  await expect(page.getByText("2 documents prêts", { exact: true })).toBeVisible({ timeout: 120000 });
  await expect(page.getByLabel("Votre question")).toHaveValue("Quel est le sujet de ces notes ?");
  await expect(page.getByRole("button", { name: "Envoyer ma question" })).toBeDisabled();
  await page.getByText("Documents à consulter", { exact: true }).click();
  await page.getByLabel("Périmètre de la réponse").selectOption("selection");
  await page.getByRole("checkbox", { name: "second.txt", exact: true }).check();
  await page.getByRole("checkbox", { name: /J’accepte l’envoi/ }).check();
  await expect(page.getByRole("button", { name: "Envoyer ma question" })).toBeEnabled();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await expect(page.getByLabel("Périmètre de la réponse")).toBeHidden();
  await page.screenshot({ path: test.info().outputPath("chat-workspace.png"), fullPage: true });
  const menu = page.getByRole("button", { name: "Ouvrir le panneau latéral" });
  if (await menu.isVisible()) {
    await menu.click();
    await expect(page.getByRole("button", { name: "Masquer le panneau latéral", exact: true })).toBeFocused();
    if (test.info().project.name === "mobile") {
      await page.keyboard.press("Shift+Tab");
      await expect(page.getByRole("button", { name: "Se déconnecter" })).toBeFocused();
    }
    await page.keyboard.press("Escape");
    await expect(menu).toBeFocused();
    await expect(page.locator(".sidebar-history")).toBeHidden();
    await expect(page.locator(".chat-sidebar")).toBeVisible();
    await menu.click();
  }
  await page.getByRole("link", { name: "Documents", exact: true }).click();
  await expect(page.getByRole("heading", { name: "premier.txt", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "second.txt", exact: true })).toBeVisible();
});
