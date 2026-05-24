import React, { useEffect, useState, useCallback } from 'react';

const API = process.env.REACT_APP_API_URL || '';

const CATEGORIA_COLORE = {
  documento: 'var(--color-border-info)',
  comunicazione: 'var(--color-border-info)',
  progetto: 'var(--color-border-warning)',
  compliance: 'var(--color-border-info)',
  agente: 'var(--color-border-info)',
};

const CATEGORIA_LABEL = {
  documento: 'Documento',
  comunicazione: 'Comunicazione',
  progetto: 'Progetto',
  compliance: 'Compliance',
  agente: 'Agente',
};

const StatCard = ({ label, value, warning }) => (
  <div style={{
    background: 'var(--color-background-primary)',
    borderRadius: 'var(--border-radius-md)',
    border: '0.5px solid var(--color-border-tertiary)',
    padding: '12px',
    flex: 1,
    minWidth: 0,
  }}>
    <p style={{ fontSize: '11px', color: 'var(--color-text-secondary)', margin: '0 0 4px' }}>{label}</p>
    <p style={{
      fontSize: '22px',
      fontWeight: 500,
      margin: 0,
      color: warning ? 'var(--color-text-warning)' : 'var(--color-text-primary)'
    }}>{value}</p>
  </div>
);

const DecisioneCard = ({ decisione, onDismiss }) => {
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

  return (
    <div style={{
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
        {decisione.azione_url && (
          <button
            style={{ flex: 1, fontSize: '12px', padding: '6px' }}
            onClick={() => window.open(API + decisione.azione_url, '_blank')}
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

const HomeCockpit = ({ currentUser }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [dismissed, setDismissed] = useState(new Set());
  const [filtro, setFiltro] = useState('tutti');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(API + '/api/v1/cockpit/decisioni');
      const json = await res.json();
      setData(json);
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
  const nomeUtente = currentUser?.nome || currentUser?.username || 'Francesco';

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
        <StatCard label="Pratiche aperte" value={stats.pratiche_aperte ?? '—'} />
        <StatCard label="Progetti attivi" value={stats.progetti_attivi ?? '—'} />
        <StatCard label="Agenti attivi" value={stats.agenti_attivi ?? '—'} />
        <StatCard label="Scadenze 7gg" value={stats.scadenze_7gg ?? '—'} warning={stats.scadenze_7gg > 0} />
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
        />
      ))}

    </div>
  );
};

export default HomeCockpit;
