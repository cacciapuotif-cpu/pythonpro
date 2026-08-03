import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import AziendaDetail from './AziendaDetail';
import { revealAziendaIban } from '../../services/apiService';

jest.mock('../../services/apiService', () => ({ revealAziendaIban: jest.fn() }));

const spec = {
  groups: [
    { name: 'identificazione', label: 'Identificazione' },
    { name: 'contatti', label: 'Contatti e web' },
  ],
  fields: [
    { name: 'ragione_sociale', label: 'Ragione sociale', group: 'identificazione', type: 'text' },
    { name: 'natura_giuridica', label: 'Natura giuridica', group: 'identificazione', type: 'text' },
    { name: 'email', label: 'Email', group: 'contatti', type: 'email' },
  ],
};

const azienda = {
  id: 9,
  ragione_sociale: 'Alfa Srl',
  partita_iva: '11111111115',
  natura_giuridica: 'S.r.l.',
  email: '',
  sedi_operative: [{ id: 2, nome: 'Napoli', tipo: 'operativa', indirizzo: 'Via Roma 1', is_principale: true }],
  conti_correnti: [{ id: 3, intestatario: 'Alfa Srl', iban_masked: 'IT••••••••••••••••••••3456', banca: 'Banca Alfa' }],
  fund_memberships: [],
  linked_projects: [{ id: 11, name: 'MAXI COMMUNICATION' }],
  note: '',
};

test('la scheda usa gruppi ed etichette della specifica e rappresenta i vuoti', () => {
  render(<AziendaDetail azienda={azienda} spec={spec} currentUser={{ role: 'consultazione' }} onClose={jest.fn()} />);
  expect(screen.getByRole('heading', { name: 'Alfa Srl', level: 2 })).toBeInTheDocument();
  expect(screen.getByText('Natura giuridica')).toBeInTheDocument();
  expect(screen.getByText('S.r.l.')).toBeInTheDocument();
  expect(screen.getAllByText('—').length).toBeGreaterThan(0);
  expect(screen.getByText('IT••••••••••••••••••••3456')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /mostra iban completo/i })).not.toBeInTheDocument();
});

test('un ruolo operativo autorizzato può rivelare l’IBAN completo', async () => {
  revealAziendaIban.mockResolvedValue({ iban: 'IT60X0542811101000000123456' });
  render(<AziendaDetail azienda={azienda} spec={spec} currentUser={{ role: 'admin' }} onClose={jest.fn()} />);
  fireEvent.click(screen.getByRole('button', { name: /mostra iban completo/i }));
  await waitFor(() => expect(screen.getByText('IT60X0542811101000000123456')).toBeInTheDocument());
  expect(revealAziendaIban).toHaveBeenCalledWith(9, 3);
});
