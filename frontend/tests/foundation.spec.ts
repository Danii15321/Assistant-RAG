import { expect, test } from "@playwright/test";

test("the real local UI reaches the API and migrated database", async ({ page }, testInfo) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("documents");
  const responsePromise = page.waitForResponse("**/api/v1/health");
  await page.getByRole("button", { name: "Vérifier la connexion" }).click();
  const response = await responsePromise;
  expect(response.status()).toBe(200);
  expect(await response.json()).toEqual({ status: "ok" });
  await expect(page.getByRole("status")).toHaveText("Connexion établie. Le socle local est prêt.");
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
  expect(overflow).toBe(false);
  await page.screenshot({ path: testInfo.outputPath("foundation.png"), fullPage: true });
});

test("an unavailable database is visible and the user can retry", async ({ page }) => {
  await page.route("**/api/v1/health", (route) => route.fulfill({
    status: 503, contentType: "application/json", body: JSON.stringify({ status: "unavailable" }),
  }));
  await page.goto("/");
  await page.getByRole("button", { name: "Vérifier la connexion" }).click();
  await expect(page.getByRole("status")).toContainText("Connexion indisponible");
  await page.unroute("**/api/v1/health");
  await page.getByRole("button", { name: "Vérifier la connexion" }).click();
  await expect(page.getByRole("status")).toContainText("Connexion établie");
});

test("a network failure does not leave the UI in a loading state", async ({ page }) => {
  await page.route("**/api/v1/health", (route) => route.abort());
  await page.goto("/");
  await page.getByRole("button", { name: "Vérifier la connexion" }).click();
  await expect(page.getByRole("status")).toContainText("Connexion indisponible");
  await expect(page.getByRole("button", { name: "Vérifier la connexion" })).toBeEnabled();
});
