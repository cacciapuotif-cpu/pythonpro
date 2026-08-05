/**
 * COMPONENTE GESTIONE PROGETTI COMPLETO
 *
 * Questa interfaccia permette di:
 * - Aggiungere nuovi progetti formativi tramite form
 * - Visualizzare lista completa progetti
 * - Modificare progetti esistenti
 * - Eliminare progetti
 * - Gestire stati e date dei progetti
 */

import React, { useState, useMemo, useEffect, useCallback } from 'react';
import { useProjects, useImplementingEntities, useCollaborators, useNotifications } from '../hooks/useEntity';
import { getProjectDeliveryContext, getProjectBeneficiari, getProjectModuliFormativi, updateProjectBeneficiarioRegime } from '../services/apiService';
import { FapiUploadSection, getFundDocumentModals } from './FapiUpload';
import { PianoTemplateWizardButton } from './PianoTemplateWizard';
import AssignmentModal from './AssignmentModal';
import GestioneAssociati from './GestioneAssociati';
import ProjectDeliveryCompanyPicker from './ProjectDeliveryCompanyPicker';
import ProjectDeliverySites from './ProjectDeliverySites';
import { canPerform, normalizeRole } from '../auth/permissions';
import { resolveFundConfig } from '../utils/fondoProgetto';
import ResponsiveEntityList from './responsive/ResponsiveEntityList';
import ResponsiveFilters from './responsive/ResponsiveFilters';
import './ProjectManager.scss';

const ROLE_EXPERIENCE = {
  admin: {
    eyebrow: 'Controllo strutturale',
    label: 'Amministratore',
    summary: 'Puoi creare, modificare e dismettere i progetti, oltre a presidiare gli elementi amministrativi piu sensibili.',
    ctaLabel: '➕ Nuovo Progetto',
  },
  operatore: {
    eyebrow: 'Presidio operativo',
    label: 'Operatore',
    summary: 'Concentrati sull’aggiornamento di delivery, stato e coerenza progettuale. Creazione ed eliminazione restano presidiate dagli admin.',
    ctaLabel: '✏️ Aggiorna Progetto',
  },
  consultazione: {
    eyebrow: 'Lettura controllata',
    label: 'Consultazione',
    summary: 'Puoi consultare dati, avanzamento e collegamenti del progetto senza modificarli.',
    ctaLabel: 'Consulta Progetto',
  },
};

const PROJECT_FORM_STEPS = [
  {
    id: 'base',
    title: 'Base',
    description: 'Identita del progetto, stato e calendario operativo.',
    fields: ['name', 'status', 'start_date', 'end_date', 'description'],
  },
  {
    id: 'governance',
    title: 'Governance',
    description: 'CUP, atto di approvazione e riferimenti amministrativi.',
    fields: ['cup', 'atto_approvazione'],
  },
  {
    id: 'delivery',
    title: 'Delivery',
    description: 'Ente attuatore, aziende, sedi di erogazione e allievi coinvolti.',
    fields: ['ente_attuatore_id', 'azienda_ids', 'azienda_sedi', 'allievo_ids'],
  },
];

const MODALITA_ICONS = {
  aula: '🏫',
  training_on_job: '🔧',
  fad_sincrona: '💻',
  fad_asincrona: '📱',
  propedeutica: '📋',
};

const formatModalita = (value) => {
  const normalized = String(value || '').trim();
  const labels = {
    aula: 'Aula',
    training_on_job: 'Training on job',
    fad_sincrona: 'FAD sincrona',
    fad_asincrona: 'FAD asincrona',
    propedeutica: 'Propedeutica',
  };
  return labels[normalized] || normalized || '-';
};

const formatOre = (value) => `${Number(value || 0).toLocaleString('it-IT', { maximumFractionDigits: 1 })}h`;

// UX-7: la scheda progetto dichiara QUANTI sono gli associati e ne nomina i
// primi. Con centinaia di allievi l'elenco esteso e' illeggibile: l'albero per
// azienda arriva con UX-9, il conteggio serve gia' adesso.
export const NOMI_ASSOCIATI_MOSTRATI = 5;

export function riepilogoAssociati(elenco, etichetta, messaggioVuoto) {
  if (!Array.isArray(elenco) || elenco.length === 0) return messaggioVuoto;
  const nomi = elenco.slice(0, NOMI_ASSOCIATI_MOSTRATI).map(etichetta).join(', ');
  const restanti = elenco.length - NOMI_ASSOCIATI_MOSTRATI;
  return `${elenco.length} — ${nomi}${restanti > 0 ? ` e altri ${restanti}` : ''}`;
}

// "sede da definire" ripetuto una volta per azienda (fino a decine di volte)
// e' illeggibile. Un conteggio sintetico dice subito quanto lavoro manca;
// il dettaglio per azienda resta disponibile espandendolo.
export function riepilogoSediDelivery(aziendeDelivery) {
  const elenco = Array.isArray(aziendeDelivery) ? aziendeDelivery : [];
  const definite = elenco.filter((item) => Array.isArray(item.sedi) && item.sedi.length > 0).length;
  return { definite, totale: elenco.length };
}

