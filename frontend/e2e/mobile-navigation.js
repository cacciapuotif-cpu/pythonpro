#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');
const baseUrl = (process.env.BASE_URL || 'http://localhost:3001').replace(/\/+$/, '');
const tokens = JSON.parse(process.env.E2E_ROLE_TOKENS || '{}');
const artifactRoot = path.resolve(
  process.env.MOB2_ARTIFACT_DIR || 'test-results/mobile-navigation',
);

const expectedBottom = {
  admin: ['home', 'calendar', 'attendance', 'proposals', 'more'],
  operatore: ['home', 'calendar', 'attendance', 'proposals', 'more'],
  consultazione: ['home', 'calendar', 'people', 'archive', 'more'],
};
const expectedSectionCount = { admin: 21, operatore: 19, consultazione: 18 };

fs.mkdirSync(artifactRoot, { recursive: true });

const visible = async (locator) => locator.evaluate((element) => {
  const style = getComputedStyle(element);
  const rect = element.getBoundingClientRect();
  return style.display !== 'none' && style.visibility !== 'hidden'
    && rect.width > 0 && rect.height > 0;
});

const run = async () => {
  const browser = await chromium.launch({ args: ['--disable-dev-shm-usage', '--no-sandbox'] });
  const report = { generatedAt: new Date().toISOString(), baseUrl, roles: [], failures: [] };

  try {
    for (const role of Object.keys(expectedBottom)) {
      if (!tokens[role]) {
        report.failures.push(`${role}: token assente`);
        continue;
      }

      const context = await browser.newContext({
        viewport: { width: 375, height: 812 },
        reducedMotion: 'reduce',
      });
      const diagnostics = [];
      const page = await context.newPage();
      page.on('pageerror', (error) => diagnostics.push(`pageerror: ${error.message}`));
      page.on('console', (message) => {
        if (message.type() === 'error') diagnostics.push(`console.error: ${message.text()}`);
      });
      page.on('requestfailed', (request) => {
        const failure = request.failure()?.errorText || '';
        if (!failure.includes('ERR_ABORTED')) {
          diagnostics.push(`requestfailed: ${request.method()} ${request.url()} ${failure}`);
        }
      });
      page.on('response', (response) => {
        if (response.status() >= 400) {
          diagnostics.push(`response: ${response.status()} ${response.url()}`);
        }
      });

      const roleReport = { role, destinations: [], coveredSections: [], diagnostics: [] };
      report.roles.push(roleReport);
      await page.addInitScript((token) => {
        localStorage.setItem('access_token', token);
        localStorage.removeItem('refresh_token');
      }, tokens[role]);
      await page.goto(baseUrl, { waitUntil: 'domcontentloaded' });
      await page.locator('main[data-active-section]').waitFor({ timeout: 30000 });
      await page.waitForLoadState('networkidle');

      const mobileNav = page.locator('nav[aria-label="Navigazione mobile"]');
      const bottomItems = mobileNav.locator('[data-mobile-destination]');
      roleReport.destinations = await bottomItems.evaluateAll(
        (items) => items.map((item) => item.dataset.mobileDestination),
      );
      if (JSON.stringify(roleReport.destinations) !== JSON.stringify(expectedBottom[role])) {
        report.failures.push(
          `${role}: bottom ${JSON.stringify(roleReport.destinations)} != ${JSON.stringify(expectedBottom[role])}`,
        );
      }
      if (await visible(page.locator('[data-desktop-navigation]'))) {
        report.failures.push(`${role}: navigazione desktop visibile a 375px`);
      }

      const targetSizes = await bottomItems.evaluateAll((items) => items.map((item) => {
        const rect = item.getBoundingClientRect();
        return {
          id: item.dataset.mobileDestination,
          width: Math.round(rect.width),
          height: Math.round(rect.height),
        };
      }));
      targetSizes.filter((target) => target.width < 44 || target.height < 44)
        .forEach((target) => report.failures.push(
          `${role}: target ${target.id} ${target.width}x${target.height}`,
        ));

      const bottomStyle = await mobileNav.evaluate((element) => ({
        position: getComputedStyle(element).position,
        bottom: Math.round(element.getBoundingClientRect().bottom),
        viewport: window.innerHeight,
      }));
      if (bottomStyle.position !== 'fixed' || bottomStyle.bottom !== bottomStyle.viewport) {
        report.failures.push(`${role}: bottom navigation non fissata ${JSON.stringify(bottomStyle)}`);
      }

      if (role === 'admin') {
        for (const width of [1280, 1440, 1920]) {
          await page.setViewportSize({ width, height: 900 });
          await page.locator('[data-desktop-navigation]').waitFor();
          if (!(await visible(page.locator('[data-desktop-navigation]')))) {
            report.failures.push(`desktop-${width}: navigazione desktop nascosta`);
          }
          if (await page.locator('nav[aria-label="Navigazione mobile"]').count()) {
            report.failures.push(`desktop-${width}: navigazione mobile montata`);
          }
        }
        await page.setViewportSize({ width: 375, height: 812 });
        await mobileNav.waitFor();
      }

      await page.screenshot({
        path: path.join(artifactRoot, `${role}-home.png`),
        fullPage: true,
      });
      const bootstrapDiagnostics = diagnostics.splice(0);
      if (bootstrapDiagnostics.length) {
        roleReport.diagnostics.push(...bootstrapDiagnostics);
        report.failures.push(`${role}: ${bootstrapDiagnostics.length} errori bootstrap browser/API`);
      }

      // La raggiungibilità è un contratto di routing/RBAC: dopo aver verificato
      // un caricamento reale per ruolo, congela le API durante il giro delle
      // 18-21 route. Evita che il test stesso saturi il limite runtime 120/min.
      await page.route('**/api/**', () => new Promise(() => {}));

      const primary = expectedBottom[role].filter((id) => id !== 'more');
      for (const destination of primary) {
        await mobileNav.locator(`[data-mobile-destination="${destination}"]`).click();
        const expectedSection = {
          attendance: 'calendar',
          proposals: 'agents-review',
          people: 'collaborators',
          archive: 'archivio-chiedi',
        }[destination] || destination;
        await page.locator(`main[data-active-section="${expectedSection}"]`).waitFor();
        roleReport.coveredSections.push(expectedSection);
      }

      await mobileNav.locator('[data-mobile-destination="more"]').click();
      const dialog = page.locator('[data-mobile-menu][role="dialog"]');
      await dialog.waitFor();
      const dialogBox = await dialog.boundingBox();
      if (!dialogBox || dialogBox.width < 374 || dialogBox.height < 811) {
        report.failures.push(`${role}: menu Altro non full-screen ${JSON.stringify(dialogBox)}`);
      }
      const menuIds = await dialog.locator('[data-section-id]').evaluateAll(
        (items) => items.map((item) => item.dataset.sectionId),
      );

      for (const sectionId of menuIds) {
        await dialog.locator(`[data-section-id="${sectionId}"]`).click();
        await page.locator(`main[data-active-section="${sectionId}"]`).waitFor();
        roleReport.coveredSections.push(sectionId);
        await mobileNav.locator('[data-mobile-destination="more"]').click();
        await dialog.waitFor();
      }
      await page.goBack();
      await dialog.waitFor({ state: 'detached' });

      const covered = [...new Set(roleReport.coveredSections)].sort();
      roleReport.coveredSections = covered;
      if (covered.length !== expectedSectionCount[role]) {
        report.failures.push(
          `${role}: coperte ${covered.length}/${expectedSectionCount[role]} sezioni (${covered.join(', ')})`,
        );
      }

      await mobileNav.locator('[data-mobile-destination="home"]').click();
      await mobileNav.locator('[data-mobile-destination="calendar"]').click();
      await mobileNav.locator(`[data-mobile-destination="${primary[2]}"]`).click();
      await page.goBack();
      await page.locator('main[data-active-section="calendar"]').waitFor();
      await page.goBack();
      await page.locator('main[data-active-section="home"]').waitFor();

      const overflow = await page.evaluate(() => ({
        document: document.documentElement.scrollWidth,
        body: document.body.scrollWidth,
        viewport: window.innerWidth,
      }));
      if (overflow.document > overflow.viewport + 1 || overflow.body > overflow.viewport + 1) {
        report.failures.push(`${role}: overflow ${JSON.stringify(overflow)}`);
      }

      if (diagnostics.length) {
        roleReport.diagnostics.push(...diagnostics);
        report.failures.push(`${role}: ${diagnostics.length} errori browser`);
      }
      await context.close();
    }

  } finally {
    await browser.close();
  }

  const reportPath = path.join(artifactRoot, 'report.json');
  fs.writeFileSync(reportPath, `${JSON.stringify(report, null, 2)}\n`);
  console.log(`Report MOB-2: ${reportPath}`);
  if (report.failures.length) {
    report.failures.forEach((failure) => console.error(`- ${failure}`));
    process.exitCode = 1;
  } else {
    console.log('Gate MOB-2 verde: 3 ruoli, tutte le sezioni RBAC, Back e target touch.');
  }
};

run().catch((error) => {
  console.error(error);
  process.exit(1);
});
