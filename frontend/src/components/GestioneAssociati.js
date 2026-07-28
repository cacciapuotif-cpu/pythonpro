import React, { useState } from 'react';

import AlberoAllievi from './AlberoAllievi';
import { canPerform, isAdminRole } from '../auth/permissions';
import { formatApiError } from '../lib/errors';
import {
  dissociaAllievoDaProgetto,
  dissociaAziendaDaProgetto,
} from '../services/apiService';

/**
 * UX-8 — staccare un'azienda o un allievo dal progetto.
 *
 * Le guardie stanno nel backend (`services/dissociazione_progetto.py`): qui si
 * rende leggibile il suo rifiuto. Il 409 porta `blocchi` gia' in italiano e un
 * `forzabile` calcolato su TUTTI i blocchi; la forzatura si propone solo se il
 * backend la ammette e chi guarda e' admin — l'operatore riceverebbe comunque
 * un 403.
 */

export const MOTIVO_MIN = 10;

export const motivoValido = (motivo) => (motivo || '').trim().length >= MOTIVO_MIN;

const nomeAllievo = (allievo) => `${allievo.nome} ${allievo.cognome}`.trim();

const dettaglioConflitto = (error) => {
  if (error?.response?.status !== 409) return null;
  const detail = error.response.data?.detail;
  return detail?.errore === 'dissociazione_bloccata' ? detail : null;
};

const GestioneAssociati = ({ project, currentUser, onChange }) => {
  const [bersaglio, setBersaglio] = useState(null);
  const [conflitto, setConflitto] = useState(null);
  const [errore, setErrore] = useState('');
  const [motivo, setMotivo] = useState('');
  const [inCorso, setInCorso] = useState(false);

  const puoStaccare = canPerform(currentUser, 'WRITE_PROJECTS');
  const puoForzare = isAdminRole(currentUser);

  const aziende = project?.aziende_coinvolte || [];
  const allievi = project?.allievi_coinvolti || [];

  const chiudi = () => {
    setBersaglio(null);
    setConflitto(null);
    setErrore('');
    setMotivo('');
  };

  const apri = (tipo, entita, nome) => {
    setBersaglio({ tipo, id: entita.id, nome });
    setConflitto(null);
    setErrore('');
    setMotivo('');
  };

  const dissocia = async (payload) => {
    const chiamata = bersaglio.tipo === 'allievo'
      ? dissociaAllievoDaProgetto
      : dissociaAziendaDaProgetto;

    setInCorso(true);
    try {
      await chiamata(project.id, bersaglio.id, payload);
      chiudi();
      if (onChange) onChange();
    } catch (err) {
      const dettaglio = dettaglioConflitto(err);
      setConflitto(dettaglio);
      setErrore(dettaglio ? '' : formatApiError(err));
    } finally {
      setInCorso(false);
    }
  };

  const forzaOfferta = Boolean(conflitto?.forzabile) && puoForzare;

  const bottoneStacca = (tipo, entita, nome) => (puoStaccare ? (
    <button
      type="button"
      className="associato-stacca"
      onClick={() => apri(tipo, entita, nome)}
    >
      {`Stacca ${nome}`}
    </button>
  ) : null);

  return (
    <section className="gestione-associati">
      <h4>Associazioni del progetto</h4>

      {aziende.length === 0 && allievi.length === 0 ? (
        <p className="associati-vuoto">Nessuna azienda o allievo associato</p>
      ) : (
        <AlberoAllievi
          aziende={aziende}
          allievi={allievi}
          aziendeSelezionate={aziende.map((a) => a.id)}
          allieviSelezionati={allievi.map((a) => a.id)}
          renderAzioneAzienda={(azienda) => bottoneStacca('azienda', azienda, azienda.ragione_sociale)}
          renderAzioneAllievo={(allievo) => bottoneStacca('allievo', allievo, nomeAllievo(allievo))}
        />
      )}

      {bersaglio && (
        <div className="modal-overlay" onClick={chiudi}>
          <div className="confirm-modal dissociazione-modal" onClick={(e) => e.stopPropagation()}>
            <h3>Stacca dal progetto</h3>
            <p>{`${bersaglio.nome} verra' staccato da questo progetto.`}</p>

            {conflitto && (
              <div className="dissociazione-blocchi" role="alert">
                <p className="dissociazione-blocchi-titolo">Il backend ha rifiutato la dissociazione:</p>
                <ul>
                  {conflitto.blocchi.map((blocco) => (
                    <li key={blocco.codice}>{blocco.messaggio}</li>
                  ))}
                </ul>
                {!conflitto.forzabile && (
                  <p className="dissociazione-nota">Questo blocco non e' superabile.</p>
                )}
                {conflitto.forzabile && !puoForzare && (
                  <p className="dissociazione-nota">
                    Il blocco e' superabile, ma solo un amministratore puo' forzare la dissociazione.
                  </p>
                )}
              </div>
            )}

            {errore && <p className="dissociazione-errore" role="alert">{errore}</p>}

            {forzaOfferta && (
              <div className="dissociazione-forzatura">
                <label htmlFor="dissociazione-motivo">
                  {`Motivo della forzatura (almeno ${MOTIVO_MIN} caratteri, finisce in audit)`}
                </label>
                <textarea
                  id="dissociazione-motivo"
                  value={motivo}
                  onChange={(e) => setMotivo(e.target.value)}
                  rows={3}
                />
              </div>
            )}

            <div className="modal-buttons">
              <button type="button" className="cancel-button" onClick={chiudi}>
                {conflitto || errore ? 'Chiudi' : 'Annulla'}
              </button>

              {!conflitto && !errore && (
                <button
                  type="button"
                  className="delete-button"
                  disabled={inCorso}
                  onClick={() => dissocia(undefined)}
                >
                  Conferma dissociazione
                </button>
              )}

              {forzaOfferta && (
                <button
                  type="button"
                  className="delete-button"
                  disabled={inCorso || !motivoValido(motivo)}
                  onClick={() => dissocia({ forza: true, motivo: motivo.trim() })}
                >
                  Forza dissociazione
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </section>
  );
};

export default GestioneAssociati;
