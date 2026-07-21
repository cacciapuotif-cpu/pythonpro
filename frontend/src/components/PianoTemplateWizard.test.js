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

/** Porta il wizard dal passo 1 al passo 2 (fondo fapi + anno 2026 + avviso + template consigliato). */
async function arrivaAllAnteprima() {
  fireEvent.change(screen.getByLabelText(/fondo/i), { target: { value: 'fapi' } });
  fireEvent.change(screen.getByLabelText(/^anno/i), { target: { value: '2026' } });
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

  test('naviga i 3 passi: selezione (con anno), anteprima, conferma (e torna indietro)', async () => {
    render(<PianoTemplateWizard availableProjects={progetti} onClose={jest.fn()} />);

    // Passo 1 — selezione: anno vive qui (I1)
    expect(screen.getByText(/passo 1 di 3/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^anno/i)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/fondo/i), { target: { value: 'fapi' } });
    fireEvent.change(screen.getByLabelText(/^anno/i), { target: { value: '2026' } });

    await waitFor(() => expect(getPianoTemplates).toHaveBeenCalledWith({ tipo_fondo: 'fapi' }));
    const radioTemplate = await screen.findByRole('radio', { name: /template fapi generico/i });
    // M4 — hint finché nessun template è selezionato
    expect(screen.getByText('Seleziona un template per proseguire')).toBeInTheDocument();
    fireEvent.click(radioTemplate);
    expect(screen.queryByText('Seleziona un template per proseguire')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /avanti/i }));

    // Passo 2 — anteprima
    expect(await screen.findByText(/passo 2 di 3/i)).toBeInTheDocument();
    await waitFor(() => expect(getPianoTemplateAnteprima).toHaveBeenCalled());
    expect(await screen.findByText('B.2')).toBeInTheDocument();
    expect(screen.getByText('Docenza')).toBeInTheDocument();
    expect(screen.getByText('Materiali didattici')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /avanti/i }));

    // Passo 3 — conferma: niente input anno (spostato al passo 1), solo recap
    expect(await screen.findByText(/passo 3 di 3/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/nome del piano/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/^anno/i)).not.toBeInTheDocument();
    expect(screen.getByText(/anno del piano/i)).toBeInTheDocument();
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

  test('I1: anteprima calcolata con l\'anno del passo 1 e ricalcolata quando cambia', async () => {
    render(<PianoTemplateWizard availableProjects={progetti} onClose={jest.fn()} />);
    await arrivaAllAnteprima();

    // Intestazione massimali con l'anno effettivamente usato
    expect(getPianoTemplateAnteprima).toHaveBeenLastCalledWith(4, { anno: 2026, avviso_id: 9 });
    expect(screen.getByText(/massimali applicati \(anno 2026\)/i)).toBeInTheDocument();

    // Torno al passo 1, cambio anno → rientrando al passo 2 l'anteprima è rifetchata
    fireEvent.click(screen.getByRole('button', { name: /indietro/i }));
    await screen.findByText(/passo 1 di 3/i);
    fireEvent.change(screen.getByLabelText(/^anno/i), { target: { value: '2027' } });
    fireEvent.click(screen.getByRole('button', { name: /avanti/i }));

    expect(await screen.findByText(/massimali applicati \(anno 2027\)/i)).toBeInTheDocument();
    expect(getPianoTemplateAnteprima).toHaveBeenLastCalledWith(4, { anno: 2027, avviso_id: 9 });
    expect(getPianoTemplateAnteprima).toHaveBeenCalledTimes(2);
  });

  test('I2: al passo 1 l\'overlay chiude il wizard', async () => {
    const onClose = jest.fn();
    const { container } = render(<PianoTemplateWizard availableProjects={progetti} onClose={onClose} />);
    await waitFor(() => expect(getAvvisi).toHaveBeenCalled());

    fireEvent.click(container.querySelector('.modal-overlay'));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  test('I2: dai passi 2-3 l\'overlay non chiude e ✕/Escape chiedono conferma', async () => {
    const onClose = jest.fn();
    const confirmSpy = jest.spyOn(window, 'confirm').mockReturnValue(false);
    const { container } = render(<PianoTemplateWizard availableProjects={progetti} onClose={onClose} />);
    await arrivaAllAnteprima();

    // Overlay al passo 2: nessuna chiusura, nessun confirm
    fireEvent.click(container.querySelector('.modal-overlay'));
    expect(onClose).not.toHaveBeenCalled();
    expect(confirmSpy).not.toHaveBeenCalled();
    expect(screen.getByText(/passo 2 di 3/i)).toBeInTheDocument();

    // ✕ al passo 2: confirm rifiutato → resta aperto
    fireEvent.click(screen.getByRole('button', { name: /chiudi wizard/i }));
    expect(confirmSpy).toHaveBeenCalledWith('Chiudere il wizard? Le selezioni andranno perse.');
    expect(onClose).not.toHaveBeenCalled();

    // Escape al passo 2: stessa logica (confirm rifiutato → resta aperto)
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(confirmSpy).toHaveBeenCalledTimes(2);
    expect(onClose).not.toHaveBeenCalled();

    // ✕ con confirm accettato → chiude
    confirmSpy.mockReturnValue(true);
    fireEvent.click(screen.getByRole('button', { name: /chiudi wizard/i }));
    expect(onClose).toHaveBeenCalledTimes(1);
    confirmSpy.mockRestore();
  });

  test('I3: errore nel caricamento avvisi visibile, con retry funzionante', async () => {
    getAvvisi.mockRejectedValueOnce(new Error('network down'));
    render(<PianoTemplateWizard availableProjects={progetti} onClose={jest.fn()} />);

    fireEvent.change(screen.getByLabelText(/fondo/i), { target: { value: 'fapi' } });
    expect(await screen.findByText(/impossibile caricare gli avvisi/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Riprova' }));
    expect(await screen.findByRole('option', { name: /avviso fapi 1\/2026/i })).toBeInTheDocument();
    expect(screen.queryByText(/impossibile caricare gli avvisi/i)).not.toBeInTheDocument();
    expect(getAvvisi).toHaveBeenCalledTimes(2);
  });

  test('I5: dialog accessibile, focus iniziale sul fondo, Escape chiude al passo 1', async () => {
    const onClose = jest.fn();
    render(<PianoTemplateWizard availableProjects={progetti} onClose={onClose} />);
    await waitFor(() => expect(getAvvisi).toHaveBeenCalled());

    const dialog = screen.getByRole('dialog', { name: /nuovo piano da template/i });
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    expect(screen.getByLabelText(/fondo/i)).toHaveFocus();

    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  test('M5: anteprima senza voci mostra il messaggio dedicato al posto della tabella', async () => {
    getPianoTemplateAnteprima.mockResolvedValue({ ...anteprima, voci: [] });
    render(<PianoTemplateWizard availableProjects={progetti} onClose={jest.fn()} />);

    fireEvent.change(screen.getByLabelText(/fondo/i), { target: { value: 'fapi' } });
    const radioTemplate = await screen.findByRole('radio', { name: /template fapi generico/i });
    fireEvent.click(radioTemplate);
    fireEvent.click(screen.getByRole('button', { name: /avanti/i }));

    expect(await screen.findByText('Il template non contiene voci.')).toBeInTheDocument();
  });

  test('M6: al passaggio 2→3 il nome vuoto viene precompilato con template e anno', async () => {
    render(<PianoTemplateWizard availableProjects={progetti} onClose={jest.fn()} />);
    await arrivaAllAnteprima();

    fireEvent.click(screen.getByRole('button', { name: /avanti/i }));
    await screen.findByText(/passo 3 di 3/i);
    expect(screen.getByLabelText(/nome del piano/i)).toHaveValue('Piano Template FAPI generico 2026');
  });

  test('conferma: submit chiama createFromTemplate col payload giusto e mostra il piano creato (I4)', async () => {
    render(<PianoTemplateWizard availableProjects={progetti} onClose={jest.fn()} />);
    await arrivaAllAnteprima();

    fireEvent.click(screen.getByRole('button', { name: /avanti/i }));
    await screen.findByText(/passo 3 di 3/i);

    fireEvent.change(screen.getByLabelText(/progetto/i), { target: { value: '5' } });
    fireEvent.change(screen.getByLabelText(/nome del piano/i), { target: { value: 'Piano da template' } });
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

    // I4 — frase esplicita con nome piano, anno e nome progetto
    const conferma = await screen.findByText(/è stato creato nel progetto/i);
    expect(conferma).toHaveTextContent('Piano da template');
    expect(conferma).toHaveTextContent('per l\'anno 2026');
    expect(conferma).toHaveTextContent('Progetto Alfa');
    // ID retrocesso a codice interno + nota sulla consultazione
    expect(screen.getByText('Codice interno: 77')).toBeInTheDocument();
    expect(screen.getByText(/non è consultabile da questa interfaccia/i)).toBeInTheDocument();
    // le voci del piano creato restano visibili
    expect(screen.getByText('B.2')).toBeInTheDocument();
    expect(screen.getByText('B.3')).toBeInTheDocument();
  });
});

describe('NEW-032: ereditarietà avviso dal progetto esplicitata in UI', () => {
  // Shape reale GET /projects (schemas.Project): avviso_id presente quando
  // il progetto è collegato a un avviso.
  const progettiConAvviso = [
    { id: 5, name: 'Progetto Alfa', avviso_id: 9 },
    { id: 6, name: 'Progetto Beta', avviso_id: null },
  ];

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

  /** Porta il wizard al passo 3 SENZA selezionare alcun avviso al passo 1. */
  async function arrivaAllaConfermaSenzaAvviso() {
    fireEvent.change(screen.getByLabelText(/fondo/i), { target: { value: 'fapi' } });
    fireEvent.change(screen.getByLabelText(/^anno/i), { target: { value: '2026' } });
    const radioTemplate = await screen.findByRole('radio', { name: /template fapi generico/i });
    fireEvent.click(radioTemplate);
    fireEvent.click(screen.getByRole('button', { name: /avanti/i }));
    await screen.findByText(/passo 2 di 3/i);
    fireEvent.click(screen.getByRole('button', { name: /avanti/i }));
    await screen.findByText(/passo 3 di 3/i);
  }

  test('nota ereditarietà visibile: nessun avviso scelto + progetto con avviso', async () => {
    render(<PianoTemplateWizard availableProjects={progettiConAvviso} onClose={jest.fn()} />);
    await arrivaAllaConfermaSenzaAvviso();

    fireEvent.change(screen.getByLabelText(/progetto/i), { target: { value: '5' } });
    const nota = screen.getByTestId('ptw-nota-ereditarieta-avviso');
    expect(nota).toHaveTextContent('Il progetto è collegato all\'avviso «Avviso FAPI 1/2026»');
    expect(nota).toHaveTextContent('il piano erediterà l\'avviso e le sue regole validate');
  });

  test('nota assente: progetto senza avviso', async () => {
    render(<PianoTemplateWizard availableProjects={progettiConAvviso} onClose={jest.fn()} />);
    await arrivaAllaConfermaSenzaAvviso();

    fireEvent.change(screen.getByLabelText(/progetto/i), { target: { value: '6' } });
    expect(screen.queryByTestId('ptw-nota-ereditarieta-avviso')).not.toBeInTheDocument();
  });

  test('nota assente: avviso scelto esplicitamente al passo 1', async () => {
    render(<PianoTemplateWizard availableProjects={progettiConAvviso} onClose={jest.fn()} />);
    await arrivaAllAnteprima();
    fireEvent.click(screen.getByRole('button', { name: /avanti/i }));
    await screen.findByText(/passo 3 di 3/i);

    fireEvent.change(screen.getByLabelText(/progetto/i), { target: { value: '5' } });
    expect(screen.queryByTestId('ptw-nota-ereditarieta-avviso')).not.toBeInTheDocument();
  });

  test('vista finale: avviso effettivo del piano (ereditato) risolto dal titolo', async () => {
    createPianoFinanziarioFromTemplate.mockResolvedValue({ ...pianoCreato, avviso_pf_id: 9 });
    render(<PianoTemplateWizard availableProjects={progettiConAvviso} onClose={jest.fn()} />);
    await arrivaAllaConfermaSenzaAvviso();

    fireEvent.change(screen.getByLabelText(/progetto/i), { target: { value: '5' } });
    fireEvent.change(screen.getByLabelText(/nome del piano/i), { target: { value: 'Piano da template' } });
    fireEvent.click(screen.getByRole('button', { name: /crea piano/i }));

    const riga = await screen.findByTestId('ptw-avviso-piano-creato');
    expect(riga).toHaveTextContent('Avviso del piano: «Avviso FAPI 1/2026»');
    expect(riga).toHaveTextContent('(ereditato dal progetto)');
  });

  test('vista finale: avviso scelto esplicitamente mostrato senza "(ereditato)"', async () => {
    createPianoFinanziarioFromTemplate.mockResolvedValue({ ...pianoCreato, avviso_pf_id: 9 });
    render(<PianoTemplateWizard availableProjects={progettiConAvviso} onClose={jest.fn()} />);
    await arrivaAllAnteprima();
    fireEvent.click(screen.getByRole('button', { name: /avanti/i }));
    await screen.findByText(/passo 3 di 3/i);

    fireEvent.change(screen.getByLabelText(/progetto/i), { target: { value: '5' } });
    fireEvent.change(screen.getByLabelText(/nome del piano/i), { target: { value: 'Piano da template' } });
    fireEvent.click(screen.getByRole('button', { name: /crea piano/i }));

    const riga = await screen.findByTestId('ptw-avviso-piano-creato');
    expect(riga).toHaveTextContent('Avviso del piano: «Avviso FAPI 1/2026»');
    expect(riga).not.toHaveTextContent('(ereditato dal progetto)');
  });

  test('vista finale: avviso non risolvibile → fallback "avviso #id"', async () => {
    createPianoFinanziarioFromTemplate.mockResolvedValue({ ...pianoCreato, avviso_pf_id: 123 });
    render(<PianoTemplateWizard availableProjects={progettiConAvviso} onClose={jest.fn()} />);
    await arrivaAllaConfermaSenzaAvviso();

    fireEvent.change(screen.getByLabelText(/progetto/i), { target: { value: '6' } });
    fireEvent.change(screen.getByLabelText(/nome del piano/i), { target: { value: 'Piano da template' } });
    fireEvent.click(screen.getByRole('button', { name: /crea piano/i }));

    const riga = await screen.findByTestId('ptw-avviso-piano-creato');
    expect(riga).toHaveTextContent('Avviso del piano: «avviso #123»');
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
