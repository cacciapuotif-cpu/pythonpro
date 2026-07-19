import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import DocumentiCollaboratore from './DocumentiCollaboratore';
import { getDocumentiCollaboratore } from '../services/apiService';

jest.mock('../services/apiService', () => ({
  downloadCurriculumFile: jest.fn(),
  downloadDocumentoIdentitaFile: jest.fn(),
  getDocumentiCollaboratore: jest.fn(),
  getDocumentiMancantiCollaboratore: jest.fn(),
  rifiutaDocumentoRichiesto: jest.fn(),
  uploadDocumentoRichiesto: jest.fn(),
  validaDocumentoRichiesto: jest.fn(),
}));

beforeEach(() => {
  getDocumentiCollaboratore.mockResolvedValue([{
    id: 1,
    tipo_documento: 'documento_identita',
    descrizione: 'Documento di identità',
    stato: 'caricato',
    file_name: 'documento.pdf',
  }]);
});

test.each([
  ['admin', true, true],
  ['operatore', false, true],
  ['consultazione', false, false],
])(
  'azioni documento per %s: file sensibile=%s scrittura=%s',
  async (role, sensitiveAllowed, writeAllowed) => {
    render(<DocumentiCollaboratore collaboratore_id={1} currentUser={{ role, username: role }} />);
    await screen.findByText('documento.pdf');

    expect(Boolean(screen.queryByRole('button', { name: 'Anteprima' }))).toBe(sensitiveAllowed);
    expect(Boolean(screen.queryByRole('button', { name: 'Scarica' }))).toBe(sensitiveAllowed);
    expect(Boolean(screen.queryByText('Upload'))).toBe(writeAllowed);
    expect(Boolean(screen.queryByRole('button', { name: 'Valida' }))).toBe(writeAllowed);
    expect(Boolean(screen.queryByRole('button', { name: 'Rifiuta' }))).toBe(writeAllowed);
  },
);

