import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { getDocumentiRichiesti } from '../services/apiService';

const pageStyle = {
  display: 'flex',
  flexDirection: 'column',
  gap: '1rem',
};

const cardStyle = {
  background: '#ffffff',
  border: '1px solid #dbe4f0',
  borderRadius: '20px',
  boxShadow: '0 18px 40px rgba(15, 23, 42, 0.06)',
  padding: '1.25rem',
};

const inputStyle = {
  border: '1px solid #cbd5e1',
  borderRadius: '12px',
  padding: '0.75rem 0.85rem',
  font: 'inherit',
  background: '#fff',
};

const primaryButtonStyle = {
  border: 'none',
  borderRadius: '999px',
  cursor: 'pointer',
  fontWeight: 700,
  padding: '0.7rem 1rem',
  background: '#0f766e',
  color: '#fff',
};

const secondaryButtonStyle = {
  border: 'none',
  borderRadius: '999px',
  cursor: 'pointer',
  fontWeight: 700,
  padding: '0.7rem 1rem',
  background: '#dbeafe',
  color: '#1d4ed8',
};

const neutralButtonStyle = {
  border: 'none',
  borderRadius: '999px',
  cursor: 'pointer',
  fontWeight: 700,
  padding: '0.7rem 1rem',
  background: '#e2e8f0',
  color: '#0f172a',
};

const tableStyle = {
  width: '100%',
  borderCollapse: 'collapse',
  minWidth: '1120px',
};

const cellStyle = {
  padding: '0.95rem 1rem',
  borderBottom: '1px solid #e2e8f0',
  verticalAlign: 'top',
};

const summaryCardStyle = {
  ...cardStyle,
  display: 'grid',
  gap: '0.45rem',
  minHeight: '140px',
};

const formatDate = (value) => {
  if (!value) {
    return 'No expiry';
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return 'No expiry';
  }
  return parsed.toLocaleDateString('it-IT');
};

const getDaysToExpiry = (value) => {
  if (!value) {
    return Number.POSITIVE_INFINITY;
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return Number.POSITIVE_INFINITY;
  }
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  parsed.setHours(0, 0, 0, 0);
  return Math.ceil((parsed.getTime() - today.getTime()) / 86400000);
};

const getCollaboratorName = (doc) => {
  const collaborator = doc.collaboratore || {};
  return (
    collaborator.full_name
    || [collaborator.first_name, collaborator.last_name].filter(Boolean).join(' ')
    || `Collaboratore #${doc.collaboratore_id || 'N/D'}`
  );
};

const buildDocumentStatus = (doc) => {
  const days = getDaysToExpiry(doc.data_scadenza);
  const expired = doc.stato === 'scaduto' || days < 0;
  const urgent = !expired && days <= 7;
  const upcoming = !expired && days <= 30;

  if (expired) {
    return {
      label: 'Scaduto',
      score: 0,
      color: '#991b1b',
      background: '#fee2e2',
      sortDays: Number.NEGATIVE_INFINITY,
    };
  }
  if (urgent) {
    return {
      label: 'Urgente',
      score: 1,
      color: '#9a3412',
      background: '#ffedd5',
      sortDays: days,
    };
  }
  if (upcoming) {
    return {
      label: 'In scadenza',
      score: 2,
      color: '#92400e',
      background: '#fef3c7',
      sortDays: days,
    };
  }
  return {
    label: 'Mancante',
    score: 3,
    color: '#1d4ed8',
    background: '#dbeafe',
    sortDays: Number.POSITIVE_INFINITY,
  };
};

const buildCollaboratorUrgency = (documenti) => {
  const statuses = documenti.map(buildDocumentStatus);
  const sortedStatuses = statuses.sort((left, right) => {
    if (left.score !== right.score) {
      return left.score - right.score;
    }
    return left.sortDays - right.sortDays;
  });
  return sortedStatuses[0] || {
    label: 'Mancante',
    score: 3,
    color: '#1d4ed8',
    background: '#dbeafe',
    sortDays: Number.POSITIVE_INFINITY,
  };
};

