/**
 * UX-7 — riepilogo degli associati nella scheda progetto.
 *
 * La scheda leggeva gia' `aziende_coinvolte` / `allievi_coinvolti`: il bug
 * viveva nello schema di risposta, che non li restituiva. Qui si blocca il
 * contratto di rendering, incluso il conteggio richiesto da UX-7d.
 */

import {
  riepilogoAssociati,
  riepilogoSediDelivery,
  NOMI_ASSOCIATI_MOSTRATI,
} from './ProjectManager';

const azienda = (ragione_sociale) => ({ ragione_sociale });
const nomeAzienda = (a) => a.ragione_sociale;

test('senza associati resta il messaggio di vuoto', () => {
  expect(riepilogoAssociati([], nomeAzienda, 'Nessuna azienda associata'))
    .toBe('Nessuna azienda associata');
});

test('un campo assente non viene scambiato per elenco vuoto renderizzabile', () => {
  expect(riepilogoAssociati(undefined, nomeAzienda, 'Nessuna azienda associata'))
    .toBe('Nessuna azienda associata');
  expect(riepilogoAssociati(null, nomeAzienda, 'Nessuna azienda associata'))
    .toBe('Nessuna azienda associata');
});

test('il conteggio precede i nomi', () => {
  const elenco = [azienda('Alfa Srl'), azienda('Beta Spa')];
  expect(riepilogoAssociati(elenco, nomeAzienda, 'vuoto'))
    .toBe('2 — Alfa Srl, Beta Spa');
});

test('oltre la soglia i nomi si troncano ma il totale resta esatto', () => {
  const elenco = Array.from({ length: 12 }, (_, i) => azienda(`Az ${i + 1}`));
  const testo = riepilogoAssociati(elenco, nomeAzienda, 'vuoto');

  expect(testo.startsWith('12 — ')).toBe(true);
  expect(testo).toContain(`Az ${NOMI_ASSOCIATI_MOSTRATI}`);
  expect(testo).not.toContain(`Az ${NOMI_ASSOCIATI_MOSTRATI + 1},`);
  expect(testo).toContain(`e altri ${12 - NOMI_ASSOCIATI_MOSTRATI}`);
});

test('esattamente alla soglia non compare la coda', () => {
  const elenco = Array.from({ length: NOMI_ASSOCIATI_MOSTRATI }, (_, i) => azienda(`Az ${i + 1}`));
  expect(riepilogoAssociati(elenco, nomeAzienda, 'vuoto')).not.toContain('e altri');
});

test('gli allievi si compongono nome e cognome', () => {
  const elenco = [{ nome: 'Ada', cognome: 'Rossi' }, { nome: 'Bruno', cognome: 'Verdi' }];
  expect(riepilogoAssociati(elenco, (a) => `${a.nome} ${a.cognome}`, 'vuoto'))
    .toBe('2 — Ada Rossi, Bruno Verdi');
});

describe('riepilogoSediDelivery', () => {
  test('nessuna azienda: zero su zero', () => {
    expect(riepilogoSediDelivery([])).toEqual({ definite: 0, totale: 0 });
    expect(riepilogoSediDelivery(undefined)).toEqual({ definite: 0, totale: 0 });
    expect(riepilogoSediDelivery(null)).toEqual({ definite: 0, totale: 0 });
  });

  test('nessuna sede definita su nessuna delle aziende', () => {
    const aziende = [
      { azienda_id: 1, sedi: [] },
      { azienda_id: 2, sedi: [] },
    ];
    expect(riepilogoSediDelivery(aziende)).toEqual({ definite: 0, totale: 2 });
  });

  test('conta solo le aziende con almeno una sede definita', () => {
    const aziende = [
      { azienda_id: 1, sedi: [{ sede_label: 'Via Roma 1' }] },
      { azienda_id: 2, sedi: [] },
      { azienda_id: 3, sedi: [{ sede_label: 'Via Milano 2' }, { sede_label: 'Via Torino 3' }] },
    ];
    expect(riepilogoSediDelivery(aziende)).toEqual({ definite: 2, totale: 3 });
  });

  test('tutte le sedi definite', () => {
    const aziende = [
      { azienda_id: 1, sedi: [{ sede_label: 'Via Roma 1' }] },
      { azienda_id: 2, sedi: [{ sede_label: 'Via Napoli 4' }] },
    ];
    expect(riepilogoSediDelivery(aziende)).toEqual({ definite: 2, totale: 2 });
  });
});

// mostraDocumentiFondo e' stata rimossa insieme al gate che rappresentava:
// la sezione documenti (FapiUploadSection) e Moduli Formativi ora montano
// sempre, per qualunque fondo (incluso uno non censito) — non c'e' piu'
// una funzione di visibilita' da testare qui. La copertura sul
// comportamento per fondo (quali pulsanti/etichette compaiono, il fallback
// per un fondo sconosciuto) vive in FapiUpload.test.js, dove risiede la
// logica (FUND_DOCUMENT_MODALS/resolveFundConfig).
