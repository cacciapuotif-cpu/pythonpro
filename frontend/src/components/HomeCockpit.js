import React, { useEffect, useState, useCallback } from 'react';
import { http } from '../lib/http';

const CATEGORIA_LABEL = {
  documento: 'Documento',
  comunicazione: 'Comunicazione',
  progetto: 'Progetto',
  compliance: 'Compliance',
  agente: 'Agente',
};

const STAT_DESTINATIONS = {
  pratiche_aperte: { section: 'documenti-mancanti', filters: { status: 'open' } },
  progetti_attivi: { section: 'projects', filters: { status: 'active' } },
  agenti_attivi: { section: 'agents-dashboard', filters: { runStatus: 'running' } },
  scadenze_7gg: { section: 'projects', filters: { status: 'deadline-7-days' } },
};

export const getDecisionDestination = (decisione) => {
  if (decisione.tipo === 'agente') {
    return {
      section: 'agents-review',
      filters: { status: 'pending', suggestionId: decisione.id },
    };
  }
  if (decisione.tipo === 'documento') {
    return {
      section: 'documenti-mancanti',
      filters: {
        status: 'uploaded',
        documentId: decisione.id,
        collaboratorId: decisione.entita_id,
      },
    };
  }
  if (decisione.tipo === 'progetto') {
    return {
      section: 'projects',
      filters: { status: 'attention', projectId: decisione.entita_id },
    };
  }
  if (decisione.tipo === 'regime_aiuto') {
    return {
      section: 'projects',
      filters: {
        status: 'attention',
        projectId: decisione.entita_id,
        focus: 'compliance',
      },
    };
  }
  return null;
};

const StatCard = ({ label, value, warning, onClick }) => (
  <button type="button" onClick={onClick} style={{
    background: 'var(--color-background-primary)',
    borderRadius: 'var(--border-radius-md)',
    border: '0.5px solid var(--color-border-tertiary)',
    padding: '12px',
    flex: 1,
    minWidth: 0,
    cursor: 'pointer',
    textAlign: 'left',
  }}>
    <p style={{ fontSize: '11px', color: 'var(--color-text-secondary)', margin: '0 0 4px' }}>{label}</p>
    <p style={{
      fontSize: '22px',
      fontWeight: 500,
      margin: 0,
      color: warning ? 'var(--color-text-warning)' : 'var(--color-text-primary)'
    }}>{value}</p>
  </button>
);