const buildMailBody = (collaboratoreNome, docs, uploadUrl) => {
  const lines = docs.map((doc) => {
    const status = buildDocumentStatus(doc);
    return `- ${doc.tipo_documento} | Stato: ${status.label} | Scadenza: ${formatDate(doc.data_scadenza)}`;
  });

  return [
    `Gentile ${collaboratoreNome},`,
    '',
    'risultano ancora mancanti o da aggiornare i seguenti documenti:',
    ...lines,
    '',
    `Area caricamento documenti: ${uploadUrl}`,
    '',
    'Ti chiediamo di completare l\'invio quanto prima.',
    '',
    'Grazie.',
  ].join('\n');
};

const escapeCsv = (value) => `"${String(value ?? '').replace(/"/g, '""')}"`;

export default function DocumentiMancanti() {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [tipoFilter, setTipoFilter] = useState('');
  const [scadenzaFilter, setScadenzaFilter] = useState('all');

  const loadData = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const statesToLoad = ['richiesto', 'scaduto'];
      const responses = await Promise.all(statesToLoad.map((stato) => getDocumentiRichiesti({ stato, limit: 500 })));
      const deduped = new Map();

      responses.flat().forEach((doc) => {
        if (doc?.id) {
          deduped.set(doc.id, doc);
        }
      });

      setDocuments(Array.from(deduped.values()));
    } catch (err) {
      setError(err?.response?.data?.detail || 'Errore nel caricamento dei documenti mancanti');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const documentTypes = useMemo(
    () => [...new Set(documents.map((doc) => doc.tipo_documento).filter(Boolean))].sort(),
    [documents],
  );

  const filteredDocuments = useMemo(() => {
    return documents.filter((doc) => {
      if (tipoFilter && doc.tipo_documento !== tipoFilter) {
        return false;
      }

      const days = getDaysToExpiry(doc.data_scadenza);
      const expired = doc.stato === 'scaduto' || days < 0;

      if (scadenzaFilter === 'expired') {
        return expired;
      }
      if (scadenzaFilter === '7days') {
        return !expired && days >= 0 && days <= 7;
      }
      if (scadenzaFilter === '30days') {
        return !expired && days >= 0 && days <= 30;
      }
      if (scadenzaFilter === 'missing-no-expiry') {
        return !doc.data_scadenza;
      }
      return true;
    });
  }, [documents, tipoFilter, scadenzaFilter]);

  const groupedCollaborators = useMemo(() => {
    const grouped = filteredDocuments.reduce((acc, doc) => {
      const id = doc.collaboratore_id || doc.collaboratore?.id;
      if (!id) {
        return acc;
      }

      if (!acc[id]) {
        acc[id] = {
          collaboratore_id: id,
          nome: getCollaboratorName(doc),
          email: doc.collaboratore?.email || doc.destinatario_email || '',
          documenti: [],
        };
      }

      acc[id].documenti.push(doc);
      return acc;
    }, {});

    return Object.values(grouped)
      .map((item) => ({
        ...item,
        urgency: buildCollaboratorUrgency(item.documenti),
        nearestExpiryDays: Math.min(...item.documenti.map((doc) => buildDocumentStatus(doc).sortDays)),
      }))
      .sort((left, right) => {
        if (left.urgency.score !== right.urgency.score) {
          return left.urgency.score - right.urgency.score;
        }
        if (left.nearestExpiryDays !== right.nearestExpiryDays) {
          return left.nearestExpiryDays - right.nearestExpiryDays;
        }
        return right.documenti.length - left.documenti.length;
      });
  }, [filteredDocuments]);

  const summary = useMemo(() => {
    const expiredCount = filteredDocuments.filter((doc) => {
      const days = getDaysToExpiry(doc.data_scadenza);
      return doc.stato === 'scaduto' || days < 0;
    }).length;
    const urgentCount = filteredDocuments.filter((doc) => {
      const days = getDaysToExpiry(doc.data_scadenza);
      return days >= 0 && days <= 7 && doc.stato !== 'scaduto';
    }).length;
    const noExpiryCount = filteredDocuments.filter((doc) => !doc.data_scadenza).length;

    return {
      totalDocuments: filteredDocuments.length,
      totalCollaborators: groupedCollaborators.length,
      expiredDocuments: expiredCount,
      urgentDocuments: urgentCount,
      noExpiryDocuments: noExpiryCount,
    };
  }, [filteredDocuments, groupedCollaborators]);

  const openMailto = (collaboratore) => {
    const subject = encodeURIComponent('Sollecito caricamento documenti');
    const body = encodeURIComponent(
      buildMailBody(
        collaboratore.nome,
        collaboratore.documenti,
        `${window.location.origin}/collaboratori/${collaboratore.collaboratore_id}/documenti`,
      ),
    );
    const recipient = collaboratore.email || '';
    window.open(`mailto:${recipient}?subject=${subject}&body=${body}`, '_blank');
  };

  const handleBulkSollecito = () => {
    const recipients = groupedCollaborators.map((item) => item.email).filter(Boolean);
    const body = encodeURIComponent([
      'Elenco collaboratori con documenti mancanti/scaduti:',
      '',
      ...groupedCollaborators.map((item) => `${item.nome}: ${item.documenti.map((doc) => doc.tipo_documento).join(', ')}`),
    ].join('\n'));
    const subject = encodeURIComponent('Sollecito documenti mancanti');
    window.open(`mailto:${recipients.join(',')}?subject=${subject}&body=${body}`, '_blank');
  };

  const exportCsv = () => {
    const rows = [
      ['Collaboratore', 'Email', 'Tipo documento', 'Stato backend', 'Urgenza', 'Scadenza', 'Giorni alla scadenza'],
      ...groupedCollaborators.flatMap((item) => item.documenti.map((doc) => {
        const days = getDaysToExpiry(doc.data_scadenza);
        const status = buildDocumentStatus(doc);
        return [
          item.nome,
          item.email || '',
          doc.tipo_documento || '',
          doc.stato || '',
          status.label,
          formatDate(doc.data_scadenza),
          Number.isFinite(days) ? days : '',
        ];
      })),
    ];

    const csv = rows.map((row) => row.map(escapeCsv).join(',')).join('\n');
    const blob = new Blob([`\ufeff${csv}`], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `documenti_mancanti_${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  return (
    <div style={pageStyle}>
      <section style={cardStyle}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '1rem', flexWrap: 'wrap' }}>
          <div>
            <div style={{ fontSize: '0.82rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#92400e' }}>
              Reportistica documentale
            </div>
            <h2 style={{ margin: '0.35rem 0 0', color: '#0f172a' }}>Documenti Mancanti</h2>
            <p style={{ margin: '0.45rem 0 0', color: '#475569', maxWidth: '780px' }}>
              Dashboard operativa dei documenti mancanti o scaduti, con ordinamento per urgenza, sollecito rapido ed export CSV.
            </p>
          </div>
          <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
            <button type="button" style={secondaryButtonStyle} onClick={exportCsv}>
              Export CSV
            </button>
            <button
              type="button"
              style={{ ...primaryButtonStyle, opacity: groupedCollaborators.length ? 1 : 0.55 }}
              disabled={groupedCollaborators.length === 0}
              onClick={handleBulkSollecito}
            >
              Invia sollecito bulk
            </button>
          </div>
        </div>
      </section>

      <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem' }}>
        <article style={summaryCardStyle}>
          <span style={{ fontSize: '0.82rem', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Totale documenti</span>
          <strong style={{ fontSize: '2rem', color: summary.totalDocuments > 0 ? '#b91c1c' : '#166534' }}>{summary.totalDocuments}</strong>
          <span style={{ color: '#475569' }}>Documenti mancanti o scaduti nei filtri correnti.</span>
        </article>
        <article style={summaryCardStyle}>
          <span style={{ fontSize: '0.82rem', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Collaboratori impattati</span>
          <strong style={{ fontSize: '2rem', color: '#0f172a' }}>{summary.totalCollaborators}</strong>
          <span style={{ color: '#475569' }}>Anagrafiche con almeno un documento da recuperare.</span>
        </article>
        <article style={summaryCardStyle}>
          <span style={{ fontSize: '0.82rem', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Gia scaduti</span>
          <strong style={{ fontSize: '2rem', color: summary.expiredDocuments > 0 ? '#991b1b' : '#166534' }}>{summary.expiredDocuments}</strong>
          <span style={{ color: '#475569' }}>Richiedono azione immediata.</span>
        </article>
        <article style={summaryCardStyle}>
          <span style={{ fontSize: '0.82rem', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Entro 7 giorni</span>
          <strong style={{ fontSize: '2rem', color: summary.urgentDocuments > 0 ? '#b45309' : '#166534' }}>{summary.urgentDocuments}</strong>
          <span style={{ color: '#475569' }}>{summary.noExpiryDocuments} senza data scadenza esplicita.</span>
        </article>
      </section>

      <section style={cardStyle}>
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
            <select value={tipoFilter} onChange={(event) => setTipoFilter(event.target.value)} style={inputStyle}>
              <option value="">Tutti i tipi documento</option>
              {documentTypes.map((type) => (
                <option key={type} value={type}>{type}</option>
              ))}
            </select>
            <select value={scadenzaFilter} onChange={(event) => setScadenzaFilter(event.target.value)} style={inputStyle}>
              <option value="all">Tutte le scadenze</option>
              <option value="expired">Gia scaduti</option>
              <option value="7days">Entro 7 giorni</option>
              <option value="30days">Entro 30 giorni</option>
              <option value="missing-no-expiry">Senza scadenza</option>
            </select>
            <button type="button" style={neutralButtonStyle} onClick={loadData}>
              Aggiorna
            </button>
          </div>
          <div style={{ color: '#64748b', fontSize: '0.92rem' }}>
            Ordinamento: scaduti, urgenti, in scadenza, mancanti senza data.
          </div>
        </div>
      </section>

      <section style={cardStyle}>
        {error ? (
          <div style={{ marginBottom: '1rem', padding: '0.95rem 1rem', borderRadius: '14px', background: '#fee2e2', color: '#991b1b', fontWeight: 600 }}>
            {error}
          </div>
        ) : null}

        <div style={{ overflowX: 'auto' }}>
          <table style={tableStyle}>
            <thead>
              <tr style={{ background: '#f8fafc', textAlign: 'left', color: '#334155' }}>
                <th style={cellStyle}>Collaboratore</th>
                <th style={cellStyle}>Email</th>
                <th style={cellStyle}>Documenti mancanti</th>
                <th style={cellStyle}>Urgenza</th>
                <th style={cellStyle}>Azione</th>
              </tr>
            </thead>
            <tbody>
              {!loading && groupedCollaborators.length === 0 ? (
                <tr>
                  <td style={cellStyle} colSpan="5">Nessun documento mancante per i filtri correnti.</td>
                </tr>
              ) : null}
              {loading ? (
                <tr>
                  <td style={cellStyle} colSpan="5">Caricamento documenti mancanti...</td>
                </tr>
              ) : null}
              {groupedCollaborators.map((item) => (
                <tr key={item.collaboratore_id}>
                  <td style={cellStyle}>
                    <strong>{item.nome}</strong>
                    <div style={{ marginTop: '0.35rem', fontSize: '0.82rem', color: '#64748b' }}>
                      {item.documenti.length} documenti aperti
                    </div>
                  </td>
                  <td style={cellStyle}>{item.email || 'Nessuna email disponibile'}</td>
                  <td style={cellStyle}>
                    <div style={{ display: 'grid', gap: '0.5rem' }}>
                      {item.documenti.map((doc) => {
                        const status = buildDocumentStatus(doc);
                        const days = getDaysToExpiry(doc.data_scadenza);
                        return (
                          <div key={doc.id} style={{ padding: '0.7rem 0.8rem', borderRadius: '12px', background: '#f8fafc', border: '1px solid #e2e8f0' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.75rem', flexWrap: 'wrap' }}>
                              <strong style={{ color: '#0f172a' }}>{doc.tipo_documento}</strong>
                              <span style={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                padding: '0.25rem 0.65rem',
                                borderRadius: '999px',
                                fontSize: '0.76rem',
                                fontWeight: 700,
                                color: status.color,
                                background: status.background,
                              }}>
                                {status.label}
                              </span>
                            </div>
                            <div style={{ marginTop: '0.25rem', fontSize: '0.82rem', color: '#64748b' }}>
                              Stato backend: {doc.stato || 'richiesto'} | Scadenza: {formatDate(doc.data_scadenza)}
                              {Number.isFinite(days) ? ` | Giorni: ${days}` : ''}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </td>
                  <td style={cellStyle}>
                    <span style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      padding: '0.35rem 0.7rem',
                      borderRadius: '999px',
                      fontSize: '0.78rem',
                      fontWeight: 700,
                      color: item.urgency.color,
                      background: item.urgency.background,
                    }}>
                      {item.urgency.label}
                    </span>
                  </td>
                  <td style={cellStyle}>
                    <button
                      type="button"
                      style={{ ...primaryButtonStyle, opacity: item.email ? 1 : 0.55 }}
                      onClick={() => openMailto(item)}
                    >
                      Invia sollecito
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
