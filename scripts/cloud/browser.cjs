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
    await page.getByRole('link', { name: 'Mes conversations', exact: true }).click();
    if (!progress.conversation) {
      await page.getByRole('button', { name: 'Nouvelle conversation' }).click();
      await expect(page).toHaveURL(/\/conversations\/[a-f0-9-]+$/, { timeout: 30000 });
      progress.conversation = page.url(); save();
    } else await page.goto(progress.conversation);
    for (const [i, question] of ["Quelle est la taille des passages dans l'atelier Iris ?", "Et quel chevauchement utilise cet atelier ?"].entries()) {
      const count = await page.locator('.chat-exchange').count();
      if (count <= i) {
        if (progress.reserved === i) throw new Error('Interrupted browser generation requires reconciliation');
        if (progress.lastRequest) await page.waitForTimeout(Math.max(0, 33000 - (Date.now()-progress.lastRequest)));
        await page.getByLabel('Votre question').fill(question);
        await expect(page.getByRole('button', { name: 'Envoyer ma question' })).toBeDisabled();
        await page.getByRole('checkbox', { name: /J’accepte l’envoi/ }).check();
        progress.reserved = i; progress.lastRequest = Date.now(); save();
        await page.getByRole('button', { name: 'Envoyer ma question' }).click();
      }
      await expect(page.locator('.answer-claims')).toHaveCount(i+1, { timeout: 180000 });
      progress.reserved = null; save();
    }
    checks.two_real_answers = true;
    await expect(page.locator('.answer-claims').first()).toContainText('220');
    await expect(page.locator('.answer-claims').last()).toContainText('40');
    await page.getByText('Vérifier la source S1', { exact: true }).first().click();
    await expect(page.locator('.answer-source pre').first()).toBeVisible();
    checks.source_visible = true;
    await page.reload();
    await expect(page.locator('.chat-exchange')).toHaveCount(2);
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
    const report = { date: new Date().toISOString(), url: state.url, checks, real_generation_requests: 2 };
    writeFileSync(root + '/evaluation/reports/browser-step8.json', JSON.stringify(report, null, 2) + '\n');
    if (!Object.values(checks).every(Boolean)) throw new Error('Browser check failed');
    console.log('Production browser flow passed:', Object.keys(checks).length, 'checks');
  } finally { await browser.close(); }
})().catch(error => { console.error(error.message); process.exitCode = 1; });
