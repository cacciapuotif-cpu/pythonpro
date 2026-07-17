import React, { useEffect, useState } from 'react';
import { http } from '../lib/http';

const TimesheetPDF = ({ projectId }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [unlocking, setUnlocking] = useState({});
  const [downloading, setDownloading] = useState({});
  const [message, setMessage] = useState(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await http.get(`/projects/${projectId}/timesheets`);
      setData(res.data);
    } catch (e) {
      setError(e.response?.data?.detail || e.message || 'Errore caricamento timesheet');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (projectId) load();
  }, [projectId]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleDownload = async (assignmentId, collaboratore) => {
    setDownloading(prev => ({ ...prev, [assignmentId]: true }));
    try {
      const res = await http.get(`/assignments/${assignmentId}/timesheet`, {
        responseType: 'blob',
      });
      const blob = new Blob([res.data], { type: 'application/pdf' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `timesheet_${(collaboratore || 'collaboratore').replace(/\s+/g, '_')}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(() => URL.revokeObjectURL(url), 60000);
      setTimeout(() => load(), 1000);
    } catch (e) {
      setMessage('Errore download: ' + (e.response?.data?.detail || e.message));
    } finally {
      setDownloading(prev => ({ ...prev, [assignmentId]: false }));
    }
  };

  const handleUnlock = async (assignmentId) => {
    const motivo = window.prompt('Motivo dello sblocco del timesheet:');
    if (motivo === null) return;
    if (!motivo.trim()) {
      setMessage('La motivazione dello sblocco è obbligatoria');
      return;
    }
    setUnlocking(prev => ({ ...prev, [assignmentId]: true }));
    try {
      await http.post(`/assignments/${assignmentId}/timesheet/unlock`, {
        motivo: motivo.trim(),
      });
      setMessage('Timesheet sbloccato');
      setTimeout(() => setMessage(null), 3000);
      await load();
    } catch (e) {
      setMessage('Errore: ' + (e.response?.data?.detail || e.message));
    } finally {
      setUnlocking(prev => ({ ...prev, [assignmentId]: false }));
    }
  };

  if (loading) return (
    <div style={{ padding: '1rem', color: 'var(--color-text-secondary)' }}>
      Caricamento timesheet...
    </div>
  );

  if (error) return (
    <div style={{ padding: '1rem', color: 'var(--color-text-danger)' }}>
      Errore: {error}
    </div>
  );

  if (!data) return null;

  return (
    <div style={{ padding: '1rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 500 }}>
          Timesheet — {data.project_name}
        </h3>
        <span style={{ fontSize: '13px', color: 'var(--color-text-secondary)' }}>
          {data.assignments.length} collaboratori
        </span>
      </div>

      {message && (
        <div style={{
          padding: '8px 12px',
          marginBottom: '1rem',
          background: 'var(--color-background-success)',
          color: 'var(--color-text-success)',
          borderRadius: '8px',
          fontSize: '13px',
        }}>
          {message}
        </div>
      )}

      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
        <thead>
          <tr style={{ background: 'var(--color-background-secondary)' }}>
            <th style={thStyle}>Collaboratore</th>
            <th style={thStyle}>Mansione</th>
            <th style={thStyle}>Ore ass.</th>
            <th style={thStyle}>Ore eff.</th>
            <th style={thStyle}>Presenze</th>
            <th style={thStyle}>Stato</th>
            <th style={thStyle}>Azioni</th>
          </tr>
        </thead>
        <tbody>
          {data.assignments.map((a) => (
            <tr key={a.assignment_id} style={{ borderBottom: '0.5px solid var(--color-border-tertiary)' }}>
              <td style={tdStyle}>{a.collaboratore}</td>
              <td style={tdStyle}>{a.ruolo}</td>
              <td style={{ ...tdStyle, textAlign: 'center' }}>{a.ore_assegnate}h</td>
              <td style={{ ...tdStyle, textAlign: 'center' }}>{a.ore_effettive}h</td>
              <td style={{ ...tdStyle, textAlign: 'center' }}>{a.presenze_count}</td>
              <td style={{ ...tdStyle, textAlign: 'center' }}>
                {a.timesheet_generato ? (
                  <span style={{
                    fontSize: '11px',
                    padding: '3px 8px',
                    borderRadius: '999px',
                    background: a.timesheet_bloccato
                      ? 'var(--color-background-warning)'
                      : 'var(--color-background-success)',
                    color: a.timesheet_bloccato
                      ? 'var(--color-text-warning)'
                      : 'var(--color-text-success)',
                  }}>
                    {a.timesheet_bloccato ? 'bloccato' : 'sbloccato'}
                  </span>
                ) : (
                  <span style={{
                    fontSize: '11px',
                    padding: '3px 8px',
                    borderRadius: '999px',
                    background: 'var(--color-background-secondary)',
                    color: 'var(--color-text-secondary)',
                  }}>
                    non generato
                  </span>
                )}
              </td>
              <td style={{ ...tdStyle, textAlign: 'center' }}>
                <div style={{ display: 'flex', gap: '6px', justifyContent: 'center' }}>
                  <button
                    onClick={() => handleDownload(a.assignment_id, a.collaboratore)}
                    disabled={downloading[a.assignment_id]}
                    style={btnStyle}
                    title="Scarica/genera PDF timesheet"
                  >
                    {downloading[a.assignment_id] ? '...' : 'PDF'}
                  </button>
                  {a.timesheet_generato && a.timesheet_bloccato && (
                    <button
                      onClick={() => handleUnlock(a.assignment_id)}
                      disabled={unlocking[a.assignment_id]}
                      style={{ ...btnStyle, background: 'var(--color-background-warning)' }}
                      title="Sblocca per rigenerazione"
                    >
                      {unlocking[a.assignment_id] ? '...' : 'Sblocca'}
                    </button>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {data.assignments.length === 0 && (
        <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--color-text-secondary)' }}>
          Nessun collaboratore assegnato a questo progetto
        </div>
      )}
    </div>
  );
};

const thStyle = {
  padding: '8px 12px',
  textAlign: 'left',
  fontWeight: 500,
  fontSize: '12px',
  color: 'var(--color-text-secondary)',
  borderBottom: '0.5px solid var(--color-border-tertiary)',
};

const tdStyle = {
  padding: '10px 12px',
  verticalAlign: 'middle',
};

const btnStyle = {
  padding: '4px 10px',
  fontSize: '12px',
  cursor: 'pointer',
  borderRadius: '6px',
  border: '0.5px solid var(--color-border-secondary)',
  background: 'var(--color-background-primary)',
  color: 'var(--color-text-primary)',
};

export default TimesheetPDF;
