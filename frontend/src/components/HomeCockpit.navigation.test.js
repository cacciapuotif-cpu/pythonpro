import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import HomeCockpit from './HomeCockpit';
import { http } from '../lib/http';

jest.mock('../lib/http', () => ({
  http: { get: jest.fn() },
}));

const response = {
  stats: {
    pratiche_aperte: 7,
    progetti_attivi: 4,
    agenti_attivi: 2,
    scadenze_7gg: 3,
  },
  decisioni: [
    {
      id: 11, tipo: 'agente', categoria: 'comunicazione', priorita: 'alta',
      titolo: 'Proposta agente', descrizione: 'Da revisionare', entita_id: 5,
      azione_url: '/api/v1/agent-suggestions/11/approve',
    },
    {
      id: 22, tipo: 'documento', categoria: 'documento', priorita: 'alta',
      titolo: 'Documento caricato', descrizione: 'Da validare', entita_id: 6,
      azione_url: '/api/v1/documenti-richiesti/22/valida',
    },
    {
      id: 33, tipo: 'progetto', categoria: 'progetto', priorita: 'media',
      titolo: 'Progetto oltre termine', descrizione: 'Da controllare', entita_id: 7,
    },
    {
      id: 44, tipo: 'regime_aiuto', categoria: 'compliance', priorita: 'media',
      titolo: 'Regime non definito', descrizione: 'Da completare', entita_id: 8,
    },
  ],
};

let openSpy;

beforeEach(() => {
  http.get.mockResolvedValue({ data: response });
  openSpy = jest.spyOn(window, 'open').mockImplementation(() => null);
});

afterEach(() => {
  openSpy.mockRestore();
  jest.clearAllMocks();
});

test.each([
  ['Pratiche aperte', { section: 'documenti-mancanti', filters: { status: 'open' } }],
  ['Progetti attivi', { section: 'projects', filters: { status: 'active' } }],
  ['Agenti attivi', { section: 'agents-dashboard', filters: { runStatus: 'running' } }],
  ['Scadenze 7gg', { section: 'projects', filters: { status: 'deadline-7-days' } }],
])('il contatore %s naviga con il filtro corretto', async (label, destination) => {
  const onNavigate = jest.fn();
  render(<HomeCockpit currentUser={{ role: 'admin' }} onNavigate={onNavigate} />);
  await screen.findByText('Proposta agente');
  const card = screen.getByRole('button', { name: new RegExp(label, 'i') });

  fireEvent.click(card);

  expect(onNavigate).toHaveBeenCalledWith(destination);
});

test.each([
  ['Proposta agente', { section: 'agents-review', filters: { status: 'pending', suggestionId: 11 } }],
  ['Documento caricato', { section: 'documenti-mancanti', filters: { status: 'uploaded', documentId: 22, collaboratorId: 6 } }],
  ['Progetto oltre termine', { section: 'projects', filters: { status: 'attention', projectId: 7 } }],
  ['Regime non definito', { section: 'projects', filters: { status: 'attention', projectId: 8, focus: 'compliance' } }],
])('Gestisci su %s apre la pagina gestionale pertinente', async (title, destination) => {
  const onNavigate = jest.fn();
  render(<HomeCockpit currentUser={{ role: 'admin' }} onNavigate={onNavigate} />);
  const heading = await screen.findByText(title);
  const card = heading.closest('[data-testid="cockpit-decision"]');
  fireEvent.click(card.querySelector('button'));

  await waitFor(() => expect(onNavigate).toHaveBeenCalledWith(destination));
  expect(openSpy).not.toHaveBeenCalled();
});

test('carica le decisioni tramite il client HTTP autenticato condiviso', async () => {
  render(<HomeCockpit currentUser={{ role: 'consultazione' }} />);

  await screen.findByText('Proposta agente');
  expect(http.get).toHaveBeenCalledWith('/cockpit/decisioni');
});

test('usa il nome completo aggiornato nel saluto della Home', async () => {
  render(<HomeCockpit currentUser={{ role: 'operatore', username: 'mario', full_name: 'Mario Rossi' }} />);

  expect(await screen.findByText('Buongiorno Mario Rossi')).toBeInTheDocument();
});
