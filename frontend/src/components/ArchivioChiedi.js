import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { getAvvisi, searchArchivio, chiediArchivio } from '../services/apiService';
import './ArchivioChiedi.css';

// Fondi allineati al wizard piano e a ResourceArchive (FONDI).
const FONDI = [
  { value: '', label: 'Tutti i fondi' },
  { value: 'fondimpresa', label: 'Fondimpresa' },
  { value: 'formazienda', label: 'Formazienda' },
  { value: 'fapi', label: 'FAPI' },
  { value: 'regionale', label: 'Regionale' },
  { value: 'altro', label: 'Altro' },
];

const FONTE_LABEL = {
  regola: 'Regola validata',
  conoscenza: 'Conoscenza operativa',
  esito: 'Esito / decisione',
};

const errorDetail = (error, fallback) => {
  const detail = error?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map((item) => item.msg).filter(Boolean).join(' · ') || fallback;
  return error?.message ? `${fallback} (${error.message})` : fallback;
};

/**
 * Citazione/risultato cliccabile. Il click delega al parent (App) la
 * navigazione verso la vista avviso: passiamo avviso_id + i riferimenti
 * disponibili (revisione, regola, articolo). Vedi limite documentato in
 * ArchivioChiedi/App: la vista avvisi seleziona l'avviso, non ancora la
 * singola regola.
 */
function Citazione({ item, evidenza, onOpen }) {
  const meta = {
    revisioneId: item.revisione_id ?? null,
    regolaId: item.regola_id ?? null,
    conoscenzaId: item.conoscenza_id ?? null,
    esitoId: item.esito_id ?? null,
    riferimentoArticolo: item.riferimento_articolo ?? null,
  };
  const label = item.riferimento_articolo
    ? `${item.avviso_titolo} · ${item.riferimento_articolo}`
    : item.avviso_titolo;

  return (
    <button
      type="button"
      className={`archivio-cite ${evidenza ? 'evidenza' : ''}`}
      onClick={() => onOpen(item.avviso_id, meta)}
      aria-label={label}
      title="Apri l'avviso citato"
    >
      <span className="archivio-cite-head">
        <span className="archivio-cite-title">{item.avviso_titolo}</span>
        <span className="archivio-cite-fonte">{FONTE_LABEL[item.fonte] || 'Fonte archivio'}</span>
      </span>
      {item.riferimento_articolo ? (
        <span className="archivio-cite-ref">{item.riferimento_articolo}</span>
      ) : null}
      <span className="archivio-cite-estratto">{item.estratto}</span>
    </button>
  );
}

