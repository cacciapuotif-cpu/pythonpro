/**
 * UX-6 — dalla scheda di un progetto il documento si ALLEGA, non crea un gemello.
 *
 * Il difetto era qui: FapiUploadSection montava il modale convenzione senza
 * passargli il progetto corrente, cosi' il modale chiamava sempre gli endpoint
 * project-less che creano un progetto nuovo.
 */

import React, { act } from 'react';
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
  getDocumentiProgetto,
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
  getDocumentiProgetto: jest.fn(),
  downloadDocumentoProgetto: jest.fn(),
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

const anteprimaMatch = {
  preview_token: 'tok-match',
  existing_project_id: 11,
  azione_predefinita: 'associa',
  match: {
    stato: 'esatto',
    project_id: 11,
    candidati: [
      {
        project_id: 11,
        nome: 'MAXI COMMUNICATION',
        codice_fapi: '20250611CMIA001',
        confidenza: 'esatta',
        motivi: ['codice_piano'],
      },
    ],
  },
  confronto: [
    {
      campo: 'codice_fapi',
      etichetta: 'Codice piano',
      valore_attuale: '20250611CMIA001',
      valore_estratto: '20250611CMIA001',
      stato: 'identico',
      conflitto: false,
    },
    {
      campo: 'costo_totale',
      etichetta: 'Costo totale',
      valore_attuale: 50000,
      valore_estratto: 51242.03,
      stato: 'diverso',
      conflitto: true,
    },
  ],
  piano: {
    codice_fapi: '20250611CMIA001',
    delibera_data: '2026-03-24',
  },
  ente_attuatore: {},
  aziende_beneficiarie: [],
  confronto_aziende: [{
    ragione_sociale: 'Power Impianti srl',
    gia_associata: true,
    codice_progetto: '20250611CMIA00101',
    num_partecipanti: 9,
    importo: 9882.36,
  }],
  warnings: [],
};

const anteprimaDestinazioneErrata = {
  ...anteprima,
  preview_token: 'tok-mismatch',
  project_id: 5,
  project_mismatch: {
    current_project_id: 5,
    current_project_name: 'poppi',
    matched_project_id: 11,
    matched_project_name: 'MAXI COMMUNICATION',
    codice_fapi: '20250611CMIA001',
  },
  match: {
    stato: 'esatto',
    project_id: 11,
    candidati: [{
      project_id: 11,
      nome: 'MAXI COMMUNICATION',
      codice_fapi: '20250611CMIA001',
      confidenza: 'esatta',
      motivi: ['codice_piano'],
    }],
  },
};

async function selezionaFile() {
  const input = document.querySelector('.fapi-file-input');
  const file = new File(['x'], 'atto.pdf', { type: 'application/pdf' });
  await act(async () => {
    fireEvent.change(input, { target: { files: [file] } });
  });
}

async function cliccaEAttendi(element) {
  await act(async () => {
    fireEvent.click(element);
  });
}

beforeEach(() => {
  jest.clearAllMocks();
  getDocumentiProgetto.mockResolvedValue([]);
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

test('la scheda progetto mostra i documenti archiviati e la versione', async () => {
  getDocumentiProgetto.mockResolvedValue([
    {
      id: 9,
      tipo_documento: 'atto_concessione',
      versione: 2,
      file_name: 'atto.pdf',
      caricato_da_user_id: 4,
    },
  ]);
  render(<FapiUploadSection project={progetto} />);

  expect(await screen.findByText(/atto concessione · v2 · atto.pdf · non disponibile · data non disponibile/i))
    .toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Scarica' })).toBeInTheDocument();
});

test('un formulario non viene etichettato come convenzione caricata', async () => {
  getDocumentiProgetto.mockResolvedValue([
    {
      id: 10,
      tipo_documento: 'formulario',
      versione: 1,
      stato: 'corrente',
      file_name: 'formulario.pdf',
    },
  ]);
  render(<FapiUploadSection project={{ ...progetto, convenzione_file_path: '/uploads/formulario.pdf' }} />);

  expect(await screen.findByText(/formulario · v1/i)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: '📄 Carica Convenzione' })).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: '✅ Convenzione' })).not.toBeInTheDocument();
});

