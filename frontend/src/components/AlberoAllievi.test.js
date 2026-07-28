/**
 * UX-9 — allievi raggruppati per azienda, in lettura e in selezione.
 *
 * L'elenco piatto e' illeggibile appena i numeri crescono, e la selezione a
 * cascata e' il modo in cui l'operatore ragiona davvero: "di questa azienda
 * entrano tutti", poi le eccezioni. `Allievo.azienda_cliente_id` porta gia' il
 * raggruppamento, quindi non serve una seconda chiamata.
 */

import React from 'react';
import { fireEvent, render, screen, within } from '@testing-library/react';
import '@testing-library/jest-dom';

import AlberoAllievi, { raggruppaPerAzienda, SENZA_AZIENDA } from './AlberoAllievi';

const aziende = [
  { id: 10, ragione_sociale: 'Power Impianti srl' },
  { id: 11, ragione_sociale: 'Beta Spa' },
  { id: 12, ragione_sociale: 'Gamma Srl' },
];

const allievi = [
  { id: 1, nome: 'Ada', cognome: 'Rossi', azienda_cliente_id: 10 },
  { id: 2, nome: 'Bruno', cognome: 'Verdi', azienda_cliente_id: 10 },
  { id: 3, nome: 'Carla', cognome: 'Neri', azienda_cliente_id: 11 },
  { id: 4, nome: 'Dario', cognome: 'Blu', azienda_cliente_id: null },
];

describe('raggruppaPerAzienda', () => {
  test('ogni allievo finisce sotto la sua azienda', () => {
    const gruppi = raggruppaPerAzienda(aziende, allievi);
    const power = gruppi.find((g) => g.id === 10);
    expect(power.allievi.map((a) => a.id)).toEqual([1, 2]);
  });

  test('un azienda senza allievi resta visibile: e associabile lo stesso', () => {
    const gruppi = raggruppaPerAzienda(aziende, allievi);
    const gamma = gruppi.find((g) => g.id === 12);
    expect(gamma).toBeDefined();
    expect(gamma.allievi).toEqual([]);
  });

  test('gli allievi senza azienda non spariscono', () => {
    const gruppi = raggruppaPerAzienda(aziende, allievi);
    const orfani = gruppi.find((g) => g.id === SENZA_AZIENDA);
    expect(orfani.allievi.map((a) => a.id)).toEqual([4]);
  });

  test('un allievo con azienda sconosciuta finisce tra i senza azienda, non nel nulla', () => {
    const gruppi = raggruppaPerAzienda(aziende, [
      { id: 9, nome: 'Eva', cognome: 'Gialli', azienda_cliente_id: 999 },
    ]);
    expect(gruppi.find((g) => g.id === SENZA_AZIENDA).allievi.map((a) => a.id)).toEqual([9]);
  });

  test('il gruppo senza azienda non compare se non serve', () => {
    const gruppi = raggruppaPerAzienda(aziende, allievi.slice(0, 3));
    expect(gruppi.find((g) => g.id === SENZA_AZIENDA)).toBeUndefined();
  });
});

const renderAlbero = (props = {}) => {
  const onChange = jest.fn();
  const utils = render(
    <AlberoAllievi
      aziende={aziende}
      allievi={allievi}
      aziendeSelezionate={[]}
      allieviSelezionati={[]}
      onChange={onChange}
      {...props}
    />,
  );
  return { ...utils, onChange };
};

const gruppo = (nome) => screen.getByRole('group', { name: new RegExp(nome) });

