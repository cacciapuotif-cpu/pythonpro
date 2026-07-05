import React, { useEffect, useState } from 'react';
import { apiRootUrl } from '../lib/http';

// Portale pubblico: l'allievo esterno non ha JWT, l'auth e' il magic
// token in query string. Niente client http (Bearer/redirect login).
const API = apiRootUrl;

const PortaleAllievi = () => {
  const [allievo, setAllievo] = useState(null);
  const [progetti, setProgetti] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const token = new URLSearchParams(window.location.search).get('token');

  useEffect(() => {
    if (!token) {
      setError('Link non valido. Richiedi un nuovo link al responsabile del corso.');
      setLoading(false);
      return;
    }

    const load = async () => {
      try {
        const res = await fetch(API + '/api/v1/portale-allievi/profilo?token=' + token);
        if (!res.ok) throw new Error('Link scaduto o non valido');
        const data = await res.json();
        setAllievo(data.allievo);
        setProgetti(data.progetti || []);
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [token]);

  if (loading) return (
    <div style={containerStyle}>
      <div style={cardStyle}>
        <p style={{ color: 'var(--color-text-secondary)', textAlign: 'center' }}>Caricamento...</p>
      </div>
    </div>
  );

  if (error) return (
    <div style={containerStyle}>
      <div style={cardStyle}>
        <p style={{ fontSize: '24px', textAlign: 'center', marginBottom: '8px' }}>⚠️</p>
        <p style={{ fontSize: '14px', color: 'var(--color-text-secondary)', textAlign: 'center' }}>{error}</p>
      </div>
    </div>
  );

  return (
    <div style={containerStyle}>
      <div style={{ maxWidth: '480px', width: '100%', padding: '0 1rem' }}>

        <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
          <div style={{
            width: '64px', height: '64px', borderRadius: '50%',
            background: 'var(--color-background-info)',
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            fontSize: '24px', marginBottom: '12px',
          }}>
            {(allievo?.nome || '?')[0].toUpperCase()}
          </div>
          <p style={{ fontSize: '20px', fontWeight: 500, margin: '0 0 4px' }}>
            {allievo?.nome} {allievo?.cognome}
          </p>
          <p style={{ fontSize: '13px', color: 'var(--color-text-secondary)', margin: 0 }}>
            {allievo?.email}
          </p>
        </div>

        <p style={{ fontSize: '12px', color: 'var(--color-text-secondary)', marginBottom: '10px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
          I tuoi corsi
        </p>

        {progetti.length === 0 && (
          <div style={cardStyle}>
            <p style={{ fontSize: '14px', color: 'var(--color-text-secondary)', textAlign: 'center', margin: 0 }}>
              Nessun corso trovato
            </p>
          </div>
        )}

        {progetti.map(p => (
          <div key={p.project_id} style={{ ...cardStyle, marginBottom: '12px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
              <div>
                <p style={{ fontSize: '15px', fontWeight: 500, margin: '0 0 2px' }}>{p.project_name}</p>
                <p style={{ fontSize: '12px', color: 'var(--color-text-secondary)', margin: 0 }}>
                  {p.ente_erogatore} · {p.avviso}
                </p>
              </div>
              <span style={{
                fontSize: '11px', padding: '3px 8px', borderRadius: '999px',
                background: p.attestato_disponibile ? 'var(--color-background-success)' : 'var(--color-background-secondary)',
                color: p.attestato_disponibile ? 'var(--color-text-success)' : 'var(--color-text-secondary)',
              }}>
                {p.attestato_disponibile ? 'Attestato disponibile' : 'In corso'}
              </span>
            </div>

            <div style={{ display: 'flex', gap: '16px', fontSize: '12px', color: 'var(--color-text-secondary)', marginBottom: '10px' }}>
              <span>Ore frequentate: {p.ore_frequentate}h</span>
              <span>Ore totali: {p.ore_totali}h</span>
              <span>Frequenza: {p.percentuale_frequenza}%</span>
            </div>

            <div style={{ height: '4px', background: 'var(--color-background-secondary)', borderRadius: '2px', overflow: 'hidden', marginBottom: '10px' }}>
              <div style={{
                width: Math.min(p.percentuale_frequenza, 100) + '%',
                height: '100%',
                background: p.attestato_disponibile ? 'var(--color-text-success)' : 'var(--color-text-info)',
              }} />
            </div>

            {p.attestato_disponibile && p.attestato_url && (
              <button
                style={{ width: '100%', padding: '10px', fontSize: '13px', fontWeight: 500 }}
                onClick={() => window.open(API + p.attestato_url, '_blank')}
              >
                Scarica attestato
              </button>
            )}
          </div>
        ))}

        <p style={{ fontSize: '11px', color: 'var(--color-text-secondary)', textAlign: 'center', marginTop: '2rem' }}>
          Portale allievi — Pythonpro
        </p>
      </div>
    </div>
  );
};

const containerStyle = {
  minHeight: '100vh',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  background: 'var(--color-background-tertiary)',
  padding: '2rem 0',
};

const cardStyle = {
  background: 'var(--color-background-primary)',
  borderRadius: 'var(--border-radius-lg)',
  border: '0.5px solid var(--color-border-tertiary)',
  padding: '1rem 1.25rem',
};

export default PortaleAllievi;
