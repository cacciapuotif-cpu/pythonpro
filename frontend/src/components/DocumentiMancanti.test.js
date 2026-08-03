import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import DocumentiMancanti from './DocumentiMancanti';
import { getDocumentiRichiesti, sendDocumentReminders } from '../services/apiService';

jest.mock('../services/apiService', () => ({
  getDocumentiRichiesti: jest.fn(),
  sendDocumentReminders: jest.fn(),
}));

jest.mock('./responsive/ResponsiveFilters', () => ({ children }) => <div>{children}</div>);
jest.mock('./responsive/ResponsiveEntityList', () => ({ items, renderDesktop }) => renderDesktop(items));

const requestedDocument = {
  id: 9,
  collaboratore_id: 1,
  tipo_documento: 'documento_identita',
  stato: 'richiesto',
  data_scadenza: null,
  collaboratore: {
    id: 1,
    first_name: 'Francesco',
    last_name: 'Cacciapuoti',
    full_name: 'Cacciapuoti Francesco',
    email: 'cacciapuotif@gmail.com',
  },
};

beforeEach(() => {
  jest.clearAllMocks();
  getDocumentiRichiesti.mockImplementation(({ stato }) => (
    Promise.resolve(stato === 'richiesto' ? [requestedDocument] : [])
  ));
});

test('invia il sollecito tramite API senza aprire il client email', async () => {
  const openSpy = jest.spyOn(window, 'open').mockImplementation(() => null);
  sendDocumentReminders.mockResolvedValue({ sent_count: 1, failed_count: 0, results: [] });

  render(<DocumentiMancanti currentUser={{ role: 'admin' }} />);

  await screen.findByText('Cacciapuoti Francesco');
  fireEvent.click(screen.getByRole('button', { name: 'Invia sollecito' }));

  await waitFor(() => expect(sendDocumentReminders).toHaveBeenCalledWith([9]));
  expect(await screen.findByRole('status')).toHaveTextContent(
    'Sollecito inviato a Cacciapuoti Francesco.',
  );
  expect(openSpy).not.toHaveBeenCalled();
  openSpy.mockRestore();
});

test('mostra un errore quando il backend non riesce a inviare', async () => {
  sendDocumentReminders.mockRejectedValue({
    response: { data: { detail: 'Invio email non riuscito' } },
  });

  render(<DocumentiMancanti currentUser={{ role: 'admin' }} />);

  await screen.findByText('Cacciapuoti Francesco');
  fireEvent.click(screen.getByRole('button', { name: 'Invia sollecito' }));

  expect(await screen.findByText('Invio email non riuscito')).toBeInTheDocument();
});
