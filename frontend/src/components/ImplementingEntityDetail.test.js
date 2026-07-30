import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import ImplementingEntityDetail from './ImplementingEntityDetail';
import apiService from '../services/apiService';

jest.mock('../services/apiService', () => ({
  __esModule: true,
  default: {
    getEntity: jest.fn(),
    getEntityLocations: jest.fn(),
    getEntityAccounts: jest.fn(),
    createEntityLocation: jest.fn(),
    updateEntityLocation: jest.fn(),
    deactivateEntityLocation: jest.fn(),
    createEntityAccount: jest.fn(),
    updateEntityAccount: jest.fn(),
    deactivateEntityAccount: jest.fn(),
    revealEntityIban: jest.fn(),
    updateEntity: jest.fn(),
    previewEntityPrint: jest.fn(),
    uploadEntityLogo: jest.fn(),
    downloadEntityLogo: jest.fn(),
    uploadEntityLetterhead: jest.fn(),
    deleteEntityLogo: jest.fn(),
    deleteEntityLetterhead: jest.fn(),
  },
}));

const entity = {
  id: 7,
  ragione_sociale: 'Ente Completo Srl',
  forma_giuridica: 'S.r.l.',
  partita_iva: '12345678901',
  codice_fiscale: '12345678901',
  email: 'info@ente.example',
  pec: 'ente@pec.example',
  telefono: '+39 081 123',
  sito_web: 'https://ente.example',
  social_links: [{ platform: 'Mastodon', url: 'https://social.example/@ente' }],
  projects: [{ id: 1 }],
  is_active: true,
  print_config_enabled: false,
  print_margin_top_mm: 20,
  print_margin_bottom_mm: 20,
  print_margin_left_mm: 20,
  print_margin_right_mm: 20,
  print_logo_width_mm: 40,
  print_logo_height_mm: 20,
  print_logo_x_mm: 20,
  print_logo_y_mm: 8,
  print_letterhead_pages: 'first',
  print_footer: '',
  logo_filename: 'logo.png',
  letterhead_filename: 'carta.pdf',
  legale_rappresentante_nome_completo: 'Mario Rossi',
  legale_rappresentante_luogo_nascita: 'Napoli',
  legale_rappresentante_data_nascita: '1980-01-01T00:00:00Z',
  legale_rappresentante_via_residenza: 'Via Verdi 1',
  legale_rappresentante_comune_residenza: 'Napoli',
  legale_rappresentante_codice_fiscale: 'RSSMRA80A01F839X',
  note: 'Nota amministrativa visibile',
};

const locations = [{
  id: 3,
  ente_id: 7,
  tipo: 'legale',
  denominazione: 'Sede legale',
  indirizzo_completo: 'Via Roma 1, Napoli',
  is_principale: true,
  is_active: true,
}];

const accounts = [{
  id: 4,
  ente_id: 7,
  banca: 'Banca Test',
  iban: null,
  iban_masked: 'IT••••••••••••••••••••3456',
  intestatario: 'Ente Completo Srl',
  is_predefinito: true,
  is_active: true,
}];

beforeEach(() => {
  jest.clearAllMocks();
  apiService.getEntity.mockResolvedValue(entity);
  apiService.getEntityLocations.mockResolvedValue(locations);
  apiService.getEntityAccounts.mockResolvedValue(accounts);
  apiService.createEntityLocation.mockResolvedValue({ id: 8 });
  apiService.revealEntityIban.mockResolvedValue({ account_id: 4, iban: 'IT60X0542811101000000123456' });
  apiService.updateEntity.mockResolvedValue(entity);
  apiService.previewEntityPrint.mockResolvedValue(new Blob(['pdf'], { type: 'application/pdf' }));
  apiService.downloadEntityLogo.mockResolvedValue(new Blob(['logo'], { type: 'image/png' }));
  window.alert = jest.fn();
  window.open = jest.fn();
  URL.createObjectURL = jest.fn(() => 'blob:preview');
  URL.revokeObjectURL = jest.fn();
});

