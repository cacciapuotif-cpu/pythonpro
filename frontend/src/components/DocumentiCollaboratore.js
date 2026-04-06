import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  getDocumentiCollaboratore,
  getDocumentiMancantiCollaboratore,
  rifiutaDocumentoRichiesto,
  uploadDocumentoRichiesto,
  validaDocumentoRichiesto,
} from '../services/apiService';

const STATUS_META = {
  richiesto: { label: 'Richiesto', color: '#92400e', background: '#fef3c7' },
  caricato: { label: 'Caricato', color: '#1d4ed8', background: '#dbeafe' },
  validato: { label: 'Validato', color: '#166534', background: '#dcfce7' },
  rifiutato: { label: 'Rifiutato', color: '#991b1b', background: '#fee2e2' },
  scaduto: { label: 'Scaduto', color: '#991b1b', background: '#fecaca' },
};

const FILTER_OPTIONS = [
  { value: '', label: 'Tutti gli stati' },
  { value: 'richiesto', label: 'Richiesti' },
  { value: 'caricato', label: 'Caricati' },
  { value: 'validato', label: 'Validati' },
  { value: 'rifiutato', label: 'Rifiutati' },
  { value: 'scaduto', label: 'Scaduti' },
  { value: '__mancanti__', label: 'Mancanti / Scaduti' },
];

const wrapStyle = {
  background: '#ffffff',
  border: '1px solid #dbe4f0',
  borderRadius: '20px',
  boxShadow: '0 18px 40px rgba(15, 23, 42, 0.06)',
  padding: '1.25rem',
};

const headerStyle = {
  display: 'flex',
  justifyContent: 'space-between',
  gap: '1rem',
  alignItems: 'center',
  marginBottom: '1rem',
};

const controlsStyle = {
  display: 'flex',
  gap: '0.75rem',
  alignItems: 'center',
  flexWrap: 'wrap',
};

const tableWrapStyle = {
  overflowX: 'auto',
  border: '1px solid #e2e8f0',
  borderRadius: '16px',
};

const tableStyle = {
  width: '100%',
  borderCollapse: 'collapse',
  minWidth: '980px',
};

const cellStyle = {
  padding: '0.9rem 1rem',
  borderBottom: '1px solid #e2e8f0',
  verticalAlign: 'top',
};

const buttonStyle = {
  border: 'none',
  borderRadius: '999px',
  cursor: 'pointer',
  fontWeight: 700,
  padding: '0.55rem 0.9rem',
};

const inputStyle = {
  border: '1px solid #cbd5e1',
  borderRadius: '12px',
  padding: '0.65rem 0.8rem',
  font: 'inherit',
  background: '#fff',
};

const formatDate = (value) => {
  if (!value) {
    return '—';
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return '—';
  }
  return parsed.toLocaleDateString('it-IT');
};

const getExpiryMeta = (value) => {
  if (!value) {
    return { label: 'Nessuna scadenza', level: 'neutral' };
  }
  const expiry = new Date(value);
  if (Number.isNaN(expiry.getTime())) {
    return { label: 'Data non valida', level: 'danger' };
  }
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  expiry.setHours(0, 0, 0, 0);
  const diff = Math.ceil((expiry - today) / 86400000);
  if (diff < 0) {
    return { label: `Scaduto da ${Math.abs(diff)} gg`, level: 'danger' };
  }
  if (diff <= 7) {
    return { label: `Scade in ${diff} gg`, level: 'warning' };
  }
  return { label: formatDate(value), level: 'ok' };
};

const statusBadgeStyle = (status) => {
  const meta = STATUS_META[status] || STATUS_META.richiesto;
  return {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '0.35rem 0.7rem',
    borderRadius: '999px',
    fontSize: '0.78rem',
    fontWeight: 700,
    color: meta.color,
    background: meta.background,
  };
};

