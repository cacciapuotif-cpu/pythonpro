import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import PortaleAllievi from './PortaleAllievi';

jest.mock('../lib/http', () => ({ apiRootUrl: 'http://backend.test' }));

beforeEach(() => {
  global.fetch = jest.fn();
});

afterEach(() => {
  jest.restoreAllMocks();
  window.history.replaceState({}, '', '/');
});

test('magic token valido apre il portale pubblico senza autenticazione ERP', async () => {
  window.history.replaceState({}, '', '/portale-allievi?token=magic-valido');
  global.fetch.mockResolvedValue({
    ok: true,
    json: async () => ({
      allievo: { nome: 'Ada', cognome: 'Lovelace', email: 'ada@example.test' },
      progetti: [{
        project_id: 7,
        project_name: 'Corso Python',
        ente_erogatore: 'FAPI',
        avviso: '1/2026',
        ore_frequentate: 12,
        ore_totali: 20,
        percentuale_frequenza: 60,
        attestato_disponibile: false,
      }],
    }),
  });

  render(<PortaleAllievi />);

  expect(await screen.findByText('Ada Lovelace')).toBeInTheDocument();
  expect(screen.getByText('Corso Python')).toBeInTheDocument();
  expect(global.fetch).toHaveBeenCalledWith(
    'http://backend.test/api/v1/portale-allievi/profilo?token=magic-valido',
  );
});

test('senza token mostra un errore del portale e non il login ERP', async () => {
  window.history.replaceState({}, '', '/portale-allievi');

  render(<PortaleAllievi />);

  expect(await screen.findByText(/link non valido.*nuovo link/i)).toBeInTheDocument();
  expect(screen.queryByText(/accesso al gestionale/i)).not.toBeInTheDocument();
  expect(global.fetch).not.toHaveBeenCalled();
});
