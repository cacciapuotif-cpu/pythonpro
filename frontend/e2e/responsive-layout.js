#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');
const sections = require('../src/navigation/sections.json');

const baseUrl = (process.env.BASE_URL || 'http://localhost:3001').replace(/\/+$/, '');
const accessToken = process.env.E2E_ACCESS_TOKEN;
const artifactRoot = path.resolve(
  process.env.RESPONSIVE_ARTIFACT_DIR || 'test-results/responsive-layout',
);

const profiles = [
  { name: 'iphone-se', width: 375, height: 812, mobile: true },
  { name: 'desktop-1280', width: 1280, height: 900, mobile: false },
  { name: 'desktop-1440', width: 1440, height: 900, mobile: false },
  { name: 'desktop-1920', width: 1920, height: 1080, mobile: false },
];

if (!accessToken) {
  console.error('E2E_ACCESS_TOKEN obbligatorio: gate non eseguito.');
  process.exit(2);
}

fs.mkdirSync(artifactRoot, { recursive: true });
for (const artifact of fs.readdirSync(artifactRoot)) {
  if (artifact.endsWith('.png') || artifact === 'report.json') {
    fs.unlinkSync(path.join(artifactRoot, artifact));
  }
}

const settleLayout = async (page) => {
  await page.evaluate(async () => {
    await document.fonts.ready;
    await new Promise((resolve) => requestAnimationFrame(
      () => requestAnimationFrame(resolve),
    ));
  });
};

const readLayout = (page, mobile) => page.evaluate((isMobile) => {
  const viewportWidth = window.innerWidth;
  const html = document.documentElement;
  const body = document.body;
  const visible = (element) => {
    const style = getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return style.display !== 'none'
      && style.visibility !== 'hidden'
      && rect.width > 0
      && rect.height > 0;
  };
  const controlsBelowMinimum = isMobile
    ? Array.from(document.querySelectorAll('input, select, textarea'))
      .filter(visible)
      .filter((element) => !['checkbox', 'radio'].includes(element.getAttribute('type')))
      .map((element) => ({
        tag: element.tagName.toLowerCase(),
        type: element.getAttribute('type'),
        name: element.getAttribute('name'),
        fontSize: Number.parseFloat(getComputedStyle(element).fontSize),
      }))
      .filter((control) => control.fontSize < 16)
    : [];
  const offenders = Array.from(document.querySelectorAll('body *'))
    .filter(visible)
    .map((element) => {
      const rect = element.getBoundingClientRect();
      return {
        tag: element.tagName.toLowerCase(),
        className: typeof element.className === 'string' ? element.className.slice(0, 120) : '',
        left: Math.round(rect.left),
        right: Math.round(rect.right),
        width: Math.round(rect.width),
      };
    })
    .filter((element) => element.left < -1 || element.right > viewportWidth + 1)
    .slice(0, 12);
  const responsiveLists = Array.from(document.querySelectorAll('[data-responsive-list]'))
    .filter(visible)
    .map((list) => {
      const layouts = Array.from(list.querySelectorAll('[data-responsive-layout]'))
        .filter(visible)
        .map((layout) => layout.getAttribute('data-responsive-layout'));
      const entityIds = Array.from(list.querySelectorAll('[data-entity-id]'))
        .map((item) => item.getAttribute('data-entity-id'));
      return {
        id: list.getAttribute('data-responsive-list'),
        layouts,
        entityCount: entityIds.length,
        duplicateEntityIds: entityIds.filter((id, index) => entityIds.indexOf(id) !== index),
      };
    });

  return {
    viewportWidth,
    clientWidth: html.clientWidth,
    documentScrollWidth: html.scrollWidth,
    bodyScrollWidth: body.scrollWidth,
    controlsBelowMinimum,
    offenders,
    responsiveLists,
  };
}, mobile);

