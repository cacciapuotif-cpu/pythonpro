import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

import ResourceArchive from './ResourceArchive';
import {
  createAvviso,
  deleteAvviso,
  getAvvisi,
  getAvvisoDeletionImpact,
  getAvvisoRevisioni,
  ingestAvvisoRevision,
  permanentlyDeleteAvviso,
  retryAvvisoExtraction,
} from '../services/apiService';

jest.mock('../services/apiService', () => ({
  createAvviso: jest.fn(),
  deleteAvviso: jest.fn(),
  getAvvisi: jest.fn(),
  getAvvisoDeletionImpact: jest.fn(),
  getAvvisoRevisioni: jest.fn(),
  ingestAvvisoRevision: jest.fn(),
  permanentlyDeleteAvviso: jest.fn(),
  retryAvvisoExtraction: jest.fn(),
}));

const avviso = {
  id: 7,
  codice: '1/2026',
  ente_erogatore: 'FAPI',
  fondo: 'fapi',
  titolo: 'Avviso FAPI 1/2026',
  stato: 'bozza',
  is_active: true,
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
        stato_estrazione: 'completata',
        original_filename: 'avviso.md',
        created_at: '2026-07-17T12:00:00Z',
      },
      estrazione: { run_id: 33, status: 'completed', suggestions_count: 4, summary: {} },
    });
    getAvvisoRevisioni
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([{ id: 12, numero_revisione: 2, stato_estrazione: 'completata' }]);

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

  test('mostra la parzialità e rilancia soltanto le sezioni mancanti', async () => {
    const partial = {
      id: 12,
      avviso_id: 7,
      numero_revisione: 2,
      titolo: 'Avviso parziale',
      stato_estrazione: 'parziale',
      extraction_run_id: 33,
      created_at: '2026-07-17T12:00:00Z',
      extraction_progress: {
        sezioni_totali: 5,
        sezioni_processate: 4,
        sezioni_complete: 4,
        sezioni_mancanti: ['soggetti'],
        categorie_totali: 12,
        categorie_coperte_count: 9,
        categorie_mancanti: ['destinatari', 'beneficiari', 'aiuti_di_stato'],
        elementi_scartati: 0,
      },
    };
    getAvvisoRevisioni.mockResolvedValue([partial]);
    retryAvvisoExtraction.mockResolvedValue({
      revisione: {
        ...partial,
        stato_estrazione: 'completata',
        extraction_run_id: 34,
        extraction_progress: {
          ...partial.extraction_progress,
          sezioni_processate: 5,
          sezioni_complete: 5,
          sezioni_mancanti: [],
          categorie_coperte_count: 12,
          categorie_mancanti: [],
        },
      },
      estrazione: { run_id: 34, status: 'completed', suggestions_count: 2 },
    });

    render(<ResourceArchive currentUser={{ id: 1, role: 'admin' }} onReviewSuggestions={jest.fn()} />);

    expect(await screen.findByText(/estrazione parziale: 4\/5 sezioni.*9\/12 categorie/i)).toBeInTheDocument();
    expect(screen.getByText(/destinatari.*beneficiari.*aiuti_di_stato/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /riprova sezioni mancanti/i }));

    await waitFor(() => expect(retryAvvisoExtraction).toHaveBeenCalledWith(7, 12));
    expect(await screen.findByText(/estrazione completata: 5\/5 sezioni.*12\/12 categorie/i)).toBeInTheDocument();
  });

  test('disattiva un avviso solo dopo conferma e lo rimuove dalla lista operativa', async () => {
    deleteAvviso.mockResolvedValue({ message: 'Avviso disattivato con successo', id: 7 });
    const confirm = jest.spyOn(window, 'confirm').mockReturnValue(true);

    render(<ResourceArchive currentUser={{ id: 1, role: 'admin' }} onReviewSuggestions={jest.fn()} />);
    await screen.findByRole('heading', { name: 'Avviso FAPI 1/2026' });
    fireEvent.click(screen.getByRole('button', { name: /disattiva avviso/i }));

    await waitFor(() => expect(deleteAvviso).toHaveBeenCalledWith(7));
    expect(await screen.findByText(/storico è stato conservato/i)).toBeInTheDocument();
    expect(screen.getByText('Disattivato')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /già disattivato/i })).toBeDisabled();
    confirm.mockRestore();
  });

  test('admin carica anche gli avvisi disattivati, manager solo quelli attivi', async () => {
    const { unmount } = render(
      <ResourceArchive currentUser={{ id: 1, role: 'admin' }} onReviewSuggestions={jest.fn()} />,
    );
    await screen.findByRole('heading', { name: 'Avviso FAPI 1/2026' });
    expect(getAvvisi).toHaveBeenCalledWith({ active_only: false, limit: 1000 });
    unmount();

    jest.clearAllMocks();
    getAvvisi.mockResolvedValue([avviso]);
    getAvvisoRevisioni.mockResolvedValue([]);
    render(<ResourceArchive currentUser={{ id: 2, role: 'manager' }} onReviewSuggestions={jest.fn()} />);
    await screen.findByRole('heading', { name: 'Avviso FAPI 1/2026' });
    expect(getAvvisi).toHaveBeenCalledWith({ active_only: true, limit: 1000 });
  });

  test('elimina definitivamente solo dopo impatto e doppia conferma admin', async () => {
    const impact = {
      avviso_id: 7,
      codice: '1/2026',
      ente_erogatore: 'FAPI',
      titolo: 'Avviso FAPI 1/2026',
      confirmation_phrase: 'ELIMINA FAPI 1/2026',
      projects: [{ id: 4, label: 'Progetto collegato' }],
      financial_plans: [{ id: 9, label: 'Piano collegato' }],
      revision_filenames: ['avviso.md'],
      counts: {},
    };
    getAvvisoDeletionImpact.mockResolvedValue(impact);
    permanentlyDeleteAvviso.mockResolvedValue({
      detached_projects: 1,
      detached_financial_plans: 1,
      deleted_files: 1,
      file_delete_errors: [],
    });
    const confirm = jest.spyOn(window, 'confirm').mockReturnValue(true);
    const prompt = jest.spyOn(window, 'prompt').mockReturnValue(impact.confirmation_phrase);

    render(<ResourceArchive currentUser={{ id: 1, role: 'admin' }} onReviewSuggestions={jest.fn()} />);
    await screen.findByRole('heading', { name: 'Avviso FAPI 1/2026' });
    fireEvent.click(screen.getByRole('button', { name: /elimina definitivamente/i }));

    await waitFor(() => {
      expect(getAvvisoDeletionImpact).toHaveBeenCalledWith(7);
      expect(confirm).toHaveBeenCalledTimes(1);
    });
    expect(confirm.mock.calls[0][0]).toMatch(/Progetto #4: Progetto collegato/);
    expect(confirm.mock.calls[0][0]).toMatch(/Piano #9: Piano collegato/);
    expect(confirm.mock.calls[0][0]).toMatch(/avviso\.md/);
    await waitFor(() => {
      expect(permanentlyDeleteAvviso).toHaveBeenCalledWith(7, impact.confirmation_phrase);
    });
    expect(await screen.findByText(/eliminato definitivamente/i)).toBeInTheDocument();
    confirm.mockRestore();
    prompt.mockRestore();
  });

  test('manager non vede il comando di eliminazione definitiva', async () => {
    render(<ResourceArchive currentUser={{ id: 2, role: 'manager' }} onReviewSuggestions={jest.fn()} />);
    await screen.findByRole('heading', { name: 'Avviso FAPI 1/2026' });
    expect(screen.queryByRole('button', { name: /elimina definitivamente/i })).not.toBeInTheDocument();
  });
});
