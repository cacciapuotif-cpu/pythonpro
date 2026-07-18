import { http } from '../lib/http';
import { ingestAvvisoRevision } from './apiService';

jest.mock('../lib/http', () => ({
  apiRootUrl: '',
  http: {
    post: jest.fn(),
  },
}));

describe('ingestAvvisoRevision', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    http.post.mockResolvedValue({ data: { revisione: { id: 12 } } });
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
});
