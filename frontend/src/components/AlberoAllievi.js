import React, { useMemo, useState } from 'react';

import './AlberoAllievi.css';

/**
 * UX-9 — allievi raggruppati per azienda.
 *
 * Lo stesso albero serve due scopi: scegliere chi entra nel progetto (con
 * `onChange`) e leggere chi c'e' gia' (senza). Il raggruppamento arriva da
 * `Allievo.azienda_cliente_id`, che l'API espone gia' dentro
 * `allievi_coinvolti` (UX-7): nessuna seconda chiamata.
 *
 * Regola di dominio, non di interfaccia: un allievo su un progetto implica la
 * sua azienda sul progetto. Il verso opposto non vale — un'azienda puo' essere
 * coinvolta senza che nessuno dei suoi sia ancora iscritto. Lo stesso vincolo
 * lo applica il backend quando si stacca (UX-8: l'azienda con suoi allievi
 * associati non si dissocia).
 */

export const SENZA_AZIENDA = 'senza-azienda';

const nomeAllievo = (allievo) => `${allievo.nome || ''} ${allievo.cognome || ''}`.trim();

export function raggruppaPerAzienda(aziende = [], allievi = []) {
  const perAzienda = new Map(
    (aziende || []).map((azienda) => [Number(azienda.id), { ...azienda, id: Number(azienda.id), allievi: [] }]),
  );
  const orfani = [];

  (allievi || []).forEach((allievo) => {
    const gruppo = perAzienda.get(Number(allievo.azienda_cliente_id));
    if (gruppo) {
      gruppo.allievi.push(allievo);
    } else {
      orfani.push(allievo);
    }
  });

  const gruppi = Array.from(perAzienda.values());
  if (orfani.length > 0) {
    gruppi.push({ id: SENZA_AZIENDA, ragione_sociale: 'Allievi senza azienda', allievi: orfani });
  }
  return gruppi;
}

const contiene = (testo, cerca) => (testo || '').toLowerCase().includes(cerca);

const AlberoAllievi = ({
  aziende = [],
  allievi = [],
  aziendeSelezionate = [],
  allieviSelezionati = [],
  onChange,
  troncato = false,
  renderAzioneAzienda,
  renderAzioneAllievo,
}) => {
  const [ricerca, setRicerca] = useState('');

  const selezionabile = typeof onChange === 'function';
  const aziendeIds = useMemo(() => aziendeSelezionate.map(Number), [aziendeSelezionate]);
  const allieviIds = useMemo(() => allieviSelezionati.map(Number), [allieviSelezionati]);

  const gruppi = useMemo(() => {
    const tutti = raggruppaPerAzienda(aziende, allievi);
    // In lettura l'albero mostra gli associati, non il catalogo intero.
    const visibili = selezionabile
      ? tutti
      : tutti
        .map((g) => ({ ...g, allievi: g.allievi.filter((a) => allieviIds.includes(Number(a.id))) }))
        .filter((g) => aziendeIds.includes(g.id) || g.allievi.length > 0);

    const cerca = ricerca.trim().toLowerCase();
    if (!cerca) return visibili;

    return visibili
      .map((g) => (
        contiene(g.ragione_sociale, cerca)
          ? g
          : { ...g, allievi: g.allievi.filter((a) => contiene(nomeAllievo(a), cerca)) }
      ))
      .filter((g) => contiene(g.ragione_sociale, cerca) || g.allievi.length > 0);
  }, [aziende, allievi, selezionabile, aziendeIds, allieviIds, ricerca]);

  const emetti = (azienda_ids, allievo_ids) => onChange({ azienda_ids, allievo_ids });

  const toggleAzienda = (gruppo) => {
    const idsSuoi = gruppo.allievi.map((a) => Number(a.id));
    const attiva = aziendeIds.includes(gruppo.id);

    if (attiva) {
      emetti(
        aziendeIds.filter((id) => id !== gruppo.id),
        allieviIds.filter((id) => !idsSuoi.includes(id)),
      );
      return;
    }
    emetti(
      gruppo.id === SENZA_AZIENDA ? aziendeIds : [...aziendeIds, gruppo.id],
      [...allieviIds, ...idsSuoi.filter((id) => !allieviIds.includes(id))],
    );
  };

  const toggleAllievo = (gruppo, allievo) => {
    const id = Number(allievo.id);
    if (allieviIds.includes(id)) {
      // Togliere l'ultimo allievo non stacca l'azienda: restare coinvolti
      // senza iscritti e' uno stato legittimo del dominio.
      emetti(aziendeIds, allieviIds.filter((altro) => altro !== id));
      return;
    }
    const azienda_ids = gruppo.id !== SENZA_AZIENDA && !aziendeIds.includes(gruppo.id)
      ? [...aziendeIds, gruppo.id]
      : aziendeIds;
    emetti(azienda_ids, [...allieviIds, id]);
  };

  const statoGruppo = (gruppo) => {
    const suoi = gruppo.allievi.map((a) => Number(a.id));
    const scelti = suoi.filter((id) => allieviIds.includes(id));
    const attiva = gruppo.id === SENZA_AZIENDA
      ? scelti.length > 0
      : aziendeIds.includes(gruppo.id);
    return {
      attiva,
      scelti: scelti.length,
      totali: suoi.length,
      parziale: attiva && suoi.length > 0 && scelti.length > 0 && scelti.length < suoi.length,
    };
  };

  return (
    <div className="albero-allievi">
      <label className="albero-ricerca">
        Cerca azienda o allievo
        <input
          type="search"
          value={ricerca}
          onChange={(e) => setRicerca(e.target.value)}
        />
      </label>

      {troncato && (
        <p className="albero-troncato" role="status">
          Elenco parziale: non tutti gli allievi sono stati caricati.
        </p>
      )}

      {gruppi.length === 0 ? (
        <p className="albero-vuoto">Nessun risultato</p>
      ) : gruppi.map((gruppo) => {
        const stato = statoGruppo(gruppo);
        return (
          <div
            className="albero-gruppo"
            key={gruppo.id}
            role="group"
            aria-label={gruppo.ragione_sociale}
          >
            <div className="albero-azienda">
              {selezionabile ? (
                <label>
                  <input
                    type="checkbox"
                    checked={stato.attiva}
                    ref={(el) => { if (el) el.indeterminate = stato.parziale; }}
                    onChange={() => toggleAzienda(gruppo)}
                  />
                  {gruppo.ragione_sociale}
                </label>
              ) : (
                <span className="albero-azienda-nome">{gruppo.ragione_sociale}</span>
              )}
              {stato.totali > 0 && (
                <span className="albero-conteggio">
                  {selezionabile
                    ? `${stato.scelti} di ${stato.totali} allievi`
                    : `${stato.totali} allievi`}
                </span>
              )}
              {gruppo.id !== SENZA_AZIENDA && renderAzioneAzienda && renderAzioneAzienda(gruppo)}
            </div>

            <ul className="albero-allievi-elenco">
              {gruppo.allievi.map((allievo) => (
                <li key={allievo.id}>
                  {selezionabile ? (
                    <label>
                      <input
                        type="checkbox"
                        checked={allieviIds.includes(Number(allievo.id))}
                        onChange={() => toggleAllievo(gruppo, allievo)}
                      />
                      {nomeAllievo(allievo)}
                    </label>
                  ) : (
                    <span>{nomeAllievo(allievo)}</span>
                  )}
                  {renderAzioneAllievo && renderAzioneAllievo(allievo)}
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </div>
  );
};

export default AlberoAllievi;
