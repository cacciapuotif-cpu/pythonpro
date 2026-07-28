/**
 * UX-8 — dalla scheda progetto si stacca un associato, e il rifiuto del backend
 * si legge.
 *
 * Il backend risponde 409 con `detail.blocchi` (messaggi gia' in italiano) e
 * `detail.forzabile`. La forzatura e' un atto riservato: la propone solo un
 * admin, e solo quando OGNI blocco e' superabile. L'attestato emesso non lo e'
 * mai.
 */

import React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import '@testing-library/jest-dom';

import GestioneAssociati from './GestioneAssociati';
import {
  dissociaAllievoDaProgetto,
  dissociaAziendaDaProgetto,
} from '../services/apiService';

jest.mock('../services/apiService', () => ({
  dissociaAllievoDaProgetto: jest.fn(),
  dissociaAziendaDaProgetto: jest.fn(),
}));

const progetto = {
  id: 11,
  aziende_coinvolte: [
    { id: 5, ragione_sociale: 'Alfa Srl' },
    { id: 6, ragione_sociale: 'Beta Spa' },
  ],
  allievi_coinvolti: [
    { id: 1, nome: 'Ada', cognome: 'Rossi', azienda_cliente_id: 5 },
    { id: 2, nome: 'Bruno', cognome: 'Verdi', azienda_cliente_id: 6 },
  ],
};

const conflitto = (detail) => {
  const err = new Error('conflitto');
  err.response = { status: 409, data: { detail } };
  return err;
};

const bloccoAttestato = {
  errore: 'dissociazione_bloccata',
  entita: 'allievo',
  entita_id: 1,
  forzabile: false,
  blocchi: [{
    codice: 'attestato_emesso',
    messaggio: "L'attestato e' gia' stato emesso per questo allievo su questo progetto: la dissociazione non e' consentita.",
    forzabile: false,
  }],
};

const bloccoOre = {
  errore: 'dissociazione_bloccata',
  entita: 'allievo',
  entita_id: 1,
  forzabile: true,
  blocchi: [{
    codice: 'ore_frequentate',
    messaggio: "L'allievo ha 12 ore frequentate registrate su questo progetto.",
    forzabile: true,
  }],
};

const renderPannello = (props = {}) => render(
  <GestioneAssociati
    project={progetto}
    currentUser={{ role: 'admin' }}
    onChange={jest.fn()}
    {...props}
  />
);

const apriConferma = (nome) => {
  fireEvent.click(screen.getByRole('button', { name: `Stacca ${nome}` }));
};

beforeEach(() => {
  jest.clearAllMocks();
});

describe('elenco e permessi', () => {
  test('elenca aziende e allievi associati', () => {
    renderPannello();
    expect(screen.getByText('Alfa Srl')).toBeInTheDocument();
    expect(screen.getByText('Ada Rossi')).toBeInTheDocument();
  });

  test('UX-9: ogni allievo sta sotto la sua azienda, non in una lista piatta', () => {
    renderPannello();
    const alfa = screen.getByRole('group', { name: /Alfa Srl/ });

    expect(within(alfa).getByText('Ada Rossi')).toBeInTheDocument();
    expect(within(alfa).queryByText('Bruno Verdi')).not.toBeInTheDocument();
    expect(within(screen.getByRole('group', { name: /Beta Spa/ })).getByText('Bruno Verdi'))
      .toBeInTheDocument();
  });

  test('la consultazione vede l elenco ma nessun pulsante Stacca', () => {
    renderPannello({ currentUser: { role: 'consultazione' } });
    expect(screen.getByText('Ada Rossi')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^Stacca / })).not.toBeInTheDocument();
  });

  test('l operatore puo staccare', () => {
    renderPannello({ currentUser: { role: 'operatore' } });
    expect(screen.getByRole('button', { name: 'Stacca Ada Rossi' })).toBeInTheDocument();
  });
});

