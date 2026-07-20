import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

import PianoTemplateWizard, { PianoTemplateWizardButton } from './PianoTemplateWizard';
import {
  createPianoFinanziarioFromTemplate,
  getAvvisi,
  getPianoTemplateAnteprima,
  getPianoTemplates,
} from '../services/apiService';

jest.mock('../services/apiService', () => ({
  createPianoFinanziarioFromTemplate: jest.fn(),
  getAvvisi: jest.fn(),
  getPianoTemplateAnteprima: jest.fn(),
  getPianoTemplates: jest.fn(),
}));

const avvisoFapi = {
  id: 9,
  codice: '1/2026',
  fondo: 'fapi',
  titolo: 'Avviso FAPI 1/2026',
  anno: 2026,
  is_active: true,
};

const templateConsigliato = {
  id: 4,
  nome: 'Template FAPI generico',
  descrizione: 'Struttura standard FAPI',
  tipo_fondo: 'fapi',
  avviso_id: 9,
  versione: 1,
  is_active: true,
  struttura_voci: {},
  preselezionato: true,
};

const templateAlternativo = {
  id: 5,
  nome: 'Template FAPI alternativo',
  descrizione: null,
  tipo_fondo: 'fapi',
  avviso_id: null,
  versione: 1,
  is_active: true,
  struttura_voci: {},
  preselezionato: false,
};

const anteprima = {
  template: templateConsigliato,
  voci: [
    { voce_codice: 'B.2', macrovoce: 'B', categoria: 'docenza', descrizione: 'Docenza' },
    { voce_codice: 'B.3', macrovoce: 'B', categoria: 'tutoraggio', descrizione: 'Tutor' },
    { voce_codice: 'B.4', macrovoce: 'B', categoria: 'materiali', descrizione: 'Materiali didattici' },
  ],
  massimali: [
    { categoria: 'docenza', limite: 80, fonte: 'regola_avviso', riferimento_articolo: 'art. 12' },
    { categoria: 'tutoraggio', limite: 30, fonte: 'massimale_fondo', riferimento_articolo: null },
  ],
};

const progetti = [
  { id: 5, name: 'Progetto Alfa' },
  { id: 6, name: 'Progetto Beta' },
];

const pianoCreato = {
  id: 77,
  nome: 'Piano da template',
  anno: 2026,
  tipo_fondo: 'fapi',
  voci: [
    { id: 701, voce_codice: 'B.2', macrovoce: 'B', categoria: 'docenza', descrizione: 'Docenza' },
    { id: 702, voce_codice: 'B.3', macrovoce: 'B', categoria: 'tutoraggio', descrizione: 'Tutor' },
  ],
};

/** Porta il wizard dal passo 1 al passo 2 (fondo fapi + avviso + template consigliato). */
async function arrivaAllAnteprima() {
  fireEvent.change(screen.getByLabelText(/fondo/i), { target: { value: 'fapi' } });
  await screen.findByRole('option', { name: /avviso fapi 1\/2026/i });
  fireEvent.change(screen.getByLabelText(/avviso/i), { target: { value: '9' } });

  await screen.findByText('Consigliato dall\'avviso');
  fireEvent.click(screen.getByRole('button', { name: /avanti/i }));
  await screen.findByText('Docenza');
}