// Moduli Formativi e' fund-agnostico lato backend (GET .../moduli-formativi
// interroga solo per project_id): la sezione e' sempre montata, per
// qualunque fondo. E' vuota per i fondi che non hanno ancora un import che
// popola ModuloFormativo — un dato mancante, non una sezione da nascondere.
const ModuliFormativiSection = ({ project, onRequestFormulario }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!project?.id) return undefined;
    let cancelled = false;

    const loadModuli = async () => {
      try {
        setLoading(true);
        setError('');
        const response = await getProjectModuliFormativi(project.id);
        if (!cancelled) setData(response);
      } catch (err) {
        if (!cancelled) {
          setError(err?.response?.data?.detail || 'Moduli formativi non disponibili');
          setData(null);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    loadModuli();
    return () => {
      cancelled = true;
    };
  }, [project?.id]);

  const progettiFapi = data?.progetti_fapi || [];
  const formularioModal = getFundDocumentModals(project).formulario;

  return (
    <section className="moduli-formativi-section">
      <div className="moduli-formativi-header">
        <div>
          <h4>Moduli Formativi</h4>
          <span>{project.codice_fapi || resolveFundConfig(project).etichetta_codice_progetto}</span>
        </div>
        {data && (
          <strong>{data.moduli_totali} moduli · {formatOre(data.ore_totali)}</strong>
        )}
      </div>

      {loading && <div className="moduli-loading">Caricamento moduli...</div>}
      {error && <div className="moduli-error">{error}</div>}
      {!loading && !error && progettiFapi.length === 0 && (
        <div className="moduli-empty">
          Nessun modulo formativo — importa il formulario o aggiungili manualmente
          {formularioModal && onRequestFormulario && (
            <button type="button" className="moduli-empty-action" onClick={onRequestFormulario}>
              Importa formulario
            </button>
          )}
        </div>
      )}

      {progettiFapi.map((gruppo, index) => {
        const allModuli = [
          ...(gruppo.moduli_formativi || []),
          ...(gruppo.moduli_propedeutici || []),
        ];
        const pgLabel = `PG${String(index + 1).padStart(2, '0')}`;
        const partecipanti = gruppo.partecipanti ? ` (${gruppo.partecipanti} partecipanti)` : '';

        return (
          <div className="moduli-fapi-group" key={gruppo.codice_progetto_fapi}>
            <div className="moduli-fapi-title">
              <span>{pgLabel} — {gruppo.azienda?.ragione_sociale || gruppo.codice_progetto_fapi}{partecipanti}</span>
              <small>{gruppo.codice_progetto_fapi}</small>
            </div>
            <div className="moduli-table-wrap">
              <table className="moduli-table">
                <thead>
                  <tr>
                    <th>Titolo modulo</th>
                    <th>Materia</th>
                    <th>Modalità</th>
                    <th>Ore</th>
                    <th>Tipo</th>
                  </tr>
                </thead>
                <tbody>
                  {allModuli.map((modulo) => (
                    <tr key={modulo.id}>
                      <td>{modulo.titolo_modulo}</td>
                      <td>{modulo.materia || '-'}</td>
                      <td>{MODALITA_ICONS[modulo.modalita_erogazione] || '•'} {formatModalita(modulo.modalita_erogazione)}</td>
                      <td>{formatOre(modulo.ore_previste)}</td>
                      <td>{modulo.tipo_attivita === 'propedeutica' ? 'Propedeutica' : 'Formativa'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="moduli-footer">
              Totale ore formative: {formatOre(gruppo.ore_formative_totali)} | Totale ore propedeutiche: {formatOre(gruppo.ore_propedeutiche_totali)}
            </div>
          </div>
        );
      })}
    </section>
  );
};

const ProjectManager = ({ currentUser, initialFilters = {} }) => {
  // ==========================================
  // CONTEXT E HOOKS
  // ==========================================

  // Carica dati dal Context
  const { data: projects, loading: loadingProjects, error: contextError, refresh, create, update, remove } = useProjects();
  const { data: allEntities, loading: loadingEntities } = useImplementingEntities();
  const { data: collaborators } = useCollaborators();
  const { showSuccess, showError } = useNotifications();
  const canWriteProjects = canPerform(currentUser, 'WRITE_PROJECTS');
  const roleExperience = ROLE_EXPERIENCE[normalizeRole(currentUser)];

  // Filtra solo enti attivi per il dropdown
  const implementingEntities = useMemo(() =>
    allEntities.filter(e => e.is_active),
    [allEntities]
  );

  // Dati del form per nuovo/modifica progetto
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    start_date: '',
    end_date: '',
    status: 'active',
    ente_erogatore: '',
    cup: '',
    atto_approvazione: '',
    sede_aziendale_comune: '',
    sede_aziendale_via: '',
    sede_aziendale_numero_civico: '',
    avviso: '',
    avviso_id: '',
    data_approvazione: '',
    data_avvio_piano: '',
    azienda_ids: [],
    allievo_ids: [],
    // { [azienda_id]: [{ sede_tipo: 'ente'|'azienda', sede_id }, ...] }
    azienda_sedi: {},
    ente_attuatore_id: null // NUOVO: FK verso ente attuatore
  });
  const [aziendaOptions, setAziendaOptions] = useState([]);
  const [allievoOptions, setAllievoOptions] = useState([]);
  const [deliveryContext, setDeliveryContext] = useState(null);
  const [deliveryContextLoading, setDeliveryContextLoading] = useState(false);

  // Stati locali dell'interfaccia
  const [editingId, setEditingId] = useState(null); // ID del progetto in modifica
  const [showForm, setShowForm] = useState(false);  // Mostra/nascondi form
  const [deleteConfirm, setDeleteConfirm] = useState(null); // Stato per conferma eliminazione
  const [statusFilter, setStatusFilter] = useState(initialFilters.status || 'all');
  const [focusedProjectId, setFocusedProjectId] = useState(initialFilters.projectId || null);
  const [activeStepIndex, setActiveStepIndex] = useState(0);
  const [beneficiariByProject, setBeneficiariByProject] = useState({});
  const [regimeSaving, setRegimeSaving] = useState({});
  const [showFapiModal, setShowFapiModal] = useState(false);
  const [regimeOpenProject, setRegimeOpenProject] = useState(null);
  // UX-8: il pannello di dissociazione sta chiuso finche' non serve, come il
  // riquadro dei regimi: la scheda resta leggibile.
  const [associatiOpenProject, setAssociatiOpenProject] = useState(null);
  const [sediOpenProject, setSediOpenProject] = useState(null);
  const [plafondByBeneficiario, setPlafondByBeneficiario] = useState({});
  const [regimeByBeneficiario, setRegimeByBeneficiario] = useState({});
  const [assignmentProject, setAssignmentProject] = useState(null);
  // Stato vuoto dei moduli formativi: l'azione "Importa formulario" apre lo
  // stesso modal che FapiUploadSection userebbe per il fondo del progetto.
  const [formularioAutoOpenProjectId, setFormularioAutoOpenProjectId] = useState(null);

  // Combina stati di loading
  const loading = loadingProjects || loadingEntities;

  const loadBeneficiari = async (projectId) => {
    if (beneficiariByProject[projectId]) return;
    try {
      const data = await getProjectBeneficiari(projectId);
      const beneficiari = data.beneficiari || [];
      setBeneficiariByProject(prev => ({ ...prev, [projectId]: beneficiari }));
      const plafondInit = {};
      const regimeInit = {};
      beneficiari.forEach(b => {
        const key = `${projectId}_${b.azienda_id}`;
        plafondInit[key] = b.plafond_dichiarato != null ? String(b.plafond_dichiarato) : '';
        regimeInit[key] = b.regime_aiuto || 'non_definito';
      });
      setPlafondByBeneficiario(prev => ({ ...prev, ...plafondInit }));
      setRegimeByBeneficiario(prev => ({ ...prev, ...regimeInit }));
    } catch {
      setBeneficiariByProject(prev => ({ ...prev, [projectId]: [] }));
    }
  };

  const handleSaveRegime = async (projectId, aziendaId) => {
    const key = `${projectId}_${aziendaId}`;
    const regime = regimeByBeneficiario[key] || 'non_definito';
    const plafondStr = plafondByBeneficiario[key] || '';
    const plafond = plafondStr !== '' ? parseFloat(plafondStr) : null;
    setRegimeSaving(prev => ({ ...prev, [key]: true }));
    try {
      const body = { regime_aiuto: regime };
      if (plafond !== null && !isNaN(plafond)) body.plafond_dichiarato = plafond;
      await updateProjectBeneficiarioRegime(projectId, aziendaId, body);
      setBeneficiariByProject(prev => ({
        ...prev,
        [projectId]: (prev[projectId] || []).map(b =>
          b.azienda_id === aziendaId
            ? { ...b, regime_aiuto: regime === 'non_definito' ? null : regime, plafond_dichiarato: plafond }
            : b
        ),
      }));
    } catch (err) {
      alert('Errore salvataggio regime: ' + (err?.response?.data?.detail || err?.message || 'Errore sconosciuto'));
    } finally {
      setRegimeSaving(prev => ({ ...prev, [key]: false }));
    }
  };

  const handleAssignmentSuccess = (message) => {
    showSuccess(message);
    setAssignmentProject(null);
    refresh();
  };

  useEffect(() => {
    if (!showForm) return undefined;
    if (!editingId) {
      setDeliveryContext({
        project_id: null,
        has_convenzione: false,
        blocked_reason: 'Collega prima la convenzione al progetto',
        ente_attuatore: null,
      });
      return undefined;
    }

    let cancelled = false;
    setDeliveryContextLoading(true);
    getProjectDeliveryContext(editingId)
      .then((context) => {
        if (cancelled) return;
        setDeliveryContext(context);
        setFormData((previous) => ({
          ...previous,
          ente_attuatore_id: context?.ente_attuatore?.id || null,
        }));
      })
      .catch((error) => {
        if (cancelled) return;
        setDeliveryContext({
          project_id: editingId,
          has_convenzione: false,
          blocked_reason: error?.response?.data?.detail || 'Impossibile verificare la convenzione del progetto',
          ente_attuatore: null,
        });
      })
      .finally(() => {
        if (!cancelled) setDeliveryContextLoading(false);
      });

    return () => { cancelled = true; };
  }, [editingId, showForm]);

  const handleCompaniesLoaded = useCallback((items) => {
    setAziendaOptions((current) => {
      const merged = new Map(current.map((item) => [Number(item.id), item]));
      (items || []).forEach((item) => merged.set(Number(item.id), item));
      return Array.from(merged.values());
    });
  }, []);

  const handleStudentsLoaded = useCallback((items) => {
    setAllievoOptions((current) => {
      const merged = new Map(current.map((item) => [Number(item.id), item]));
      (items || []).forEach((item) => merged.set(Number(item.id), item));
      return Array.from(merged.values());
    });
  }, []);

  const handleDeliveryError = useCallback((message) => showError(message), [showError]);

  // ==========================================
  // GESTIONE FORM
  // ==========================================

  /**
   * GESTISCE I CAMBIAMENTI NEI CAMPI DEL FORM
   */
  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  // UX-9: l'albero emette la coppia coerente (aziende, allievi) in un colpo
  // solo: la regola "un allievo tira dentro la sua azienda" vive li', non qui.
  const handleAlberoChange = ({ azienda_ids, allievo_ids }) => {
    setFormData((prev) => {
      // Un'azienda che esce dalla selezione perde anche la sede scelta:
      // altrimenti resterebbe uno stato orfano che il submit rimanderebbe
      // per un'azienda non piu' coinvolta.
      const nextSedi = {};
      azienda_ids.forEach((id) => {
        if (prev.azienda_sedi[id]) nextSedi[id] = prev.azienda_sedi[id];
      });
      return { ...prev, azienda_ids, allievo_ids, azienda_sedi: nextSedi };
    });
  };

  /**
   * VALIDA I DATI DEL FORM
   */
  const validateForm = () => {
    const errors = [];

    if (!formData.name.trim()) {
      errors.push('Il nome del progetto è obbligatorio');
    }

    if (!formData.description.trim()) {
      errors.push('La descrizione è obbligatoria');
    }

    if (!formData.atto_approvazione.trim()) {
      errors.push('L\'atto di approvazione è obbligatorio');
    }

    // Validazione date
    if (formData.start_date && formData.end_date) {
      const startDate = new Date(formData.start_date);
      const endDate = new Date(formData.end_date);

      if (endDate <= startDate) {
        errors.push('La data di fine deve essere successiva alla data di inizio');
      }
    }

    return errors;
  };

  const getStepErrorCounts = () => {
    const errors = validateForm();
    return PROJECT_FORM_STEPS.map((step) =>
      step.fields.filter((field) =>
        errors.some((error) => {
          if (field === 'name') return error.includes('nome del progetto');
          if (field === 'description') return error.includes('descrizione');
          if (field === 'atto_approvazione') return error.includes("atto di approvazione");
          if (field === 'end_date' || field === 'start_date') return error.includes('data di fine');
          return false;
        })
      ).length
    );
  };

  /**
   * GESTISCE L'INVIO DEL FORM
   */
  const handleSubmit = async (e) => {
    e.preventDefault();

    // Validazione
    const errors = validateForm();
    if (errors.length > 0) {
      showError(errors.join(', '));
      return;
    }
    if (editingId && deliveryContext?.blocked_reason) {
      showError(deliveryContext.blocked_reason);
      return;
    }

    try {
      // Prepara i dati (converte date vuote in null e formatta quelle presenti)
      const projectData = {
        ...formData,
        ente_attuatore_id: editingId ? (deliveryContext?.ente_attuatore?.id || null) : null,
        azienda_ids: Array.isArray(formData.azienda_ids) ? formData.azienda_ids.map((id) => parseInt(id, 10)) : [],
        allievo_ids: Array.isArray(formData.allievo_ids) ? formData.allievo_ids.map((id) => parseInt(id, 10)) : [],
        azienda_sedi: (Array.isArray(formData.azienda_ids) ? formData.azienda_ids : []).flatMap((id) =>
          (formData.azienda_sedi[id] || []).map((sede) => ({
            azienda_id: parseInt(id, 10),
            sede_tipo: sede.sede_tipo,
            sede_id: parseInt(sede.sede_id, 10),
          }))
        ),
        start_date: formData.start_date ? `${formData.start_date}T00:00:00Z` : null,
        end_date: formData.end_date ? `${formData.end_date}T23:59:59Z` : null,
        ente_erogatore: formData.ente_erogatore || null,
        avviso: formData.avviso || null,
        avviso_id: formData.avviso_id ? parseInt(formData.avviso_id, 10) : null,
        data_approvazione: formData.data_approvazione || null,
        data_avvio_piano: formData.data_avvio_piano || null,
      };

      if (editingId) {
        // MODALITÀ MODIFICA
        await update(editingId, projectData);
        showSuccess('Progetto aggiornato con successo!');
      } else {
        // MODALITÀ CREAZIONE
        await create(projectData);
        showSuccess('Progetto aggiunto con successo!');
      }

      // Ricarica i dati e reimposta il form
      await refresh();
      resetForm();

    } catch (err) {
      console.error('Errore salvataggio:', err);
      showError(err?.response?.data?.detail || err?.message || 'Errore nel salvataggio. Riprova.');
    }
  };

  /**
   * REIMPOSTA IL FORM
   */
  const resetForm = () => {
    setFormData({
      name: '',
      description: '',
      start_date: '',
      end_date: '',
      status: 'active',
      ente_erogatore: '',
      cup: '',
      atto_approvazione: '',
      sede_aziendale_comune: '',
      sede_aziendale_via: '',
      sede_aziendale_numero_civico: '',
      avviso: '',
      avviso_id: '',
      data_approvazione: '',
      data_avvio_piano: '',
      azienda_ids: [],
      allievo_ids: [],
      azienda_sedi: {},
      ente_attuatore_id: null
    });
    setEditingId(null);
    setShowForm(false);
    setActiveStepIndex(0);
    setAziendaOptions([]);
    setAllievoOptions([]);
    setDeliveryContext(null);
  };

  // ==========================================
  // AZIONI SUI PROGETTI
  // ==========================================

  /**
   * AVVIA MODIFICA PROGETTO
   */
  const startEdit = (project) => {
    setAziendaOptions(Array.isArray(project.aziende_coinvolte) ? project.aziende_coinvolte : []);
    setAllievoOptions(Array.isArray(project.allievi_coinvolti) ? project.allievi_coinvolti : []);
    setDeliveryContext(null);
    setFormData({
      name: project.name,
      description: project.description || '',
      start_date: project.start_date ? project.start_date.split('T')[0] : '',
      end_date: project.end_date ? project.end_date.split('T')[0] : '',
      status: project.status,
      ente_erogatore: project.ente_erogatore || '',
      cup: project.cup || '',
      atto_approvazione: project.atto_approvazione || '',
      sede_aziendale_comune: project.sede_aziendale_comune || '',
      sede_aziendale_via: project.sede_aziendale_via || '',
      sede_aziendale_numero_civico: project.sede_aziendale_numero_civico || '',
      avviso: project.avviso || '',
      avviso_id: project.avviso_id ? String(project.avviso_id) : '',
      data_approvazione: project.data_approvazione ? project.data_approvazione.split('T')[0] : '',
      data_avvio_piano: project.data_avvio_piano ? project.data_avvio_piano.split('T')[0] : '',
      azienda_ids: Array.isArray(project.azienda_ids) ? project.azienda_ids.map((id) => Number(id)) : [],
      allievo_ids: Array.isArray(project.allievo_ids) ? project.allievo_ids.map((id) => Number(id)) : [],
      azienda_sedi: Array.isArray(project.aziende_delivery)
        ? project.aziende_delivery.reduce((acc, item) => {
          acc[item.azienda_id] = (item.sedi || []).map((sede) => ({
            sede_tipo: sede.sede_tipo,
            sede_id: sede.sede_tipo === 'ente' ? sede.sede_ente_location_id : sede.sede_azienda_operativa_id,
          }));
          return acc;
        }, {})
        : {},
      ente_attuatore_id: project.ente_attuatore_id || null
    });
    setEditingId(project.id);
    setShowForm(true);
    setActiveStepIndex(0);
  };

  /**
   * ELIMINA PROGETTO
   */
  const handleDelete = async (projectId) => {
    try {
      await remove(projectId);
      showSuccess('Progetto eliminato con successo!');
      await refresh();
      setDeleteConfirm(null);
    } catch (err) {
      console.error('Errore eliminazione:', err);
      showError('Errore nell\'eliminazione. Riprova.');
    }
  };

  // ==========================================
  // FUNZIONI DI UTILITÀ
  // ==========================================

  /**
   * OTTIENI COLORE PER STATO PROGETTO
   */
  const getStatusColor = (status) => {
    switch (status) {
      case 'active': return '#28a745';
      case 'completed': return '#17a2b8';
      case 'paused': return '#ffc107';
      case 'cancelled': return '#dc3545';
      default: return '#6c757d';
    }
  };

  /**
   * OTTIENI ETICHETTA PER STATO
   */
  const getStatusLabel = (status) => {
    switch (status) {
      case 'active': return '🟢 Attivo';
      case 'completed': return '✅ Completato';
      case 'paused': return '⏸️ In Pausa';
      case 'cancelled': return '❌ Annullato';
      case 'attention': return '⚠️ In attenzione';
      case 'deadline-7-days': return '⏳ In scadenza entro 7 giorni';
      default: return '❓ Sconosciuto';
    }
  };

  /**
   * FILTRA PROGETTI PER STATO
   */
  const getProjectOperationalState = (project) => {
    const hasEntity = !!project.ente_attuatore_id;

    if (project.status === 'active' && project.end_date) {
      const endDate = new Date(project.end_date);
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      endDate.setHours(0, 0, 0, 0);
      const diffDays = Math.ceil((endDate - today) / (1000 * 60 * 60 * 24));

      if (diffDays < 0) {
        return 'overdue';
      }

      if (diffDays <= 30 || !hasEntity) {
        return 'attention';
      }
    }

    if (!hasEntity) {
      return 'attention';
    }

    return 'stable';
  };

  const isDeadlineWithinSevenDays = (project) => {
    if (project.status !== 'active' || !project.end_date) return false;
    const endDate = new Date(project.end_date);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    endDate.setHours(0, 0, 0, 0);
    const diffDays = Math.ceil((endDate - today) / (1000 * 60 * 60 * 24));
    return diffDays >= 0 && diffDays <= 7;
  };

  const filteredProjects = projects.filter(project => {
    if (focusedProjectId) return String(project.id) === String(focusedProjectId);
    if (statusFilter === 'all') return true;
    if (statusFilter === 'attention') return getProjectOperationalState(project) !== 'stable';
    if (statusFilter === 'deadline-7-days') return isDeadlineWithinSevenDays(project);
    return project.status === statusFilter;
  });

  const projectSummary = useMemo(() => {
    return projects.reduce((summary, project) => {
      const state = getProjectOperationalState(project);
      summary.total += 1;
      if (project.status === 'active') summary.active += 1;
      if (state === 'attention') summary.attention += 1;
      if (state === 'overdue') summary.overdue += 1;
      if (!project.ente_attuatore_id) summary.missingEntity += 1;
      return summary;
    }, {
      total: 0,
      active: 0,
      attention: 0,
      overdue: 0,
      missingEntity: 0,
    });
  }, [projects]);

  const stepErrorCounts = getStepErrorCounts();
  const completedFields = [
    formData.name,
    formData.description,
    formData.start_date,
    formData.end_date,
    formData.avviso_id,
    formData.cup,
    formData.atto_approvazione,
    formData.ente_attuatore_id,
    formData.azienda_ids.length > 0 ? 'aziende' : '',
    Object.values(formData.azienda_sedi).some((sedi) => sedi?.length) ? 'sedi' : '',
    formData.allievo_ids.length > 0 ? 'allievi' : '',
  ].filter((value) => `${value ?? ''}`.trim() !== '').length;
  const completionPercentage = Math.round((completedFields / 10) * 100);
  const currentStep = PROJECT_FORM_STEPS[activeStepIndex];
  const selectedEntity = deliveryContext?.ente_attuatore || null;
  const selectedAziende = formData.azienda_ids
    .map((aziendaId) => aziendaOptions.find((azienda) => Number(azienda.id) === Number(aziendaId)))
    .filter(Boolean);
  const selectedAllievi = formData.allievo_ids
    .map((allievoId) => allievoOptions.find((allievo) => Number(allievo.id) === Number(allievoId)))
    .filter(Boolean);
  const aziendeSenzaSede = selectedAziende.filter((azienda) => !(formData.azienda_sedi[azienda.id] || []).length);
  const showCreateAction = canWriteProjects;

  const goToStep = (index) => {
    if (index < 0 || index >= PROJECT_FORM_STEPS.length) {
      return;
    }

    setActiveStepIndex(index);
  };

  // ==========================================
  // RENDER DEL COMPONENTE
  // ==========================================

  if (loading && projects.length === 0) {
    return (
      <div className="project-manager">
        <div className="loading">
          <div className="spinner"></div>
          <p>Caricamento progetti...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="project-manager">
      {/* INTESTAZIONE */}
      <div className="manager-header">
        <h1>📁 Gestione Progetti</h1>
        <p>Crea e gestisci i progetti formativi della tua organizzazione</p>

        <div className="role-operations-banner project-role-banner">
          <div>
            <span className="role-operations-eyebrow">{roleExperience.eyebrow}</span>
            <strong>{roleExperience.label}</strong>
          </div>
          <p>{roleExperience.summary}</p>
        </div>

        {showCreateAction ? (
          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
            <button
              className={`add-button ${showForm ? 'active' : ''}`}
              onClick={() => {
                setShowForm(!showForm);
                if (showForm) {
                  resetForm();
                } else {
                  setActiveStepIndex(0);
                }
              }}
            >
              {showForm ? '❌ Chiudi Form' : roleExperience.ctaLabel}
            </button>
            <button
              style={{
                padding: '8px 14px',
                fontSize: '13px',
                borderRadius: '8px',
                border: '0.5px solid #2c6fad',
                background: '#ebf4ff',
                color: '#1a4a7a',
                cursor: 'pointer',
              }}
              onClick={() => setShowFapiModal(true)}
            >
              📄 Carica Atto / Convenzione
            </button>
            {/* E1.5: percorso guidato da template, ACCANTO al percorso libero
                (upload atto/convenzione + piano XLSX) che resta invariato.
                RBAC dentro al bottone: solo admin+operatore. */}
            <PianoTemplateWizardButton
              currentUser={currentUser}
              availableProjects={projects}
              onCreated={refresh}
            />
          </div>
        ) : (
          <div className="project-guidance-pill">
            Apri un progetto esistente per aggiornarne stato, delivery e riferimenti attuativi.
          </div>
        )}
      </div>

      {/* MESSAGGI DI STATO */}
      {contextError && (
        <div className="message error-message">
          ⚠️ {contextError.message || 'Errore nel caricamento dei progetti'}
        </div>
      )}

      {/* FORM AGGIUNTA/MODIFICA */}
      {showForm && (
        <div className="form-section project-wizard">
          <div className="wizard-header">
            <div>
              <span className="wizard-eyebrow">Wizard progetto</span>
              <h2>{editingId ? 'Modifica progetto' : 'Nuovo progetto'}</h2>
              <p>
                Organizza il progetto in tre passaggi: base, governance e delivery operativo.
              </p>
            </div>
            <div className="wizard-progress-card project-progress-card">
              <span>Completamento</span>
              <strong>{completionPercentage}%</strong>
              <small>{completedFields} campi su 12 valorizzati</small>
            </div>
          </div>

          <div className="wizard-layout">
            <aside className="wizard-sidebar">
              <ol className="wizard-steps">
                {PROJECT_FORM_STEPS.map((step, index) => {
                  const isActive = index === activeStepIndex;
                  const isDone = index < activeStepIndex;
                  const hasErrors = stepErrorCounts[index] > 0;

                  return (
                    <li key={step.id}>
                      <button
                        type="button"
                        className={`wizard-step ${isActive ? 'active' : ''} ${isDone ? 'done' : ''}`}
                        onClick={() => goToStep(index)}
                      >
                        <span className={`wizard-step-index ${hasErrors ? 'error' : ''}`}>
                          {isDone ? '✓' : index + 1}
                        </span>
                        <span className="wizard-step-copy">
                          <strong>{step.title}</strong>
                          <small>{step.description}</small>
                          {hasErrors ? <em>{stepErrorCounts[index]} controlli aperti</em> : null}
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ol>

              <div className="wizard-summary-card">
                <h3>Checkpoint progetto</h3>
                <ul>
                  <li className={formData.name ? 'done' : ''}>
                    Nome progetto {formData.name ? 'presente' : 'mancante'}
                  </li>
                  <li className={formData.atto_approvazione ? 'done' : ''}>
                    Atto di approvazione {formData.atto_approvazione ? 'presente' : 'mancante'}
                  </li>
                  <li className={formData.start_date && formData.end_date ? 'done' : ''}>
                    Finestra temporale {formData.start_date && formData.end_date ? 'impostata' : 'incompleta'}
                  </li>
                  <li className={formData.ente_attuatore_id ? 'done' : ''}>
                    Ente attuatore {formData.ente_attuatore_id ? 'selezionato' : 'non selezionato'}
                  </li>
                  <li className={formData.azienda_ids.length > 0 ? 'done' : ''}>
                    Aziende coinvolte {formData.azienda_ids.length > 0 ? 'associate' : 'non associate'}
                  </li>
                  <li className={selectedAziende.length > 0 && aziendeSenzaSede.length === 0 ? 'done' : ''}>
                    {aziendeSenzaSede.length > 0
                      ? `Sede di erogazione mancante per: ${aziendeSenzaSede.map((azienda) => azienda.ragione_sociale).join(', ')}`
                      : selectedAziende.length > 0 ? 'Sedi di erogazione indicate' : 'Sedi di erogazione non verificabili'}
                  </li>
                  <li className={formData.allievo_ids.length > 0 ? 'done' : ''}>
                    Allievi coinvolti {formData.allievo_ids.length > 0 ? 'associati' : 'non associati'}
                  </li>
                </ul>
              </div>
            </aside>

            <form onSubmit={handleSubmit} className="project-form wizard-form">
              <div className="wizard-step-panel">
                <div className="wizard-step-header">
                  <div>
                    <span className="wizard-step-label">
                      Step {activeStepIndex + 1} di {PROJECT_FORM_STEPS.length}
                    </span>
                    <h3>{currentStep.title}</h3>
                    <p>{currentStep.description}</p>
                  </div>
                </div>

                {currentStep.id === 'base' && (
                  <div className="form-grid">
                    <div className="form-group">
                      <label htmlFor="name">Nome Progetto *</label>
                      <input
                        type="text"
                        id="name"
                        name="name"
                        value={formData.name}
                        onChange={handleInputChange}
                        placeholder="Es: Corso React Avanzato"
                        required
                      />
                    </div>

                    <div className="form-group">
                      <label htmlFor="status">Stato Progetto</label>
                      <select
                        id="status"
                        name="status"
                        value={formData.status}
                        onChange={handleInputChange}
                      >
                        <option value="active">🟢 Attivo</option>
                        <option value="paused">⏸️ In Pausa</option>
                        <option value="completed">✅ Completato</option>
                        <option value="cancelled">❌ Annullato</option>
                      </select>
                    </div>

                    <div className="form-group">
                      <label htmlFor="start_date">Data Inizio</label>
                      <input
                        type="date"
                        id="start_date"
                        name="start_date"
                        value={formData.start_date}
                        onChange={handleInputChange}
                      />
                    </div>

                    <div className="form-group">
                      <label htmlFor="end_date">Data Fine</label>
                      <input
                        type="date"
                        id="end_date"
                        name="end_date"
                        value={formData.end_date}
                        onChange={handleInputChange}
                      />
                    </div>

                    <div className="form-group full-width">
                      <label htmlFor="description">Descrizione *</label>
                      <textarea
                        id="description"
                        name="description"
                        value={formData.description}
                        onChange={handleInputChange}
                        placeholder="Descrivi obiettivi, attivita, target e valore operativo del progetto..."
                        rows="5"
                        required
                      />
                    </div>
                  </div>
                )}

                {currentStep.id === 'governance' && (
                  <div className="form-grid">
                    <div className="form-group">
                      <label htmlFor="cup">Codice CUP</label>
                      <input
                        type="text"
                        id="cup"
                        name="cup"
                        value={formData.cup}
                        onChange={handleInputChange}
                        placeholder="Es: C12D20001234567"
                        maxLength="15"
                      />
                      <small className="field-hint">
                        Utile per tracciabilita, reporting e documentazione.
                      </small>
                    </div>

                    <div className="wizard-hint-card project-hint-card">
                      <h4>Governance minima</h4>
                      <p>
                        Atto di approvazione e date coerenti sono la base per evitare attriti a valle su presenze, assegnazioni e contratti.
                      </p>
                    </div>

                    <div className="form-group full-width">
                      <label htmlFor="atto_approvazione">Atto di Approvazione *</label>
                      <input
                        type="text"
                        id="atto_approvazione"
                        name="atto_approvazione"
                        value={formData.atto_approvazione}
                        onChange={handleInputChange}
                        placeholder="Es: DD n. 123 del 15/02/2026"
                        required
                      />
                    </div>

                    <div className="form-group">
                      <label htmlFor="data_approvazione">Data Approvazione {!editingId && '*'}</label>
                      <input
                        type="date"
                        id="data_approvazione"
                        name="data_approvazione"
                        value={formData.data_approvazione}
                        onChange={handleInputChange}
                        required={!editingId}
                      />
                      <small className="field-hint">
                        Obbligatoria per creare un nuovo progetto attivo.
                      </small>
                    </div>

                    <div className="form-group">
                      <label htmlFor="data_avvio_piano">Data Avvio Piano {!editingId && '*'}</label>
                      <input
                        type="date"
                        id="data_avvio_piano"
                        name="data_avvio_piano"
                        value={formData.data_avvio_piano}
                        onChange={handleInputChange}
                        required={!editingId}
                      />
                      <small className="field-hint">
                        Obbligatoria per creare un nuovo progetto attivo.
                      </small>
                    </div>
                  </div>
                )}

                {currentStep.id === 'delivery' && (
                  <div className="wizard-documents-grid">
                    <div className="form-grid">
                      <div className="form-group full-width">
                        <label htmlFor="ente_attuatore_delivery">Ente Attuatore</label>
                        <input
                          id="ente_attuatore_delivery"
                          type="text"
                          readOnly
                          value={deliveryContextLoading
                            ? 'Verifica convenzione in corso…'
                            : selectedEntity?.ragione_sociale || 'Non disponibile'}
                        />
                        <small className="field-hint">
                          Valore derivato dalla convenzione collegata al progetto; non è modificabile dalla Delivery.
                        </small>
                      </div>

                      {deliveryContext?.blocked_reason ? (
                        <div className="form-group full-width delivery-blocked" role="alert">
                          <strong>{deliveryContext.blocked_reason}</strong>
                          <p>La selezione di ente, aziende e allievi resta bloccata finché il progetto non ha una convenzione collegata.</p>
                        </div>
                      ) : (
                        <div className="form-group full-width">
                          <label>Aziende e allievi coinvolti</label>
                          <small className="field-hint">
                            {formData.ente_erogatore === 'Formazienda'
                              ? "L'atto di adesione non elenca beneficiarie: la ricerca usa l'intero catalogo aziende."
                              : 'La ricerca usa soltanto le aziende comprese nella convenzione del progetto.'}
                            {' '}Gli allievi vengono caricati quando apri la singola azienda.
                          </small>
                          <ProjectDeliveryCompanyPicker
                            projectId={editingId}
                            aziendeSelezionate={formData.azienda_ids}
                            allieviSelezionati={formData.allievo_ids}
                            onChange={handleAlberoChange}
                            onCompaniesLoaded={handleCompaniesLoaded}
                            onStudentsLoaded={handleStudentsLoaded}
                            onError={handleDeliveryError}
                          />
                        </div>
                      )}

                      {!deliveryContext?.blocked_reason && selectedAziende.length > 0 && (
                        <div className="form-group full-width">
                          <label>Sede di erogazione per azienda</label>
                          <small className="field-hint">
                            Ogni azienda puo' avere una o piu' sedi del proprio
                            anagrafico oppure dell'ente attuatore. Le sedi nuove
                            restano disponibili per i progetti successivi.
                          </small>
                          <ProjectDeliverySites
                            aziende={selectedAziende}
                            ente={selectedEntity}
                            value={formData.azienda_sedi}
                            onChange={(azienda_sedi) => setFormData((previous) => ({ ...previous, azienda_sedi }))}
                            onError={showError}
                          />
                        </div>
                      )}

                    </div>

                    <div className="project-delivery-card">
                      <h4>Riepilogo delivery</h4>
                      <div className="project-delivery-list">
                        <div>
                          <span>Ente attuatore</span>
                          <strong>{selectedEntity ? `${selectedEntity.ragione_sociale} (da convenzione)` : 'Non disponibile'}</strong>
                        </div>
                        <div>
                          <span>Aziende coinvolte</span>
                          <strong>
                            {selectedAziende.length > 0
                              ? selectedAziende.map((azienda) => `${azienda.ragione_sociale} (${(formData.azienda_sedi[azienda.id] || []).length} sedi)`).join(', ')
                              : 'Non impostate'}
                          </strong>
                        </div>
                        <div>
                          <span>Allievi coinvolti</span>
                          <strong>{selectedAllievi.length > 0 ? selectedAllievi.map((allievo) => `${allievo.nome} ${allievo.cognome}`).join(', ') : 'Non impostati'}</strong>
                        </div>
                        <div>
                          <span>Ente erogatore</span>
                          <strong>{formData.ente_erogatore || 'Non impostato'}</strong>
                        </div>
                        <div>
                          <span>Avviso</span>
                          <strong>{formData.avviso || 'Non impostato'}</strong>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              <div className="form-buttons wizard-actions">
                <button
                  type="button"
                  onClick={resetForm}
                  className="cancel-button"
                >
                  Annulla
                </button>

                <div className="wizard-actions-right">
                  <button
                    type="button"
                    onClick={() => goToStep(activeStepIndex - 1)}
                    className="secondary-button"
                    disabled={activeStepIndex === 0}
                  >
                    Indietro
                  </button>

                  {activeStepIndex < PROJECT_FORM_STEPS.length - 1 ? (
                    <button
                      type="button"
                      onClick={() => goToStep(activeStepIndex + 1)}
                      className="submit-button"
                    >
                      Continua
                    </button>
                  ) : (
                    <button
                      type="submit"
                      className="submit-button"
                      disabled={loading || Boolean(editingId && deliveryContext?.blocked_reason)}
                    >
                      {loading ? '⏳ Salvando...' : (editingId ? '✏️ Aggiorna' : '➕ Crea Progetto')}
                    </button>
                  )}
                </div>
              </div>
            </form>
          </div>
        </div>
      )}

      <div className="projects-ops-summary">
        <div className="ops-summary-card info">
          <span>Progetti attivi</span>
          <strong>{projectSummary.active}</strong>
          <small>Pipeline operativa corrente</small>
        </div>
        <div className="ops-summary-card warning">
          <span>In attenzione</span>
          <strong>{projectSummary.attention}</strong>
          <small>Scadenza vicina o ente mancante</small>
        </div>
        <div className="ops-summary-card critical">
          <span>Oltre termine</span>
          <strong>{projectSummary.overdue}</strong>
          <small>Ancora attivi oltre data fine</small>
        </div>
      </div>

      {!canWriteProjects ? (
        <div className="project-ops-note">
          Profilo in sola consultazione: puoi leggere stato, date, ente attuatore e dati di delivery senza modificarli.
        </div>
      ) : null}

      {/* FILTRI */}
      <ResponsiveFilters
        className="filters-section"
        title="Filtri progetti"
        layerId="project-filters"
        activeCount={Number(statusFilter !== 'all' || Boolean(focusedProjectId))}
        onReset={() => { setStatusFilter('all'); setFocusedProjectId(null); }}
      >
        <h2>🔍 Filtra per Stato</h2>
        <div className="filter-buttons">
          <button
            className={`filter-button ${statusFilter === 'all' ? 'active' : ''}`}
            onClick={() => { setStatusFilter('all'); setFocusedProjectId(null); }}
          >
            📋 Tutti ({projects.length})
          </button>
          <button
            className={`filter-button ${statusFilter === 'active' ? 'active' : ''}`}
            onClick={() => { setStatusFilter('active'); setFocusedProjectId(null); }}
          >
            🟢 Attivi ({projects.filter(p => p.status === 'active').length})
          </button>
          <button
            className={`filter-button ${statusFilter === 'completed' ? 'active' : ''}`}
            onClick={() => { setStatusFilter('completed'); setFocusedProjectId(null); }}
          >
            ✅ Completati ({projects.filter(p => p.status === 'completed').length})
          </button>
          <button
            className={`filter-button ${statusFilter === 'paused' ? 'active' : ''}`}
            onClick={() => { setStatusFilter('paused'); setFocusedProjectId(null); }}
          >
            ⏸️ In Pausa ({projects.filter(p => p.status === 'paused').length})
          </button>
          <button
            className={`filter-button ${statusFilter === 'attention' ? 'active' : ''}`}
            onClick={() => { setStatusFilter('attention'); setFocusedProjectId(null); }}
          >
            ⚠️ Attenzione ({projectSummary.attention + projectSummary.overdue})
          </button>
          <button
            className={`filter-button ${statusFilter === 'deadline-7-days' ? 'active' : ''}`}
            onClick={() => { setStatusFilter('deadline-7-days'); setFocusedProjectId(null); }}
          >
            ⏳ Scadenze 7gg ({projects.filter(isDeadlineWithinSevenDays).length})
          </button>
        </div>
      </ResponsiveFilters>

      {/* LISTA PROGETTI */}
      <div className="projects-list">
        <h2>📋 Progetti ({filteredProjects.length})</h2>

        <ResponsiveEntityList
          listId="projects"
          items={filteredProjects}
          entityLabel="progetti"
          emptyIcon="📁"
          emptyMessage={statusFilter === 'all'
            ? 'Nessun progetto trovato.'
            : `Nessun progetto con stato "${getStatusLabel(statusFilter).replace(/^[^\s]+\s/, '')}".`}
          renderDesktop={(items) => (
          <div className="projects-grid">
            {items.map(project => (
              <div key={project.id} data-entity-id={project.id} className={`project-card project-state-${getProjectOperationalState(project)}`}>
                {/* Header Card */}
                <div className="card-header">
                  <div className="project-title">
                    <h3>{project.name}</h3>
                    <div className="project-attention-row">
                      {getProjectOperationalState(project) === 'attention' && (
                        <span className="project-operational-pill attention">Scadenza/ente da verificare</span>
                      )}
                      {getProjectOperationalState(project) === 'overdue' && (
                        <span className="project-operational-pill overdue">Oltre data fine</span>
                      )}
                      {!project.ente_attuatore_id && (
                        <span className="project-operational-pill neutral">Ente attuatore mancante</span>
                      )}
                    </div>
                    <span
                      className="status-badge"
                      style={{ backgroundColor: getStatusColor(project.status) }}
                    >
                      {getStatusLabel(project.status)}
                    </span>
                  </div>
                  <div className="card-actions">
                    {canWriteProjects ? <button
                      onClick={() => startEdit(project)}
                      className="edit-button"
                      title="Modifica progetto"
                    >
                      ✏️
                    </button> : null}
                    {canWriteProjects ? <button
                      onClick={() => setDeleteConfirm(project.id)}
                      className="delete-button"
                      title="Elimina progetto"
                    >
                      🗑️
                    </button> : null}
                  </div>
                </div>

                {/* Descrizione */}
                <div className="project-description">
                  <p>{project.description}</p>
                </div>

                {/* Info Progetto */}
                <div className="project-info">
                  {/* Identificazione: ente/fondo, avviso, attuatore, CUP, codice
                      progetto, atto — ordine fisso per ogni fondo, mai una riga
                      assente. Avviso e codice progetto sono sempre presenti
                      anche vuoti: uno stato vuoto con azione, non una riga che
                      scompare, cosi' l'operatore vede che il dato manca. */}
                  {project.ente_erogatore && (
                    <div className="info-row">
                      <span className="label">🏛️ Ente:</span>
                      <span>{project.ente_erogatore}</span>
                    </div>
                  )}

                  <div className="info-row">
                    <span className="label">📢 Avviso:</span>
                    {project.avviso ? (
                      <span>{project.avviso}</span>
                    ) : (
                      <span className="info-empty">
                        Avviso non collegato
                        {canWriteProjects && (
                          <button type="button" className="info-empty-action" onClick={() => startEdit(project)}>
                            Collega avviso
                          </button>
                        )}
                      </span>
                    )}
                  </div>

                  <div className="info-row">
                    <span className="label">🤝 Attuatore:</span>
                    <span>
                      {implementingEntities.find((entity) => entity.id === project.ente_attuatore_id)?.ragione_sociale || 'Non associato'}
                    </span>
                  </div>

                  {project.cup && (
                    <div className="info-row">
                      <span className="label">🏷️ CUP:</span>
                      <span>{project.cup}</span>
                    </div>
                  )}

                  <div className="info-row">
                    <span className="label">🔢 {resolveFundConfig(project).etichetta_codice_progetto}:</span>
                    {project.codice_fapi ? (
                      <span>{project.codice_fapi}</span>
                    ) : (
                      <span className="info-empty">Nessun codice progetto collegato</span>
                    )}
                  </div>

                  <div className="info-row">
                    <span className="label">📄 Atto:</span>
                    <span>
                      {project.atto_approvazione || 'Non impostato'}
                      {project.delibera_numero && ` · Delibera n. ${project.delibera_numero} del ${project.delibera_data || '—'}`}
                    </span>
                  </div>

                  {project.start_date && (
                    <div className="info-row">
                      <span className="label">📅 Inizio:</span>
                      <span>{new Date(project.start_date).toLocaleDateString('it-IT')}</span>
                    </div>
                  )}

                  {project.end_date && (
                    <div className="info-row">
                      <span className="label">🏁 Fine:</span>
                      <span>{new Date(project.end_date).toLocaleDateString('it-IT')}</span>
                    </div>
                  )}

                  {(project.sede_aziendale_comune || project.sede_aziendale_via || project.sede_aziendale_numero_civico) && (
                    <div className="info-row">
                      <span className="label">🏢 Sede nei contratti:</span>
                      <span>
                        {[project.sede_aziendale_via, project.sede_aziendale_numero_civico, project.sede_aziendale_comune]
                          .filter(Boolean)
                          .join(', ')}
                      </span>
                    </div>
                  )}

                  {Array.isArray(project.aziende_delivery) && project.aziende_delivery.length > 0 && (() => {
                    const { definite, totale } = riepilogoSediDelivery(project.aziende_delivery);
                    const espanso = sediOpenProject === project.id;
                    return (
                      <div className="info-row info-row-multi">
                        <span className="label">🏭 Sedi corso:</span>
                        <span>
                          <span>Sedi: {definite} definite su {totale} aziende</span>
                          <button
                            type="button"
                            className="info-empty-action sedi-toggle"
                            onClick={() => setSediOpenProject(espanso ? null : project.id)}
                          >
                            {espanso ? 'Nascondi dettaglio' : 'Mostra dettaglio'}
                          </button>
                          {definite < totale && canWriteProjects && (
                            <button
                              type="button"
                              className="info-empty-action"
                              onClick={() => { startEdit(project); setActiveStepIndex(2); }}
                            >
                              Completa sedi
                            </button>
                          )}
                          {espanso && (
                            <ul className="sedi-detail-list">
                              {project.aziende_delivery.map((item) => (
                                <li key={item.azienda_id}>
                                  {item.ragione_sociale}: {riepilogoAssociati(
                                    item.sedi,
                                    (sede) => sede.sede_label,
                                    'Sede da definire',
                                  )}
                                </li>
                              ))}
                            </ul>
                          )}
                        </span>
                      </div>
                    );
                  })()}

                  <div className="info-row info-row-multi">
                    <span className="label">🏢 Aziende coinvolte:</span>
                    <span>
                      {riepilogoAssociati(
                        project.aziende_coinvolte,
                        (azienda) => azienda.ragione_sociale,
                        'Nessuna azienda associata',
                      )}
                    </span>
                  </div>

                  <div className="info-row info-row-multi">
                    <span className="label">🎓 Allievi:</span>
                    <span>
                      {riepilogoAssociati(
                        project.allievi_coinvolti,
                        (allievo) => `${allievo.nome} ${allievo.cognome}`,
                        'Nessun allievo associato',
                      )}
                    </span>
                  </div>

                  <div className="info-row">
                    <span className="label">🗓️ Creato:</span>
                    <span>{new Date(project.created_at).toLocaleDateString('it-IT')}</span>
                  </div>
                </div>

                {/* Documenti versionati e parser specifici del fondo: struttura
                    fissa per ogni progetto, la config per fondo cambia solo
                    etichette e modal aperti (vedi FUND_DOCUMENT_MODALS). */}
                <FapiUploadSection
                  project={project}
                  currentUser={currentUser}
                  onRefresh={refresh}
                  autoOpenConvenzione={formularioAutoOpenProjectId === project.id}
                  autoOpenMode={getFundDocumentModals(project).formulario}
                  onAutoClose={() => setFormularioAutoOpenProjectId(null)}
                />

                <ModuliFormativiSection
                  project={project}
                  onRequestFormulario={() => setFormularioAutoOpenProjectId(project.id)}
                />

                {/* Footer con statistiche */}
                <div className="project-stats">
                  <div className="stat">
                    <span className="stat-number">ID: {project.id}</span>
                    <span className="stat-label">Codice Progetto</span>
                  </div>
                  <div className="stat">
                    <button
                      onClick={() => {
                        if (regimeOpenProject === project.id) {
                          setRegimeOpenProject(null);
                        } else {
                          setRegimeOpenProject(project.id);
                          loadBeneficiari(project.id);
                        }
                      }}
                      style={{
                        padding: '6px 14px',
                        fontSize: '12px',
                        cursor: 'pointer',
                        borderRadius: '6px',
                        border: '0.5px solid var(--color-border-secondary)',
                        background: regimeOpenProject === project.id ? '#2c3e50' : 'var(--color-background-primary)',
                        color: regimeOpenProject === project.id ? 'white' : 'var(--color-text-primary)',
                      }}
                    >
                      Aziende Beneficiarie
                    </button>
                  </div>
                  {canWriteProjects && (
                    <div className="stat">
                      <button
                        onClick={() => setAssignmentProject(project)}
                        className="assignment-project-button"
                      >
                        Nuova Assegnazione
                      </button>
                    </div>
                  )}
                  <div className="stat">
                    <button
                      onClick={() => setAssociatiOpenProject(
                        associatiOpenProject === project.id ? null : project.id,
                      )}
                      className="associati-toggle"
                    >
                      Associazioni
                    </button>
                  </div>
                </div>
                {associatiOpenProject === project.id && (
                  <GestioneAssociati
                    project={project}
                    currentUser={currentUser}
                    onChange={refresh}
                  />
                )}
                {regimeOpenProject === project.id && (
                  <div style={{ borderTop: '0.5px solid var(--color-border-tertiary)', marginTop: '0.5rem', padding: '0.75rem 1rem' }}>
                    <div style={{ fontSize: '13px', fontWeight: 500, marginBottom: '0.5rem', color: 'var(--color-text-primary)' }}>
                      Aziende Beneficiarie — Regime aiuto
                    </div>
                    {!beneficiariByProject[project.id] ? (
                      <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)' }}>Caricamento...</div>
                    ) : beneficiariByProject[project.id].length === 0 ? (
                      <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)' }}>Nessuna azienda beneficiaria</div>
                    ) : (
                      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
                        <thead>
                          <tr>
                            <th style={{ textAlign: 'left', padding: '4px 8px', color: 'var(--color-text-secondary)', fontWeight: 500 }}>Azienda</th>
                            <th style={{ textAlign: 'left', padding: '4px 8px', color: 'var(--color-text-secondary)', fontWeight: 500 }}>Regime</th>
                            <th style={{ textAlign: 'left', padding: '4px 8px', color: 'var(--color-text-secondary)', fontWeight: 500 }}>Plafond (€)</th>
                            <th style={{ padding: '4px 8px' }}></th>
                          </tr>
                        </thead>
                        <tbody>
                          {beneficiariByProject[project.id].map(b => {
                            const key = `${project.id}_${b.azienda_id}`;
                            return (
                              <tr key={b.azienda_id}>
                                <td style={{ padding: '4px 8px' }}>{b.ragione_sociale}</td>
                                <td style={{ padding: '4px 8px' }}>
                                  <select
                                    value={regimeByBeneficiario[key] ?? (b.regime_aiuto || 'non_definito')}
                                    disabled={!canWriteProjects || regimeSaving[key]}
                                    onChange={e => setRegimeByBeneficiario(prev => ({ ...prev, [key]: e.target.value }))}
                                    style={{ fontSize: '12px', padding: '2px 6px', borderRadius: '4px', border: '0.5px solid var(--color-border-secondary)' }}
                                  >
                                    <option value="non_definito">Non definito</option>
                                    <option value="de_minimis">De Minimis</option>
                                    <option value="esenzione">Esenzione</option>
                                  </select>
                                </td>
                                <td style={{ padding: '4px 8px' }}>
                                  <input
                                    type="number"
                                    min="0"
                                    step="1000"
                                    value={plafondByBeneficiario[key] ?? (b.plafond_dichiarato != null ? String(b.plafond_dichiarato) : '')}
                                    disabled={!canWriteProjects || regimeSaving[key]}
                                    onChange={e => setPlafondByBeneficiario(prev => ({ ...prev, [key]: e.target.value }))}
                                    placeholder="es. 200000"
                                    style={{ fontSize: '12px', padding: '2px 6px', borderRadius: '4px', border: '0.5px solid var(--color-border-secondary)', width: '110px' }}
                                  />
                                </td>
                                <td style={{ padding: '4px 8px' }}>
                                  {canWriteProjects ? <button
                                    onClick={() => handleSaveRegime(project.id, b.azienda_id)}
                                    disabled={regimeSaving[key]}
                                    style={{ fontSize: '11px', padding: '2px 10px', borderRadius: '4px', border: 'none', background: 'var(--color-accent)', color: 'white', cursor: regimeSaving[key] ? 'not-allowed' : 'pointer' }}
                                  >
                                    {regimeSaving[key] ? '...' : 'Salva'}
                                  </button> : null}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
          )}
          renderCard={(project) => {
            const operationalState = getProjectOperationalState(project);
            const companyCount = Array.isArray(project.aziende_coinvolte) ? project.aziende_coinvolte.length : 0;
            const studentCount = Array.isArray(project.allievi_coinvolti) ? project.allievi_coinvolti.length : 0;
            return (
              <article className="responsive-card">
                <div className="responsive-card-header">
                  <h3 className="responsive-card-title">{project.name}</h3>
                  <span className="status-badge" style={{ backgroundColor: getStatusColor(project.status) }}>
                    {getStatusLabel(project.status)}
                  </span>
                </div>
                {operationalState !== 'stable' ? (
                  <p className={`project-operational-pill ${operationalState}`}>
                    {operationalState === 'overdue' ? 'Oltre data fine' : 'Richiede attenzione'}
                  </p>
                ) : null}
                <dl className="responsive-card-fields">
                  <div className="responsive-card-field">
                    <dt>Avviso / fondo</dt>
                    <dd>{project.avviso || project.ente_erogatore || 'Non indicato'}</dd>
                  </div>
                  <div className="responsive-card-field">
                    <dt>Scadenza</dt>
                    <dd>{project.end_date ? new Date(project.end_date).toLocaleDateString('it-IT') : 'Non indicata'}</dd>
                  </div>
                  <div className="responsive-card-field">
                    <dt>Partecipanti</dt>
                    <dd>{companyCount} aziende · {studentCount} allievi</dd>
                  </div>
                </dl>
                <details className="responsive-card-details">
                  <summary data-primary-action>Dettaglio</summary>
                  <p>{project.description || 'Nessuna descrizione.'}</p>
                  <p><strong>Attuatore:</strong> {implementingEntities.find((entity) => entity.id === project.ente_attuatore_id)?.ragione_sociale || 'Non associato'}</p>
                  {project.cup ? <p><strong>CUP:</strong> {project.cup}</p> : null}
                </details>
                <div className="responsive-card-actions">
                  {canWriteProjects ? <button className="btn-secondary" data-action="edit" onClick={() => startEdit(project)}>Modifica</button> : <span>Sola lettura</span>}
                  {canWriteProjects ? <button className="btn-danger is-destructive" data-action="delete" onClick={() => setDeleteConfirm(project.id)}>Elimina</button> : null}
                </div>
              </article>
            );
          }}
        />
      </div>

      {/* MODAL CONVENZIONE FAPI da toolbar */}
      {showFapiModal && (
        <FapiUploadSection
          project={null}
          currentUser={currentUser}
          onRefresh={refresh}
          autoOpenConvenzione
          autoOpenMode="new-piano"
          onAutoClose={() => setShowFapiModal(false)}
        />
      )}

      <AssignmentModal
        isOpen={!!assignmentProject}
        onClose={() => setAssignmentProject(null)}
        onSuccess={handleAssignmentSuccess}
        project={assignmentProject}
        availableProjects={projects}
        availableCollaborators={collaborators}
      />

      {/* MODAL CONFERMA ELIMINAZIONE */}
      {deleteConfirm && (
        <div className="modal-overlay">
          <div className="confirm-modal">
            <h3>⚠️ Conferma Eliminazione</h3>
            <p>Sei sicuro di voler eliminare questo progetto?</p>
            <p><strong>Verranno eliminate anche tutte le presenze associate!</strong></p>
            <p>Questa azione non può essere annullata.</p>

            <div className="modal-buttons">
              <button
                onClick={() => setDeleteConfirm(null)}
                className="cancel-button"
              >
                Annulla
              </button>
              <button
                onClick={() => handleDelete(deleteConfirm)}
                className="delete-button"
                disabled={!canWriteProjects}
              >
                🗑️ Elimina
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ProjectManager;
