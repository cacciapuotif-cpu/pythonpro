import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import AziendeBulkImport from './AziendeBulkImport';
import { executeAziendaImport, previewAziendaImport } from '../../services/apiService';

jest.mock('../../services/apiService', () => ({
  downloadAziendaImportTemplate: jest.fn(),
  executeAziendaImport: jest.fn(),
  previewAziendaImport: jest.fn(),
}));

beforeEach(() => {
  URL.createObjectURL = jest.fn(() => 'blob:test');
  URL.revokeObjectURL = jest.fn();
});

test('mostra anteprima create/aggiornate/scartate ed errori riga-colonna', async () => {
  previewAziendaImport.mockResolvedValue({
    summary: { create: 2, update: 1, reject: 1, valid: 3 },
    warnings: ['Formato legacy: deprecato'],
    errors: [{ sheet: 'Aziende', row: 5, column: 'Ragione sociale', message: 'campo obbligatorio' }],
  });
  render(<AziendeBulkImport onClose={jest.fn()} />);
  const file = new File(['xlsx'], 'aziende.xlsx', { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
  fireEvent.change(screen.getByLabelText(/seleziona file excel/i), { target: { files: [file] } });
  await waitFor(() => expect(screen.getByText('2')).toBeInTheDocument());
  expect(screen.getAllByText('1', { selector: 'strong' })).toHaveLength(2);
  expect(screen.getByText(/Aziende, riga 5, colonna Ragione sociale/i)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /importa 3 righe valide/i })).toBeEnabled();
});

test('esegue l’import e rende scaricabile il report', async () => {
  previewAziendaImport.mockResolvedValue({ summary: { create: 1, update: 0, reject: 0, valid: 1 }, warnings: [], errors: [] });
  executeAziendaImport.mockResolvedValue({
    created: 1, updated: 0, rejected: 0,
    report_rows: [{ row: 4, partita_iva: '11111111115', ragione_sociale: 'Alfa', outcome: 'Creata', message: 'OK' }],
  });
  const onImported = jest.fn();
  render(<AziendeBulkImport onImported={onImported} onClose={jest.fn()} />);
  const file = new File(['xlsx'], 'aziende.xlsx', { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
  fireEvent.change(screen.getByLabelText(/seleziona file excel/i), { target: { files: [file] } });
  const button = await screen.findByRole('button', { name: /importa 1 righe valide/i });
  fireEvent.click(button);
  await waitFor(() => expect(screen.getByText(/1 create, 0 aggiornate, 0 scartate/i)).toBeInTheDocument());
  expect(onImported).toHaveBeenCalled();
  expect(screen.getByRole('button', { name: /scarica report esito csv/i })).toBeInTheDocument();
});