test('mostra una scheda di dettaglio separata dalla modifica', async () => {
  render(<ImplementingEntityDetail entityId={7} currentUser={{ role: 'admin' }} onClose={jest.fn()} onEdit={jest.fn()} />);

  expect(await screen.findByRole('heading', { name: 'Ente Completo Srl' })).toBeInTheDocument();
  expect(screen.getByText('Dati legali')).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'https://ente.example' })).toHaveAttribute('href', 'https://ente.example');
  expect(screen.getByRole('link', { name: 'Mastodon' })).toHaveAttribute('href', 'https://social.example/@ente');
  expect(screen.getByText('Mario Rossi')).toBeInTheDocument();
  expect(screen.getByText('Nota amministrativa visibile')).toBeInTheDocument();
  expect(await screen.findByAltText('Logo Ente Completo Srl')).toHaveAttribute('src', 'blob:preview');
  expect(screen.getByRole('button', { name: 'Modifica anagrafica' })).toBeInTheDocument();
});

test('gestisce sedi multiple e invia il tipo estendibile previsto', async () => {
  render(<ImplementingEntityDetail entityId={7} currentUser={{ role: 'admin' }} />);
  await screen.findByRole('heading', { name: 'Ente Completo Srl' });
  fireEvent.click(screen.getByRole('button', { name: 'Sedi (1)' }));
  expect(screen.getByText('Via Roma 1, Napoli')).toBeInTheDocument();

  fireEvent.click(screen.getByRole('button', { name: 'Aggiungi sede' }));
  fireEvent.change(screen.getByLabelText('Tipo'), { target: { value: 'accreditata' } });
  fireEvent.change(screen.getByLabelText('Denominazione'), { target: { value: 'Sede Fondo' } });
  fireEvent.change(screen.getByLabelText('Codice accreditamento'), { target: { value: 'ACC-77' } });
  fireEvent.click(screen.getByRole('button', { name: 'Salva sede' }));

  await waitFor(() => expect(apiService.createEntityLocation).toHaveBeenCalledWith(
    7,
    expect.objectContaining({
      tipo: 'accreditata',
      denominazione: 'Sede Fondo',
      accreditamento_codice: 'ACC-77',
    })
  ));
  await waitFor(() => expect(screen.queryByRole('button', { name: 'Salva sede' })).not.toBeInTheDocument());
});

test('mostra IBAN mascherato e usa il reveal auditabile solo su richiesta', async () => {
  render(<ImplementingEntityDetail entityId={7} currentUser={{ role: 'operatore' }} />);
  await screen.findByRole('heading', { name: 'Ente Completo Srl' });
  fireEvent.click(screen.getByRole('button', { name: 'Conti correnti (1)' }));

  expect(screen.getByText('IT••••••••••••••••••••3456')).toBeInTheDocument();
  expect(screen.queryByText('IT60X0542811101000000123456')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Mostra IBAN' }));
  expect(await screen.findByText('IT60X0542811101000000123456')).toBeInTheDocument();
  expect(apiService.revealEntityIban).toHaveBeenCalledWith(7, 4);
});

test('offre logo e carta intestata indipendenti e anteprima senza contratto', async () => {
  render(<ImplementingEntityDetail entityId={7} currentUser={{ role: 'admin' }} />);
  await screen.findByRole('heading', { name: 'Ente Completo Srl' });
  fireEvent.click(screen.getByRole('button', { name: 'Stampa e branding' }));

  expect(screen.getByText('logo.png')).toBeInTheDocument();
  expect(screen.getByText('carta.pdf')).toBeInTheDocument();
  fireEvent.click(screen.getByLabelText('Usa questa configurazione nei nuovi documenti'));
  fireEvent.click(screen.getByRole('button', { name: 'Genera anteprima PDF' }));

  await waitFor(() => expect(apiService.previewEntityPrint).toHaveBeenCalledWith(
    7,
    expect.objectContaining({ print_config_enabled: true })
  ));
  await waitFor(() => expect(window.open).toHaveBeenCalledWith(
    'blob:preview',
    '_blank',
    'noopener,noreferrer'
  ));
});
