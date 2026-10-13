import { test, expect, request as apiRequest, type APIRequestContext } from "@playwright/test";
import { Pool } from "pg";

const baseURL = process.env.TEST_BASE_URL!;
const apiURL = process.env.TEST_API_URL!;
const databaseURL = process.env.AUTH_TEST_DATABASE_URL;
if (!databaseURL || new URL(databaseURL).pathname !== "/assistant_rag_test") throw new Error("Dedicated database required");
const pool = new Pool({ connectionString: databaseURL, max: 2 });
test.beforeEach(async () => { await pool.query("DELETE FROM auth_rate_limit"); });
test.afterAll(async () => { await pool.end(); });

async function account(context: APIRequestContext, name: string) {
  expect((await context.post("/api/auth/sign-up/username", {
    headers: { origin: baseURL }, data: { username: `${name}.t${Date.now()}${Math.floor(Math.random()*1000)}`, password: "Local import password 2026!" },
  })).status()).toBe(200);
}
async function reserve(context: APIRequestContext, filename: string, bytes: Buffer, content_type = "text/plain") {
  const response = await context.post("/api/v1/documents/uploads", {
    headers: { origin: baseURL }, data: { filename, size_bytes: bytes.length, content_type },
  });
  expect(response.status()).toBe(201);
  return response.json();
}
async function upload(context: APIRequestContext, filename: string, bytes: Buffer) {
  const reservation = await reserve(context, filename, bytes);
  const result = await context.put(reservation.upload_url, { data: bytes,
    headers: { origin: baseURL, authorization: `Bearer ${reservation.upload_token}`, "content-type": "text/plain" },
  });
  expect(result.status()).toBe(204);
  const finalized = await context.post("/api/v1/documents", { headers: { origin: baseURL }, data: { upload_id: reservation.document.id } });
  expect([200,202]).toContain(finalized.status());
  return finalized.json();
}

