#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const { chromium, request } = require('playwright');

const baseUrl = (process.env.BASE_URL || 'http://192.168.2.41:3001').replace(/\/+$/, '');
const token = process.env.E2E_ACCESS_TOKEN;
const projectId = 11;
const artifacts = path.resolve(process.env.DELIVERY_ARTIFACT_DIR || 'test-results/delivery-sites-real');

if (!token) throw new Error('E2E_ACCESS_TOKEN obbligatorio');
fs.mkdirSync(artifacts, { recursive: true });

const results = [];
const assert = (condition, message) => { if (!condition) throw new Error(message); };
const record = (caseNumber, outcome, evidence) => results.push({ case: caseNumber, outcome, evidence });

const run = async () => {
  const api = await request.newContext({
    baseURL: baseUrl,
    extraHTTPHeaders: { Authorization: `Bearer ${token}` },
  });
  const getJson = async (url) => {
    const response = await api.get(url);
    assert(response.ok(), `GET ${url}: ${response.status()} ${await response.text()}`);
    return response.json();
  };
  const project = () => getJson(`/api/v1/projects/${projectId}`);
  const aziende = (await getJson('/api/v1/aziende-clienti/?page=1&limit=100')).items;
  const entity = await getJson('/api/v1/entities/1');
  const power = aziende.find((item) => item.id === 10);
  const martinelli = aziende.find((item) => item.id === 11);
  const maximercato = aziende.find((item) => item.id === 12);
  assert(power?.sedi_operative?.length, 'Power Impianti non ha la sede attesa');
  assert(entity?.sedi?.filter((item) => item.is_active).length >= 2, 'Ente attuatore senza due sedi attive');

  const ownSite = power.sedi_operative[0];
  const entitySites = entity.sedi.filter((item) => item.is_active);
  const browser = await chromium.launch({ args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  await context.addInitScript((accessToken) => localStorage.setItem('access_token', accessToken), token);
  const page = await context.newPage();

  const openDelivery = async () => {
    await page.goto(`${baseUrl}/projects`, { waitUntil: 'networkidle' });
    const card = page.locator(`[data-entity-id="${projectId}"]:visible`);
    await card.waitFor();
    await card.getByTitle('Modifica progetto').click();
    await page.getByRole('heading', { name: 'Modifica progetto' }).waitFor();
    await page.locator('.wizard-step').filter({ hasText: 'Delivery' }).click();
    await page.getByText('Sede di erogazione per azienda', { exact: true }).waitFor();
  };
  const companySection = (name) => page.locator('.delivery-company').filter({ hasText: name });
  const addExisting = async (name, optionValue) => {
    const section = companySection(name);
    await section.locator('.delivery-add-row select').selectOption(optionValue);
    await section.getByRole('button', { name: 'Aggiungi sede', exact: true }).click();
  };
  const save = async () => {
    await page.getByRole('button', { name: /Aggiorna/ }).click();
    await page.getByRole('heading', { name: 'Modifica progetto' }).waitFor({ state: 'detached' });
  };
  const deliveryFor = (body, aziendaId) => body.aziende_delivery.find((item) => item.azienda_id === aziendaId);

  await openDelivery();
  const flatLabels = await page.locator('label').filter({ hasText: /Sede Aziendale -|Sede nei contratti/ }).count();
  const companyAreas = await page.locator('.delivery-company').count();
  const initialProject = await project();
  assert(flatLabels === 0, 'I campi piatti sono ancora nel passo Delivery');
  assert(companyAreas === initialProject.azienda_ids.length, `Aree sede ${companyAreas}, aziende ${initialProject.azienda_ids.length}`);
  await page.screenshot({ path: path.join(artifacts, '01-delivery-new-ui.png'), fullPage: true });
  record(1, 'PASS', `${companyAreas} aree azienda; 0 campi piatti`);

  await addExisting(power.ragione_sociale, `azienda:${ownSite.id}`);
  await save();
  await openDelivery();
  assert(await companySection(power.ragione_sociale).getByText(ownSite.nome, { exact: true }).count() === 1, 'Sede aziendale non persistita a riapertura');
  record(2, 'PASS', `${power.ragione_sociale} -> ${ownSite.nome}, persistita`);

  await addExisting(maximercato.ragione_sociale, `ente:${entitySites[0].id}`);
  await save();
  let stored = await project();
  assert(deliveryFor(stored, maximercato.id).sedi.some((site) => site.sede_ente_location_id === entitySites[0].id), 'Sede ente non salvata');
  record(3, 'PASS', `${maximercato.ragione_sociale} -> ${entitySites[0].denominazione}`);

  await openDelivery();
  await addExisting(power.ragione_sociale, `ente:${entitySites[1].id}`);
  await save();
  stored = await project();
  assert(deliveryFor(stored, power.id).sedi.length === 2, 'Seconda sede della stessa azienda non salvata');
  record(4, 'PASS', `${power.ragione_sociale}: 2 sedi persistite`);

  await openDelivery();
  const martinelliSection = companySection(martinelli.ragione_sociale);
  await martinelliSection.getByRole('button', { name: '+ Nuova sede azienda', exact: true }).click();
  const uniqueName = `Aula Delivery UI ${Date.now()}`;
  await martinelliSection.getByPlaceholder('Denominazione').fill(uniqueName);
  await martinelliSection.getByPlaceholder('Indirizzo').fill('Via Roma 25');
  await martinelliSection.getByPlaceholder('Comune').fill('Napoli');
  await martinelliSection.getByPlaceholder('Provincia').fill('NA');
  await martinelliSection.getByPlaceholder('CAP').fill('80100');
  await martinelliSection.getByRole('button', { name: 'Crea e assegna', exact: true }).click();
  await martinelliSection.getByText(uniqueName, { exact: true }).waitFor();
  await save();
  stored = await project();
  const createdSite = deliveryFor(stored, martinelli.id).sedi.find((site) => site.denominazione === uniqueName);
  assert(createdSite, 'Sede creata al volo non salvata sul progetto');
  const martinelliRegistry = await getJson(`/api/v1/aziende-clienti/${martinelli.id}`);
  assert(martinelliRegistry.sedi_operative.some((site) => site.id === createdSite.sede_azienda_operativa_id), 'Sede creata non presente in anagrafica');
  record(5, 'PASS', `${uniqueName} creata in anagrafica e assegnata`);

  const validPayload = stored.aziende_delivery.flatMap((item) => item.sedi.map((site) => ({
    azienda_id: item.azienda_id,
    sede_tipo: site.sede_tipo,
    sede_id: site.sede_tipo === 'ente' ? site.sede_ente_location_id : site.sede_azienda_operativa_id,
  })));
  const wrongResponse = await api.put(`/api/v1/projects/${projectId}`, {
    data: {
      azienda_ids: stored.azienda_ids,
      azienda_sedi: [...validPayload, { azienda_id: maximercato.id, sede_tipo: 'azienda', sede_id: ownSite.id }],
    },
  });
  assert([400, 422].includes(wrongResponse.status()), `Sede estranea accettata: HTTP ${wrongResponse.status()}`);
  const wrongBody = await wrongResponse.json();
  assert(JSON.stringify(wrongBody).includes('non trovata per'), `Messaggio rifiuto non chiaro: ${JSON.stringify(wrongBody)}`);
  record(6, 'PASS', `HTTP ${wrongResponse.status()}: ${wrongBody.detail}`);

  const withoutMartinelli = stored.azienda_ids.filter((id) => id !== martinelli.id);
  const withoutMartinelliSites = validPayload.filter((item) => item.azienda_id !== martinelli.id);
  const removeResponse = await api.put(`/api/v1/projects/${projectId}`, { data: { azienda_ids: withoutMartinelli, azienda_sedi: withoutMartinelliSites } });
  assert(removeResponse.ok(), `Rimozione azienda fallita: ${removeResponse.status()} ${await removeResponse.text()}`);
  let removed = await project();
  assert(!removed.azienda_ids.includes(martinelli.id), 'Azienda non rimossa');
  assert(!removed.aziende_delivery.some((item) => item.azienda_id === martinelli.id), 'Sedi rimaste dopo rimozione azienda');
  const restoreResponse = await api.put(`/api/v1/projects/${projectId}`, {
    data: {
      azienda_ids: stored.azienda_ids,
      azienda_sedi: validPayload,
    },
  });
  assert(restoreResponse.ok(), `Ripristino azienda fallito: ${restoreResponse.status()} ${await restoreResponse.text()}`);
  record(7, 'PASS', 'Azienda e link sedi rimossi insieme; associazione ripristinata per non alterare il progetto finale');

  await context.close();
  const cleanContext = await browser.newContext({ viewport: { width: 375, height: 812 } });
  await cleanContext.addInitScript((accessToken) => localStorage.setItem('access_token', accessToken), token);
  const cleanPage = await cleanContext.newPage();
  await cleanPage.goto(`${baseUrl}/projects`, { waitUntil: 'networkidle' });
  const mobileCard = cleanPage.locator('.responsive-card').filter({ hasText: 'MAXI COMMUNICATION' });
  await mobileCard.getByRole('button', { name: 'Modifica', exact: true }).click();
  await cleanPage.locator('.wizard-step').filter({ hasText: 'Delivery' }).click();
  await cleanPage.getByText('Sede di erogazione per azienda', { exact: true }).waitFor();
  const horizontalOverflow = await cleanPage.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
  assert(!horizontalOverflow, 'Scroll orizzontale a 375px');
  assert(await cleanPage.locator('.delivery-company').count() === stored.azienda_ids.length, 'Interfaccia nuova non presente nel contesto pulito');
  await cleanPage.screenshot({ path: path.join(artifacts, '08-mobile-clean-context.png'), fullPage: true });
  record(8, 'PASS', 'Nuovo browser context, 375px, nuova UI e nessun overflow orizzontale');

  await cleanContext.close();
  await browser.close();
  await api.dispose();
  fs.writeFileSync(path.join(artifacts, 'report.json'), JSON.stringify({ projectId, results }, null, 2));
  process.stdout.write(`${JSON.stringify(results, null, 2)}\n`);
};

run().catch((error) => {
  fs.writeFileSync(path.join(artifacts, 'failure.txt'), `${error.stack || error}\n`);
  console.error(error);
  process.exit(1);
});