const DecisioneCard = ({ decisione, onDismiss, onNavigate }) => {
  const colore = decisione.priorita === 'alta'
    ? 'var(--color-border-warning)'
    : 'var(--color-border-info)';

  const tempoFa = (iso) => {
    if (!iso) return '';
    const diff = Math.floor((Date.now() - new Date(iso)) / 60000);
    if (diff < 60) return diff + ' min fa';
    if (diff < 1440) return Math.floor(diff / 60) + ' ore fa';
    return Math.floor(diff / 1440) + ' giorni fa';
  };

  const destination = getDecisionDestination(decisione);

  return (
    <div data-testid="cockpit-decision" style={{
      background: 'var(--color-background-primary)',
      borderRadius: 'var(--border-radius-lg)',
      border: '0.5px solid var(--color-border-tertiary)',
      borderLeft: '2px solid ' + colore,
      padding: '1rem 1.25rem',
      marginBottom: '10px',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
        <span style={{
          fontSize: '11px',
          color: decisione.priorita === 'alta' ? 'var(--color-text-warning)' : 'var(--color-text-info)',
          fontWeight: 500,
          textTransform: 'uppercase',
        }}>
          {CATEGORIA_LABEL[decisione.categoria] || decisione.tipo}
        </span>
        <span style={{ fontSize: '11px', color: 'var(--color-text-secondary)' }}>
          {tempoFa(decisione.creato_il)}
        </span>
      </div>
      <p style={{ fontSize: '14px', fontWeight: 500, margin: '0 0 4px' }}>{decisione.titolo}</p>
      <p style={{ fontSize: '13px', color: 'var(--color-text-secondary)', margin: '0 0 10px', lineHeight: 1.4 }}>
        {decisione.descrizione}
      </p>
      <div style={{ display: 'flex', gap: '8px' }}>
        {destination && (
          <button
            style={{ flex: 1, fontSize: '12px', padding: '6px' }}
            onClick={() => onNavigate(destination)}
          >
            Gestisci
          </button>
        )}
        <button
          style={{ flex: 1, fontSize: '12px', padding: '6px' }}
          onClick={() => onDismiss && onDismiss(decisione.id, decisione.tipo)}
        >
          Ignora
        </button>
      </div>
    </div>
  );
};

const HomeCockpit = ({
  currentUser,
  onNavigate = () => {},
}) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [dismissed, setDismissed] = useState(new Set());
  const [filtro, setFiltro] = useState('tutti');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await http.get('/cockpit/decisioni');
      setData(res.data);
    } catch (e) {
      console.error('Errore cockpit:', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleDismiss = (id, tipo) => {
    setDismissed(prev => new Set([...prev, tipo + '_' + id]));
  };

  const now = new Date();
  const giornoSettimana = now.toLocaleDateString('it-IT', { weekday: 'long' });
  const dataOggi = now.toLocaleDateString('it-IT', { day: 'numeric', month: 'long' });
  const nomeUtente = currentUser?.full_name || currentUser?.nome || currentUser?.username || 'Francesco';

  const decisioni = (data?.decisioni || []).filter(d =>
    !dismissed.has(d.tipo + '_' + d.id) &&
    (filtro === 'tutti' || d.categoria === filtro)
  );

  const stats = data?.stats || {};

  return (
    <div style={{ maxWidth: '720px', margin: '0 auto', padding: '0.5rem' }}>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
        <div>
          <p style={{ fontSize: '13px', color: 'var(--color-text-secondary)', margin: 0, textTransform: 'capitalize' }}>
            {giornoSettimana} {dataOggi}
          </p>
          <p style={{ fontSize: '18px', fontWeight: 500, margin: '2px 0 0' }}>
            Buongiorno {nomeUtente}
          </p>
        </div>
        <button onClick={load} style={{ fontSize: '12px', padding: '6px 12px' }}>
          Aggiorna
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: '10px', marginBottom: '1.25rem' }}>
        <StatCard label="Pratiche aperte" value={stats.pratiche_aperte ?? '—'} onClick={() => onNavigate(STAT_DESTINATIONS.pratiche_aperte)} />
        <StatCard label="Progetti attivi" value={stats.progetti_attivi ?? '—'} onClick={() => onNavigate(STAT_DESTINATIONS.progetti_attivi)} />
        <StatCard label="Agenti attivi" value={stats.agenti_attivi ?? '—'} onClick={() => onNavigate(STAT_DESTINATIONS.agenti_attivi)} />
        <StatCard label="Scadenze 7gg" value={stats.scadenze_7gg ?? '—'} warning={stats.scadenze_7gg > 0} onClick={() => onNavigate(STAT_DESTINATIONS.scadenze_7gg)} />
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <div>
          <p style={{ fontSize: '12px', color: 'var(--color-text-secondary)', margin: '0 0 2px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
            Richiedono attenzione
          </p>
          <p style={{ fontSize: '22px', fontWeight: 500, margin: 0, color: decisioni.length > 0 ? 'var(--color-text-warning)' : 'var(--color-text-success)' }}>
            {loading ? '...' : decisioni.length}
          </p>
        </div>
        <select
          value={filtro}
          onChange={e => setFiltro(e.target.value)}
          style={{ fontSize: '12px', padding: '6px 10px', borderRadius: '6px', border: '0.5px solid var(--color-border-secondary)' }}
        >
          <option value="tutti">Tutti</option>
          <option value="documento">Documenti</option>
          <option value="progetto">Progetti</option>
          <option value="compliance">Compliance</option>
          <option value="comunicazione">Comunicazioni</option>
        </select>
      </div>

      {loading && (
        <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--color-text-secondary)', fontSize: '14px' }}>
          Caricamento decisioni...
        </div>
      )}

      {!loading && decisioni.length === 0 && (
        <div style={{
          padding: '2rem',
          textAlign: 'center',
          background: 'var(--color-background-primary)',
          borderRadius: 'var(--border-radius-lg)',
          border: '0.5px solid var(--color-border-tertiary)',
        }}>
          <p style={{ fontSize: '16px', margin: '0 0 4px', fontWeight: 500 }}>Tutto in ordine</p>
          <p style={{ fontSize: '13px', color: 'var(--color-text-secondary)', margin: 0 }}>
            Nessuna decisione urgente in questo momento
          </p>
        </div>
      )}

      {!loading && decisioni.map(d => (
        <DecisioneCard
          key={d.tipo + '_' + d.id}
          decisione={d}
          onDismiss={handleDismiss}
          onNavigate={onNavigate}
        />
      ))}

    </div>
  );
};

export default HomeCockpit;