export default function DocumentiCollaboratore({ collaboratore_id, currentUser, onUpdated }) {
  const [documenti, setDocumenti] = useState([]);
  const [filter, setFilter] = useState('');
  const [loading, setLoading] = useState(false);
  const [busyDocId, setBusyDocId] = useState(null);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  const isOperatore = ['user', 'manager'].includes(currentUser?.role);

  const clearMessages = () => {
    setError('');
    setMessage('');
  };

  const loadDocumenti = useCallback(async () => {
    if (!collaboratore_id) {
      setDocumenti([]);
      return;
    }
    setLoading(true);
    setError('');
    try {
      const data = filter === '__mancanti__'
        ? await getDocumentiMancantiCollaboratore(collaboratore_id)
        : await getDocumentiCollaboratore(collaboratore_id, filter ? { stato: filter } : {});
      setDocumenti(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err?.response?.data?.detail || 'Errore nel caricamento documenti');
    } finally {
      setLoading(false);
    }
  }, [collaboratore_id, filter]);

  useEffect(() => {
    loadDocumenti();
  }, [loadDocumenti]);

  const summary = useMemo(() => {
    return documenti.reduce((acc, doc) => {
      acc.total += 1;
      if (doc.stato === 'scaduto') acc.scaduti += 1;
      if (doc.stato === 'richiesto') acc.richiesti += 1;
      if (doc.stato === 'validato') acc.validati += 1;
      return acc;
    }, { total: 0, scaduti: 0, richiesti: 0, validati: 0 });
  }, [documenti]);

  const refresh = async () => {
    await loadDocumenti();
    if (typeof onUpdated === 'function') {
      await onUpdated();
    }
  };

  const handleUpload = async (docId, file, dataScadenza = null) => {
    if (!file) {
      return;
    }
    clearMessages();
    setBusyDocId(docId);
    try {
      await uploadDocumentoRichiesto(docId, file, dataScadenza);
      setMessage('Documento caricato con successo');
      await refresh();
    } catch (err) {
      setError(err?.response?.data?.detail || 'Errore nel caricamento del file');
    } finally {
      setBusyDocId(null);
    }
  };

  const handleValida = async (docId) => {
    clearMessages();
    setBusyDocId(docId);
    try {
      await validaDocumentoRichiesto(docId, {
        validato_da: currentUser?.username || currentUser?.email || 'operatore',
      });
      setMessage('Documento validato');
      await refresh();
    } catch (err) {
      setError(err?.response?.data?.detail || 'Errore nella validazione');
    } finally {
      setBusyDocId(null);
    }
  };

  const handleRifiuta = async (docId) => {
    const note = window.prompt('Inserisci una nota per il rifiuto del documento:');
    if (note === null) {
      return;
    }
    clearMessages();
    setBusyDocId(docId);
    try {
      await rifiutaDocumentoRichiesto(docId, { note });
      setMessage('Documento rifiutato');
      await refresh();
    } catch (err) {
      setError(err?.response?.data?.detail || 'Errore nel rifiuto del documento');
    } finally {
      setBusyDocId(null);
    }
  };

  return (
    <section style={wrapStyle}>
      <div style={headerStyle}>
        <div>
          <div style={{ fontSize: '0.8rem', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: '#92400e' }}>
            Fascicolo Documentale
          </div>
          <h3 style={{ margin: '0.35rem 0 0', color: '#0f172a' }}>Documenti collaboratore</h3>
        </div>
        <div style={controlsStyle}>
          <select value={filter} onChange={(e) => setFilter(e.target.value)} style={inputStyle}>
            {FILTER_OPTIONS.map((option) => (
              <option key={option.value || 'all'} value={option.value}>{option.label}</option>
            ))}
          </select>
          <button
            type="button"
            onClick={refresh}
            style={{ ...buttonStyle, background: '#e2e8f0', color: '#0f172a' }}
          >
            Aggiorna
          </button>
        </div>
      </div>

      <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
        <span style={{ ...statusBadgeStyle('richiesto') }}>Richiesti: {summary.richiesti}</span>
        <span style={{ ...statusBadgeStyle('validato') }}>Validati: {summary.validati}</span>
        <span style={{ ...statusBadgeStyle('scaduto') }}>Scaduti: {summary.scaduti}</span>
        <span style={{ ...statusBadgeStyle('caricato') }}>Totale: {summary.total}</span>
      </div>

      {message ? (
        <div style={{ marginBottom: '1rem', padding: '0.9rem 1rem', borderRadius: '12px', background: '#dcfce7', color: '#166534', fontWeight: 600 }}>
          {message}
        </div>
      ) : null}
      {error ? (
        <div style={{ marginBottom: '1rem', padding: '0.9rem 1rem', borderRadius: '12px', background: '#fee2e2', color: '#991b1b', fontWeight: 600 }}>
          {error}
        </div>
      ) : null}

      <div style={tableWrapStyle}>
        <table style={tableStyle}>
          <thead>
            <tr style={{ background: '#f8fafc', color: '#334155', textAlign: 'left' }}>
              <th style={cellStyle}>Tipo documento</th>
              <th style={cellStyle}>Descrizione</th>
              <th style={cellStyle}>Stato</th>
              <th style={cellStyle}>Scadenza</th>
              <th style={cellStyle}>File</th>
              <th style={cellStyle}>Azioni</th>
            </tr>
          </thead>
          <tbody>
            {!loading && documenti.length === 0 ? (
              <tr>
                <td style={cellStyle} colSpan="6">Nessun documento trovato per questo collaboratore.</td>
              </tr>
            ) : null}
            {documenti.map((doc) => {
              const expiry = getExpiryMeta(doc.data_scadenza);
              const showWarning = expiry.level === 'warning' || expiry.level === 'danger';
              const busy = busyDocId === doc.id;
              return (
                <tr key={doc.id}>
                  <td style={cellStyle}>
                    <strong>{doc.tipo_documento}</strong>
                    {doc.obbligatorio ? (
                      <div style={{ fontSize: '0.78rem', color: '#b45309', marginTop: '0.3rem' }}>Obbligatorio</div>
                    ) : null}
                  </td>
                  <td style={cellStyle}>{doc.descrizione || '—'}</td>
                  <td style={cellStyle}>
                    <span style={statusBadgeStyle(doc.stato)}>
                      {(STATUS_META[doc.stato] || STATUS_META.richiesto).label}
                    </span>
                  </td>
                  <td style={cellStyle}>
                    <div style={{ color: showWarning ? '#b91c1c' : '#334155', fontWeight: showWarning ? 700 : 500 }}>
                      {expiry.label}
                    </div>
                  </td>
                  <td style={cellStyle}>
                    {doc.file_name ? (
                      <div>
                        <div style={{ fontWeight: 600, color: '#0f172a' }}>{doc.file_name}</div>
                        <div style={{ fontSize: '0.78rem', color: '#64748b' }}>Caricato: {formatDate(doc.data_caricamento)}</div>
                      </div>
                    ) : (
                      <span style={{ color: '#94a3b8' }}>Nessun file</span>
                    )}
                  </td>
                  <td style={cellStyle}>
                    <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
                      <label style={{ ...buttonStyle, background: '#dbeafe', color: '#1d4ed8', display: 'inline-flex' }}>
                        {busy ? 'Caricamento...' : 'Upload'}
                        <input
                          type="file"
                          hidden
                          disabled={busy}
                          onChange={(event) => {
                            const file = event.target.files?.[0];
                            handleUpload(doc.id, file, doc.data_scadenza || null);
                            event.target.value = '';
                          }}
                        />
                      </label>
                      {isOperatore ? (
                        <>
                          <button
                            type="button"
                            disabled={busy}
                            onClick={() => handleValida(doc.id)}
                            style={{ ...buttonStyle, background: '#dcfce7', color: '#166534' }}
                          >
                            Valida
                          </button>
                          <button
                            type="button"
                            disabled={busy}
                            onClick={() => handleRifiuta(doc.id)}
                            style={{ ...buttonStyle, background: '#fee2e2', color: '#991b1b' }}
                          >
                            Rifiuta
                          </button>
                        </>
                      ) : null}
                    </div>
                    {doc.note_operatore ? (
                      <div style={{ marginTop: '0.55rem', fontSize: '0.78rem', color: '#64748b' }}>
                        Nota: {doc.note_operatore}
                      </div>
                    ) : null}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
