import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

import ResourceArchive from './ResourceArchive';
import {
  createAvviso,
  getAvvisi,
  getAvvisoRevisioni,
  ingestAvvisoRevision,
} from '../services/apiService';

jest.mock('../services/apiService', () => ({
  createAvviso: jest.fn(),
  getAvvisi: jest.fn(),
  getAvvisoRevisioni: jest.fn(),
  ingestAvvisoRevision: jest.fn(),
}));

const avviso = {
  id: 7,
  codice: '1/2026',
  ente_erogatore: 'FAPI',
  fondo: 'fapi',
  titolo: 'Avviso FAPI 1/2026',
  stato: 'bozza',
};

describe('ResourceArchive', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    getAvvisi.mockResolvedValue([avviso]);
    getAvvisoRevisioni.mockResolvedValue([]);
  });

  test('mostra gli avvisi e spiega il workflow di validazione umana', async () => {
    render(<ResourceArchive currentUser={{ id: 1, role: 'admin' }} onReviewSuggestions={jest.fn()} />);

    expect(await screen.findByRole('heading', { name: 'Avviso FAPI 1/2026' })).toBeInTheDocument();
    expect(screen.getByText(/regole e scadenze diventano operative solo dopo validazione umana/i)).toBeInTheDocument();
    await waitFor(() => expect(getAvvisoRevisioni).toHaveBeenCalledWith(7));
    expect(await screen.findByText('Nessuna revisione caricata.')).toBeInTheDocument();
  });

  test('carica un markdown come nuova revisione ed espone il passaggio alla review', async () => {
    const onReviewSuggestions = jest.fn();
    ingestAvvisoRevision.mockResolvedValue({
      revisione: {
        id: 12,
        numero_revisione: 2,
        titolo: 'Avviso FAPI aggiornato',
        stato_estrazione: 'estratto',
        original_filename: 'avviso.md',
        created_at: '2026-07-17T12:00:00Z',
      },
      estrazione: { run_id: 33, status: 'completed', suggestions_count: 4, summary: {} },
    });
    getAvvisoRevisioni
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([{ id: 12, numero_revisione: 2, stato_estrazione: 'estratto' }]);

    render(<ResourceArchive currentUser={{ id: 1, role: 'admin' }} onReviewSuggestions={onReviewSuggestions} />);
    await screen.findByRole('heading', { name: 'Avviso FAPI 1/2026' });

    const file = new File(['# Art. 1\nMassimale 50.000 euro.'], 'avviso.md', { type: 'text/markdown' });
    fireEvent.change(screen.getByLabelText(/file markdown/i), { target: { files: [file] } });
    fireEvent.change(screen.getByLabelText(/titolo revisione/i), { target: { value: 'Avviso FAPI aggiornato' } });
    fireEvent.click(screen.getByRole('button', { name: /analizza e crea proposte/i }));

    await waitFor(() => {
      expect(ingestAvvisoRevision).toHaveBeenCalledWith(7, expect.objectContaining({
        file,
        titolo: 'Avviso FAPI aggiornato',
        eseguiEstrazione: true,
      }));
    });
    expect(await screen.findByText(/4 proposte create/i)).toBeInTheDocument();

    const reviewButtons = screen.getAllByRole('button', { name: /vai alla revisione umana/i });
    fireEvent.click(reviewButtons[reviewButtons.length - 1]);
    expect(onReviewSuggestions).toHaveBeenCalled();
  });

  test('crea una nuova identità avviso prima dell’upload', async () => {
    createAvviso.mockResolvedValue({ ...avviso, id: 8, codice: '2/2026', titolo: 'Nuovo avviso' });
    getAvvisoRevisioni.mockResolvedValue([]);

    render(<ResourceArchive currentUser={{ id: 1, role: 'admin' }} onReviewSuggestions={jest.fn()} />);
    await screen.findByRole('heading', { name: 'Avviso FAPI 1/2026' });

    fireEvent.click(screen.getByRole('button', { name: /nuovo avviso/i }));
    fireEvent.change(screen.getByLabelText(/^codice avviso/i), { target: { value: '2/2026' } });
    fireEvent.change(screen.getByLabelText(/^ente erogatore/i), { target: { value: 'FAPI' } });
    fireEvent.change(screen.getByLabelText(/^titolo avviso/i), { target: { value: 'Nuovo avviso' } });
    fireEvent.click(screen.getByRole('button', { name: /crea avviso/i }));

    await waitFor(() => expect(createAvviso).toHaveBeenCalledWith(expect.objectContaining({
      codice: '2/2026',
      ente_erogatore: 'FAPI',
      titolo: 'Nuovo avviso',
    })));
    expect(await screen.findByText(/avviso creato/i)).toBeInTheDocument();
  });
});
