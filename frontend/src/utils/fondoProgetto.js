/**
 * Rilevamento fondo condiviso: unico punto che calcola "e' un progetto FAPI?"
 * invece della stessa logica reimplementata in piu' componenti.
 */

export function fundKey(project) {
  return String(project?.ente_erogatore || '').trim().toLowerCase();
}

export function isFapiProject(project) {
  return fundKey(project) === 'fapi' || Boolean(project?.codice_fapi);
}

// Il backend e' la fonte autorevole (project.fund_config, calcolato da
// atto_concessorio_registry.py e servito su ogni risposta progetto). Questo
// fallback copre solo i casi in cui l'oggetto progetto non arriva ancora
// dall'API — fixture di test, stato locale transitorio — con le stesse
// chiavi/valori del registry backend: non e' una seconda fonte di verita'
// in produzione, e' resilienza per quando quella fonte non e' disponibile.
const FALLBACK_FUND_CONFIG = {
  fapi: {
    etichetta_atto: 'Convenzione',
    etichetta_formulario: 'Formulario',
    etichetta_piano_finanziario: 'Piano Finanziario',
    etichetta_codice_progetto: 'Codice FAPI',
  },
  fondimpresa: {
    etichetta_atto: 'Lettera di ammissione',
    etichetta_formulario: 'Formulario',
    etichetta_piano_finanziario: 'Excel Riepilogo',
    etichetta_codice_progetto: 'Codice pratica Fondimpresa',
  },
  formazienda: {
    etichetta_atto: 'Atto di adesione (Allegato E)',
    etichetta_formulario: 'Formulario (Allegato A)',
    etichetta_piano_finanziario: 'Piano Fin.',
    etichetta_codice_progetto: 'Codice pratica Formazienda',
  },
};

const DEFAULT_FUND_CONFIG = {
  etichetta_atto: 'Convenzione',
  etichetta_formulario: 'Formulario',
  etichetta_piano_finanziario: 'Piano finanziario',
  etichetta_codice_progetto: 'Codice progetto',
};

export function resolveFundConfig(project) {
  if (project?.fund_config) return project.fund_config;
  return FALLBACK_FUND_CONFIG[fundKey(project)] || DEFAULT_FUND_CONFIG;
}
