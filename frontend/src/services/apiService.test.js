import { http } from '../lib/http';
import { ingestAvvisoRevision, permanentlyDeleteAvviso, healthCheck } from './apiService';

jest.mock('../lib/http', () => ({
  apiRootUrl: '',
  http: {
    delete: jest.fn(),
    post: jest.fn(),
    get: jest.fn(),
  },
}));

describe('ingestAvvisoRevision', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    http.post.mockResolvedValue({ data: { revisione: { id: 12 } } });
    http.delete.mockResolvedValue({ data: { id: 1 } });
  });

  test('invia file e metadati come multipart/form-data', async () => {
    const file = new File(['# Avviso\nTesto'], 'avviso.md', { type: 'text/markdown' });

    await ingestAvvisoRevision(1, {
      file,
      titolo: 'Formazienda 2/2022',
      etichettaRevisione: 'ultima revisione',
      eseguiEstrazione: true,
    });

    expect(http.post).toHaveBeenCalledWith(
      '/avvisi/1/revisioni/ingest',
      expect.any(FormData),
      expect.objectContaining({
        timeout: 180000,
        headers: { 'Content-Type': 'multipart/form-data' },
      }),
    );
    const body = http.post.mock.calls[0][1];
    expect(body.get('file')).toBe(file);
    expect(body.get('titolo')).toBe('Formazienda 2/2022');
    expect(body.get('etichetta_revisione')).toBe('ultima revisione');
    expect(body.get('esegui_estrazione')).toBe('true');
  });

  test('invia la frase esatta e la conferma collegamenti per hard delete', async () => {
    await permanentlyDeleteAvviso(1, 'ELIMINA FORMAZIENDA 2/2025');

    expect(http.delete).toHaveBeenCalledWith('/avvisi/1/permanent', {
      data: {
        confirmation_phrase: 'ELIMINA FORMAZIENDA 2/2025',
        linked_records_confirmed: true,
      },
    });
  });
});

describe('healthCheck (NEW-020: portabilità same-origin)', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    http.get.mockResolvedValue({ data: { status: 'ok' } });
  });

  test('same-origin (apiRootUrl vuoto): colpisce /health forzando baseURL, NON /api/v1/health', async () => {
    // apiRootUrl è mockato a '' → il baseURL per-request svincola la richiesta
    // dal prefisso /api/v1 dell'istanza axios.
    await healthCheck();

    expect(http.get).toHaveBeenCalledTimes(1);
    const [url, config] = http.get.mock.calls[0];
    expect(url).toBe('/health');
    expect(url).not.toBe('/api/v1/health');
    expect(config).toEqual({ baseURL: '' });
  });
});

describe('healthCheck (NEW-020: scenario LAN)', () => {
  test('LAN (apiRootUrl assoluto): colpisce http://IP:8001/health', async () => {
    jest.resetModules();
    jest.doMock('../lib/http', () => ({
      apiRootUrl: 'http://192.168.1.50:8001',
      http: {
        delete: jest.fn(),
        post: jest.fn(),
        get: jest.fn().mockResolvedValue({ data: { status: 'ok' } }),
      },
    }));

    // eslint-disable-next-line global-require
    const lanHttp = require('../lib/http').http;
    // eslint-disable-next-line global-require
    const { healthCheck: lanHealthCheck } = require('./apiService');

    await lanHealthCheck();

    expect(lanHttp.get).toHaveBeenCalledTimes(1);
    const [url, config] = lanHttp.get.mock.calls[0];
    expect(url).toBe('/health');
    expect(config).toEqual({ baseURL: 'http://192.168.1.50:8001' });

    jest.dontMock('../lib/http');
    jest.resetModules();
  });
});
