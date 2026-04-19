import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  getAllievi,
  getAllievo,
  createAllievo,
  updateAllievo,
  deleteAllievo,
  getAziendeClienti,
  getProjects,
  bulkImportAllievi,
} from '../services/apiService';
import AllieviBulkImport from './allievi/AllieviBulkImport';
import './AllieviManager.css';

const blankToNull = (value) => {
  if (typeof value !== 'string') return value;
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
};

const sedeOperativaLabel = (sede = {}) => {
  const details = [sede.citta, sede.provincia].filter(Boolean).join(' ');
  return details ? `${sede.nome} · ${details}` : sede.nome || 'Sede operativa';
};

const EMPTY_FORM = {
  nome: '',
  cognome: '',
  codice_fiscale: '',
  luogo_nascita: '',
  data_nascita: '',
  telefono: '',
  email: '',
  residenza: '',
  cap: '',
  citta: '',
  provincia: '',
  occupato: false,
  azienda_cliente_id: '',
  azienda_sede_operativa_id: '',
  data_assunzione: '',
  tipo_contratto: '',
  ccnl: '',
  mansione: '',
  livello_inquadramento: '',
  note: '',
  project_ids: [],
};

const projectLabel = (project = {}) => {
  const primaryName = project.name || project.titolo || project.nome || `Progetto #${project.id}`;
  return project.status ? `${primaryName} · ${project.status}` : primaryName;
};

const mapAllievoToForm = (allievo = {}) => ({
  nome: allievo.nome || '',
  cognome: allievo.cognome || '',
  codice_fiscale: allievo.codice_fiscale || '',
  luogo_nascita: allievo.luogo_nascita || '',
  data_nascita: allievo.data_nascita ? `${allievo.data_nascita}`.slice(0, 10) : '',
  telefono: allievo.telefono || '',
  email: allievo.email || '',
  residenza: allievo.residenza || '',
  cap: allievo.cap || '',
  citta: allievo.citta || '',
  provincia: allievo.provincia || '',
  occupato: allievo.occupato ?? false,
  azienda_cliente_id: allievo.azienda_cliente_id || '',
  azienda_sede_operativa_id: allievo.azienda_sede_operativa_id || '',
  data_assunzione: allievo.data_assunzione ? `${allievo.data_assunzione}`.slice(0, 10) : '',
  tipo_contratto: allievo.tipo_contratto || '',
  ccnl: allievo.ccnl || '',
  mansione: allievo.mansione || '',
  livello_inquadramento: allievo.livello_inquadramento || '',
  note: allievo.note || '',
  project_ids: Array.isArray(allievo.project_ids) ? allievo.project_ids.map((id) => Number(id)) : [],
});

const sortAllieviBySurname = (items = []) => [...items].sort((left, right) => {
  const leftSurname = (left.cognome || '').trim();
  const rightSurname = (right.cognome || '').trim();
  const surnameCompare = leftSurname.localeCompare(rightSurname, 'it', { sensitivity: 'base' });
  if (surnameCompare !== 0) return surnameCompare;

  const leftName = (left.nome || '').trim();
  const rightName = (right.nome || '').trim();
  return leftName.localeCompare(rightName, 'it', { sensitivity: 'base' });
});