test("import des trois formats, extraction, indexation réelle, doublon, échec, relance et suppression", async ({ page }) => {
  test.setTimeout(300000);
  await account(page.request, "import");
  await page.goto("/library");
  await page.locator(".library-import > summary").click();
  const files = ["atelier-rag.pdf", "parcours-2026.docx", "reseau.txt"];
  for (const filename of files) {
    await page.getByLabel("Choisir des fichiers").setInputFiles(`/corpus/${filename}`);
    await page.getByRole("button", { name: "Importer", exact: true }).click();
    const row = page.getByRole("listitem").filter({ has: page.getByRole("heading", { name: filename, exact: true }) });
    await expect(row.getByText("Prêt", { exact: true })).toBeVisible({ timeout: 120000 });
    await row.getByRole("button", { name: "Voir les passages" }).click();
    await expect(page.locator(".indexed-passage").first()).toBeVisible();
    const documentId = await row.getAttribute("data-document-id");
    const passages = await (await page.request.get(`/api/v1/documents/${documentId}/passages?limit=20`)).json();
    const units = await (await page.request.get(`/api/v1/documents/${documentId}/extraction?limit=50`)).json();
    const canonical = units.map((unit: { text: string }) => unit.text).join("\n\n");
    expect(passages.length).toBeGreaterThan(0);
    for (const passage of passages) {
      expect(passage.text).toBe(canonical.slice(passage.start_offset, passage.end_offset));
      expect(passage.token_count).toBeLessThanOrEqual(300);
      expect(units[passage.start_unit - 1].number).toBe(passage.start_number);
      expect(units[passage.end_unit - 1].number).toBe(passage.end_number);
    }
    const stored = await pool.query("SELECT vector_dims(embedding) AS dimension, vector_norm(embedding) AS norm FROM index_chunks WHERE document_id=$1", [documentId]);
    expect(stored.rows.length).toBe(passages.length);
    for (const vector of stored.rows) { expect(vector.dimension).toBe(384); expect(Math.abs(vector.norm - 1)).toBeLessThan(0.001); }
    expect((await page.request.get(`/api/v1/documents/${documentId}/passages`)).headers()["cache-control"]).toBe("no-store");
    await page.screenshot({ path: test.info().outputPath(`index-${filename}.png`), fullPage: true });
    await page.getByRole("button", { name: "Fermer les passages" }).click();
    await row.getByRole("button", { name: "Voir le texte" }).click();
    await expect(page.locator(".extracted-unit").first()).toBeVisible();
    const label = filename.endsWith("pdf") ? "Page 1" : filename.endsWith("docx") ? "Paragraphe 1" : "Ligne 1";
    await expect(page.locator(".extracted-unit").first().getByRole("heading")).toHaveText(label);
    expect((await page.locator(".extracted-unit pre").first().textContent())!.length).toBeGreaterThan(10);
    await page.getByRole("button", { name: "Fermer le texte" }).click();
  }
  await page.getByLabel("Choisir des fichiers").setInputFiles("/corpus/reseau.txt");
  await page.getByRole("button", { name: "Importer", exact: true }).click();
  await expect(page.getByRole("status")).toHaveText("Ce fichier est déjà dans votre bibliothèque.");
  await expect(page.getByRole("listitem")).toHaveCount(3);
  // The duplicate notice precedes refresh completion; users can select only once enabled.
  await expect(page.getByLabel("Choisir des fichiers")).toBeEnabled();
  await page.getByLabel("Choisir des fichiers").setInputFiles("/corpus/scan.pdf");
  await page.getByRole("button", { name: "Importer", exact: true }).click();
  const scan = page.getByRole("listitem").filter({ has: page.getByRole("heading", { name: "scan.pdf", exact: true }) });
  await expect(scan.getByText("Extraction impossible", { exact: true })).toBeVisible({ timeout: 120000 });
  await expect(scan.getByText(/PDF scannés/)).toBeVisible();
  await scan.getByRole("button", { name: "Relancer" }).click();
  await expect(scan.getByText("Extraction impossible", { exact: true })).toBeVisible({ timeout: 120000 });
  await scan.getByRole("button", { name: "Supprimer" }).click();
  await expect(scan).toHaveCount(0);
  await page.getByRole("listitem").filter({ has: page.getByRole("heading", { name: "atelier-rag.pdf", exact: true }) }).getByRole("button", { name: "Voir le texte" }).click();
  await expect(page.locator(".extracted-unit").first()).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect(await page.evaluate(() => Object.values(localStorage))).toEqual([]);
  await page.screenshot({ path: test.info().outputPath("import-library.png"), fullPage: true });
  await page.reload();
  await expect(page.getByRole("listitem")).toHaveCount(3);
  if (await page.getByRole("button", { name: "Ouvrir le panneau latéral" }).isVisible()) await page.getByRole("button", { name: "Ouvrir le panneau latéral" }).click();
  await page.getByRole("button", { name: "Se déconnecter" }).click();
    await expect(page).toHaveURL(/sign-in/);
  expect((await page.request.get("/api/v1/documents")).status()).toBe(401);
});