export default function ArchivioChiedi({ currentUser = null, onOpenAvviso = null }) {
  const [mode, setMode] = useState('chiedi'); // 'chiedi' | 'search'
  const [avvisi, setAvvisi] = useState([]);
  const [fondo, setFondo] = useState('');
  const [avvisoId, setAvvisoId] = useState('');

  const [domanda, setDomanda] = useState('');
  const [query, setQuery] = useState('');

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [chiediResult, setChiediResult] = useState(null);
  const [searchResults, setSearchResults] = useState(null);

  useEffect(() => {
    let alive = true;
    getAvvisi({ limit: 1000 })
      .then((data) => { if (alive) setAvvisi(Array.isArray(data) ? data : []); })
      .catch(() => { if (alive) setAvvisi([]); });
    return () => { alive = false; };
  }, []);

  // Avvisi selezionabili nel filtro, ristretti al fondo scelto.
  const avvisiFiltrati = useMemo(() => (
    fondo ? avvisi.filter((a) => a.fondo === fondo) : avvisi
  ), [avvisi, fondo]);

  // Se cambio fondo e l'avviso selezionato non appartiene più al fondo, azzero.
  useEffect(() => {
    if (avvisoId && !avvisiFiltrati.some((a) => String(a.id) === String(avvisoId))) {
      setAvvisoId('');
    }
  }, [avvisiFiltrati, avvisoId]);

  const openAvviso = useCallback((id, meta) => {
    if (onOpenAvviso) onOpenAvviso(id, meta);
  }, [onOpenAvviso]);

  const handleChiedi = async (event) => {
    event.preventDefault();
    if (!domanda.trim() || loading) return;
    setLoading(true);
    setError('');
    setChiediResult(null);
    try {
      const result = await chiediArchivio({
        domanda: domanda.trim(),
        avvisoId: avvisoId ? Number(avvisoId) : undefined,
        tipoFondo: fondo || undefined,
      });
      setChiediResult(result);
    } catch (err) {
      setError(errorDetail(err, 'Richiesta all’archivio non riuscita.'));
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = async (event) => {
    event.preventDefault();
    if (!query.trim() || loading) return;
    setLoading(true);
    setError('');
    setSearchResults(null);
    try {
      const results = await searchArchivio(query.trim(), {
        avvisoId: avvisoId ? Number(avvisoId) : undefined,
        tipoFondo: fondo || undefined,
      });
      setSearchResults(Array.isArray(results) ? results : []);
    } catch (err) {
      setError(errorDetail(err, 'Ricerca nell’archivio non riuscita.'));
    } finally {
      setLoading(false);
    }
  };

  const switchMode = (next) => {
    setMode(next);
    setError('');
  };

  const filtri = (
    <div className="archivio-filtri">
      <label>
        <span>Fondo</span>
        <select aria-label="Filtro fondo" value={fondo} onChange={(e) => setFondo(e.target.value)}>
          {FONDI.map((f) => <option key={f.value || 'all'} value={f.value}>{f.label}</option>)}
        </select>
      </label>
      <label>
        <span>Avviso</span>
        <select aria-label="Filtro avviso" value={avvisoId} onChange={(e) => setAvvisoId(e.target.value)}>
          <option value="">Tutti gli avvisi</option>
          {avvisiFiltrati.map((a) => (
            <option key={a.id} value={a.id}>{a.titolo || `Avviso ${a.codice}`}</option>
          ))}
        </select>
      </label>
    </div>
  );

  return (
    <div className="archivio-page">
      <section className="archivio-hero">
        <div>
          <span className="archivio-eyebrow">Archivio normativo</span>
          <h2>Chiedi all’archivio</h2>
          <p>
            Interroga le regole validate, la conoscenza operativa e gli esiti registrati.
            Ogni risposta cita la fonte: clicca una citazione per aprire l’avviso.
          </p>
        </div>
      </section>

      <p className="archivio-disclaimer" role="note">
        Risposta assistita: fa fede il testo dell’avviso.
      </p>

      <div className="archivio-modes" role="tablist" aria-label="Modalità di consultazione">
        <button
          type="button"
          role="tab"
          aria-selected={mode === 'chiedi'}
          className={`archivio-mode ${mode === 'chiedi' ? 'active' : ''}`}
          onClick={() => switchMode('chiedi')}
        >
          Chiedi
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={mode === 'search'}
          className={`archivio-mode ${mode === 'search' ? 'active' : ''}`}
          onClick={() => switchMode('search')}
        >
          Cerca
        </button>
      </div>

      {error ? <div className="archivio-alert error" role="alert">{error}</div> : null}

      {mode === 'chiedi' ? (
        <form className="archivio-form" onSubmit={handleChiedi}>
          <label className="archivio-field">
            <span>Domanda</span>
            <textarea
              aria-label="Domanda"
              rows={3}
              value={domanda}
              onChange={(e) => setDomanda(e.target.value)}
              placeholder="Es. Qual è il massimale per impresa nell’avviso FAPI 1/2026?"
            />
          </label>
          {filtri}
          <button type="submit" className="archivio-button primary" disabled={loading || !domanda.trim()}>
            {loading ? 'Sto interrogando l’archivio…' : 'Invia domanda'}
          </button>
        </form>
      ) : (
        <form className="archivio-form" onSubmit={handleSearch}>
          <label className="archivio-field">
            <span>Testo da cercare</span>
            <input
              aria-label="Testo da cercare"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Parole chiave: massimale, scadenza, beneficiari…"
            />
          </label>
          {filtri}
          <button type="submit" className="archivio-button primary" disabled={loading || !query.trim()}>
            {loading ? 'Ricerca in corso…' : 'Avvia ricerca'}
          </button>
        </form>
      )}

      {/* ─── Esiti modalità CHIEDI ─── */}
      {mode === 'chiedi' && chiediResult ? (
        <section className="archivio-esito" aria-live="polite">
          {chiediResult.stato === 'ok' ? (
            <>
              <div className="archivio-risposta">
                <h3>Risposta</h3>
                <p>{chiediResult.risposta}</p>
              </div>
              {chiediResult.citazioni?.length ? (
                <div className="archivio-citazioni">
                  <h4>Fonti citate</h4>
                  <div className="archivio-cite-list">
                    {chiediResult.citazioni.map((c, i) => (
                      <Citazione key={`cit-${i}`} item={c} evidenza onOpen={openAvviso} />
                    ))}
                  </div>
                </div>
              ) : null}
            </>
          ) : null}

          {chiediResult.stato === 'degradato' ? (
            <div className="archivio-degradato">
              <div className="archivio-banner warning" role="status">
                <strong>AI non disponibile — risultati di sola ricerca.</strong>
                <span>La sintesi assistita non è disponibile: sotto trovi i passaggi trovati nell’archivio.</span>
              </div>
              <ResultsList items={chiediResult.risultati} onOpen={openAvviso} />
            </div>
          ) : null}

          {chiediResult.stato === 'non_presente' ? (
            <div className="archivio-banner neutral" role="status">
              <strong>Non presente in archivio.</strong>
              <span>Nessun passaggio dell’archivio risponde alla domanda. Verifica i filtri o carica l’avviso.</span>
            </div>
          ) : null}
        </section>
      ) : null}

      {/* ─── Esiti modalità CERCA ─── */}
      {mode === 'search' && searchResults ? (
        <section className="archivio-esito" aria-live="polite">
          <h3>Risultati ({searchResults.length})</h3>
          <ResultsList items={searchResults} onOpen={openAvviso} />
        </section>
      ) : null}
    </div>
  );
}

function ResultsList({ items, onOpen }) {
  if (!items || items.length === 0) {
    return <div className="archivio-empty">Nessun risultato in archivio.</div>;
  }
  return (
    <div className="archivio-cite-list">
      {items.map((r, i) => (
        <Citazione key={`res-${i}`} item={r} onOpen={onOpen} />
      ))}
    </div>
  );
}
