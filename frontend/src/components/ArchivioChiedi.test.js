import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

import ArchivioChiedi from './ArchivioChiedi';
import { getAvvisi, searchArchivio, chiediArchivio } from '../services/apiService';

jest.mock('../services/apiService', () => ({
  getAvvisi: jest.fn(),
  searchArchivio: jest.fn(),
  chiediArchivio: jest.fn(),
}));

const avviso = {
  id: 7,
  codice: '1/2026',
  ente_erogatore: 'FAPI',
  fondo: 'fapi',
  titolo: 'Avviso FAPI 1/2026',
  is_active: true,
};

const risultato = {
  fonte: 'regola',
  avviso_id: 7,
  avviso_titolo: 'Avviso FAPI 1/2026',
  revisione_id: 3,
  regola_id: 42,
  conoscenza_id: null,
  esito_id: null,
  riferimento_articolo: 'Art. 5 comma 2',
  estratto: 'Il massimale per impresa è di 50.000 euro.',
  rank: 0.9,
};

const ADMIN = { id: 1, role: 'admin' };

describe('ArchivioChiedi', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    getAvvisi.mockResolvedValue([avviso]);
    searchArchivio.mockResolvedValue([]);
    chiediArchivio.mockResolvedValue({ stato: 'non_presente', risposta: null, citazioni: [], risultati: [] });
  });

  test('il disclaimer di responsabilità è sempre visibile', async () => {
    render(<ArchivioChiedi currentUser={ADMIN} onOpenAvviso={jest.fn()} />);
    expect(
      await screen.findByText(/Risposta assistita: fa fede il testo dell/i),
    ).toBeInTheDocument();
  });

  test('la ricerca pura renderizza i risultati con estratto, fonte e riferimento', async () => {
    searchArchivio.mockResolvedValue([risultato]);

    render(<ArchivioChiedi currentUser={ADMIN} onOpenAvviso={jest.fn()} />);
    await screen.findByRole('tab', { name: 'Cerca' });

    fireEvent.click(screen.getByRole('tab', { name: 'Cerca' }));
    fireEvent.change(screen.getByLabelText(/testo da cercare/i), { target: { value: 'massimale' } });
    fireEvent.click(screen.getByRole('button', { name: /avvia ricerca/i }));

    await waitFor(() => expect(searchArchivio).toHaveBeenCalledWith('massimale', expect.any(Object)));
    expect(await screen.findByText(/Il massimale per impresa è di 50.000 euro./i)).toBeInTheDocument();
    expect(screen.getByText(/Art\. 5 comma 2/)).toBeInTheDocument();
    expect(screen.getByText('Avviso FAPI 1/2026', { selector: '.archivio-cite-title' })).toBeInTheDocument();
  });

  test('la risposta "chiedi" mostra il testo e le citazioni in evidenza', async () => {
    chiediArchivio.mockResolvedValue({
      stato: 'ok',
      risposta: 'Il massimale per impresa è 50.000 euro secondo l\'Art. 5.',
      citazioni: [risultato],
      risultati: [risultato],
    });

    render(<ArchivioChiedi currentUser={ADMIN} onOpenAvviso={jest.fn()} />);
    await screen.findByLabelText(/domanda/i);

    fireEvent.change(screen.getByLabelText(/domanda/i), { target: { value: 'Qual è il massimale?' } });
    fireEvent.click(screen.getByRole('button', { name: /invia domanda/i }));

    await waitFor(() => expect(chiediArchivio).toHaveBeenCalledWith(
      expect.objectContaining({ domanda: 'Qual è il massimale?' }),
    ));
    expect(await screen.findByText(/Il massimale per impresa è 50.000 euro secondo/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Art\. 5 comma 2/ })).toBeInTheDocument();
  });

  test('cliccando una citazione naviga alla vista avviso corrispondente', async () => {
    const onOpenAvviso = jest.fn();
    chiediArchivio.mockResolvedValue({
      stato: 'ok',
      risposta: 'Risposta con fonte.',
      citazioni: [risultato],
      risultati: [risultato],
    });

    render(<ArchivioChiedi currentUser={ADMIN} onOpenAvviso={onOpenAvviso} />);
    await screen.findByLabelText(/domanda/i);

    fireEvent.change(screen.getByLabelText(/domanda/i), { target: { value: 'Qual è il massimale?' } });
    fireEvent.click(screen.getByRole('button', { name: /invia domanda/i }));

    const citazione = await screen.findByRole('button', { name: /Art\. 5 comma 2/ });
    fireEvent.click(citazione);

    expect(onOpenAvviso).toHaveBeenCalledWith(7, expect.objectContaining({
      revisioneId: 3,
      regolaId: 42,
      riferimentoArticolo: 'Art. 5 comma 2',
    }));
  });

  test('lo stato degradato è visibile e mostra comunque i risultati di ricerca', async () => {
    chiediArchivio.mockResolvedValue({
      stato: 'degradato',
      risposta: null,
      citazioni: [],
      risultati: [risultato],
    });

    render(<ArchivioChiedi currentUser={ADMIN} onOpenAvviso={jest.fn()} />);
    await screen.findByLabelText(/domanda/i);

    fireEvent.change(screen.getByLabelText(/domanda/i), { target: { value: 'Domanda qualsiasi' } });
    fireEvent.click(screen.getByRole('button', { name: /invia domanda/i }));

    expect(await screen.findByText(/AI non disponibile — risultati di sola ricerca/i)).toBeInTheDocument();
    expect(screen.getByText(/Il massimale per impresa è di 50.000 euro./i)).toBeInTheDocument();
  });

  test('lo stato non_presente è esplicito', async () => {
    chiediArchivio.mockResolvedValue({
      stato: 'non_presente',
      risposta: null,
      citazioni: [],
      risultati: [],
    });

    render(<ArchivioChiedi currentUser={ADMIN} onOpenAvviso={jest.fn()} />);
    await screen.findByLabelText(/domanda/i);

    fireEvent.change(screen.getByLabelText(/domanda/i), { target: { value: 'Domanda senza risposta' } });
    fireEvent.click(screen.getByRole('button', { name: /invia domanda/i }));

    expect(await screen.findByText(/Non presente in archivio/i)).toBeInTheDocument();
  });

  test('mostra un errore di rete leggibile', async () => {
    chiediArchivio.mockRejectedValue(new Error('boom'));

    render(<ArchivioChiedi currentUser={ADMIN} onOpenAvviso={jest.fn()} />);
    await screen.findByLabelText(/domanda/i);

    fireEvent.change(screen.getByLabelText(/domanda/i), { target: { value: 'Domanda' } });
    fireEvent.click(screen.getByRole('button', { name: /invia domanda/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/non riuscita|errore/i);
  });
});
