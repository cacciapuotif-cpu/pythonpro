import React, { useCallback, useEffect, useMemo, useState } from 'react';
import apiService from '../services/apiService';
import { canPerform, normalizeRole } from '../auth/permissions';
import './ImplementingEntityDetail.css';

const EMPTY_LOCATION = {
  tipo: 'operativa',
  denominazione: '',
  indirizzo: '',
  cap: '',
  citta: '',
  provincia: '',
  nazione: 'IT',
  email: '',
  pec: '',
  telefono: '',
  is_principale: false,
  accreditamento_ente: '',
  accreditamento_codice: '',
  accreditamento_data: '',
  accreditamento_scadenza: '',
  is_active: true,
  attiva_dal: '',
  dismessa_dal: '',
};

const EMPTY_ACCOUNT = {
  banca: '',
  agenzia: '',
  iban: '',
  bic_swift: '',
  intestatario: '',
  is_predefinito: false,
  is_active: true,
  note: '',
};

const PRINT_FIELDS = [
  'print_config_enabled',
  'print_margin_top_mm',
  'print_margin_bottom_mm',
  'print_margin_left_mm',
  'print_margin_right_mm',
  'print_logo_width_mm',
  'print_logo_height_mm',
  'print_logo_x_mm',
  'print_logo_y_mm',
  'print_letterhead_pages',
  'print_footer',
];

const cleanPayload = (value) => Object.fromEntries(
  Object.entries(value).map(([key, item]) => [key, item === '' ? null : item])
);