test('dentro un progetto usa il percorso di associazione, non quello di creazione', async () => {
  render(<FapiUploadSection project={progetto} />);
  fireEvent.click(screen.getByRole('button', { name: /Convenzione/i }));
  await selezionaFile();

  await waitFor(() => expect(uploadConvenzioneProgetto).toHaveBeenCalledWith(11, expect.any(File)));
  expect(uploadConvenzione).not.toHaveBeenCalled();
});

test('senza progetto resta il percorso di creazione', async () => {
  uploadConvenzione.mockResolvedValue({ preview_token: 't', piano: {}, ente_attuatore: {}, aziende_beneficiarie: [], warnings: [] });
  render(<FapiUploadSection project={null} autoOpenConvenzione autoOpenMode="convenzione" />);
  await selezionaFile();

  await waitFor(() => expect(uploadConvenzione).toHaveBeenCalled());
  expect(uploadConvenzioneProgetto).not.toHaveBeenCalled();
});

test('i conflitti non sono spuntati di default: nessuna sovrascrittura implicita', async () => {
  render(<FapiUploadSection project={progetto} />);
  fireEvent.click(screen.getByRole('button', { name: /Convenzione/i }));
  await selezionaFile();

  const checkbox = await screen.findByLabelText('Sovrascrivi Costo totale');
  expect(checkbox).not.toBeChecked();

  await cliccaEAttendi(screen.getByRole('button', { name: /Allega al progetto/i }));
  await waitFor(() =>
    expect(confirmConvenzioneProgetto).toHaveBeenCalledWith(11, 'tok-1', [])
  );
});

test('il campo in conflitto viene inviato solo se spuntato', async () => {
  render(<FapiUploadSection project={progetto} />);
  fireEvent.click(screen.getByRole('button', { name: /Convenzione/i }));
  await selezionaFile();

  fireEvent.click(await screen.findByLabelText('Sovrascrivi Costo totale'));
  await cliccaEAttendi(screen.getByRole('button', { name: /Allega al progetto/i }));

  await waitFor(() =>
    expect(confirmConvenzioneProgetto).toHaveBeenCalledWith(11, 'tok-1', ['costo_totale'])
  );
});