test("objets privés, propriétaires, autorisation courte, CSRF et finalisation idempotente", async () => {
  test.setTimeout(180000);
  const alice = await apiRequest.newContext({ baseURL });
  const bob = await apiRequest.newContext({ baseURL });
  try {
    await account(alice, "privatealice"); await account(bob, "privatebob");
    const bytes = Buffer.from("Texte privé synthétique.\nLigne suivante.");
    const reservation = await reserve(alice, "notes.txt", bytes);
    const id = reservation.document.id;
    const params = { headers: { origin: baseURL }, data: { upload_id: id } };
    expect((await alice.post("/api/v1/documents", params)).status()).toBe(409);
    expect((await alice.post("/api/v1/documents/uploads", { headers: { origin: "https://attacker.invalid" }, data: {} })).status()).toBe(403);
    expect((await alice.post("/api/v1/documents/uploads", { headers: { origin: baseURL }, data: { filename: "x.txt", size_bytes: 5, content_type: "text/plain", owner_id: "forged" } })).status()).toBe(422);
    expect((await bob.get(`/api/v1/documents/${id}`)).status()).toBe(404);
    expect((await bob.post("/api/v1/documents", params)).status()).toBe(404);
    for (const path of ["", "/extraction", "/passages", "/retry"]) {
      const response = path === "/retry" ? await bob.post(`/api/v1/documents/${id}${path}`, { headers: { origin: baseURL }, data: {} }) : await bob.get(`/api/v1/documents/${id}${path}`);
      expect(response.status()).toBe(404);
    }
    expect((await bob.delete(`/api/v1/documents/${id}`, { headers: { origin: baseURL } })).status()).toBe(404);
    const correct = { origin: baseURL, authorization: `Bearer ${reservation.upload_token}`, "content-type": "text/plain" };
    expect((await alice.get(reservation.upload_url)).status()).toBe(405);
    expect((await alice.put(reservation.upload_url, { data: bytes, headers: { ...correct, authorization: "Bearer wrong" } })).status()).toBe(404);
    expect((await alice.put(reservation.upload_url, { data: bytes, headers: { ...correct, origin: "https://attacker.invalid" } })).status()).toBe(403);
    expect((await alice.put(reservation.upload_url, { data: bytes.subarray(1), headers: correct })).status()).toBe(422);
    expect((await alice.put(reservation.upload_url, { data: bytes, headers: correct })).status()).toBe(204);
    expect((await alice.put(reservation.upload_url, { data: bytes, headers: correct })).status()).toBe(404);
    for (let event = 0; event < 3; event++) expect((await alice.post("/api/v1/documents", params)).status()).toBe(202);
    await expect.poll(async () => (await (await alice.get(`/api/v1/documents/${id}`)).json()).state, { timeout: 120000 }).toBe("ready");
    expect((await (await bob.get("/api/v1/documents")).json())).toEqual([]);
    expect((await upload(alice, "duplicate.txt", bytes)).id).toBe(id);
    const differentOwner = await upload(bob, "notes.txt", bytes);
    expect(differentOwner.id).not.toBe(id);
    const abandoned = await reserve(alice, "abandoned.txt", bytes);
    await alice.post("/api/auth/sign-out", { headers: { origin: baseURL }, data: {} });
    expect((await alice.put(abandoned.upload_url, { data: bytes, headers: { ...correct, authorization: `Bearer ${abandoned.upload_token}` } })).status()).toBe(404);
    expect((await alice.get(`${apiURL}/api/v1/documents`)).status()).toBe(401);
  } finally { await alice.dispose(); await bob.dispose(); }
});

test("envoi direct de vingt Mio et refus au-delà de la limite", async ({ page }) => {
  test.setTimeout(300000);
  await account(page.request, "boundary");
  await page.goto("/library");
  await page.locator(".library-import > summary").click();
  const prefix = Buffer.from("Document de vingt Mio.\n");
  const bytes = Buffer.alloc(20 * 1024 * 1024, 32); prefix.copy(bytes);
  const uploads: string[] = [];
  page.on("request", request => { if (request.method() === "PUT") uploads.push(request.url()); });
  await page.getByLabel("Choisir des fichiers").setInputFiles({ name: "vingt-mio.txt", mimeType: "text/plain", buffer: bytes });
  await page.getByRole("button", { name: "Importer", exact: true }).click();
  const row = page.getByRole("listitem").filter({ has: page.getByRole("heading", { name: "vingt-mio.txt", exact: true }) });
  await expect(row.getByText("Prêt", { exact: true })).toBeVisible({ timeout: 180000 });
  expect(uploads).toHaveLength(1); expect(uploads[0].startsWith(apiURL + "/api/v1/uploads/")).toBe(true);
  await row.getByRole("button", { name: "Voir le texte" }).click();
  await expect(page.locator(".extracted-unit pre").first()).toHaveText("Document de vingt Mio.");
  const oversized = await page.request.post("/api/v1/documents/uploads", {
    headers: { origin: baseURL }, data: { filename: "trop-grand.txt", size_bytes: bytes.length + 1, content_type: "text/plain" },
  });
  expect(oversized.status()).toBe(413);
  expect((await page.request.post("/api/v1/documents/uploads", { headers: { origin: baseURL }, data: { filename: "x.exe", size_bytes: 1, content_type: "application/octet-stream" } })).status()).toBe(415);
  await row.getByRole("button", { name: "Supprimer" }).click();
  await expect(row).toHaveCount(0);
});
