/* Actual browser and actual Groq. State is private; screenshots contain CC0 fixtures only. */
const { createRequire } = require('node:module');
const { readFileSync, writeFileSync, mkdirSync, existsSync } = require('node:fs');
const { resolve } = require('node:path');
const requireFrontend = createRequire('/app/package.json');
const { chromium, expect } = requireFrontend('@playwright/test');
const root = resolve(__dirname, '../..');
const state = JSON.parse(readFileSync(root + '/evaluation/.qa/production-smoke-state.json', 'utf8'));
const marker = root + '/evaluation/.qa/browser-state.json';
const progress = existsSync(marker) ? JSON.parse(readFileSync(marker, 'utf8')) : {};
const save = () => writeFileSync(marker, JSON.stringify(progress, null, 2), { mode: 0o600 });
(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  const checks = {};
  try {
    await page.goto(state.url + '/sign-in');
    await page.getByLabel('Nom d’utilisateur').fill(state.accounts[0].username);
    await page.getByLabel('Mot de passe', { exact: true }).fill(state.accounts[0].password);
    await page.getByRole('button', { name: 'Se connecter' }).click();
    await expect(page).toHaveURL(/\/library$/, { timeout: 30000 });
    checks.login = true;
    const uploads = [];
    let selectedBytes = 0;
    page.on('request', request => {
      if (request.method() === 'PUT') uploads.push({ host: new URL(request.url()).hostname,
        path: new URL(request.url()).pathname, selected_bytes: selectedBytes,
        credentials: !!(request.headers().authorization || request.headers().cookie) });
    });
    if (!progress.uploads) {
      for (const filename of ['atelier-rag.pdf', 'parcours-2026.docx', 'reseau.txt', 'vingt-mio.txt']) {
        const twenty = Buffer.alloc(20 * 1024 * 1024, ' ');
        Buffer.from('Qualification vingt Mio.\n').copy(twenty);
        await page.getByLabel('Choisir des fichiers').setInputFiles(filename === 'vingt-mio.txt'
          ? { name: filename, mimeType: 'text/plain', buffer: twenty }
          : root + '/evaluation/corpus/' + filename);
        selectedBytes = await page.getByLabel('Choisir des fichiers').evaluate(input => input.files[0].size);
        await page.getByRole('button', { name: 'Importer', exact: true }).click();
        await expect(page.locator('.upload-card [role="status"]')).toHaveText('Ce fichier est déjà dans votre bibliothèque.', { timeout: 180000 });
        // Cloud documentRequest is bounded at 70 s, including a cold refresh.
        await expect(page.getByLabel('Choisir des fichiers')).toBeEnabled({ timeout: 70000 });
      }
      progress.upload_attempt = uploads; save();
      // @vercel/blob 2.8.1 presigned PUT targets the Blob API, while private GET
      // targets the private store host. Neither is our application's function.
      if (uploads.length !== 4 || !uploads.every(u => u.host === 'vercel.com' && u.path === '/api/blob/' && !u.credentials)
          || !uploads.some(u => u.selected_bytes === 20 * 1024 * 1024)) throw new Error('Direct browser upload check failed');
      progress.uploads = uploads; save();
    }
    checks.browser_direct_upload_and_deduplication = true;
    if (process.argv.includes('--imports-only')) {
      console.log('Browser imports passed: three formats and 20 MiB, direct and private');
      return;
    }
    await page.getByRole('link', { name: 'Mes conversations', exact: true }).click();
    if (!progress.conversation) {
      await page.getByRole('button', { name: 'Nouvelle conversation' }).click();
      await expect(page).toHaveURL(/\/conversations\/[a-f0-9-]+$/, { timeout: 30000 });
      progress.conversation = page.url(); save();
    } else await page.goto(progress.conversation);
    await expect(page.getByLabel('Votre question')).toBeVisible({ timeout: 30000 });
    for (const [i, question] of ["Quelle est la taille des passages dans l'atelier Iris ?", "Et quel chevauchement utilise cet atelier ?"].entries()) {
      if (progress.generations?.[i]) continue;
      const count = await page.locator('.chat-exchange').count();
      let started;
      if (count <= i + (progress.failedBefore ?? 0)) {
        if (progress.reserved === i) throw new Error('Interrupted browser generation requires reconciliation');
        if (progress.lastRequest) await page.waitForTimeout(Math.max(0, 35000 - (Date.now()-progress.lastRequest)));
        await page.getByLabel('Votre question').fill(question);
        await expect(page.getByRole('button', { name: 'Envoyer ma question' })).toBeDisabled();
        await page.getByRole('checkbox', { name: /J’accepte l’envoi/ }).check();
        progress.reserved = i; progress.lastRequest = Date.now(); save();
        started = performance.now();
        await page.getByRole('button', { name: 'Envoyer ma question' }).click();
      }
      await expect(page.locator('.chat-exchange')).toHaveCount(count + 1, { timeout: 180000 });
      const last = page.locator('.chat-exchange').last();
      await expect.poll(async () => {
        if (await last.locator('.answer-claims').count()) return 'answered';
        if ((await last.innerText()).includes('Échange échoué')) return 'failed';
        return 'pending';
      }, { timeout: 180000 }).not.toBe('pending');
      if (!(await last.locator('.answer-claims').count())) {
        progress.technicalFailures ??= [];
        progress.technicalFailures.push({ question, elapsed_ms: performance.now() - started,
          state: 'failed', observed_at: new Date().toISOString() });
        save();
        throw new Error('New exchange failed; preserve it and reconcile before another request');
      }
      if (started !== undefined) {
        const elapsed = performance.now() - started;
        const exchanges = await (await page.request.get(progress.conversation.replace('/conversations/', '/api/v1/conversations/') + '/messages')).json();
        const exchange = exchanges.at(-1);
        if (exchange.question !== question || exchange.state !== 'answered') throw new Error('New exchange did not produce a validated answer');
        const answer = exchange.answer;
        progress.generations ??= [];
        progress.generations.push({ question, elapsed_ms: elapsed, state: answer.state,
          provider_called: answer.provider_called, prompt_version: answer.prompt_version,
          server_ms: answer.elapsed_ms });
        progress.lastRequest = Date.now();
      }
      progress.reserved = null; save();
    }
    checks.two_real_answers = true;
    await expect(page.locator('.answer-claims').first()).toContainText('220');
    await expect(page.locator('.answer-claims').last()).toContainText('40');
    await page.getByText('Vérifier la source S1', { exact: true }).first().click();
    await expect(page.locator('.answer-source pre').first()).toBeVisible();
    checks.source_visible = true;
    await page.reload();
    await expect(page.locator('.chat-exchange')).toHaveCount(2 + (progress.failedBefore ?? 0));
    if (progress.failedBefore) {
      await expect(page.locator('.chat-exchange').first()).toContainText('Échange échoué');
      checks.rejected_answer_remains_in_history = true;
    }
    checks.reload = true;
    mkdirSync(root + '/evaluation/reports/images', { recursive: true });
    await page.screenshot({ path: root + '/evaluation/reports/images/step8-conversation-desktop.png', fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    checks.mobile_no_overflow = await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth);
    checks.no_local_storage = (await page.evaluate(() => Object.keys(localStorage))).length === 0;
    await page.screenshot({ path: root + '/evaluation/reports/images/step8-conversation-mobile.png', fullPage: true });
    await page.getByRole('button', { name: 'Se déconnecter' }).click();
    await expect(page).toHaveURL(/\/sign-in$/, { timeout: 30000 });
    const id = progress.conversation.split('/').pop();
    checks.logout = (await page.request.get(state.url + `/api/v1/conversations/${id}/messages`)).status() === 401;
    await page.getByLabel('Nom d’utilisateur').fill(state.accounts[1].username);
    await page.getByLabel('Mot de passe', { exact: true }).fill(state.accounts[1].password);
    await page.getByRole('button', { name: 'Se connecter' }).click();
    await expect(page).toHaveURL(/\/library$/, { timeout: 30000 });
    checks.conversation_isolation = (await page.request.get(state.url + `/api/v1/conversations/${id}/messages`)).status() === 404;
    const report = { date: new Date().toISOString(), url: state.url, checks, uploads: progress.uploads,
      generations: progress.generations, initial_failure: progress.initialFailure,
      technical_failures: progress.technicalFailures,
      real_generation_requests: 2 + (progress.failedBefore ?? 0) };
    writeFileSync(root + '/evaluation/reports/browser-step8.json', JSON.stringify(report, null, 2) + '\n');
    if (!Object.values(checks).every(Boolean)) throw new Error('Browser check failed');
    console.log('Production browser flow passed:', Object.keys(checks).length, 'checks');
  } finally { await browser.close(); }
})().catch(error => { console.error(error.message); process.exitCode = 1; });