test('se il PDF appartiene a un altro progetto mostra il bivio e invia il target corretto', async () => {
  uploadConvenzioneProgetto.mockResolvedValue(anteprimaDestinazioneErrata);
  render(<FapiUploadSection project={{
    id: 5,
    name: 'poppi',
    ente_erogatore: 'FAPI',
  }} />);
  fireEvent.click(screen.getByRole('button', { name: /Carica Convenzione/i }));
  await selezionaFile();

  expect(await screen.findByText(/Il documento non appartiene al progetto aperto/i))
    .toBeInTheDocument();
  expect(screen.getByText(/Stai operando su #5/i)).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /^Allega al progetto$/i }))
    .not.toBeInTheDocument();

  await cliccaEAttendi(screen.getByRole('button', {
    name: /Allega a #11 · MAXI COMMUNICATION/i,
  }));
  await waitFor(() => expect(confirmConvenzioneProgetto).toHaveBeenCalledWith(
    11,
    'tok-mismatch',
    [],
    'associa',
    'convenzione',
  ));
});

test('l esito dichiara cosa e rimasto invariato', async () => {
  render(<FapiUploadSection project={progetto} />);
  fireEvent.click(screen.getByRole('button', { name: /Convenzione/i }));
  await selezionaFile();

  await cliccaEAttendi(await screen.findByRole('button', { name: /Allega al progetto/i }));
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
  await selezionaFile();

  await waitFor(() =>
    expect(uploadAmmissioneFondimpresaProgetto).toHaveBeenCalledWith(7, expect.any(File))
  );
  expect(uploadAmmissioneFondimpresa).not.toHaveBeenCalled();
});

test('con match globale propone tre azioni e associa e la predefinita', async () => {
  uploadConvenzione.mockResolvedValue(anteprimaMatch);
  render(<FapiUploadSection project={null} autoOpenConvenzione autoOpenMode="convenzione" />);
  await selezionaFile();

  const associaButton = await screen.findByRole('button', {
    name: /Associa al progetto esistente/i,
  });
  expect(associaButton).toHaveClass('primary');
  expect(screen.getByRole('button', {
    name: /Aggiorna dati del progetto esistente/i,
  })).toBeInTheDocument();
  expect(screen.getByRole('button', {
    name: /Crea comunque un nuovo progetto/i,
  })).toBeInTheDocument();
  expect(screen.queryByRole('button', {
    name: /^Conferma e Crea Progetto$/i,
  })).not.toBeInTheDocument();

  await cliccaEAttendi(associaButton);
  await waitFor(() => expect(confirmConvenzioneProgetto).toHaveBeenCalledWith(
    11,
    'tok-match',
    [],
    'associa',
    'convenzione',
  ));
  expect(confirmConvenzione).not.toHaveBeenCalled();
});

test('il confronto completo mostra identici diversi e aggiorna solo la selezione', async () => {
  uploadConvenzione.mockResolvedValue(anteprimaMatch);
  render(<FapiUploadSection project={null} autoOpenConvenzione autoOpenMode="convenzione" />);
  await selezionaFile();

  expect(await screen.findByText('identico')).toBeInTheDocument();
  expect(screen.getByText('diverso')).toBeInTheDocument();
  expect(screen.getByText('20250611CMIA00101')).toBeInTheDocument();
  expect(screen.getByText('Associata')).toBeInTheDocument();
  const checkbox = screen.getByLabelText('Aggiorna Costo totale');
  expect(checkbox).not.toBeChecked();
  fireEvent.click(checkbox);
  await cliccaEAttendi(screen.getByRole('button', {
    name: /Aggiorna dati del progetto esistente/i,
  }));

  await waitFor(() => expect(confirmConvenzioneProgetto).toHaveBeenCalledWith(
    11,
    'tok-match',
    ['costo_totale'],
    'aggiorna',
    'convenzione',
  ));
});

test('un match incerto confronta i valori del candidato scelto', async () => {
  uploadConvenzione.mockResolvedValue({
    ...anteprimaMatch,
    existing_project_id: null,
    match: {
      stato: 'incerto',
      project_id: null,
      candidati: [
        { project_id: 11, nome: 'Primo', codice_fapi: 'CODICE' },
        { project_id: 12, nome: 'Secondo', codice_fapi: 'CODICE' },
      ],
    },
    confronto: [],
    confronti_per_progetto: {
      11: [{
        campo: 'name',
        etichetta: 'Titolo',
        valore_attuale: 'Titolo primo',
        valore_estratto: 'Titolo estratto',
        stato: 'diverso',
      }],
      12: [{
        campo: 'name',
        etichetta: 'Titolo',
        valore_attuale: 'Titolo secondo',
        valore_estratto: 'Titolo estratto',
        stato: 'diverso',
      }],
    },
  });
  render(<FapiUploadSection project={null} autoOpenConvenzione autoOpenMode="convenzione" />);
  await selezionaFile();

  const selector = await screen.findByLabelText('Progetto destinatario');
  fireEvent.change(selector, { target: { value: '12' } });
  expect(await screen.findByText('Titolo secondo')).toBeInTheDocument();
  expect(screen.queryByText('Titolo primo')).not.toBeInTheDocument();
});

test('crea comunque richiede conferma aggiuntiva esplicita', async () => {
  uploadConvenzione.mockResolvedValue(anteprimaMatch);
  confirmConvenzione.mockResolvedValue({
    project_id: 22,
    aziende_create: 0,
    aziende_associate: 0,
    suggestions_create: 0,
  });
  const confirmSpy = jest.spyOn(window, 'confirm').mockReturnValue(true);
  render(<FapiUploadSection project={null} autoOpenConvenzione autoOpenMode="convenzione" />);
  await selezionaFile();

  fireEvent.change(await screen.findByLabelText('Data avvio piano'), {
    target: { value: '2026-04-01' },
  });
  await cliccaEAttendi(screen.getByRole('button', {
    name: /Crea comunque un nuovo progetto/i,
  }));

  expect(confirmSpy).toHaveBeenCalledWith(expect.stringMatching(
    /creerai un secondo progetto con lo stesso codice FAPI/i,
  ));
  await waitFor(() => expect(confirmConvenzione).toHaveBeenCalledWith(
    'tok-match',
    expect.objectContaining({
      conferma_creazione_duplicato: true,
      data_approvazione: '2026-03-24',
      data_avvio_piano: '2026-04-01',
    }),
  ));
  confirmSpy.mockRestore();
});
