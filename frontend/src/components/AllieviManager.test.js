import React, { act } from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

import AllieviManager from './AllieviManager';
import {
  getAllievi,
  getAllievo,
  getAziendeClienti,
  getProjects,
  updateAllievo,
} from '../services/apiService';

jest.mock('../services/apiService', () => ({
  getAllievi: jest.fn(),
  getAllievo: jest.fn(),
  createAllievo: jest.fn(),
  updateAllievo: jest.fn(),
  deleteAllievo: jest.fn(),
  getAziendeClienti: jest.fn(),
  getProjects: jest.fn(),
  bulkImportAllievi: jest.fn(),
}));

jest.mock('../auth/permissions', () => ({
  canPerform: () => true,
}));

const caruso = {
  id: 4,
  nome: 'GIOVANNI',
  cognome: 'CARUSO',
  occupato: true,
  azienda_cliente_id: 10,
  azienda_sede_operativa_id: null,
  azienda_cliente: {
    id: 10,
    ragione_sociale: 'Power Impianti srl',
  },
  project_ids: [12, 11],
  projects: [
    {
      id: 12,
      name: 'MAXI COMMUNICATION',
      status: 'cancelled',
      is_active: false,
    },
    {
      id: 11,
      name: 'MAXI COMMUNICATION',
      status: 'active',
      is_active: true,
    },
  ],
};

beforeEach(() => {
  jest.clearAllMocks();
  getAllievi.mockResolvedValue({
    items: [caruso],
    total: 1,
    pages: 1,
  });
  getAllievo.mockResolvedValue(caruso);
  getAziendeClienti.mockResolvedValue({
    items: [
      { id: 10, ragione_sociale: 'Power Impianti srl', project_ids: [11, 12, 13] },
      { id: 20, ragione_sociale: 'Nuova Azienda srl', project_ids: [20] },
    ],
  });
  getProjects.mockResolvedValue({
    items: [
      { id: 11, name: 'MAXI COMMUNICATION', status: 'active', is_active: true },
      { id: 13, name: 'Progetto Power nuovo', status: 'active', is_active: true },
      { id: 20, name: 'Nuovo progetto', status: 'active', is_active: true },
    ],
  });
  updateAllievo.mockResolvedValue({ ...caruso, azienda_cliente_id: 20 });
});

test('mostra azienda corrente e tutti i progetti, incluso lo storico', async () => {
  render(<AllieviManager currentUser={{ role: 'admin' }} />);

  expect(await screen.findByText('Power Impianti srl')).toBeInTheDocument();
  expect(screen.getByText('Azienda attuale')).toBeInTheDocument();
  expect(screen.getAllByText(/#11 · Attivo/i).length).toBeGreaterThan(0);
  expect(screen.getAllByText(/#12 · Cancellato · storico/i).length).toBeGreaterThan(0);
});

test('su mobile accumula la seconda pagina senza duplicare la prima', async () => {
  document.documentElement.style.setProperty('--breakpoint-mobile-max', '48rem');
  const previousMatchMedia = window.matchMedia;
  window.matchMedia = jest.fn().mockReturnValue({
    matches: true,
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
  });
  getAllievi
    .mockResolvedValueOnce({ items: [caruso], total: 2, pages: 2 })
    .mockResolvedValueOnce({
      items: [{ ...caruso, id: 5, nome: 'ADA', cognome: 'LOVELACE' }],
      total: 2,
      pages: 2,
    });

  const { unmount } = render(<AllieviManager currentUser={{ role: 'admin' }} />);
  expect(await screen.findByText('CARUSO GIOVANNI')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Carica altri' }));

  expect(await screen.findByText('LOVELACE ADA')).toBeInTheDocument();
  expect(screen.getByText('CARUSO GIOVANNI')).toBeInTheDocument();
  expect(document.querySelectorAll('[data-responsive-list="students"] [data-entity-id]')).toHaveLength(2);

  unmount();
  window.matchMedia = previousMatchMedia;
  document.documentElement.style.removeProperty('--breakpoint-mobile-max');
});

test('cambiare azienda conserva tutti i progetti gia frequentati', async () => {
  render(<AllieviManager currentUser={{ role: 'admin' }} />);
  const editButton = await screen.findByRole('button', { name: 'Modifica' });
  await act(async () => {
    fireEvent.click(editButton);
  });
  await screen.findByRole('heading', { name: 'Modifica Allievo' });

  const companySelect = screen.getAllByRole('combobox')
    .find((element) => element.value === '10');
  expect(companySelect).toBeDefined();
  fireEvent.change(companySelect, { target: { value: '20' } });

  expect(screen.getAllByText(/#11 · Attivo/i).length).toBeGreaterThan(0);
  expect(screen.getAllByText(/#12 · Cancellato · storico/i).length).toBeGreaterThan(0);

  fireEvent.click(screen.getByRole('button', { name: 'Salva' }));
  await waitFor(() => expect(updateAllievo).toHaveBeenCalled());
  expect(updateAllievo.mock.calls[0][1]).toEqual(expect.objectContaining({
    azienda_cliente_id: 20,
    project_ids: [12, 11],
  }));
});

test('cambiare azienda scarta un progetto nuovo non ancora salvato', async () => {
  render(<AllieviManager currentUser={{ role: 'admin' }} />);
  const editButton = await screen.findByRole('button', { name: 'Modifica' });
  await act(async () => {
    fireEvent.click(editButton);
  });
  await screen.findByRole('heading', { name: 'Modifica Allievo' });

  const projectSelect = screen.getAllByRole('combobox')
    .find((element) => Array.from(element.options)
      .some((option) => option.value === '13'));
  expect(projectSelect).toBeDefined();
  fireEvent.change(projectSelect, { target: { value: '13' } });
  fireEvent.click(screen.getByRole('button', { name: 'Aggiungi' }));
  expect(screen.getByText('Progetto Power nuovo')).toBeInTheDocument();

  const companySelect = screen.getAllByRole('combobox')
    .find((element) => element.value === '10');
  fireEvent.change(companySelect, { target: { value: '20' } });
  await waitFor(() => expect(screen.queryByText('Progetto Power nuovo')).not.toBeInTheDocument());

  fireEvent.click(screen.getByRole('button', { name: 'Salva' }));
  await waitFor(() => expect(updateAllievo).toHaveBeenCalled());
  expect(updateAllievo.mock.calls[0][1]).toEqual(expect.objectContaining({
    azienda_cliente_id: 20,
    project_ids: [12, 11],
  }));
});
