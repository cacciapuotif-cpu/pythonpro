const { chromium } = require('playwright');
const fs = require('fs');

const baseUrl = process.env.BASE_URL || 'http://host.docker.internal:3001';
const token = fs.readFileSync(process.env.TOKEN_FILE || '/run/admin_token', 'utf8').trim();
const inputFile = process.env.INPUT_FILE || '/work/azienda_input.xlsx';
const outputDir = process.env.OUTPUT_DIR || '/out';
const chromiumExecutablePath = process.env.CHROMIUM_EXECUTABLE_PATH;

const checks = [];
const record = (caseNumber, description, passed, evidence) => {
  checks.push({ case: caseNumber, description, passed, evidence });
  if (!passed) throw new Error(`Caso ${caseNumber} fallito: ${description}`);
};

const authenticate = async (context) => {
  await context.addInitScript((accessToken) => {
    localStorage.setItem('access_token', accessToken);
  }, token);
};

(async () => {
  fs.mkdirSync(outputDir, { recursive: true });
  const browser = await chromium.launch({
    headless: true,
    args: ['--disable-gpu', '--disable-software-rasterizer'],
    ...(chromiumExecutablePath ? { executablePath: chromiumExecutablePath } : {}),
  });
  try {
    const desktop = await browser.newContext({ viewport: { width: 1440, height: 1000 }, acceptDownloads: true });
    await authenticate(desktop);
    const page = await desktop.newPage();
    await page.goto(`${baseUrl}/aziende-clienti`, { waitUntil: 'networkidle' });
    await page.getByRole('heading', { name: 'Aziende Clienti' }).waitFor();

    await page.getByRole('button', { name: 'Importa Excel' }).click();
    const templateDownload = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Scarica template Excel' }).click();
    const template = await templateDownload;
    await template.saveAs(`${outputDir}/template-scaricato-ui.xlsx`);
    record(1, 'Template scaricato dalla piattaforma', fs.existsSync(`${outputDir}/template-scaricato-ui.xlsx`), 'template-scaricato-ui.xlsx');

    await page.locator('#aziende-file-input').setInputFiles(inputFile);
    await page.getByRole('heading', { name: 'Anteprima importazione' }).waitFor();
    const previewText = await page.locator('.preview-section').innerText();
    record(2, 'File con due aziende e tre sedi accettato in anteprima', /2\s+da aggiornare/i.test(previewText) && /0\s+da scartare/i.test(previewText), previewText);
    await page.getByRole('button', { name: /Importa 2 righe valide/i }).click();
    await page.getByRole('heading', { name: 'Importazione completata' }).waitFor();
    const importText = await page.locator('.import-result').innerText();
    record(3, 'Reimport aggiorna senza duplicare', /0 create, 2 aggiornate, 0 scartate/i.test(importText), importText);
    await page.getByRole('button', { name: 'Chiudi', exact: true }).click();

    const search = page.getByPlaceholder(/Cerca ragione sociale/i);
    await search.fill('COLLAUDO ALLINEAMENTO ALFA');
    await page.waitForTimeout(500);
    const row = page.locator('tr', { hasText: 'COLLAUDO ALLINEAMENTO ALFA SRL' });
    await row.getByText('Azioni', { exact: true }).click();
    await row.getByRole('button', { name: 'Apri scheda' }).click();
    const dialog = page.getByRole('dialog', { name: 'COLLAUDO ALLINEAMENTO ALFA SRL' });
    await dialog.waitFor();
    await page.waitForTimeout(350);
    await page.screenshot({ path: `${outputDir}/04-scheda-desktop.png` });
    const sectionText = await dialog.innerText();
    const sites = await dialog.locator('.azienda-detail-card').filter({ hasText: /Alfa (Napoli|Caserta|Salerno)/ }).count();
    const maskedIban = await dialog.locator('.azienda-detail-iban').innerText();
    await dialog.getByRole('button', { name: 'Mostra IBAN completo' }).click();
    await page.waitForFunction(
      ([selector, previous]) => document.querySelector(selector)?.textContent?.trim() !== previous,
      ['.azienda-detail-iban', maskedIban],
    );
    const revealedIban = await dialog.locator('.azienda-detail-iban').innerText();
    record(
      4,
      'Scheda leggibile, campi nel gruppo corretto, tre sedi e IBAN autorizzato presenti',
      sites === 3
        && sectionText.includes('CCNL prevalente')
        && sectionText.includes('Commercio')
        && sectionText.includes('Riferimenti commerciali')
        && revealedIban !== maskedIban
        && !revealedIban.includes('•'),
      `sedi=${sites}; iban_mascherato=${maskedIban}; iban_rivelato=${revealedIban}`,
    );
    await page.waitForTimeout(350);
    await page.screenshot({ path: `${outputDir}/04-scheda-desktop-relazioni.png` });
    await dialog.getByRole('button', { name: 'Chiudi', exact: true }).click();

    const exportDownload = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Esporta Excel' }).click();
    const exported = await exportDownload;
    await exported.saveAs(`${outputDir}/export-scaricato-ui.xlsx`);
    record(5, 'Export scaricato dalla piattaforma', fs.existsSync(`${outputDir}/export-scaricato-ui.xlsx`), 'export-scaricato-ui.xlsx');
    await desktop.close();

    const mobile = await browser.newContext({ viewport: { width: 375, height: 812 } });
    await authenticate(mobile);
    const mobilePage = await mobile.newPage();
    await mobilePage.goto(`${baseUrl}/aziende-clienti`, { waitUntil: 'networkidle' });
    await mobilePage.getByPlaceholder(/Cerca ragione sociale/i).fill('COLLAUDO ALLINEAMENTO ALFA');
    await mobilePage.waitForTimeout(500);
    const card = mobilePage.locator('article.responsive-card', { hasText: 'COLLAUDO ALLINEAMENTO ALFA SRL' });
    await card.getByRole('button', { name: 'Apri scheda' }).click();
    await mobilePage.getByRole('dialog', { name: 'COLLAUDO ALLINEAMENTO ALFA SRL' }).waitFor();
    await mobilePage.getByText('Identificazione', { exact: true }).click();
    const mobileMetrics = await mobilePage.evaluate(() => ({
      viewport: window.innerWidth,
      documentWidth: document.documentElement.scrollWidth,
      shortTargets: [...document.querySelectorAll('.azienda-detail button')]
        .filter((element) => element.getBoundingClientRect().height < 44)
        .map((element) => element.textContent.trim()),
    }));
    record(6, 'Mobile 375px senza scroll orizzontale e target almeno 44px', mobileMetrics.documentWidth <= mobileMetrics.viewport && mobileMetrics.shortTargets.length === 0, mobileMetrics);
    await mobilePage.waitForTimeout(350);
    await mobilePage.screenshot({ path: `${outputDir}/06-scheda-mobile-375.png` });
    await mobile.close();
  } finally {
    await browser.close();
  }
  fs.writeFileSync(`${outputDir}/report.json`, JSON.stringify({ passed: checks.every((item) => item.passed), checks }, null, 2));
})().catch((error) => {
  fs.mkdirSync(outputDir, { recursive: true });
  fs.writeFileSync(`${outputDir}/report.json`, JSON.stringify({ passed: false, checks, error: error.stack }, null, 2));
  process.exitCode = 1;
});