describe('dissociazione pulita', () => {
  test('l allievo si stacca dopo conferma e la scheda si ricarica', async () => {
    const onChange = jest.fn();
    dissociaAllievoDaProgetto.mockResolvedValue({ dissociato: true });
    renderPannello({ onChange });

    apriConferma('Ada Rossi');
    fireEvent.click(screen.getByRole('button', { name: 'Conferma dissociazione' }));

    await waitFor(() => expect(dissociaAllievoDaProgetto).toHaveBeenCalledWith(11, 1, undefined));
    await waitFor(() => expect(onChange).toHaveBeenCalled());
    expect(screen.queryByRole('button', { name: 'Conferma dissociazione' })).not.toBeInTheDocument();
  });

  test('annullare non chiama il backend', () => {
    renderPannello();
    apriConferma('Alfa Srl');
    fireEvent.click(screen.getByRole('button', { name: 'Annulla' }));

    expect(dissociaAziendaDaProgetto).not.toHaveBeenCalled();
    expect(screen.queryByRole('button', { name: 'Conferma dissociazione' })).not.toBeInTheDocument();
  });

  test('l azienda passa dal suo endpoint', async () => {
    dissociaAziendaDaProgetto.mockResolvedValue({ dissociato: true });
    renderPannello();

    apriConferma('Beta Spa');
    fireEvent.click(screen.getByRole('button', { name: 'Conferma dissociazione' }));

    await waitFor(() => expect(dissociaAziendaDaProgetto).toHaveBeenCalledWith(11, 6, undefined));
  });
});

describe('blocco non forzabile', () => {
  test('il messaggio del backend si legge e la forzatura non viene offerta', async () => {
    dissociaAllievoDaProgetto.mockRejectedValue(conflitto(bloccoAttestato));
    renderPannello();

    apriConferma('Ada Rossi');
    fireEvent.click(screen.getByRole('button', { name: 'Conferma dissociazione' }));

    expect(await screen.findByText(/L'attestato e' gia' stato emesso/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Forza/ })).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/Motivo/)).not.toBeInTheDocument();
  });
});

describe('blocco forzabile', () => {
  test('l admin puo forzare, ma solo con motivo di almeno 10 caratteri', async () => {
    dissociaAllievoDaProgetto.mockRejectedValueOnce(conflitto(bloccoOre));
    const onChange = jest.fn();
    renderPannello({ onChange });

    apriConferma('Ada Rossi');
    fireEvent.click(screen.getByRole('button', { name: 'Conferma dissociazione' }));

    expect(await screen.findByText(/12 ore frequentate/)).toBeInTheDocument();
    const forza = screen.getByRole('button', { name: 'Forza dissociazione' });
    expect(forza).toBeDisabled();

    fireEvent.change(screen.getByLabelText(/Motivo/), { target: { value: 'corto' } });
    expect(forza).toBeDisabled();

    dissociaAllievoDaProgetto.mockResolvedValueOnce({ dissociato: true, forzata: true });
    fireEvent.change(screen.getByLabelText(/Motivo/), {
      target: { value: 'Iscrizione errata, ore da annullare' },
    });
    expect(forza).toBeEnabled();
    fireEvent.click(forza);

    await waitFor(() => expect(dissociaAllievoDaProgetto).toHaveBeenLastCalledWith(11, 1, {
      forza: true,
      motivo: 'Iscrizione errata, ore da annullare',
    }));
    await waitFor(() => expect(onChange).toHaveBeenCalled());
  });

  test('all operatore la forzatura non viene offerta nemmeno se il blocco e forzabile', async () => {
    dissociaAllievoDaProgetto.mockRejectedValue(conflitto(bloccoOre));
    renderPannello({ currentUser: { role: 'operatore' } });

    apriConferma('Ada Rossi');
    fireEvent.click(screen.getByRole('button', { name: 'Conferma dissociazione' }));

    expect(await screen.findByText(/12 ore frequentate/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Forza/ })).not.toBeInTheDocument();
    expect(screen.getByText(/solo un amministratore/i)).toBeInTheDocument();
  });

  test('un errore non 409 non offre la forzatura', async () => {
    const err = new Error('boom');
    err.response = { status: 500, data: { detail: 'Errore interno' } };
    dissociaAllievoDaProgetto.mockRejectedValue(err);
    renderPannello();

    apriConferma('Ada Rossi');
    fireEvent.click(screen.getByRole('button', { name: 'Conferma dissociazione' }));

    expect(await screen.findByRole('alert')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Forza/ })).not.toBeInTheDocument();
  });
});
