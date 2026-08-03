import React, { useState } from 'react';
import { revealAziendaIban } from '../../services/apiService';
import useMobileLayout from '../../hooks/useMobileLayout';
import './AziendaDetail.scss';

const emptyValue = (value) => (value === null || value === undefined || value === '' ? '—' : value);

const formatValue = (azienda, field) => {
  if (field.name === 'agenzia_id') return azienda.agenzia?.nome || '—';
  if (field.name === 'consulente_id') {
    const consulente = azienda.consulente;
    return consulente ? `${consulente.cognome || ''} ${consulente.nome || ''}`.trim() : '—';
  }
  const value = azienda[field.name];
  if (field.type === 'choice' && typeof value === 'boolean') return value ? 'Sì' : 'No';
  if (field.type === 'date' && value) return new Date(value).toLocaleDateString('it-IT');
  return emptyValue(value);
};

const FieldValue = ({ azienda, field }) => {
  const value = formatValue(azienda, field);
  if (field.type === 'url' && value !== '—') {
    return <a href={value} target="_blank" rel="noreferrer">{value}</a>;
  }
  if (field.type === 'email' && value !== '—') return <a href={`mailto:${value}`}>{value}</a>;
  return value;
};

export default function AziendaDetail({ azienda, spec, currentUser, onClose, onEdit }) {
  const isMobile = useMobileLayout();
  const [revealedIbans, setRevealedIbans] = useState({});
  const [revealError, setRevealError] = useState('');
  const groups = spec?.groups || [];
  const fields = spec?.fields || [];
  const canRevealIban = ['admin', 'operatore'].includes(currentUser?.role);

  const revealIban = async (account) => {
    setRevealError('');
    try {
      const response = await revealAziendaIban(azienda.id, account.id);
      setRevealedIbans((current) => ({ ...current, [account.id]: response.iban }));
    } catch (error) {
      setRevealError(error?.response?.data?.detail || 'IBAN non disponibile');
    }
  };

  return (
    <div className="modal-overlay azienda-detail-overlay" onClick={onClose}>
      <article className="azienda-detail" role="dialog" aria-modal="true" aria-labelledby="azienda-detail-title" onClick={(event) => event.stopPropagation()}>
        <header className="azienda-detail-header">
          <div>
            <span className="azienda-detail-eyebrow">Scheda azienda</span>
            <h2 id="azienda-detail-title">{azienda.ragione_sociale}</h2>
            <p>Partita IVA {azienda.partita_iva || 'non indicata'}</p>
          </div>
          <button type="button" className="azienda-detail-close" onClick={onClose} aria-label="Chiudi scheda">×</button>
        </header>

        <div className="azienda-detail-body">
          {groups.filter((group) => group.name !== 'note').map((group) => {
            const groupFields = fields.filter((field) => field.group === group.name);
            if (!groupFields.length) return null;
            return (
              <details className="azienda-detail-section" key={group.name} open={!isMobile}>
                <summary>{group.label}</summary>
                <dl className="azienda-detail-grid">
                  {groupFields.map((field) => (
                    <div className={field.type === 'multiline' ? 'azienda-detail-field is-wide' : 'azienda-detail-field'} key={field.name}>
                      <dt>{field.label}</dt>
                      <dd><FieldValue azienda={azienda} field={field} /></dd>
                    </div>
                  ))}
                </dl>
              </details>
            );
          })}

          <details className="azienda-detail-section" open={!isMobile}>
            <summary>Sedi operative</summary>
            <div className="azienda-detail-cards">
              {azienda.sedi_operative?.length ? azienda.sedi_operative.map((sede) => (
                <section className="azienda-detail-card" key={sede.id}>
                  <h3>{sede.nome}</h3>
                  <span className="azienda-detail-badge">{sede.tipo || 'operativa'}{sede.is_principale ? ' · principale' : ''}</span>
                  <p>{[sede.indirizzo, sede.cap, sede.citta, sede.provincia].filter(Boolean).join(', ') || 'Indirizzo non indicato'}</p>
                  <p>{[sede.email, sede.telefono].filter(Boolean).join(' · ') || 'Contatti non indicati'}</p>
                </section>
              )) : <p className="azienda-detail-empty">Nessuna sede operativa indicata.</p>}
            </div>
          </details>

          <details className="azienda-detail-section" open={!isMobile}>
            <summary>Dati bancari</summary>
            {revealError && <p className="form-error" role="alert">{revealError}</p>}
            <div className="azienda-detail-cards">
              {azienda.conti_correnti?.length ? azienda.conti_correnti.map((account) => (
                <section className="azienda-detail-card" key={account.id}>
                  <h3>{account.intestatario}</h3>
                  <p>{account.banca || 'Banca non indicata'}{account.agenzia ? ` · ${account.agenzia}` : ''}</p>
                  <p className="azienda-detail-iban">{revealedIbans[account.id] || account.iban_masked || 'IBAN non disponibile'}</p>
                  <p>{account.bic_swift || 'BIC/SWIFT non indicato'}{account.is_predefinito ? ' · predefinito' : ''}</p>
                  {canRevealIban && !revealedIbans[account.id] && (
                    <button type="button" className="btn-secondary" onClick={() => revealIban(account)}>Mostra IBAN completo</button>
                  )}
                </section>
              )) : <p className="azienda-detail-empty">Nessun conto corrente indicato.</p>}
            </div>
          </details>

          <details className="azienda-detail-section" open={!isMobile}>
            <summary>Dati contrattuali e fondi</summary>
            <div className="azienda-detail-cards">
              {azienda.fund_memberships?.length ? azienda.fund_memberships.map((membership) => (
                <section className="azienda-detail-card" key={membership.id}>
                  <h3>{membership.fondo}</h3>
                  <p>Dal {new Date(membership.data_inizio).toLocaleDateString('it-IT')}{membership.data_fine ? ` al ${new Date(membership.data_fine).toLocaleDateString('it-IT')}` : ' · adesione attiva'}</p>
                  <p>{membership.note || 'Nessuna nota'}</p>
                </section>
              )) : <p className="azienda-detail-empty">Nessuna adesione a fondi indicata.</p>}
            </div>
          </details>

          <details className="azienda-detail-section" open={!isMobile}>
            <summary>Progetti collegati</summary>
            {azienda.linked_projects?.length ? (
              <ul className="azienda-detail-list">{azienda.linked_projects.map((project) => <li key={project.id}>{project.name || project.titolo || project.nome || `Progetto #${project.id}`}</li>)}</ul>
            ) : <p className="azienda-detail-empty">Nessun progetto collegato.</p>}
          </details>

          <details className="azienda-detail-section" open={!isMobile}>
            <summary>Documenti</summary>
            <p className="azienda-detail-empty">Nessun documento aziendale specifico collegato all’anagrafica.</p>
          </details>

          <details className="azienda-detail-section" open={!isMobile}>
            <summary>Note</summary>
            <p className="azienda-detail-notes">{azienda.note || '—'}</p>
          </details>
        </div>

        <footer className="azienda-detail-footer">
          {onEdit && <button type="button" className="btn-primary" onClick={() => onEdit(azienda)}>Modifica</button>}
          <button type="button" className="btn-secondary" onClick={onClose}>Chiudi</button>
        </footer>
      </article>
    </div>
  );
}