describe('PianoTemplateWizard', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    getAvvisi.mockResolvedValue([avvisoFapi]);
    getPianoTemplates.mockImplementation((params = {}) => Promise.resolve(
      params.avviso_id ? [templateConsigliato, templateAlternativo] : [
        { ...templateConsigliato, preselezionato: false },
        templateAlternativo,
      ],
    ));
    getPianoTemplateAnteprima.mockResolvedValue(anteprima);
    createPianoFinanziarioFromTemplate.mockResolvedValue(pianoCreato);
  });

  test('naviga i 3 passi: selezione, anteprima, conferma (e torna indietro)', async () => {
    render(<PianoTemplateWizard availableProjects={progetti} onClose={jest.fn()} />);

    // Passo 1 — selezione
    expect(screen.getByText(/passo 1 di 3/i)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/fondo/i), { target: { value: 'fapi' } });

    await waitFor(() => expect(getPianoTemplates).toHaveBeenCalledWith({ tipo_fondo: 'fapi' }));
    const radioTemplate = await screen.findByRole('radio', { name: /template fapi generico/i });
    fireEvent.click(radioTemplate);
    fireEvent.click(screen.getByRole('button', { name: /avanti/i }));

    // Passo 2 — anteprima
    expect(await screen.findByText(/passo 2 di 3/i)).toBeInTheDocument();
    await waitFor(() => expect(getPianoTemplateAnteprima).toHaveBeenCalled());
    expect(await screen.findByText('B.2')).toBeInTheDocument();
    expect(screen.getByText('Docenza')).toBeInTheDocument();
    expect(screen.getByText('Materiali didattici')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /avanti/i }));

    // Passo 3 — conferma
    expect(await screen.findByText(/passo 3 di 3/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/nome del piano/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/anno/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/budget totale/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/progetto/i)).toBeInTheDocument();

    // Indietro riporta all'anteprima
    fireEvent.click(screen.getByRole('button', { name: /indietro/i }));
    expect(await screen.findByText(/passo 2 di 3/i)).toBeInTheDocument();
  });

  test('preseleziona ed evidenzia il template consigliato dall\'avviso', async () => {
    render(<PianoTemplateWizard availableProjects={progetti} onClose={jest.fn()} />);

    fireEvent.change(screen.getByLabelText(/fondo/i), { target: { value: 'fapi' } });
    await screen.findByRole('option', { name: /avviso fapi 1\/2026/i });
    fireEvent.change(screen.getByLabelText(/avviso/i), { target: { value: '9' } });

    await waitFor(() => expect(getPianoTemplates).toHaveBeenCalledWith({ tipo_fondo: 'fapi', avviso_id: 9 }));
    expect(await screen.findByText('Consigliato dall\'avviso')).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: /template fapi generico/i })).toBeChecked();
    expect(screen.getByRole('radio', { name: /template fapi alternativo/i })).not.toBeChecked();
  });

  test('anteprima: badge fonte per regola avviso e massimale fondo generico', async () => {
    render(<PianoTemplateWizard availableProjects={progetti} onClose={jest.fn()} />);
    await arrivaAllAnteprima();

    expect(screen.getByText('Regola avviso (art. 12)')).toBeInTheDocument();
    expect(screen.getByText('Massimale fondo generico')).toBeInTheDocument();
    // la categoria senza massimale non ha alcun badge fonte
    expect(screen.getAllByTestId('badge-fonte-massimale')).toHaveLength(2);
  });

  test('conferma: submit chiama createFromTemplate col payload giusto e mostra il piano creato con le voci', async () => {
    render(<PianoTemplateWizard availableProjects={progetti} onClose={jest.fn()} />);
    await arrivaAllAnteprima();

    fireEvent.click(screen.getByRole('button', { name: /avanti/i }));
    await screen.findByText(/passo 3 di 3/i);

    fireEvent.change(screen.getByLabelText(/progetto/i), { target: { value: '5' } });
    fireEvent.change(screen.getByLabelText(/nome del piano/i), { target: { value: 'Piano da template' } });
    fireEvent.change(screen.getByLabelText(/anno/i), { target: { value: '2026' } });
    fireEvent.change(screen.getByLabelText(/budget totale/i), { target: { value: '10000' } });

    fireEvent.click(screen.getByRole('button', { name: /crea piano/i }));

    await waitFor(() => expect(createPianoFinanziarioFromTemplate).toHaveBeenCalledWith({
      template_id: 4,
      progetto_id: 5,
      avviso_id: 9,
      anno: 2026,
      nome: 'Piano da template',
      budget_totale: 10000,
    }));

    // il piano creato viene selezionato/mostrato con le sue voci
    const conferma = await screen.findByText(/piano creato/i);
    expect(conferma).toHaveTextContent('ID: 77');
    expect(conferma).toHaveTextContent('Piano da template');
    expect(screen.getByText('B.2')).toBeInTheDocument();
    expect(screen.getByText('B.3')).toBeInTheDocument();
  });
});

describe('PianoTemplateWizardButton (RBAC)', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    getAvvisi.mockResolvedValue([]);
    getPianoTemplates.mockResolvedValue([]);
  });

  test('il ruolo consultazione non vede il bottone', () => {
    render(
      <PianoTemplateWizardButton
        currentUser={{ id: 3, role: 'consultazione' }}
        availableProjects={progetti}
      />,
    );
    expect(screen.queryByRole('button', { name: /nuovo piano da template/i })).not.toBeInTheDocument();
  });

  test('admin e operatore vedono il bottone che apre il wizard', async () => {
    const { unmount } = render(
      <PianoTemplateWizardButton
        currentUser={{ id: 1, role: 'admin' }}
        availableProjects={progetti}
      />,
    );
    expect(screen.getByRole('button', { name: /nuovo piano da template/i })).toBeInTheDocument();
    unmount();

    render(
      <PianoTemplateWizardButton
        currentUser={{ id: 2, role: 'operatore' }}
        availableProjects={progetti}
      />,
    );
    const button = screen.getByRole('button', { name: /nuovo piano da template/i });
    fireEvent.click(button);
    expect(screen.getByText(/passo 1 di 3/i)).toBeInTheDocument();
    await waitFor(() => expect(getAvvisi).toHaveBeenCalled());
  });
});
