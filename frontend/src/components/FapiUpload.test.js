/**
 * UX-6 — dalla scheda di un progetto il documento si ALLEGA, non crea un gemello.
 *
 * Il difetto era qui: FapiUploadSection montava il modale convenzione senza
 * passargli il progetto corrente, cosi' il modale chiamava sempre gli endpoint
 * project-less che creano un progetto nuovo.
 */

import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

import { FapiUploadSection } from './FapiUpload';
import {
  uploadConvenzione,
  confirmConvenzione,
  uploadConvenzioneProgetto,
  confirmConvenzioneProgetto,
  uploadAmmissioneFondimpresa,
  uploadAmmissioneFondimpresaProgetto,
} from '../services/apiService';

jest.mock('../services/apiService', () => ({
  uploadConvenzione: jest.fn(),
  confirmConvenzione: jest.fn(),
  uploadConvenzioneProgetto: jest.fn(),
  confirmConvenzioneProgetto: jest.fn(),
  uploadFormulario: jest.fn(),
  confirmFormulario: jest.fn(),
  uploadPianoFinanziario: jest.fn(),
  confirmPianoFinanziario: jest.fn(),
  uploadAmmissioneFondimpresa: jest.fn(),
  confirmAmmissioneFondimpresa: jest.fn(),
  uploadAmmissioneFondimpresaProgetto: jest.fn(),
  confirmAmmissioneFondimpresaProgetto: jest.fn(),
  uploadRiepilogoFondimpresa: jest.fn(),
  confirmRiepilogoFondimpresa: jest.fn(),
}));

const progetto = { id: 11, ente_erogatore: 'FAPI', codice_fapi: '20250611CMIA001' };

const anteprima = {
  preview_token: 'tok-1',
  project_id: 11,
  diff: [
    {
      campo: 'delibera_numero',
      etichetta: 'Numero delibera',
      valore_attuale: null,
      valore_estratto: '42',
      conflitto: false,
    },
    {
      campo: 'costo_totale',
      etichetta: 'Costo totale',
      valore_attuale: 51242.03,
      valore_estratto: 99999,
      conflitto: true,
    },
  ],
  piano: {},
  ente_attuatore: {},
  aziende_beneficiarie: [],
  warnings: [],
};

function selezionaFile() {
  const input = document.querySelector('.fapi-file-input');
  const file = new File(['x'], 'atto.pdf', { type: 'application/pdf' });
  fireEvent.change(input, { target: { files: [file] } });
}

beforeEach(() => {
  jest.clearAllMocks();
  uploadConvenzioneProgetto.mockResolvedValue(anteprima);
  confirmConvenzioneProgetto.mockResolvedValue({
    project_id: 11,
    campi_applicati: ['delibera_numero'],
    campi_in_conflitto_non_applicati: ['costo_totale'],
    aziende_create: 0,
    aziende_associate: 0,
    suggestions_create: 0,
  });
});

test('dentro un progetto usa il percorso di associazione, non quello di creazione', async () => {
  render(<FapiUploadSection project={progetto} />);
  fireEvent.click(screen.getByRole('button', { name: /Convenzione/i }));
  selezionaFile();

  await waitFor(() => expect(uploadConvenzioneProgetto).toHaveBeenCalledWith(11, expect.any(File)));
  expect(uploadConvenzione).not.toHaveBeenCalled();
});

test('senza progetto resta il percorso di creazione', async () => {
  uploadConvenzione.mockResolvedValue({ preview_token: 't', piano: {}, ente_attuatore: {}, aziende_beneficiarie: [], warnings: [] });
  render(<FapiUploadSection project={null} autoOpenConvenzione autoOpenMode="convenzione" />);
  selezionaFile();

  await waitFor(() => expect(uploadConvenzione).toHaveBeenCalled());
  expect(uploadConvenzioneProgetto).not.toHaveBeenCalled();
});

test('i conflitti non sono spuntati di default: nessuna sovrascrittura implicita', async () => {
  render(<FapiUploadSection project={progetto} />);
  fireEvent.click(screen.getByRole('button', { name: /Convenzione/i }));
  selezionaFile();

  const checkbox = await screen.findByLabelText('Sovrascrivi Costo totale');
  expect(checkbox).not.toBeChecked();

  fireEvent.click(screen.getByRole('button', { name: /Allega al progetto/i }));
  await waitFor(() =>
    expect(confirmConvenzioneProgetto).toHaveBeenCalledWith(11, 'tok-1', [])
  );
});

test('il campo in conflitto viene inviato solo se spuntato', async () => {
  render(<FapiUploadSection project={progetto} />);
  fireEvent.click(screen.getByRole('button', { name: /Convenzione/i }));
  selezionaFile();

  fireEvent.click(await screen.findByLabelText('Sovrascrivi Costo totale'));
  fireEvent.click(screen.getByRole('button', { name: /Allega al progetto/i }));

  await waitFor(() =>
    expect(confirmConvenzioneProgetto).toHaveBeenCalledWith(11, 'tok-1', ['costo_totale'])
  );
});

test('l esito dichiara cosa e rimasto invariato', async () => {
  render(<FapiUploadSection project={progetto} />);
  fireEvent.click(screen.getByRole('button', { name: /Convenzione/i }));
  selezionaFile();

  fireEvent.click(await screen.findByRole('button', { name: /Allega al progetto/i }));
  expect(await screen.findByText(/lasciati invariati/i)).toBeInTheDocument();
});


test('anche Fondimpresa allega al progetto invece di crearne uno nuovo', async () => {
  uploadAmmissioneFondimpresaProgetto.mockResolvedValue({
    preview_token: 'tok-fi',
    project_id: 7,
    diff: [],
    warnings: [],
  });
  render(<FapiUploadSection project={{ id: 7, ente_erogatore: 'Fondimpresa' }} />);
  fireEvent.click(screen.getByRole('button', { name: /Lettera ammissione/i }));
  selezionaFile();

  await waitFor(() =>
    expect(uploadAmmissioneFondimpresaProgetto).toHaveBeenCalledWith(7, expect.any(File))
  );
  expect(uploadAmmissioneFondimpresa).not.toHaveBeenCalled();
});
