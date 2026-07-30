import { http } from '../lib/http';
import apiService, {
  ingestAvvisoRevision,
  permanentlyDeleteAvviso,
  healthCheck,
  caricaTuttiGliAllievi,
} from './apiService';

jest.mock('../lib/http', () => ({
  apiRootUrl: '',
  http: {
    delete: jest.fn(),
    post: jest.fn(),
    get: jest.fn(),
    patch: jest.fn(),
  },
}));

describe('area personale', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('aggiorna il solo profilo corrente', async () => {
    const profile = { full_name: 'Mario Rossi', email: 'mario@example.com' };
    http.patch.mockResolvedValue({ data: { id: 7, username: 'mario', ...profile } });

    const result = await apiService.updateCurrentUser(profile);

    expect(http.patch).toHaveBeenCalledWith('/auth/me', profile);
    expect(result.full_name).toBe('Mario Rossi');
  });

  test('invia il cambio password all endpoint autenticato', async () => {
    const payload = {
      current_password: 'CurrentPass123!',
      new_password: 'NewPassword456!',
      confirm_password: 'NewPassword456!',
    };
    http.post.mockResolvedValue({ data: { status: 'password_changed' } });

    const result = await apiService.changePassword(payload);

    expect(http.post).toHaveBeenCalledWith('/auth/change-password', payload);
    expect(result.status).toBe('password_changed');
  });

  test('carica la foto profilo come multipart autenticato', async () => {
    const file = new File(['avatar'], 'avatar.png', { type: 'image/png' });
    http.post.mockResolvedValue({ data: { id: 7, has_avatar: true } });

    const result = await apiService.uploadCurrentUserAvatar(file);

    expect(http.post).toHaveBeenCalledWith(
      '/auth/me/avatar',
      expect.any(FormData),
      { headers: { 'Content-Type': 'multipart/form-data' } },
    );
    expect(http.post.mock.calls[0][1].get('file')).toBe(file);
    expect(result.has_avatar).toBe(true);
  });

  test('richiede e consuma il recupero password sugli endpoint pubblici', async () => {
    http.post
      .mockResolvedValueOnce({ data: { status: 'accepted' } })
      .mockResolvedValueOnce({ data: { status: 'password_reset' } });
    const resetPayload = {
      token: 'reset-token',
      new_password: 'RecoveredPassword789!',
      confirm_password: 'RecoveredPassword789!',
    };

    await apiService.requestPasswordReset('mario@example.com');
    await apiService.resetPassword(resetPayload);

    expect(http.post).toHaveBeenNthCalledWith(
      1,
      '/auth/forgot-password',
      { email: 'mario@example.com' },
    );
    expect(http.post).toHaveBeenNthCalledWith(
      2,
      '/auth/reset-password',
      resetPayload,
    );
  });
});

describe('generazione contratto con sede e conto dell ente', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    http.get.mockResolvedValue({ data: new Blob(['pdf']) });
  });

  test('trasmette le selezioni esplicite al backend', async () => {
    await apiService.downloadAssignmentContract(9, {
      sedeId: 3,
      contoCorrenteId: 4,
    });

    expect(http.get).toHaveBeenCalledWith('/assignments/9/contract', {
      params: {
        sede_id: 3,
        conto_corrente_id: 4,
      },
      responseType: 'blob',
    });
  });
});

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

describe('caricaTuttiGliAllievi (UX-9)', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('segue le pagine finche has_next e restituisce l elenco intero', async () => {
    http.get
      .mockResolvedValueOnce({ data: { items: [{ id: 1 }, { id: 2 }], has_next: true, total: 3 } })
      .mockResolvedValueOnce({ data: { items: [{ id: 3 }], has_next: false, total: 3 } });

    const esito = await caricaTuttiGliAllievi();

    expect(esito.items.map((a) => a.id)).toEqual([1, 2, 3]);
    expect(esito.troncato).toBe(false);
    expect(http.get).toHaveBeenCalledTimes(2);
    expect(http.get.mock.calls[1][1].params.page).toBe(2);
  });

  test('si ferma al tetto di pagine e lo dichiara invece di mentire', async () => {
    http.get.mockResolvedValue({ data: { items: [{ id: 1 }], has_next: true, total: 9999 } });

    const esito = await caricaTuttiGliAllievi({ maxPagine: 3 });

    expect(http.get).toHaveBeenCalledTimes(3);
    expect(esito.troncato).toBe(true);
    expect(esito.items).toHaveLength(3);
  });

  test('una risposta senza paginazione non manda in loop', async () => {
    http.get.mockResolvedValue({ data: [{ id: 7 }] });

    const esito = await caricaTuttiGliAllievi();

    expect(http.get).toHaveBeenCalledTimes(1);
    expect(esito.items.map((a) => a.id)).toEqual([7]);
    expect(esito.troncato).toBe(false);
  });
});