export default function AllieviManager() {
  const [result, setResult] = useState({ items: [], total: 0, pages: 1 });
  const [aziendaOptions, setAziendaOptions] = useState([]);
  const [projectOptions, setProjectOptions] = useState([]);
  const [filters, setFilters] = useState({ search: '', occupato: '', page: 1, limit: 20 });
  const [loading, setLoading] = useState(false);
  const [modal, setModal] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [allievoProjectToAdd, setAllievoProjectToAdd] = useState('');
  const [showBulkImport, setShowBulkImport] = useState(false);
  const [bulkImporting, setBulkImporting] = useState(false);

  const loadReferenceData = useCallback(async () => {
    try {
      const [aziendeData, projectsData] = await Promise.all([
        getAziendeClienti({ page: 1, limit: 100 }),
        getProjects(0, 200),
      ]);
      setAziendaOptions(aziendeData.items || aziendeData || []);
      setProjectOptions(projectsData.items || projectsData || []);
    } catch {
      setAziendaOptions([]);
      setProjectOptions([]);
    }
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = { page: filters.page, limit: filters.limit };
      if (filters.search) params.search = filters.search;
      if (filters.occupato !== '') params.occupato = filters.occupato === 'true';
      const data = await getAllievi(params);
      setResult({
        items: sortAllieviBySurname(data.items || []),
        total: data.total || 0,
        pages: data.pages || 1,
      });
    } catch {
      setError('Errore nel caricamento allievi');
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { loadReferenceData(); }, [loadReferenceData]);

  const showToast = (message, type = 'success') => {
    if (type === 'success') setSuccess(message);
    else setError(message);
    setTimeout(() => {
      setSuccess(null);
      setError(null);
    }, 3500);
  };

  const openCreate = () => {
    setForm(EMPTY_FORM);
    setAllievoProjectToAdd('');
    setModal({ mode: 'create' });
  };

  const openEdit = async (allievo) => {
    try {
      const detail = await getAllievo(allievo.id);
      setForm(mapAllievoToForm(detail));
    } catch {
      setForm(mapAllievoToForm(allievo));
    }
    setAllievoProjectToAdd('');
    setModal({ mode: 'edit', data: allievo });
  };

  const validateForm = () => {
    if (!form.nome.trim() || !form.cognome.trim()) {
      showToast('Nome e cognome sono obbligatori', 'error');
      return false;
    }
    if (form.occupato && !form.azienda_cliente_id) {
      showToast('Se l’allievo è occupato devi indicare l’azienda', 'error');
      return false;
    }
    if (form.occupato && selectedCompany && selectedCompanySediOperative.length > 0 && !form.azienda_sede_operativa_id) {
      showToast('Seleziona la sede operativa del dipendente', 'error');
      return false;
    }
    return true;
  };

  const handleAddProject = () => {
    const selectedId = Number(allievoProjectToAdd);
    if (!selectedId) return;
    setForm((prev) => (
      prev.project_ids.includes(selectedId)
        ? prev
        : { ...prev, project_ids: [...prev.project_ids, selectedId] }
    ));
    setAllievoProjectToAdd('');
  };

  const handleRemoveProject = (projectIdToRemove) => {
    setForm((prev) => ({
      ...prev,
      project_ids: prev.project_ids.filter((projectId) => projectId !== projectIdToRemove),
    }));
  };

  const selectedCompany = form.occupato && form.azienda_cliente_id
    ? aziendaOptions.find((azienda) => Number(azienda.id) === Number(form.azienda_cliente_id))
    : null;

  const companyProjectIds = useMemo(
    () => (selectedCompany && Array.isArray(selectedCompany.project_ids)
      ? selectedCompany.project_ids.map((id) => Number(id))
      : []),
    [selectedCompany]
  );

  const selectedCompanySediOperative = useMemo(
    () => (selectedCompany && Array.isArray(selectedCompany.sedi_operative)
      ? selectedCompany.sedi_operative
      : []),
    [selectedCompany]
  );

  const companyProjectIdSet = useMemo(
    () => new Set(companyProjectIds),
    [companyProjectIds]
  );
  const companySediOperativeIdSet = useMemo(
    () => new Set(selectedCompanySediOperative.map((sede) => Number(sede.id))),
    [selectedCompanySediOperative]
  );
  const selectedCompanyId = selectedCompany ? Number(selectedCompany.id) : null;
  const eligibleProjectOptions = form.occupato
    ? (selectedCompany
      ? projectOptions.filter((project) => companyProjectIdSet.has(Number(project.id)))
      : [])
    : projectOptions;

  const selectedProjects = form.project_ids
    .map((projectId) => projectOptions.find((project) => Number(project.id) === Number(projectId)))
    .filter(Boolean);

  const availableProjects = eligibleProjectOptions.filter(
    (project) => !form.project_ids.includes(Number(project.id))
  );

  useEffect(() => {
    if (!form.occupato || !selectedCompanyId) {
      return;
    }

    const allowedProjectIds = new Set(companyProjectIds);
    setForm((prev) => {
      const filteredProjectIds = prev.project_ids.filter((projectId) => allowedProjectIds.has(Number(projectId)));
      const hasValidSedeOperativa = prev.azienda_sede_operativa_id && companySediOperativeIdSet.has(Number(prev.azienda_sede_operativa_id));
      const nextSedeOperativaId = hasValidSedeOperativa ? prev.azienda_sede_operativa_id : '';
      return filteredProjectIds.length === prev.project_ids.length && nextSedeOperativaId === prev.azienda_sede_operativa_id
        ? prev
        : { ...prev, project_ids: filteredProjectIds, azienda_sede_operativa_id: nextSedeOperativaId };
    });
  }, [form.occupato, selectedCompanyId, companyProjectIds, companySediOperativeIdSet]);

  const handleSave = async () => {
    if (!validateForm()) return;
    setSaving(true);
    const normalizedProjectIds = Array.isArray(form.project_ids)
      ? form.project_ids
        .map((projectId) => Number(projectId))
        .filter((projectId) => !Number.isNaN(projectId))
        .filter((projectId) => (
          !form.occupato || !selectedCompany ? true : companyProjectIdSet.has(projectId)
        ))
      : [];

    const payload = {
      nome: form.nome.trim(),
      cognome: form.cognome.trim(),
      codice_fiscale: blankToNull(form.codice_fiscale)?.toUpperCase() || null,
      luogo_nascita: blankToNull(form.luogo_nascita),
      telefono: blankToNull(form.telefono),
      email: blankToNull(form.email),
      residenza: blankToNull(form.residenza),
      cap: blankToNull(form.cap),
      citta: blankToNull(form.citta),
      provincia: blankToNull(form.provincia)?.toUpperCase() || null,
      occupato: Boolean(form.occupato),
      azienda_cliente_id: form.occupato && form.azienda_cliente_id ? Number(form.azienda_cliente_id) : null,
      azienda_sede_operativa_id: form.occupato && form.azienda_sede_operativa_id ? Number(form.azienda_sede_operativa_id) : null,
      data_nascita: form.data_nascita ? `${form.data_nascita}T00:00:00Z` : null,
      data_assunzione: form.occupato && form.data_assunzione ? `${form.data_assunzione}T00:00:00Z` : null,
      project_ids: normalizedProjectIds,
      tipo_contratto: form.occupato ? blankToNull(form.tipo_contratto) : null,
      ccnl: form.occupato ? blankToNull(form.ccnl) : null,
      mansione: form.occupato ? blankToNull(form.mansione) : null,
      livello_inquadramento: form.occupato ? blankToNull(form.livello_inquadramento) : null,
      note: blankToNull(form.note),
      attivo: true,
    };

    try {
      if (modal.mode === 'create') {
        await createAllievo(payload);
        showToast('Allievo creato');
      } else {
        await updateAllievo(modal.data.id, payload);
        showToast('Allievo aggiornato');
      }
      setModal(null);
      load();
      loadReferenceData();
    } catch (e) {
      showToast(e?.response?.data?.detail || 'Errore nel salvataggio allievo', 'error');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (allievo) => {
    if (!window.confirm(`Disattivare l'allievo "${allievo.nome} ${allievo.cognome}"?`)) return;
    try {
      await deleteAllievo(allievo.id);
      showToast('Allievo disattivato');
      load();
    } catch {
      showToast('Errore nella disattivazione', 'error');
    }
  };

  const handleBulkImport = async (rows) => {
    setBulkImporting(true);
    try {
      const result = await bulkImportAllievi(rows);
      await load();
      await loadReferenceData();
      if (result.success_count > 0) {
        showToast(`Importazione completata: ${result.success_count} allievi su ${result.total}`);
      }
      if (result.error_count > 0) {
        const details = result.errors.slice(0, 5).map((item) => `• ${item.name}: ${item.error}`).join('\n');
        showToast(`${result.error_count} allievi non importati:\n${details}${result.errors.length > 5 ? '\n… altri errori' : ''}`, 'error');
      }
      if (result.error_count === 0) {
        setShowBulkImport(false);
      }
    } catch (e) {
      showToast(e?.response?.data?.detail || 'Errore durante l’importazione massiva', 'error');
    } finally {
      setBulkImporting(false);
    }
  };

  const allieviOccupatiCount = useMemo(
    () => result.items.filter((item) => item.occupato).length,
    [result.items]
  );

  return (
    <div className="allievi-manager">
      <div className="allievi-header">
        <div>
          <h2>Allievi</h2>
          <p>Gestisci anagrafica allievi, progetti frequentati e collegamento azienda per gli occupati.</p>
        </div>
        <div style={{ display: 'flex', gap: '12px' }}>
          <button className="btn-secondary" onClick={() => setShowBulkImport((prev) => !prev)} disabled={bulkImporting}>
            {showBulkImport ? 'Chiudi Import Excel' : 'Importa Excel'}
          </button>
          <button className="btn-primary" onClick={openCreate}>+ Nuovo Allievo</button>
        </div>
      </div>

      {showBulkImport && (
        <AllieviBulkImport
          onImport={handleBulkImport}
          onClose={() => setShowBulkImport(false)}
          isLoading={bulkImporting}
          aziende={aziendaOptions}
        />
      )}

      <div className="allievi-summary">
        <div className="summary-card">
          <span>Totale</span>
          <strong>{result.total}</strong>
        </div>
        <div className="summary-card">
          <span>Occupati</span>
          <strong>{allieviOccupatiCount}</strong>
        </div>
      </div>

      {success && <div className="toast toast-success">{success}</div>}
      {error && <div className="toast toast-error">{error}</div>}

      <div className="allievi-filters">
        <input
          placeholder="Cerca nome, cognome, email o CF..."
          value={filters.search}
          onChange={(e) => setFilters((prev) => ({ ...prev, search: e.target.value, page: 1 }))}
        />
        <select
          value={filters.occupato}
          onChange={(e) => setFilters((prev) => ({ ...prev, occupato: e.target.value, page: 1 }))}
        >
          <option value="">Tutti</option>
          <option value="true">Solo occupati</option>
          <option value="false">Solo non occupati</option>
        </select>
      </div>

      {loading ? (
        <div className="loading-spinner">Caricamento...</div>
      ) : (
        <div className="allievi-table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Allievo</th>
                <th>Contatti</th>
                <th>Residenza</th>
                <th>Azienda</th>
                <th>Progetti</th>
                <th>Azioni</th>
              </tr>
            </thead>
            <tbody>
              {result.items.length === 0 ? (
                <tr><td colSpan={6} className="empty-cell">Nessun allievo trovato.</td></tr>
              ) : result.items.map((allievo) => (
                <tr key={allievo.id}>
                  <td>
                    <strong>{[allievo.cognome, allievo.nome].filter(Boolean).join(' ')}</strong>
                    <div className="sub-text">
                      {[allievo.luogo_nascita, allievo.data_nascita ? new Date(allievo.data_nascita).toLocaleDateString('it-IT') : null].filter(Boolean).join(' · ') || 'Anagrafica base'}
                    </div>
                  </td>
                  <td>
                    <div>{allievo.telefono || '—'}</div>
                    {allievo.email && <div className="sub-text">{allievo.email}</div>}
                  </td>
                  <td>{[allievo.residenza, allievo.citta, allievo.provincia].filter(Boolean).join(', ') || '—'}</td>
                  <td>
                    {allievo.azienda_cliente ? (
                      <>
                        <div>{allievo.azienda_cliente.ragione_sociale}</div>
                        {allievo.sede_operativa?.nome && <div className="sub-text">{allievo.sede_operativa.nome}</div>}
                        {allievo.mansione && <div className="sub-text">{allievo.mansione}</div>}
                      </>
                    ) : '—'}
                  </td>
                  <td>
                    {Array.isArray(allievo.projects) && allievo.projects.length > 0
                      ? allievo.projects.map((project) => (
                        <div key={project.id} className="sub-text project-line">{project.name}</div>
                      ))
                      : '—'}
                  </td>
                  <td className="action-cell">
                    <button className="btn-sm btn-secondary" onClick={() => openEdit(allievo)}>Modifica</button>
                    <button className="btn-sm btn-danger" onClick={() => handleDelete(allievo)}>Disattiva</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {modal && (
        <div className="modal-overlay" onClick={() => setModal(null)}>
          <div className="modal-box modal-xl" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{modal.mode === 'create' ? 'Nuovo Allievo' : 'Modifica Allievo'}</h3>
              <button className="modal-close" onClick={() => setModal(null)}>×</button>
            </div>
            <div className="modal-body">
              <div className="allievi-form-grid">
                <div className="form-group">
                  <label>Nome *</label>
                  <input value={form.nome} onChange={(e) => setForm((prev) => ({ ...prev, nome: e.target.value }))} />
                </div>
                <div className="form-group">
                  <label>Cognome *</label>
                  <input value={form.cognome} onChange={(e) => setForm((prev) => ({ ...prev, cognome: e.target.value }))} />
                </div>
                <div className="form-group">
                  <label>Codice fiscale</label>
                  <input value={form.codice_fiscale} onChange={(e) => setForm((prev) => ({ ...prev, codice_fiscale: e.target.value }))} maxLength={16} />
                </div>
                <div className="form-group">
                  <label>Luogo di nascita</label>
                  <input value={form.luogo_nascita} onChange={(e) => setForm((prev) => ({ ...prev, luogo_nascita: e.target.value }))} />
                </div>
                <div className="form-group">
                  <label>Data di nascita</label>
                  <input type="date" value={form.data_nascita} onChange={(e) => setForm((prev) => ({ ...prev, data_nascita: e.target.value }))} />
                </div>
                <div className="form-group">
                  <label>Telefono</label>
                  <input value={form.telefono} onChange={(e) => setForm((prev) => ({ ...prev, telefono: e.target.value }))} />
                </div>
                <div className="form-group">
                  <label>Email</label>
                  <input type="email" value={form.email} onChange={(e) => setForm((prev) => ({ ...prev, email: e.target.value }))} />
                </div>
                <div className="form-group allievi-col-span-2">
                  <label>Residenza</label>
                  <input value={form.residenza} onChange={(e) => setForm((prev) => ({ ...prev, residenza: e.target.value }))} />
                </div>
                <div className="form-group">
                  <label>CAP</label>
                  <input value={form.cap} onChange={(e) => setForm((prev) => ({ ...prev, cap: e.target.value }))} maxLength={5} />
                </div>
                <div className="form-group">
                  <label>Città</label>
                  <input value={form.citta} onChange={(e) => setForm((prev) => ({ ...prev, citta: e.target.value }))} />
                </div>
                <div className="form-group">
                  <label>Provincia</label>
                  <input value={form.provincia} onChange={(e) => setForm((prev) => ({ ...prev, provincia: e.target.value }))} maxLength={2} />
                </div>
                <div className="form-group checkbox-group">
                  <label>
                    <input
                      type="checkbox"
                      checked={form.occupato}
                      onChange={(e) => setForm((prev) => ({ ...prev, occupato: e.target.checked }))}
                    />
                    Occupato
                  </label>
                </div>

                {form.occupato && (
                  <>
                    <div className="form-group">
                      <label>Azienda</label>
                      <select value={form.azienda_cliente_id} onChange={(e) => setForm((prev) => ({ ...prev, azienda_cliente_id: e.target.value }))}>
                        <option value="">Seleziona azienda</option>
                        {aziendaOptions.map((azienda) => (
                          <option key={azienda.id} value={azienda.id}>{azienda.ragione_sociale}</option>
                        ))}
                      </select>
                    </div>
                    <div className="form-group">
                      <label>Sede operativa</label>
                      <select
                        value={form.azienda_sede_operativa_id}
                        onChange={(e) => setForm((prev) => ({ ...prev, azienda_sede_operativa_id: e.target.value }))}
                        disabled={!selectedCompany}
                      >
                        <option value="">
                          {!selectedCompany
                            ? 'Seleziona prima l’azienda'
                            : (selectedCompanySediOperative.length > 0 ? 'Seleziona sede operativa' : 'Nessuna sede operativa registrata')}
                        </option>
                        {selectedCompanySediOperative.map((sede) => (
                          <option key={sede.id} value={sede.id}>{sedeOperativaLabel(sede)}</option>
                        ))}
                      </select>
                    </div>
                    <div className="form-group">
                      <label>Data assunzione</label>
                      <input type="date" value={form.data_assunzione} onChange={(e) => setForm((prev) => ({ ...prev, data_assunzione: e.target.value }))} />
                    </div>
                    <div className="form-group">
                      <label>Contratto</label>
                      <input value={form.tipo_contratto} onChange={(e) => setForm((prev) => ({ ...prev, tipo_contratto: e.target.value }))} />
                    </div>
                    <div className="form-group">
                      <label>CCNL</label>
                      <input value={form.ccnl} onChange={(e) => setForm((prev) => ({ ...prev, ccnl: e.target.value }))} />
                    </div>
                    <div className="form-group">
                      <label>Mansione</label>
                      <input value={form.mansione} onChange={(e) => setForm((prev) => ({ ...prev, mansione: e.target.value }))} />
                    </div>
                    <div className="form-group">
                      <label>Livello</label>
                      <input value={form.livello_inquadramento} onChange={(e) => setForm((prev) => ({ ...prev, livello_inquadramento: e.target.value }))} />
                    </div>
                  </>
                )}

                <div className="form-group allievi-col-span-2">
                  <label>Progetti collegati</label>
                  {form.occupato && (
                    <small className="sub-text">
                      {selectedCompany
                        ? (availableProjects.length > 0 || selectedProjects.length > 0
                          ? 'Sono disponibili solo i progetti collegati all’azienda selezionata.'
                          : 'L’azienda selezionata non ha ancora progetti associati in Aziende Clienti.')
                        : 'Seleziona prima l’azienda per vedere i progetti disponibili.'}
                    </small>
                  )}
                  <div className="allievi-project-picker">
                    <select value={allievoProjectToAdd} onChange={(e) => setAllievoProjectToAdd(e.target.value)}>
                      <option value="">{form.occupato && !selectedCompany ? 'Seleziona prima l’azienda' : 'Seleziona progetto'}</option>
                      {availableProjects.map((project) => (
                        <option key={project.id} value={project.id}>{projectLabel(project)}</option>
                      ))}
                    </select>
                    <button type="button" className="btn-sm btn-secondary" onClick={handleAddProject} disabled={!allievoProjectToAdd}>
                      Aggiungi
                    </button>
                  </div>
                  <div className="allievi-project-list">
                    {selectedProjects.length > 0 ? selectedProjects.map((project) => (
                      <div key={project.id} className="allievi-project-item">
                        <div>
                          <strong>{project.name}</strong>
                          {project.status && <small>{project.status}</small>}
                        </div>
                        <button type="button" className="btn-sm btn-danger" onClick={() => handleRemoveProject(Number(project.id))}>
                          Rimuovi
                        </button>
                      </div>
                    )) : <div className="allievi-empty">Nessun progetto associato.</div>}
                  </div>
                </div>

                <div className="form-group allievi-col-span-2">
                  <label>Note</label>
                  <textarea rows={3} value={form.note} onChange={(e) => setForm((prev) => ({ ...prev, note: e.target.value }))} />
                </div>
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn-secondary" onClick={() => setModal(null)}>Annulla</button>
              <button className="btn-primary" onClick={handleSave} disabled={saving}>
                {saving ? 'Salvataggio...' : 'Salva'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