const ImplementingEntityDetail = ({ entityId, currentUser, onClose, onEdit, onChanged }) => {
  const [entity, setEntity] = useState(null);
  const [locations, setLocations] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [tab, setTab] = useState('overview');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [locationForm, setLocationForm] = useState(null);
  const [accountForm, setAccountForm] = useState(null);
  const [revealedIbans, setRevealedIbans] = useState({});
  const [printConfig, setPrintConfig] = useState(null);
  const [logoPreviewUrl, setLogoPreviewUrl] = useState(null);
  const canWrite = canPerform(currentUser, 'WRITE_ENTITIES');
  const canRevealIban = ['admin', 'operatore'].includes(normalizeRole(currentUser));

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [detail, locationRows, accountRows] = await Promise.all([
        apiService.getEntity(entityId),
        apiService.getEntityLocations(entityId),
        apiService.getEntityAccounts(entityId),
      ]);
      setEntity(detail);
      setLocations(locationRows);
      setAccounts(accountRows);
      setPrintConfig(Object.fromEntries(PRINT_FIELDS.map((field) => [field, detail[field]])));
    } catch (requestError) {
      setError(requestError.response?.data?.detail || 'Impossibile caricare la scheda ente');
    } finally {
      setLoading(false);
    }
  }, [entityId]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    let active = true;
    let objectUrl = null;

    if (!entity?.logo_filename) {
      setLogoPreviewUrl(null);
      return () => {};
    }

    apiService.downloadEntityLogo(entity.id)
      .then((blob) => {
        if (!active) return;
        objectUrl = URL.createObjectURL(blob);
        setLogoPreviewUrl(objectUrl);
      })
      .catch(() => {
        if (active) setLogoPreviewUrl(null);
      });

    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [entity?.id, entity?.logo_filename]);

  const activeLocations = useMemo(
    () => locations.filter((location) => location.is_active),
    [locations]
  );
  const activeAccounts = useMemo(
    () => accounts.filter((account) => account.is_active),
    [accounts]
  );

  const run = async (operation, successMessage) => {
    setBusy(true);
    setError('');
    try {
      await operation();
      await load();
      onChanged?.();
      if (successMessage) window.alert(successMessage);
      return true;
    } catch (requestError) {
      setError(requestError.response?.data?.detail || 'Operazione non riuscita');
      return false;
    } finally {
      setBusy(false);
    }
  };

  const saveLocation = async (event) => {
    event.preventDefault();
    const { id, ...payload } = locationForm;
    const saved = await run(
      () => id
        ? apiService.updateEntityLocation(entityId, id, cleanPayload(payload))
        : apiService.createEntityLocation(entityId, cleanPayload(payload))
    );
    if (saved) setLocationForm(null);
  };

  const saveAccount = async (event) => {
    event.preventDefault();
    const { id, ...payload } = accountForm;
    if (id && !payload.iban) delete payload.iban;
    const saved = await run(
      () => id
        ? apiService.updateEntityAccount(entityId, id, cleanPayload(payload))
        : apiService.createEntityAccount(entityId, cleanPayload(payload))
    );
    if (saved) setAccountForm(null);
  };

  const revealIban = async (account) => {
    setBusy(true);
    setError('');
    try {
      const result = await apiService.revealEntityIban(entityId, account.id);
      setRevealedIbans((current) => ({ ...current, [account.id]: result.iban }));
    } catch (requestError) {
      setError(requestError.response?.data?.detail || 'IBAN non disponibile');
    } finally {
      setBusy(false);
    }
  };

  const savePrintConfig = () => run(
    () => apiService.updateEntity(entityId, cleanPayload(printConfig)),
    'Configurazione di stampa salvata'
  );

  const previewPrint = async () => {
    setBusy(true);
    setError('');
    try {
      const blob = await apiService.previewEntityPrint(entityId, cleanPayload(printConfig));
      const url = URL.createObjectURL(blob);
      window.open(url, '_blank', 'noopener,noreferrer');
      window.setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (requestError) {
      setError(requestError.response?.data?.detail || 'Anteprima non disponibile');
    } finally {
      setBusy(false);
    }
  };

  const uploadBrandAsset = async (kind, file) => {
    if (!file) return;
    await run(
      () => kind === 'logo'
        ? apiService.uploadEntityLogo(entityId, file)
        : apiService.uploadEntityLetterhead(entityId, file),
      kind === 'logo' ? 'Logo caricato' : 'Carta intestata caricata'
    );
  };

  if (loading) {
    return <div className="entity-detail-overlay"><div className="entity-detail-shell">Caricamento scheda…</div></div>;
  }

  if (!entity) {
    return (
      <div className="entity-detail-overlay">
        <div className="entity-detail-shell">
          <p className="alert alert-error">{error}</p>
          <button className="btn-secondary" onClick={onClose}>Chiudi</button>
        </div>
      </div>
    );
  }

  return (
    <div className="entity-detail-overlay" role="dialog" aria-modal="true" aria-label="Scheda ente attuatore">
      <div className="entity-detail-shell">
        <header className="entity-detail-header">
          <div>
            <span className="detail-eyebrow">Scheda ente attuatore · #{entity.id}</span>
            <h2>{entity.ragione_sociale}</h2>
            <p>{entity.forma_giuridica || 'Forma giuridica non indicata'} · P.IVA {entity.partita_iva}</p>
          </div>
          <div className="entity-detail-actions">
            {canWrite && <button className="btn-secondary" onClick={() => onEdit(entity)}>Modifica anagrafica</button>}
            <button className="close-button" onClick={onClose} aria-label="Chiudi">×</button>
          </div>
        </header>

        <nav className="entity-detail-tabs" aria-label="Sezioni scheda ente">
          {[
            ['overview', 'Dettaglio'],
            ['locations', `Sedi (${activeLocations.length})`],
            ['accounts', `Conti correnti (${activeAccounts.length})`],
            ['printing', 'Stampa e branding'],
          ].map(([id, label]) => (
            <button key={id} className={tab === id ? 'active' : ''} onClick={() => setTab(id)}>
              {label}
            </button>
          ))}
        </nav>

        {error && <div className="alert alert-error">{error}</div>}

        <main className="entity-detail-body">
          {tab === 'overview' && (
            <div className="entity-detail-grid">
              <section className="detail-card">
                <h3>Dati legali</h3>
                <dl>
                  <dt>Ragione sociale</dt><dd>{entity.ragione_sociale}</dd>
                  <dt>Partita IVA</dt><dd>{entity.partita_iva || '—'}</dd>
                  <dt>Codice fiscale</dt><dd>{entity.codice_fiscale || '—'}</dd>
                  <dt>ATECO</dt><dd>{entity.codice_ateco || '—'}</dd>
                  <dt>REA</dt><dd>{entity.rea_numero || '—'}</dd>
                  <dt>Registro imprese</dt><dd>{entity.registro_imprese || '—'}</dd>
                </dl>
              </section>
              <section className="detail-card">
                <h3>Contatti</h3>
                <dl>
                  <dt>Email</dt><dd>{entity.email || '—'}</dd>
                  <dt>PEC</dt><dd>{entity.pec || '—'}</dd>
                  <dt>Telefono</dt><dd>{entity.telefono || '—'}</dd>
                  <dt>SDI</dt><dd>{entity.sdi || '—'}</dd>
                  <dt>Sito web</dt>
                  <dd>{entity.sito_web ? <a href={entity.sito_web} target="_blank" rel="noreferrer">{entity.sito_web}</a> : '—'}</dd>
                </dl>
                <div className="social-links">
                  {(entity.social_links || []).map((link, index) => (
                    <a key={`${link.platform}-${index}`} href={link.url} target="_blank" rel="noreferrer">
                      {link.label || link.platform}
                    </a>
                  ))}
                </div>
              </section>
              <section className="detail-card">
                <h3>Legale rappresentante</h3>
                <dl>
                  <dt>Nominativo</dt><dd>{entity.legale_rappresentante_nome_completo || '—'}</dd>
                  <dt>Luogo e data di nascita</dt>
                  <dd>{entity.legale_rappresentante_luogo_nascita || '—'} · {entity.legale_rappresentante_data_nascita?.slice(0, 10) || '—'}</dd>
                  <dt>Residenza</dt><dd>{entity.legale_rappresentante_via_residenza || '—'}, {entity.legale_rappresentante_comune_residenza || '—'}</dd>
                  <dt>Codice fiscale</dt><dd>{entity.legale_rappresentante_codice_fiscale || '—'}</dd>
                </dl>
              </section>
              <section className="detail-card">
                <h3>Logo</h3>
                {logoPreviewUrl ? (
                  <img className="entity-logo-preview" src={logoPreviewUrl} alt={`Logo ${entity.ragione_sociale}`} />
                ) : (
                  <p>{entity.logo_filename ? 'Anteprima logo non disponibile' : 'Nessun logo caricato'}</p>
                )}
              </section>
              <section className="detail-card">
                <h3>Referente e progetti</h3>
                <dl>
                  <dt>Referente</dt><dd>{entity.referente_nome_completo || '—'}</dd>
                  <dt>Ruolo</dt><dd>{entity.referente_ruolo || '—'}</dd>
                  <dt>Contatti</dt><dd>{entity.referente_email || '—'} · {entity.referente_telefono || '—'}</dd>
                  <dt>Progetti collegati</dt><dd>{entity.projects?.length || 0}</dd>
                  <dt>Stato</dt><dd>{entity.is_active ? 'Attivo' : 'Disattivato'}</dd>
                </dl>
              </section>
              <section className="detail-card detail-card-wide"><h3>Note</h3><p>{entity.note || 'Nessuna nota inserita'}</p></section>
            </div>
          )}

          {tab === 'locations' && (
            <section>
              <div className="detail-section-heading">
                <div><h3>Sedi</h3><p>Una sola sede legale attiva e una sola sede principale.</p></div>
                {canWrite && <button className="btn-primary" onClick={() => setLocationForm({ ...EMPTY_LOCATION })}>Aggiungi sede</button>}
              </div>
              <div className="detail-list">
                {locations.map((location) => (
                  <article key={location.id} className={`detail-list-item ${!location.is_active ? 'inactive' : ''}`}>
                    <div>
                      <div className="detail-badges">
                        <span>{location.tipo}</span>
                        {location.is_principale && <span>principale</span>}
                        {!location.is_active && <span>dismessa</span>}
                      </div>
                      <h4>{location.denominazione}</h4>
                      <p>{location.indirizzo_completo || 'Indirizzo non indicato'}</p>
                      <small>{[location.email, location.pec, location.telefono].filter(Boolean).join(' · ') || 'Contatti non indicati'}</small>
                      {location.tipo === 'accreditata' && (
                        <p>Accreditamento: {location.accreditamento_ente || '—'} · {location.accreditamento_codice || '—'}</p>
                      )}
                    </div>
                    {canWrite && (
                      <div className="detail-row-actions">
                        <button className="btn-secondary" onClick={() => setLocationForm({ ...location })}>Modifica</button>
                        {location.is_active && <button className="btn-danger" onClick={() => run(() => apiService.deactivateEntityLocation(entityId, location.id))}>Disattiva</button>}
                      </div>
                    )}
                  </article>
                ))}
              </div>
              {locationForm && (
                <form className="inline-detail-form" onSubmit={saveLocation}>
                  <h4>{locationForm.id ? 'Modifica sede' : 'Nuova sede'}</h4>
                  <div className="detail-form-grid">
                    <label>Tipo<select value={locationForm.tipo} onChange={(e) => setLocationForm({ ...locationForm, tipo: e.target.value })}>
                      <option value="legale">Legale</option><option value="operativa">Operativa</option>
                      <option value="amministrativa">Amministrativa</option><option value="accreditata">Accreditata</option>
                    </select></label>
                    <label>Denominazione<input required value={locationForm.denominazione || ''} onChange={(e) => setLocationForm({ ...locationForm, denominazione: e.target.value })} /></label>
                    <label className="wide">Indirizzo<input value={locationForm.indirizzo || ''} onChange={(e) => setLocationForm({ ...locationForm, indirizzo: e.target.value })} /></label>
                    <label>CAP<input value={locationForm.cap || ''} onChange={(e) => setLocationForm({ ...locationForm, cap: e.target.value })} /></label>
                    <label>Città<input value={locationForm.citta || ''} onChange={(e) => setLocationForm({ ...locationForm, citta: e.target.value })} /></label>
                    <label>Provincia<input value={locationForm.provincia || ''} onChange={(e) => setLocationForm({ ...locationForm, provincia: e.target.value.toUpperCase() })} /></label>
                    <label>Nazione<input value={locationForm.nazione || 'IT'} onChange={(e) => setLocationForm({ ...locationForm, nazione: e.target.value.toUpperCase() })} /></label>
                    <label>Email<input type="email" value={locationForm.email || ''} onChange={(e) => setLocationForm({ ...locationForm, email: e.target.value })} /></label>
                    <label>PEC<input type="email" value={locationForm.pec || ''} onChange={(e) => setLocationForm({ ...locationForm, pec: e.target.value })} /></label>
                    <label>Telefono<input value={locationForm.telefono || ''} onChange={(e) => setLocationForm({ ...locationForm, telefono: e.target.value })} /></label>
                    <label>Attiva dal<input type="date" value={locationForm.attiva_dal || ''} onChange={(e) => setLocationForm({ ...locationForm, attiva_dal: e.target.value })} /></label>
                    {locationForm.tipo === 'accreditata' && <>
                      <label>Ente accreditante<input value={locationForm.accreditamento_ente || ''} onChange={(e) => setLocationForm({ ...locationForm, accreditamento_ente: e.target.value })} /></label>
                      <label>Codice accreditamento<input value={locationForm.accreditamento_codice || ''} onChange={(e) => setLocationForm({ ...locationForm, accreditamento_codice: e.target.value })} /></label>
                      <label>Data accreditamento<input type="date" value={locationForm.accreditamento_data || ''} onChange={(e) => setLocationForm({ ...locationForm, accreditamento_data: e.target.value })} /></label>
                      <label>Scadenza<input type="date" value={locationForm.accreditamento_scadenza || ''} onChange={(e) => setLocationForm({ ...locationForm, accreditamento_scadenza: e.target.value })} /></label>
                    </>}
                    <label className="checkbox"><input type="checkbox" checked={Boolean(locationForm.is_principale)} onChange={(e) => setLocationForm({ ...locationForm, is_principale: e.target.checked })} /> Sede principale</label>
                  </div>
                  <div className="detail-row-actions">
                    <button type="button" className="btn-secondary" onClick={() => setLocationForm(null)}>Annulla</button>
                    <button className="btn-primary" disabled={busy}>Salva sede</button>
                  </div>
                </form>
              )}
            </section>
          )}

          {tab === 'accounts' && (
            <section>
              <div className="detail-section-heading">
                <div><h3>Conti correnti</h3><p>Negli elenchi l’IBAN è sempre mascherato; la visualizzazione completa viene registrata in audit.</p></div>
                {canWrite && <button className="btn-primary" onClick={() => setAccountForm({ ...EMPTY_ACCOUNT, intestatario: entity.ragione_sociale })}>Aggiungi conto</button>}
              </div>
              <div className="detail-list">
                {accounts.map((account) => (
                  <article key={account.id} className={`detail-list-item ${!account.is_active ? 'inactive' : ''}`}>
                    <div>
                      <div className="detail-badges">
                        {account.is_predefinito && <span>predefinito</span>}
                        {!account.is_active && <span>disattivato</span>}
                      </div>
                      <h4>{account.banca || 'Banca non indicata'} {account.agenzia ? `· ${account.agenzia}` : ''}</h4>
                      <p className="iban-value">{revealedIbans[account.id] || account.iban_masked}</p>
                      <small>{account.intestatario} · BIC/SWIFT {account.bic_swift || '—'}</small>
                    </div>
                    <div className="detail-row-actions">
                      {canRevealIban && !revealedIbans[account.id] && <button className="btn-secondary" onClick={() => revealIban(account)}>Mostra IBAN</button>}
                      {canWrite && <button className="btn-secondary" onClick={() => setAccountForm({ ...account, iban: '' })}>Modifica</button>}
                      {canWrite && account.is_active && <button className="btn-danger" onClick={() => run(() => apiService.deactivateEntityAccount(entityId, account.id))}>Disattiva</button>}
                    </div>
                  </article>
                ))}
              </div>
              {accountForm && (
                <form className="inline-detail-form" onSubmit={saveAccount}>
                  <h4>{accountForm.id ? 'Modifica conto' : 'Nuovo conto'}</h4>
                  <div className="detail-form-grid">
                    <label>Banca<input value={accountForm.banca || ''} onChange={(e) => setAccountForm({ ...accountForm, banca: e.target.value })} /></label>
                    <label>Agenzia<input value={accountForm.agenzia || ''} onChange={(e) => setAccountForm({ ...accountForm, agenzia: e.target.value })} /></label>
                    <label className="wide">IBAN<input required={!accountForm.id} value={accountForm.iban || ''} placeholder={accountForm.id ? 'Lascia vuoto per non cambiarlo' : 'IBAN italiano o estero'} onChange={(e) => setAccountForm({ ...accountForm, iban: e.target.value.toUpperCase() })} /></label>
                    <label>BIC/SWIFT<input value={accountForm.bic_swift || ''} onChange={(e) => setAccountForm({ ...accountForm, bic_swift: e.target.value.toUpperCase() })} /></label>
                    <label>Intestatario<input required value={accountForm.intestatario || ''} onChange={(e) => setAccountForm({ ...accountForm, intestatario: e.target.value })} /></label>
                    <label className="wide">Note<textarea value={accountForm.note || ''} onChange={(e) => setAccountForm({ ...accountForm, note: e.target.value })} /></label>
                    <label className="checkbox"><input type="checkbox" checked={Boolean(accountForm.is_predefinito)} onChange={(e) => setAccountForm({ ...accountForm, is_predefinito: e.target.checked })} /> Conto predefinito</label>
                  </div>
                  <div className="detail-row-actions">
                    <button type="button" className="btn-secondary" onClick={() => setAccountForm(null)}>Annulla</button>
                    <button className="btn-primary" disabled={busy}>Salva conto</button>
                  </div>
                </form>
              )}
            </section>
          )}

          {tab === 'printing' && printConfig && (
            <section>
              <div className="detail-section-heading">
                <div><h3>Logo, carta intestata e stampa</h3><p>I due file sono indipendenti. L’anteprima non crea contratti né dati applicativi.</p></div>
                <button className="btn-primary" onClick={previewPrint} disabled={busy}>Genera anteprima PDF</button>
              </div>
              <div className="brand-assets-grid">
                <article className="detail-card">
                  <h4>Logo</h4>
                  <p>{entity.logo_filename || 'Nessun logo caricato'}</p>
                  {canWrite && <input type="file" accept="image/png,image/jpeg,image/gif" onChange={(e) => uploadBrandAsset('logo', e.target.files?.[0])} />}
                  {canWrite && entity.logo_filename && <button className="btn-danger" onClick={() => run(() => apiService.deleteEntityLogo(entityId))}>Elimina logo</button>}
                </article>
                <article className="detail-card">
                  <h4>Carta intestata</h4>
                  <p>{entity.letterhead_filename || 'Nessuna carta intestata caricata'}</p>
                  {canWrite && <input type="file" accept="image/png,image/jpeg,application/pdf" onChange={(e) => uploadBrandAsset('letterhead', e.target.files?.[0])} />}
                  {canWrite && entity.letterhead_filename && <button className="btn-danger" onClick={() => run(() => apiService.deleteEntityLetterhead(entityId))}>Elimina carta intestata</button>}
                </article>
              </div>
              <div className="inline-detail-form">
                <label className="checkbox"><input type="checkbox" checked={Boolean(printConfig.print_config_enabled)} onChange={(e) => setPrintConfig({ ...printConfig, print_config_enabled: e.target.checked })} /> Usa questa configurazione nei nuovi documenti</label>
                <div className="detail-form-grid printing-grid">
                  {[
                    ['print_margin_top_mm', 'Margine superiore (mm)'],
                    ['print_margin_bottom_mm', 'Margine inferiore (mm)'],
                    ['print_margin_left_mm', 'Margine sinistro (mm)'],
                    ['print_margin_right_mm', 'Margine destro (mm)'],
                    ['print_logo_width_mm', 'Larghezza logo (mm)'],
                    ['print_logo_height_mm', 'Altezza logo (mm)'],
                    ['print_logo_x_mm', 'Posizione X logo (mm)'],
                    ['print_logo_y_mm', 'Distanza logo dall’alto (mm)'],
                  ].map(([field, label]) => (
                    <label key={field}>{label}<input type="number" min="0" step="0.5" value={printConfig[field] ?? ''} onChange={(e) => setPrintConfig({ ...printConfig, [field]: Number(e.target.value) })} /></label>
                  ))}
                  <label>Carta intestata<select value={printConfig.print_letterhead_pages || 'first'} onChange={(e) => setPrintConfig({ ...printConfig, print_letterhead_pages: e.target.value })}>
                    <option value="first">Solo prima pagina</option><option value="all">Tutte le pagine</option>
                  </select></label>
                  <label className="wide">Piè di pagina<textarea value={printConfig.print_footer || ''} onChange={(e) => setPrintConfig({ ...printConfig, print_footer: e.target.value })} /></label>
                </div>
                {canWrite && <button className="btn-primary" onClick={savePrintConfig} disabled={busy}>Salva configurazione</button>}
              </div>
            </section>
          )}
        </main>
      </div>
    </div>
  );
};

export default ImplementingEntityDetail;
