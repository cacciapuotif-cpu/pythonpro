import React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import ImplementingEntityModal from './ImplementingEntityModal';
import apiService from '../services/apiService';

jest.mock('../services/apiService', () => ({
  __esModule: true,
  default: {
    getEntityLocations: jest.fn(),
    getEntityAccounts: jest.fn(),
    createEntityLocation: jest.fn(),
    updateEntityLocation: jest.fn(),
    deactivateEntityLocation: jest.fn(),
    createEntityAccount: jest.fn(),
    updateEntityAccount: jest.fn(),
    deactivateEntityAccount: jest.fn(),
  },
}));

const entity = {
  id: 7,
  ragione_sociale: 'Ente Modifica Srl',
  partita_iva: '12345678901',
  nazione: 'IT',
  legale_rappresentante_nome: 'Mario',
  legale_rappresentante_cognome: 'Rossi',
  legale_rappresentante_luogo_nascita: 'Napoli',
  legale_rappresentante_data_nascita: '1980-01-01T00:00:00Z',
  legale_rappresentante_comune_residenza: 'Napoli',
  legale_rappresentante_via_residenza: 'Via Verdi 1',
  legale_rappresentante_codice_fiscale: 'RSSMRA80A01F839X',
  note: 'Nota ente esistente',
  is_active: true,
};

const location = {
  id: 3,
  ente_id: 7,
  tipo: 'legale',
  denominazione: 'Sede legale corrente',
  indirizzo_completo: 'Via Roma 1, Napoli',
  is_principale: true,
  is_active: true,
};

const account = {
  id: 4,
  ente_id: 7,
  banca: 'Banca Corrente',
  iban: null,
  iban_masked: 'IT••••••••••••••••••••3456',
  intestatario: 'Ente Modifica Srl',
  is_predefinito: true,
  is_active: true,
};

beforeEach(() => {
  jest.clearAllMocks();
  apiService.getEntityLocations.mockResolvedValue([location]);
  apiService.getEntityAccounts.mockResolvedValue([account]);
  apiService.createEntityAccount.mockResolvedValue({ id: 8 });
  window.alert = jest.fn();
});

const openSection = (name) => {
  fireEvent.click(screen.getByText(name, { selector: '.step-title' }));
};

test('la modifica mostra e gestisce sedi e conti correnti nella stessa finestra', async () => {
  const { container } = render(
    <ImplementingEntityModal entity={entity} onClose={jest.fn()} onSave={jest.fn()} />
  );

  await waitFor(() => expect(apiService.getEntityLocations).toHaveBeenCalledWith(7));
  openSection('Sede Legale');
  expect(await screen.findByText('Sede legale corrente')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Aggiungi sede' })).toBeInTheDocument();

  openSection('Conti correnti');
  expect(await screen.findByText('IT••••••••••••••••••••3456')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Aggiungi conto' }));
  const accountInputs = container.querySelectorAll('.related-inline-form input');
  fireEvent.change(accountInputs[2], { target: { value: 'DE89370400440532013000' } });
  fireEvent.change(accountInputs[4], { target: { value: 'Ente Modifica Srl' } });
  fireEvent.click(screen.getByRole('button', { name: 'Salva conto' }));

  await waitFor(() => expect(apiService.createEntityAccount).toHaveBeenCalledWith(
    7,
    expect.objectContaining({
      iban: 'DE89370400440532013000',
      intestatario: 'Ente Modifica Srl',
    })
  ));
});

test('legale rappresentante, note e logo sono sezioni direttamente visibili', async () => {
  render(<ImplementingEntityModal entity={entity} onClose={jest.fn()} onSave={jest.fn()} />);

  const sectionNavigation = screen.getByRole('navigation', { name: 'Sezioni modifica ente' });
  [
    'Dati Legali',
    'Sede Legale',
    'Contatti',
    'Conti correnti',
    'Legale Rappresentante',
    'Note & Logo',
  ].forEach((label) => {
    expect(within(sectionNavigation).getByRole('button', { name: label })).toBeVisible();
  });
  expect(within(sectionNavigation).getByRole('button', { name: 'Dati Legali' })).toHaveAttribute('aria-current', 'step');

  openSection('Legale Rappresentante');
  expect(within(sectionNavigation).getByRole('button', { name: 'Legale Rappresentante' })).toHaveAttribute('aria-current', 'step');
  expect(screen.getByDisplayValue('Mario')).toBeInTheDocument();
  expect(screen.getByDisplayValue('Rossi')).toBeInTheDocument();

  openSection('Note & Logo');
  expect(screen.getByDisplayValue('Nota ente esistente')).toBeInTheDocument();
  expect(screen.getByText('Logo ente')).toBeInTheDocument();
  expect(screen.getByText(/Formati: PNG, JPG, GIF/)).toBeInTheDocument();
});
