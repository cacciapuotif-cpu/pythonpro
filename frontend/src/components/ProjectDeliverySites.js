import React, { useMemo, useState } from 'react';
import apiService, { createAziendaSedeOperativa } from '../services/apiService';

const emptyForm = { denominazione: '', indirizzo: '', comune: '', provincia: '', cap: '' };

const siteAddress = (site) => [
  site.indirizzo,
  [site.cap, site.citta || site.comune].filter(Boolean).join(' '),
  site.provincia ? `(${site.provincia})` : '',
].filter(Boolean).join(', ');

const siteName = (site) => site.denominazione || site.nome || 'Sede';

const ProjectDeliverySites = ({ aziende, ente, allievi, value, onChange, onError }) => {
  const [pending, setPending] = useState({});
  const [newSite, setNewSite] = useState(null);
  const [siteForm, setSiteForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);
  const [extraCompanySites, setExtraCompanySites] = useState({});
  const [extraEntitySites, setExtraEntitySites] = useState([]);

  const entitySites = useMemo(() => {
    const source = [...(ente?.sedi || []).filter((site) => site.is_active), ...extraEntitySites];
    return Array.from(new Map(source.map((site) => [String(site.id), site])).values());
  }, [ente, extraEntitySites]);

  const companySites = (azienda) => {
    const source = [...(azienda.sedi_operative || []), ...(extraCompanySites[azienda.id] || [])];
    return Array.from(new Map(source.map((site) => [String(site.id), site])).values());
  };

  const addSelected = (aziendaId) => {
    const raw = pending[aziendaId];
    if (!raw) return;
    const [sede_tipo, sede_id] = raw.split(':');
    const current = value[aziendaId] || [];
    if (!current.some((item) => item.sede_tipo === sede_tipo && String(item.sede_id) === sede_id)) {
      onChange({ ...value, [aziendaId]: [...current, { sede_tipo, sede_id: Number(sede_id) }] });
    }
    setPending((previous) => ({ ...previous, [aziendaId]: '' }));
  };

  const removeSelected = (aziendaId, index) => {
    const remaining = (value[aziendaId] || []).filter((_, itemIndex) => itemIndex !== index);
    onChange({ ...value, [aziendaId]: remaining });
  };

  const openNewSite = (aziendaId, tipo) => {
    setNewSite({ aziendaId, tipo });
    setSiteForm(emptyForm);
  };

  const saveNewSite = async () => {
    setSaving(true);
    try {
      let created;
      if (newSite.tipo === 'azienda') {
        created = await createAziendaSedeOperativa(newSite.aziendaId, {
          nome: siteForm.denominazione,
          indirizzo: siteForm.indirizzo,
          citta: siteForm.comune,
          provincia: siteForm.provincia,
          cap: siteForm.cap,
        });
        setExtraCompanySites((previous) => ({
          ...previous,
          [newSite.aziendaId]: [...(previous[newSite.aziendaId] || []), created],
        }));
      } else {
        created = await apiService.createEntityLocation(ente.id, {
          tipo: 'operativa',
          denominazione: siteForm.denominazione,
          indirizzo: siteForm.indirizzo,
          citta: siteForm.comune,
          provincia: siteForm.provincia,
          cap: siteForm.cap,
          nazione: 'IT',
          is_active: true,
        });
        setExtraEntitySites((previous) => [...previous, created]);
      }
      const aziendaId = newSite.aziendaId;
      const current = value[aziendaId] || [];
      onChange({ ...value, [aziendaId]: [...current, { sede_tipo: newSite.tipo, sede_id: created.id }] });
      setNewSite(null);
      setSiteForm(emptyForm);
    } catch (error) {
      onError(error?.response?.data?.detail || error?.message || 'Impossibile creare la sede');
    } finally {
      setSaving(false);
    }
  };

  const resolveSite = (azienda, selected) => (
    selected.sede_tipo === 'ente'
      ? entitySites.find((site) => String(site.id) === String(selected.sede_id))
      : companySites(azienda).find((site) => String(site.id) === String(selected.sede_id))
  );

  return (
    <div className="delivery-company-list">
      {aziende.map((azienda) => {
        const ownSites = companySites(azienda);
        const selectedSites = value[azienda.id] || [];
        const companyStudents = allievi.filter((item) => Number(item.azienda_cliente_id) === Number(azienda.id));
        return (
          <section className="delivery-company" key={azienda.id}>
            <header>
              <strong>{azienda.ragione_sociale}</strong>
              <span>{selectedSites.length} {selectedSites.length === 1 ? 'sede indicata' : 'sedi indicate'}</span>
            </header>

            <div className="delivery-sites">
              {selectedSites.length === 0 && <p className="delivery-missing">Sede di erogazione mancante</p>}
              {selectedSites.map((selected, index) => {
                const site = resolveSite(azienda, selected);
                return (
                  <div className="delivery-site" key={`${selected.sede_tipo}-${selected.sede_id}`}>
                    <div>
                      <span className={`delivery-site-type ${selected.sede_tipo}`}>
                        {selected.sede_tipo === 'ente' ? 'Sede ente' : 'Sede azienda'}
                      </span>
                      <strong>{siteName(site || {})}</strong>
                      <small>{siteAddress(site || {}) || 'Indirizzo non disponibile'}</small>
                    </div>
                    <button type="button" className="delivery-remove" onClick={() => removeSelected(azienda.id, index)}>
                      Rimuovi
                    </button>
                  </div>
                );
              })}

              <div className="delivery-add-row">
                <select
                  aria-label={`Nuova sede per ${azienda.ragione_sociale}`}
                  value={pending[azienda.id] || ''}
                  onChange={(event) => setPending((previous) => ({ ...previous, [azienda.id]: event.target.value }))}
                >
                  <option value="">Seleziona un'altra sede</option>
                  <optgroup label={`Sedi di ${azienda.ragione_sociale}`}>
                    {ownSites.map((site) => <option key={`azienda-${site.id}`} value={`azienda:${site.id}`}>{siteName(site)} — {siteAddress(site)}</option>)}
                  </optgroup>
                  <optgroup label="Sedi dell'ente attuatore">
                    {entitySites.map((site) => <option key={`ente-${site.id}`} value={`ente:${site.id}`}>{siteName(site)} — {siteAddress(site)}</option>)}
                  </optgroup>
                </select>
                <button type="button" onClick={() => addSelected(azienda.id)} disabled={!pending[azienda.id]}>Aggiungi sede</button>
              </div>

              <div className="delivery-create-actions">
                <button type="button" onClick={() => openNewSite(azienda.id, 'azienda')}>+ Nuova sede azienda</button>
                <button type="button" onClick={() => openNewSite(azienda.id, 'ente')} disabled={!ente}>+ Nuova sede ente</button>
              </div>

              {newSite?.aziendaId === azienda.id && (
                <div className="delivery-inline-form">
                  <strong>Nuova sede {newSite.tipo === 'ente' ? "dell'ente attuatore" : "dell'azienda"}</strong>
                  <input required value={siteForm.denominazione} onChange={(e) => setSiteForm({ ...siteForm, denominazione: e.target.value })} placeholder="Denominazione" />
                  <input required value={siteForm.indirizzo} onChange={(e) => setSiteForm({ ...siteForm, indirizzo: e.target.value })} placeholder="Indirizzo" />
                  <input required value={siteForm.comune} onChange={(e) => setSiteForm({ ...siteForm, comune: e.target.value })} placeholder="Comune" />
                  <input required maxLength="2" value={siteForm.provincia} onChange={(e) => setSiteForm({ ...siteForm, provincia: e.target.value.toUpperCase() })} placeholder="Provincia" />
                  <input required inputMode="numeric" pattern="[0-9]{5}" value={siteForm.cap} onChange={(e) => setSiteForm({ ...siteForm, cap: e.target.value })} placeholder="CAP" />
                  <div>
                    <button type="button" onClick={saveNewSite} disabled={saving}>{saving ? 'Salvataggio...' : 'Crea e assegna'}</button>
                    <button type="button" onClick={() => setNewSite(null)}>Annulla</button>
                  </div>
                </div>
              )}
            </div>

            <div className="delivery-students">
              <span>Allievi</span>
              <p>{companyStudents.length ? companyStudents.map((item) => `${item.nome} ${item.cognome}`).join(', ') : 'Nessun allievo selezionato'}</p>
            </div>
          </section>
        );
      })}
    </div>
  );
};

export default ProjectDeliverySites;