describe('selezione a cascata', () => {
  test('spuntare l azienda seleziona lei e tutti i suoi allievi', () => {
    const { onChange } = renderAlbero();
    fireEvent.click(screen.getByRole('checkbox', { name: /Power Impianti srl/ }));

    expect(onChange).toHaveBeenCalledWith({ azienda_ids: [10], allievo_ids: [1, 2] });
  });

  test('togliere la spunta all azienda stacca anche i suoi allievi', () => {
    const { onChange } = renderAlbero({ aziendeSelezionate: [10], allieviSelezionati: [1, 2, 3] });
    fireEvent.click(screen.getByRole('checkbox', { name: /Power Impianti srl/ }));

    expect(onChange).toHaveBeenCalledWith({ azienda_ids: [], allievo_ids: [3] });
  });

  test('selezionare un allievo tira dentro la sua azienda', () => {
    const { onChange } = renderAlbero();
    fireEvent.click(screen.getByRole('checkbox', { name: 'Ada Rossi' }));

    expect(onChange).toHaveBeenCalledWith({ azienda_ids: [10], allievo_ids: [1] });
  });

  test('l ultimo allievo tolto non trascina fuori l azienda: puo restare da sola', () => {
    const { onChange } = renderAlbero({ aziendeSelezionate: [10], allieviSelezionati: [1] });
    fireEvent.click(screen.getByRole('checkbox', { name: 'Ada Rossi' }));

    expect(onChange).toHaveBeenCalledWith({ azienda_ids: [10], allievo_ids: [] });
  });

  test('un allievo senza azienda non inventa associazioni', () => {
    const { onChange } = renderAlbero();
    fireEvent.click(screen.getByRole('checkbox', { name: 'Dario Blu' }));

    expect(onChange).toHaveBeenCalledWith({ azienda_ids: [], allievo_ids: [4] });
  });

  test('la spunta dell azienda e parziale quando lo sono i suoi allievi', () => {
    renderAlbero({ aziendeSelezionate: [10], allieviSelezionati: [1] });
    const casella = screen.getByRole('checkbox', { name: /Power Impianti srl/ });

    expect(casella.indeterminate).toBe(true);
  });
});

describe('ricerca e leggibilita', () => {
  test('la ricerca filtra per nome e tiene il gruppo che lo contiene', () => {
    renderAlbero();
    fireEvent.change(screen.getByLabelText(/Cerca/), { target: { value: 'carla' } });

    expect(screen.getByText('Carla Neri')).toBeInTheDocument();
    expect(screen.queryByText('Ada Rossi')).not.toBeInTheDocument();
    expect(screen.queryByText(/Power Impianti srl/)).not.toBeInTheDocument();
  });

  test('la ricerca trova anche per ragione sociale, con tutti i suoi allievi', () => {
    renderAlbero();
    fireEvent.change(screen.getByLabelText(/Cerca/), { target: { value: 'power' } });

    expect(within(gruppo('Power Impianti srl')).getByText('Ada Rossi')).toBeInTheDocument();
    expect(screen.queryByText('Carla Neri')).not.toBeInTheDocument();
  });

  test('ogni azienda dichiara quanti dei suoi sono selezionati', () => {
    renderAlbero({ aziendeSelezionate: [10], allieviSelezionati: [1] });
    expect(screen.getByText(/1 di 2 allievi/)).toBeInTheDocument();
  });
});

describe('elenco troncato', () => {
  test('se la lista e parziale l albero lo dichiara invece di far finta di niente', () => {
    renderAlbero({ troncato: true });
    expect(screen.getByRole('status')).toHaveTextContent(/elenco parziale/i);
  });

  test('senza troncamento nessun avviso', () => {
    renderAlbero();
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });
});

describe('sola lettura', () => {
  test('senza onChange non ci sono caselle da spuntare', () => {
    render(
      <AlberoAllievi
        aziende={aziende}
        allievi={allievi}
        aziendeSelezionate={[10]}
        allieviSelezionati={[1]}
      />,
    );

    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
    expect(screen.getByText('Ada Rossi')).toBeInTheDocument();
  });

  test('in lettura mostra solo cio che e associato', () => {
    render(
      <AlberoAllievi
        aziende={aziende}
        allievi={allievi}
        aziendeSelezionate={[10]}
        allieviSelezionati={[1]}
      />,
    );

    expect(screen.getByText('Ada Rossi')).toBeInTheDocument();
    expect(screen.queryByText('Bruno Verdi')).not.toBeInTheDocument();
    expect(screen.queryByText(/Beta Spa/)).not.toBeInTheDocument();
  });

  test('l azione contestuale arriva dall esterno, una per riga', () => {
    render(
      <AlberoAllievi
        aziende={aziende}
        allievi={allievi}
        aziendeSelezionate={[10]}
        allieviSelezionati={[1]}
        renderAzioneAllievo={(allievo) => <button type="button">{`Stacca ${allievo.nome}`}</button>}
        renderAzioneAzienda={(azienda) => <button type="button">{`Stacca ${azienda.ragione_sociale}`}</button>}
      />,
    );

    expect(screen.getByRole('button', { name: 'Stacca Ada' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Stacca Power Impianti srl' })).toBeInTheDocument();
  });
});