const run = async () => {
  const browser = await chromium.launch({
    args: ['--disable-dev-shm-usage', '--no-sandbox'],
  });
  const report = {
    generatedAt: new Date().toISOString(),
    baseUrl,
    profiles: [],
    failures: [],
  };

  const profileReports = new Map(profiles.map((profile) => {
    const profileReport = { ...profile, sections: [], publicFlows: [] };
    report.profiles.push(profileReport);
    return [profile.name, profileReport];
  }));
  const firstProfile = profiles[0];
  const context = await browser.newContext({
    viewport: { width: firstProfile.width, height: firstProfile.height },
    reducedMotion: 'reduce',
  });
  const page = await context.newPage();
  const browserDiagnostics = [];

  page.on('console', (message) => {
    if (['error', 'warning'].includes(message.type())) {
      browserDiagnostics.push(`console.${message.type()}: ${message.text()}`);
    }
  });
  page.on('pageerror', (error) => browserDiagnostics.push(`pageerror: ${error.message}`));
  page.on('requestfailed', (request) => {
    browserDiagnostics.push(
      `requestfailed: ${request.method()} ${request.url()} ${request.failure()?.errorText || ''}`,
    );
  });
  page.on('response', (response) => {
    if (response.status() >= 400) {
      browserDiagnostics.push(`response: ${response.status()} ${response.url()}`);
    }
  });

  try {
    await page.addInitScript((token) => {
      window.localStorage.setItem('access_token', token);
      window.localStorage.removeItem('refresh_token');
    }, accessToken);
    await page.goto(baseUrl, { waitUntil: 'domcontentloaded' });
    try {
      await page.locator('main[data-active-section]').waitFor({ timeout: 30000 });
    } catch (error) {
      const bodyText = (await page.locator('body').innerText()).slice(0, 1200);
      console.error(`Applicazione non pronta\n${bodyText}`);
      browserDiagnostics.forEach((item) => console.error(`- ${item}`));
      await page.screenshot({
        path: path.join(artifactRoot, 'bootstrap-FAIL.png'),
        fullPage: true,
      });
      throw error;
    }

    const viewportMeta = await page.locator('meta[name="viewport"]').getAttribute('content');
    const requiredViewportValues = ['width=device-width', 'initial-scale=1', 'viewport-fit=cover'];
    for (const value of requiredViewportValues) {
      if (!(viewportMeta || '').split(',').map((item) => item.trim()).includes(value)) {
        report.failures.push(`Meta viewport privo di ${value}`);
      }
    }

    await page.evaluate(() => {
      document.documentElement.style.setProperty('--safe-area-top', '13px');
      document.documentElement.style.setProperty('--safe-area-right', '11px');
      document.documentElement.style.setProperty('--safe-area-bottom', '17px');
      document.documentElement.style.setProperty('--safe-area-left', '7px');
    });
    const safeArea = await page.evaluate(() => ({
      headerTop: Number.parseFloat(getComputedStyle(document.querySelector('.app-header')).paddingTop),
      mainRight: Number.parseFloat(getComputedStyle(document.querySelector('.app-main')).paddingRight),
      mainBottom: Number.parseFloat(getComputedStyle(document.querySelector('.app-main')).paddingBottom),
      mainLeft: Number.parseFloat(getComputedStyle(document.querySelector('.app-main')).paddingLeft),
    }));
    if (safeArea.headerTop < 13 || safeArea.mainRight < 11
      || safeArea.mainBottom < 17 || safeArea.mainLeft < 7) {
      report.failures.push(`Safe area non applicata ${JSON.stringify(safeArea)}`);
    }

    // Una sola visita dati per sezione, poi quattro misure di viewport sullo
    // stesso DOM: evita di quadruplicare le API e rispetta il rate limit reale.
    const orderedSections = [
      ...sections.filter((section) => section.hidden),
      ...sections.filter((section) => !section.hidden),
    ];
    for (const section of orderedSections) {
      const navButton = page.locator(`[data-section-id="${section.id}"]`);
      if (await navButton.count()) {
        await navButton.click();
      } else if (section.hidden) {
        const route = section.id === 'agents-review' ? '/agents/review' : '/';
        await page.goto(`${baseUrl}${route}`, { waitUntil: 'domcontentloaded' });
      } else {
        profileReports.forEach((profileReport) => {
          profileReport.sections.push({ id: section.id, skipped: 'non consentita dal ruolo' });
        });
        continue;
      }

      try {
        await page.locator(`main[data-active-section="${section.id}"]`).waitFor({ timeout: 30000 });
      } catch (error) {
        const activeSection = await page.locator('main[data-active-section]')
          .getAttribute('data-active-section')
          .catch(() => null);
        console.error(
          `${section.id}: sezione non pronta (attiva: ${activeSection || 'nessuna'})`,
        );
        browserDiagnostics.slice(-12).forEach((item) => console.error(`- ${item}`));
        throw error;
      }
      await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => {});
      await settleLayout(page);

      for (const profile of profiles) {
        await page.setViewportSize({ width: profile.width, height: profile.height });
        await settleLayout(page);
        let loadMore = null;
        if (profile.mobile) {
          const loadMoreButton = page.locator(
            'main[data-active-section] [data-pagination-layout="mobile"] [data-load-more]',
          ).first();
          if (await loadMoreButton.count() && await loadMoreButton.isEnabled()) {
            const items = page.locator(
              'main[data-active-section] [data-responsive-layout="mobile"] [data-entity-id]',
            );
            const before = await items.count();
            await loadMoreButton.click();
            await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => {});
            await settleLayout(page);
            const after = await items.count();
            loadMore = { before, after, advanced: after > before };
          }
        }
        const layout = await readLayout(page, profile.mobile);
        const overflow = layout.documentScrollWidth > layout.clientWidth + 1
          || layout.bodyScrollWidth > layout.viewportWidth + 1;
        const invalidResponsiveLists = layout.responsiveLists.filter((list) => (
          list.layouts.length !== 1
          || list.layouts[0] !== (profile.mobile ? 'mobile' : 'desktop')
          || list.duplicateEntityIds.length > 0
        ));
        const failed = overflow
          || layout.controlsBelowMinimum.length > 0
          || invalidResponsiveLists.length > 0
          || loadMore?.advanced === false;
        profileReports.get(profile.name).sections.push({
          id: section.id,
          failed,
          loadMore,
          ...layout,
        });

        if (failed) {
          const reasons = [];
          if (overflow) {
            reasons.push(
              `scrollWidth html/body ${layout.documentScrollWidth}/${layout.bodyScrollWidth}`
              + ` > viewport ${layout.viewportWidth}`,
            );
          }
          if (layout.controlsBelowMinimum.length) {
            reasons.push(`${layout.controlsBelowMinimum.length} controlli sotto 16px`);
          }
          if (invalidResponsiveLists.length) {
            reasons.push(`liste responsive non valide: ${JSON.stringify(invalidResponsiveLists)}`);
          }
          if (loadMore?.advanced === false) {
            reasons.push(`Carica altri non ha aggiunto elementi: ${JSON.stringify(loadMore)}`);
          }
          report.failures.push(`${profile.name}/${section.id}: ${reasons.join(', ')}`);
          await page.screenshot({
            path: path.join(artifactRoot, `${profile.name}-${section.id}-FAIL.png`),
            fullPage: true,
          });
        } else if (
          ['home', 'calendar'].includes(section.id)
          || (
            ['iphone-se', 'desktop-1280'].includes(profile.name)
            && [
              'documenti-mancanti',
              'collaborators',
              'allievi',
              'projects',
              'aziende-clienti',
              'preventivi',
              'ordini',
              'resources',
              'agents-review',
            ].includes(section.id)
          )
        ) {
          await page.screenshot({
            path: path.join(artifactRoot, `${profile.name}-${section.id}.png`),
            fullPage: true,
          });
        }
      }
    }

    const publicContext = await browser.newContext({
      viewport: { width: firstProfile.width, height: firstProfile.height },
      reducedMotion: 'reduce',
    });
    const publicPage = await publicContext.newPage();
    const publicFlows = [
      {
        id: 'login',
        open: () => publicPage.goto(baseUrl, { waitUntil: 'domcontentloaded' }),
        ready: () => publicPage.getByRole('heading', { name: 'Accesso al gestionale' }).waitFor(),
      },
      {
        id: 'recupero-password',
        open: () => publicPage.getByRole('button', { name: 'Password dimenticata?' }).click(),
        ready: () => publicPage.getByRole('heading', { name: 'Password dimenticata' }).waitFor(),
      },
      {
        id: 'reset-password',
        open: () => publicPage.goto(`${baseUrl}/reset-password?token=e2e-invalid`, {
          waitUntil: 'domcontentloaded',
        }),
        ready: () => publicPage.getByRole('heading', { name: 'Reimposta la password' }).waitFor(),
      },
      {
        id: 'portale-allievi',
        open: () => publicPage.goto(`${baseUrl}/portale-allievi`, {
          waitUntil: 'domcontentloaded',
        }),
        ready: () => publicPage.getByText('Link non valido.', { exact: false }).waitFor(),
      },
    ];

    try {
      for (const flow of publicFlows) {
        await flow.open();
        await flow.ready();
        for (const profile of profiles) {
          await publicPage.setViewportSize({ width: profile.width, height: profile.height });
          await settleLayout(publicPage);
          const layout = await readLayout(publicPage, profile.mobile);
          const overflow = layout.documentScrollWidth > layout.clientWidth + 1
            || layout.bodyScrollWidth > layout.viewportWidth + 1;
          const failed = overflow || layout.controlsBelowMinimum.length > 0;
          profileReports.get(profile.name).publicFlows.push({
            id: flow.id,
            failed,
            ...layout,
          });
          if (failed) {
            report.failures.push(
              `${profile.name}/${flow.id}: layout pubblico fuori contratto`,
            );
            await publicPage.screenshot({
              path: path.join(artifactRoot, `${profile.name}-${flow.id}-FAIL.png`),
              fullPage: true,
            });
          } else if (
            flow.id === 'login'
            && ['iphone-se', 'desktop-1280'].includes(profile.name)
          ) {
            await publicPage.screenshot({
              path: path.join(artifactRoot, `${profile.name}-${flow.id}.png`),
              fullPage: true,
            });
          }
        }
      }
    } finally {
      await publicContext.close();
    }
  } finally {
    await context.close();
    await browser.close();
  }

  const reportPath = path.join(artifactRoot, 'report.json');
  fs.writeFileSync(reportPath, `${JSON.stringify(report, null, 2)}\n`);
  console.log(`Report responsive: ${reportPath}`);
  if (report.failures.length) {
    report.failures.forEach((failure) => console.error(`- ${failure}`));
    process.exit(1);
  }
  console.log(
    `Gate verde: ${profiles.length} profili × `
    + `${sections.length} sezioni + 4 flussi pubblici.`,
  );
};

run().catch((error) => {
  console.error(error);
  process.exit(1);
});
