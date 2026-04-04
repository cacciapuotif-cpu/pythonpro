import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  createPianoFinanziario,
  exportPianoFinanziarioExcel,
  getContractTemplates,
  getAvvisi,
  getPianiFinanziari,
  getPianoFinanziario,
  getProjects,
  getRiepilogoPianoFinanziario,
  updateVociPianoFinanziario,
} from '../services/apiService';
import './PianiFinanziariManager.css';

const STANDARD_FONDI = [
  { value: 'Formazienda', label: 'Formazienda', defaultAvviso: '' },
  { value: 'FAPI', label: 'FAPI', defaultAvviso: '' },
  { value: 'Regione Campania', label: 'Regione Campania', defaultAvviso: '' },
  { value: 'Altro', label: 'Altro', defaultAvviso: '' },
];

const MACROVOCE_LIMITS = { A: 20, B: 50, C: 30, D: null };
const MACROVOCE_LABELS = {
  A: 'Macrovoce A - Progettazione della formazione',
  B: 'Macrovoce B - Erogazione della formazione',
  C: 'Macrovoce C - Gestione e amministrazione',
  D: 'Macrovoce D - Costo del personale in formazione',
};

const VOICE_TEMPLATES = [
  { macrovoce: 'A', voce_codice: 'A.1', descrizione: 'Progettazione esecutiva', isDynamic: false },
  { macrovoce: 'A', voce_codice: 'A.2', descrizione: 'Rilevazione fabbisogni', isDynamic: false },
  { macrovoce: 'A', voce_codice: 'A.3', descrizione: 'Promozione', isDynamic: false },
  { macrovoce: 'A', voce_codice: 'A.4', descrizione: 'Monitoraggio e valutazione', isDynamic: false },
  { macrovoce: 'A', voce_codice: 'A.5', descrizione: 'Diffusione', isDynamic: false },
  { macrovoce: 'A', voce_codice: 'A.6', descrizione: 'Viaggi e trasferte', isDynamic: false },
  { macrovoce: 'A', voce_codice: 'A.7', descrizione: 'Altro', isDynamic: false },
  { macrovoce: 'B', voce_codice: 'B.1', descrizione: 'Coordinamento', isDynamic: false },
  { macrovoce: 'B', voce_codice: 'B.2', descrizione: 'Docenza', isDynamic: true },
  { macrovoce: 'B', voce_codice: 'B.3', descrizione: 'Tutor', isDynamic: true },
  { macrovoce: 'B', voce_codice: 'B.4', descrizione: 'Materiali didattici', isDynamic: false },
  { macrovoce: 'B', voce_codice: 'B.5', descrizione: 'Materiali di consumo', isDynamic: false },
  { macrovoce: 'B', voce_codice: 'B.6', descrizione: 'Aule didattiche', isDynamic: false },
  { macrovoce: 'B', voce_codice: 'B.7', descrizione: 'Attrezzature', isDynamic: false },
  { macrovoce: 'B', voce_codice: 'B.8', descrizione: 'Certificazione delle competenze', isDynamic: false },
  { macrovoce: 'B', voce_codice: 'B.9', descrizione: 'Viaggi e trasferte', isDynamic: false },
  { macrovoce: 'B', voce_codice: 'B.10', descrizione: 'Altro', isDynamic: false },
  { macrovoce: 'C', voce_codice: 'C.1', descrizione: 'Designer', isDynamic: false },
  { macrovoce: 'C', voce_codice: 'C.2', descrizione: 'Personale amministrativo', isDynamic: false },
  { macrovoce: 'C', voce_codice: 'C.3', descrizione: 'Rendicontazione', isDynamic: false },
  { macrovoce: 'C', voce_codice: 'C.4', descrizione: 'Revisione dei conti', isDynamic: false },
  { macrovoce: 'C', voce_codice: 'C.5', descrizione: 'Fidejussione', isDynamic: false },
  { macrovoce: 'C', voce_codice: 'C.6', descrizione: 'Costi generali e amministrativi (forfait)', isDynamic: false },
  { macrovoce: 'C', voce_codice: 'C.7', descrizione: 'Viaggi e trasferte', isDynamic: false },
  { macrovoce: 'C', voce_codice: 'C.8', descrizione: 'Altro', isDynamic: false },
  { macrovoce: 'D', voce_codice: 'D.1', descrizione: 'Retribuzione ed oneri del personale', isDynamic: false },
  { macrovoce: 'D', voce_codice: 'D.2', descrizione: 'Assicurazioni', isDynamic: false },
  { macrovoce: 'D', voce_codice: 'D.3', descrizione: 'Rimborsi viaggi e trasferte', isDynamic: false },
  { macrovoce: 'D', voce_codice: 'D.4', descrizione: 'Altro', isDynamic: false },
];

const fmtCurrency = (value) => new Intl.NumberFormat('it-IT', {
  style: 'currency',
  currency: 'EUR',
  minimumFractionDigits: 2,
}).format(Number(value || 0));

const fmtPercent = (value) => `${Number(value || 0).toFixed(2)}%`;

const formatInputNumber = (value) => new Intl.NumberFormat('it-IT', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
}).format(Number(value || 0));

const parseLocaleNumber = (value) => {
  if (value === null || value === undefined || value === '') {
    return 0;
  }

  const normalized = String(value).trim().replace(/\./g, '').replace(',', '.').replace(/[^\d.-]/g, '');
  const parsed = Number.parseFloat(normalized);
  return Number.isFinite(parsed) ? parsed : 0;
};

const createLocalKey = () => `tmp-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`;
const normalizeText = (value) => String(value || '').trim().toLowerCase();

const createRowModel = (row, fallback) => ({
  id: row?.id ?? null,
  localKey: row?.id ? `row-${row.id}` : createLocalKey(),
  macrovoce: row?.macrovoce || fallback.macrovoce,
  voce_codice: row?.voce_codice || fallback.voce_codice,
  descrizione: row?.descrizione || fallback.descrizione,
  progetto_label: row?.progetto_label || fallback.progetto_label || '',
  edizione_label: row?.edizione_label || fallback.edizione_label || '',
  ore: row ? formatInputNumber(row.ore || 0) : formatInputNumber(0),
  importo_consuntivo: row ? formatInputNumber(row.importo_consuntivo || 0) : formatInputNumber(0),
  importo_preventivo: row ? formatInputNumber(row.importo_preventivo || 0) : formatInputNumber(0),
  importo_presentato: row ? formatInputNumber(row.importo_presentato || 0) : formatInputNumber(0),
});

const buildRowsFromPiano = (piano) => {
  const rowsByCode = (piano?.voci || []).reduce((accumulator, voce) => {
    accumulator[voce.voce_codice] = accumulator[voce.voce_codice] || [];
    accumulator[voce.voce_codice].push(voce);
    return accumulator;
  }, {});

  const rows = [];
  VOICE_TEMPLATES.forEach((template) => {
    const items = rowsByCode[template.voce_codice] || [];
    if (template.isDynamic) {
      items
        .sort((left, right) => `${left.progetto_label || ''}${left.edizione_label || ''}`.localeCompare(`${right.progetto_label || ''}${right.edizione_label || ''}`))
        .forEach((item) => rows.push(createRowModel(item, template)));
      return;
    }

    rows.push(createRowModel(items[0], template));
  });
  return rows;
};

const computeClientSummary = (rows) => {
  const totals = { A: 0, B: 0, C: 0, D: 0 };
  const preventivi = { A: 0, B: 0, C: 0, D: 0 };
  const presentati = { A: 0, B: 0, C: 0, D: 0 };

  rows.forEach((row) => {
    totals[row.macrovoce] += parseLocaleNumber(row.importo_consuntivo);
    preventivi[row.macrovoce] += parseLocaleNumber(row.importo_preventivo);
    presentati[row.macrovoce] += parseLocaleNumber(row.importo_presentato);
  });

  const totaleConsuntivo = Object.values(totals).reduce((sum, value) => sum + value, 0);
  const totalePreventivo = Object.values(preventivi).reduce((sum, value) => sum + value, 0);
  const totalePresentato = Object.values(presentati).reduce((sum, value) => sum + value, 0);
  const c6 = rows.find((row) => row.voce_codice === 'C.6');
  const c6Percent = totalePreventivo ? (parseLocaleNumber(c6?.importo_preventivo) / totalePreventivo) * 100 : 0;

  const macrovoci = ['A', 'B', 'C', 'D'].map((macrovoce) => {
    const percentuale = totaleConsuntivo ? (totals[macrovoce] / totaleConsuntivo) * 100 : 0;
    const limite = MACROVOCE_LIMITS[macrovoce];
    let alertLevel = 'ok';

    if (limite !== null && percentuale > limite) {
      alertLevel = 'danger';
    } else if (limite !== null && percentuale >= limite * 0.9) {
      alertLevel = 'warning';
    }

    return {
      macrovoce,
      titolo: MACROVOCE_LABELS[macrovoce],
      limite_percentuale: limite,
      importo_consuntivo: totals[macrovoce],
      importo_preventivo: preventivi[macrovoce],
      importo_presentato: presentati[macrovoce],
      percentuale_consuntivo: percentuale,
      percentuale_preventivo: totalePreventivo ? (preventivi[macrovoce] / totalePreventivo) * 100 : 0,
      alert_level: alertLevel,
      sforata: alertLevel === 'danger',
    };
  });

  const alerts = [];
  macrovoci.forEach((macrovoce) => {
    if (macrovoce.alert_level === 'danger') {
      alerts.push(`Macrovoce ${macrovoce.macrovoce} oltre soglia (${fmtPercent(macrovoce.percentuale_consuntivo)}).`);
    } else if (macrovoce.alert_level === 'warning') {
      alerts.push(`Macrovoce ${macrovoce.macrovoce} vicina alla soglia (${fmtPercent(macrovoce.percentuale_consuntivo)}).`);
    }
  });

  if (c6Percent > 10) {
    alerts.push(`C.6 oltre il 10% del preventivo (${fmtPercent(c6Percent)}).`);
  } else if (c6Percent >= 9) {
    alerts.push(`C.6 vicina al limite del 10% (${fmtPercent(c6Percent)}).`);
  }

  return {
    totale_consuntivo: totaleConsuntivo,
    totale_preventivo: totalePreventivo,
    totale_presentato: totalePresentato,
    contributo_richiesto: totals.A + totals.B + totals.C,
    cofinanziamento: totals.D,
    macrovoci,
    alerts,
  };
};

export default function PianiFinanziariManager({ forcedProjectId = '', forcedEnte = '', embedded = false }) {
  const [projects, setProjects] = useState([]);
  const [plans, setPlans] = useState([]);
  const [selectedProjectId, setSelectedProjectId] = useState('');
  const [selectedPianoId, setSelectedPianoId] = useState('');
  const [selectedTemplateId, setSelectedTemplateId] = useState('');
  const [financialTemplates, setFinancialTemplates] = useState([]);
  const [avvisiCatalogo, setAvvisiCatalogo] = useState([]);
  const [anno, setAnno] = useState(new Date().getFullYear());
  const [enteErogatore, setEnteErogatore] = useState('Formazienda');
  const [avviso, setAvviso] = useState('');
  const [piano, setPiano] = useState(null);
  const [rows, setRows] = useState([]);
  const [serverSummary, setServerSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [creating, setCreating] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [message, setMessage] = useState(null);
  const [error, setError] = useState(null);

  const selectedProject = useMemo(
    () => projects.find((project) => String(project.id) === String(selectedProjectId)),
    [projects, selectedProjectId],
  );

  const selectedEnteConfig = useMemo(
    () => STANDARD_FONDI.find((item) => item.value === enteErogatore) || STANDARD_FONDI[0],
    [enteErogatore],
  );
  const selectedTemplate = useMemo(
    () => financialTemplates.find((template) => String(template.id) === String(selectedTemplateId)),
    [financialTemplates, selectedTemplateId],
  );
  const linkedAvvisiByTemplate = useMemo(
    () => (Array.isArray(avvisiCatalogo) ? avvisiCatalogo : []).reduce((accumulator, avvisoItem) => {
      if (!avvisoItem?.template_id) {
        return accumulator;
      }
      const key = String(avvisoItem.template_id);
      accumulator[key] = accumulator[key] || [];
      accumulator[key].push(avvisoItem);
      return accumulator;
    }, {}),
    [avvisiCatalogo],
  );
  const getTemplateLinkedAvvisi = useCallback(
    (template) => linkedAvvisiByTemplate[String(template?.id || '')] || [],
    [linkedAvvisiByTemplate],
  );
  const getTemplateAvvisoCodes = useCallback(
    (template) => {
      const linkedCodes = getTemplateLinkedAvvisi(template).map((item) => item.codice).filter(Boolean);
      if (linkedCodes.length > 0) {
        return linkedCodes;
      }
      return template?.avviso ? [template.avviso] : [];
    },
    [getTemplateLinkedAvvisi],
  );
  const selectedTemplateAvvisoCodes = useMemo(
    () => getTemplateAvvisoCodes(selectedTemplate),
    [getTemplateAvvisoCodes, selectedTemplate],
  );
  const selectableAvvisi = useMemo(() => {
    if (selectedTemplate && getTemplateLinkedAvvisi(selectedTemplate).length > 0) {
      return getTemplateLinkedAvvisi(selectedTemplate);
    }
    return avvisiCatalogo.filter((a) => normalizeText(a.ente_erogatore) === normalizeText(enteErogatore));
  }, [selectedTemplate, getTemplateLinkedAvvisi, avvisiCatalogo, enteErogatore]);

  const clientSummary = useMemo(() => computeClientSummary(rows), [rows]);

  const showMessage = (text, kind = 'success') => {
    setMessage({ text, kind });
    setTimeout(() => setMessage(null), 3500);
  };

  const loadProjects = useCallback(async () => {
    const data = await getProjects(0, 300);
    setProjects(Array.isArray(data) ? data : []);
  }, []);

  const loadPlans = useCallback(async (projectId) => {
    const data = await getPianiFinanziari(projectId ? { progetto_id: projectId, limit: 50 } : { limit: 100 });
    setPlans(Array.isArray(data) ? data : []);
  }, []);

  const loadFinancialTemplates = useCallback(async (projectId, selectedEnte) => {
    if (!projectId) {
      setFinancialTemplates([]);
      return;
    }

    const project = projects.find((item) => String(item.id) === String(projectId));
    const enteRif = (selectedEnte || project?.ente_erogatore || '').trim();
    const data = await getContractTemplates({
      ambito_template: 'piano_finanziario',
      progetto_id: projectId,
      ente_erogatore: enteRif || undefined,
      is_active: true,
      limit: 100,
    });
    setFinancialTemplates(Array.isArray(data) ? data : []);
  }, [projects]);

  const loadAvvisi = useCallback(async () => {
    const data = await getAvvisi({ active_only: true, limit: 1000 });
    setAvvisiCatalogo(Array.isArray(data) ? data : []);
  }, []);

  const loadPiano = useCallback(async (pianoId) => {
    if (!pianoId) {
      setPiano(null);
      setRows([]);
      setServerSummary(null);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const [detail, riepilogo] = await Promise.all([
        getPianoFinanziario(pianoId),
        getRiepilogoPianoFinanziario(pianoId),
      ]);
      setPiano(detail);
      setRows(buildRowsFromPiano(detail));
      setServerSummary(riepilogo);
      setSelectedProjectId(String(detail.progetto_id));
      setSelectedTemplateId(detail.template_id ? String(detail.template_id) : '');
      setEnteErogatore(detail.ente_erogatore || 'Formazienda');
      setAvviso(detail.avviso || '');
    } catch (loadError) {
      setError(loadError?.response?.data?.detail || 'Errore nel caricamento del piano finanziario.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (selectedPianoId) {
      return;
    }

    const projectEnte = String(selectedProject?.ente_erogatore || '').trim().toUpperCase();
    if (projectEnte) {
      setEnteErogatore(selectedProject.ente_erogatore);
    }
  }, [selectedPianoId, selectedProject]);

  useEffect(() => {
    if (selectedPianoId) {
      return;
    }

    if (selectedProject?.avviso) {
      setAvviso((current) => current || selectedProject.avviso);
      return;
    }

    if (selectedTemplateAvvisoCodes.length > 0) {
      setAvviso(selectedTemplateAvvisoCodes[0]);
      return;
    }

    setAvviso((current) => current || selectedEnteConfig.defaultAvviso);
  }, [selectedPianoId, selectedEnteConfig, selectedProject, selectedTemplateAvvisoCodes]);

  useEffect(() => {
    loadProjects();
    loadPlans();
    loadAvvisi();
  }, [loadProjects, loadPlans, loadAvvisi]);

  useEffect(() => {
    const match = window.location.pathname.match(/^\/piani-finanziari\/(\d+)/);
    if (match && match[1]) {
      setSelectedPianoId(match[1]);
    }
  }, []);

  useEffect(() => {
    if (!forcedProjectId) {
      return;
    }
    setSelectedProjectId(String(forcedProjectId));
  }, [forcedProjectId]);

  useEffect(() => {
    if (!forcedEnte) {
      return;
    }
    setEnteErogatore(forcedEnte);
  }, [forcedEnte]);

  useEffect(() => {
    if (!selectedProjectId) {
      setPlans([]);
      setPiano(null);
      setRows([]);
      setFinancialTemplates([]);
      setSelectedTemplateId('');
      return;
    }

    loadPlans(selectedProjectId)
      .catch(() => setError('Errore nel caricamento dei piani finanziari del progetto.'));
    loadFinancialTemplates(selectedProjectId, enteErogatore)
      .catch(() => setError('Errore nel caricamento dei template piano finanziario.'));
  }, [selectedProjectId, enteErogatore, loadPlans, loadFinancialTemplates]);

  useEffect(() => {
    if (selectedPianoId) {
      return;
    }

    if (selectedProject?.template_piano_finanziario_id) {
      setSelectedTemplateId(String(selectedProject.template_piano_finanziario_id));
      return;
    }

    if (!financialTemplates.length) {
      setSelectedTemplateId('');
      return;
    }

    const normalizedSelectedAvviso = normalizeText(avviso);
    const exactTemplate = financialTemplates.find((template) =>
      getTemplateAvvisoCodes(template).some((code) => normalizeText(code) === normalizedSelectedAvviso)
    );
    const fallbackTemplate = financialTemplates[0];
    const nextTemplateId = exactTemplate?.id || fallbackTemplate?.id || '';
    if (String(selectedTemplateId) !== String(nextTemplateId)) {
      setSelectedTemplateId(String(nextTemplateId));
    }
  }, [selectedPianoId, financialTemplates, avviso, selectedProject, selectedTemplateId, getTemplateAvvisoCodes]);

  useEffect(() => {
    if (!forcedProjectId) {
      return;
    }

    if (!Array.isArray(plans) || plans.length === 0) {
      setSelectedPianoId('');
      return;
    }

    const normalizedEnte = String(enteErogatore || '').trim().toLowerCase();
    const normalizedAvviso = String(avviso || '').trim().toLowerCase();
    const matchingPlan = plans.find((plan) =>
      String(plan.ente_erogatore || '').trim().toLowerCase() === normalizedEnte
      && String(plan.avviso || '').trim().toLowerCase() === normalizedAvviso
    );
    const fallbackByEnte = plans.find((plan) => String(plan.ente_erogatore || '').trim().toLowerCase() === normalizedEnte);
    const fallbackPlan = plans[0];
    const nextPlanId = matchingPlan?.id || fallbackByEnte?.id || fallbackPlan?.id || '';

    if (String(selectedPianoId) !== String(nextPlanId)) {
      setSelectedPianoId(String(nextPlanId));
    }
  }, [forcedProjectId, plans, enteErogatore, avviso, selectedPianoId]);

  useEffect(() => {
    if (selectedPianoId) {
      window.history.replaceState({}, '', `/piani-finanziari/${selectedPianoId}`);
      loadPiano(selectedPianoId);
    } else if (window.location.pathname.startsWith('/piani-finanziari')) {
      window.history.replaceState({}, '', '/piani-finanziari');
    }
  }, [selectedPianoId, loadPiano]);

  const handleCreatePlan = async () => {
    if (!selectedProjectId) {
      setError('Seleziona prima un progetto.');
      return;
    }

    setCreating(true);
    setError(null);
    try {
      const detail = await createPianoFinanziario({
        progetto_id: Number(selectedProjectId),
        template_id: selectedTemplateId ? Number(selectedTemplateId) : null,
        anno: Number(anno),
        ente_erogatore: enteErogatore,
        avviso: avviso || selectedEnteConfig.defaultAvviso || '',
      });
      await loadPlans(selectedProjectId);
      setSelectedPianoId(String(detail.id));
      showMessage(`Piano finanziario ${detail.ente_erogatore} creato con il template base.`);
    } catch (createError) {
      setError(createError?.response?.data?.detail || 'Errore nella creazione del piano finanziario.');
    } finally {
      setCreating(false);
    }
  };

  const handleFieldChange = (localKey, field, value) => {
    setRows((currentRows) => currentRows.map((row) => (
      row.localKey === localKey ? { ...row, [field]: value } : row
    )));
  };

  const handleAddDynamicRow = (template) => {
    const nextIndex = rows.filter((row) => row.voce_codice === template.voce_codice).length + 1;
    const defaultProjectLabel = selectedProject?.name || `PROG ${selectedProjectId || 1}`;
    setRows((currentRows) => [
      ...currentRows,
      createRowModel(null, {
        ...template,
        progetto_label: defaultProjectLabel,
        edizione_label: `ED ${nextIndex}`,
      }),
    ]);
  };

  const handleRemoveDynamicRow = (localKey) => {
    setRows((currentRows) => currentRows.filter((row) => row.localKey !== localKey));
  };

  const handleSave = async () => {
    if (!selectedPianoId) {
      setError('Crea o seleziona un piano prima di salvare.');
      return;
    }

    setSaving(true);
    setError(null);
    try {
      const payload = {
        voci: rows.map((row) => ({
          id: row.id,
          macrovoce: row.macrovoce,
          voce_codice: row.voce_codice,
          descrizione: row.descrizione,
          progetto_label: row.progetto_label || null,
          edizione_label: row.edizione_label || null,
          ore: parseLocaleNumber(row.ore),
          importo_consuntivo: parseLocaleNumber(row.importo_consuntivo),
          importo_preventivo: parseLocaleNumber(row.importo_preventivo),
          importo_presentato: parseLocaleNumber(row.importo_presentato),
        })),
      };

      const updated = await updateVociPianoFinanziario(selectedPianoId, payload);
      const riepilogo = await getRiepilogoPianoFinanziario(selectedPianoId);
      setPiano(updated);
      setRows(buildRowsFromPiano(updated));
      setServerSummary(riepilogo);
      showMessage('Piano finanziario salvato con successo.');
    } catch (saveError) {
      setError(saveError?.response?.data?.detail || 'Errore nel salvataggio del piano finanziario.');
    } finally {
      setSaving(false);
    }
  };

  const handleExport = async () => {
    if (!selectedPianoId) {
      setError('Seleziona prima un piano da esportare.');
      return;
    }

    setExporting(true);
    setError(null);
    try {
      const response = await exportPianoFinanziarioExcel(selectedPianoId);
      const blob = new Blob([response.data], {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `piano_finanziario_${selectedProject?.name || selectedPianoId}.xlsx`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (exportError) {
      setError(exportError?.response?.data?.detail || 'Errore durante l’esportazione Excel.');
    } finally {
      setExporting(false);
    }
  };

  const rowsByCode = useMemo(
    () => rows.reduce((accumulator, row) => {
      accumulator[row.voce_codice] = accumulator[row.voce_codice] || [];
      accumulator[row.voce_codice].push(row);
      return accumulator;
    }, {}),
    [rows],
  );

  return (
    <div className={embedded ? 'piani-finanziari-embedded' : 'piani-finanziari-page'}>
      {!embedded && (
        <div className="page-header">
          <div>
            <span className="page-eyebrow">{enteErogatore}{avviso ? ` · Avviso ${avviso}` : ''}</span>
            <h2>Piani Finanziari Standard</h2>
            <p>Ogni piano ha un solo ente erogatore di riferimento. Qui gestisci i piani standard; Fondimpresa resta su un modulo dedicato.</p>
          </div>
          <div className="header-actions">
            <button className="btn-secondary" onClick={handleExport} disabled={!selectedPianoId || exporting}>
              {exporting ? 'Esportazione...' : 'Esporta Excel'}
            </button>
            <button className="btn-primary" onClick={handleSave} disabled={!selectedPianoId || saving}>
              {saving ? 'Salvataggio...' : 'Salva'}
            </button>
          </div>
        </div>
      )}

      {embedded && (
        <div className="page-header">
          <div>
            <span className="page-eyebrow">{enteErogatore}{avviso ? ` · Avviso ${avviso}` : ''}</span>
            <h2>Piano Finanziario</h2>
            <p>Layout standard attivato dall'ente erogatore del progetto selezionato.</p>
          </div>
          <div className="header-actions">
            <button className="btn-secondary" onClick={handleExport} disabled={!selectedPianoId || exporting}>
              {exporting ? 'Esportazione...' : 'Esporta Excel'}
            </button>
            <button className="btn-primary" onClick={handleSave} disabled={!selectedPianoId || saving}>
              {saving ? 'Salvataggio...' : 'Salva'}
            </button>
          </div>
        </div>
      )}

      {message && <div className={`banner ${message.kind}`}>{message.text}</div>}
      {error && <div className="banner error">{error}</div>}

      <div className="toolbar-card">
        <div className="toolbar-grid">
          {!forcedProjectId && (
            <label>
              <span>Progetto</span>
              <select value={selectedProjectId} onChange={(event) => {
                setSelectedProjectId(event.target.value);
                setSelectedPianoId('');
              }}>
                <option value="">Seleziona progetto</option>
                {projects.map((project) => (
                  <option key={project.id} value={project.id}>{project.name}</option>
                ))}
              </select>
            </label>
          )}

          <label>
            <span>Anno piano</span>
            <input type="number" value={anno} onChange={(event) => setAnno(event.target.value)} min="2020" max="2100" />
          </label>

          {!forcedEnte && (
            <label>
              <span>Ente Erogatore</span>
              <select value={enteErogatore} onChange={(event) => {
                const nextEnte = event.target.value;
                setEnteErogatore(nextEnte);
                setSelectedPianoId('');
                setAvviso('');
              }}>
                {STANDARD_FONDI.map((item) => (
                  <option key={item.value} value={item.value}>{item.label}</option>
                ))}
              </select>
            </label>
          )}

          <label>
            <span>Avviso</span>
            <select value={avviso} onChange={(event) => setAvviso(event.target.value)}>
              <option value="">Seleziona avviso</option>
              {selectableAvvisi.map((a) => (
                <option key={a.id} value={a.codice}>{a.codice}</option>
              ))}
            </select>
          </label>

          <label>
            <span>Template piano</span>
            <select
              value={selectedTemplateId}
              onChange={(event) => {
                const nextTemplateId = event.target.value;
                setSelectedTemplateId(nextTemplateId);
                const nextTemplate = financialTemplates.find((template) => String(template.id) === String(nextTemplateId));
                if (nextTemplate) {
                  setEnteErogatore(nextTemplate.ente_erogatore || enteErogatore);
                  const linkedCodes = getTemplateAvvisoCodes(nextTemplate);
                  setAvviso(linkedCodes[0] || '');
                }
              }}
              disabled={!selectedProjectId}
            >
              <option value="">Template automatico / nessuno</option>
              {financialTemplates.map((template) => (
                <option key={template.id} value={template.id}>
                  {template.nome_template}
                  {template.ente_erogatore ? ` · ${template.ente_erogatore}` : ''}
                  {getTemplateAvvisoCodes(template).length > 0 ? ` · Avvisi ${getTemplateAvvisoCodes(template).join(', ')}` : ''}
                </option>
              ))}
            </select>
          </label>

          <label>
            <span>Piano esistente</span>
            <select value={selectedPianoId} onChange={(event) => setSelectedPianoId(event.target.value)} disabled={!selectedProjectId}>
              <option value="">Seleziona piano</option>
              {plans.map((plan) => (
                <option key={plan.id} value={plan.id}>
                  {plan.anno} · {plan.ente_erogatore}{plan.avviso ? ` · Avviso ${plan.avviso}` : ''}
                </option>
              ))}
            </select>
          </label>

          <div className="toolbar-create">
            <button className="btn-primary" onClick={handleCreatePlan} disabled={!selectedProjectId || creating}>
              {creating ? 'Creazione...' : 'Crea Piano Base'}
            </button>
            <small>Un piano = un ente erogatore. Genera le righe standard A, B, C, D per {enteErogatore} e abilita l’inserimento di docenza e tutor per edizione.</small>
          </div>
        </div>
      </div>

      {(loading || piano) && (
        <div className="summary-grid">
          {clientSummary.macrovoci.map((macrovoce) => (
            <div key={macrovoce.macrovoce} className={`summary-card ${macrovoce.alert_level}`}>
              <div className="summary-card-top">
                <span>{macrovoce.titolo}</span>
                <strong>{fmtCurrency(macrovoce.importo_consuntivo)}</strong>
              </div>
              <div className="summary-meta">
                <span>Preventivo {fmtCurrency(macrovoce.importo_preventivo)}</span>
                <span className={`badge ${macrovoce.alert_level}`}>
                  {macrovoce.limite_percentuale ? `${fmtPercent(macrovoce.percentuale_consuntivo)} / ${macrovoce.limite_percentuale}%` : 'Cofinanziamento'}
                </span>
              </div>
            </div>
          ))}
          <div className="summary-card highlight">
            <span>Totale preventivo</span>
            <strong>{fmtCurrency(clientSummary.totale_preventivo)}</strong>
            <small>Totale consuntivo {fmtCurrency(clientSummary.totale_consuntivo)}</small>
          </div>
          <div className="summary-card highlight">
            <span>Contributo richiesto</span>
            <strong>{fmtCurrency(clientSummary.contributo_richiesto)}</strong>
            <small>Cofinanziamento {fmtCurrency(clientSummary.cofinanziamento)}</small>
          </div>
        </div>
      )}

      {clientSummary.alerts.length > 0 && (
        <div className="alerts-strip">
          {clientSummary.alerts.map((alert) => (
            <span key={alert} className="alert-pill">{alert}</span>
          ))}
        </div>
      )}

      {!selectedPianoId ? (
        <div className="empty-state">
          <div>💼</div>
          <h3>Nessun piano finanziario attivo</h3>
          <p>Seleziona un progetto e crea un piano base {enteErogatore} per iniziare a compilare le macrovoci standard.</p>
        </div>
      ) : (
        <div className="table-shell">
          <table className="piano-table">
            <thead>
              <tr>
                <th>Voce</th>
                <th>Progetto</th>
                <th>Edizione</th>
                <th>Ore</th>
                <th>Consuntivo (€)</th>
                <th>%</th>
                <th>Preventivo (€)</th>
                <th>Presentato (€)</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {['A', 'B', 'C', 'D'].map((macrovoce) => {
                const macroSummary = clientSummary.macrovoci.find((item) => item.macrovoce === macrovoce);
                return (
                  <React.Fragment key={macrovoce}>
                    <tr className="macro-row">
                      <td colSpan="9">
                        <div className="macro-header">
                          <div>
                            <strong>{MACROVOCE_LABELS[macrovoce]}</strong>
                            <span>{MACROVOCE_LIMITS[macrovoce] ? `Soglia ${MACROVOCE_LIMITS[macrovoce]}% sul consuntivo` : 'Solo cofinanziamento aziendale'}</span>
                          </div>
                          <span className={`badge ${macroSummary?.alert_level || 'ok'}`}>
                            {macroSummary?.limite_percentuale ? fmtPercent(macroSummary.percentuale_consuntivo) : 'D esclusa dal contributo'}
                          </span>
                        </div>
                      </td>
                    </tr>

                    {VOICE_TEMPLATES.filter((template) => template.macrovoce === macrovoce).map((template) => {
                      const templateRows = rowsByCode[template.voce_codice] || [];
                      if (template.isDynamic) {
                        return (
                          <React.Fragment key={template.voce_codice}>
                            <tr className="voice-subheader">
                              <td colSpan="9">
                                <div className="dynamic-header">
                                  <strong>{template.voce_codice} - {template.descrizione}</strong>
                                  <button type="button" className="btn-inline" onClick={() => handleAddDynamicRow(template)}>
                                    + Aggiungi edizione
                                  </button>
                                </div>
                              </td>
                            </tr>
                            {templateRows.length === 0 ? (
                              <tr className="dynamic-empty">
                                <td>{template.voce_codice}</td>
                                <td colSpan="8">Nessuna edizione inserita</td>
                              </tr>
                            ) : templateRows.map((row) => {
                              const rowPercent = clientSummary.totale_consuntivo
                                ? (parseLocaleNumber(row.importo_consuntivo) / clientSummary.totale_consuntivo) * 100
                                : 0;
                              return (
                                <tr key={row.localKey}>
                                  <td>{row.voce_codice} - {row.descrizione}</td>
                                  <td><input type="text" value={row.progetto_label} onChange={(event) => handleFieldChange(row.localKey, 'progetto_label', event.target.value)} /></td>
                                  <td><input type="text" value={row.edizione_label} onChange={(event) => handleFieldChange(row.localKey, 'edizione_label', event.target.value)} /></td>
                                  <td><input type="text" value={row.ore} onChange={(event) => handleFieldChange(row.localKey, 'ore', event.target.value)} /></td>
                                  <td><input type="text" value={row.importo_consuntivo} onChange={(event) => handleFieldChange(row.localKey, 'importo_consuntivo', event.target.value)} /></td>
                                  <td>{fmtPercent(rowPercent)}</td>
                                  <td><input type="text" value={row.importo_preventivo} onChange={(event) => handleFieldChange(row.localKey, 'importo_preventivo', event.target.value)} /></td>
                                  <td><input type="text" value={row.importo_presentato} onChange={(event) => handleFieldChange(row.localKey, 'importo_presentato', event.target.value)} /></td>
                                  <td><button type="button" className="btn-remove" onClick={() => handleRemoveDynamicRow(row.localKey)}>✕</button></td>
                                </tr>
                              );
                            })}
                          </React.Fragment>
                        );
                      }

                      const row = templateRows[0] || createRowModel(null, {
                        ...template,
                        progetto_label: '',
                        edizione_label: '',
                      });
                      const rowPercent = clientSummary.totale_consuntivo
                        ? (parseLocaleNumber(row.importo_consuntivo) / clientSummary.totale_consuntivo) * 100
                        : 0;
                      return (
                        <tr key={row.localKey}>
                          <td>{row.voce_codice} - {row.descrizione}</td>
                          <td className="muted">-</td>
                          <td className="muted">-</td>
                          <td><input type="text" value={row.ore} onChange={(event) => handleFieldChange(row.localKey, 'ore', event.target.value)} /></td>
                          <td><input type="text" value={row.importo_consuntivo} onChange={(event) => handleFieldChange(row.localKey, 'importo_consuntivo', event.target.value)} /></td>
                          <td>{fmtPercent(rowPercent)}</td>
                          <td><input type="text" value={row.importo_preventivo} onChange={(event) => handleFieldChange(row.localKey, 'importo_preventivo', event.target.value)} /></td>
                          <td><input type="text" value={row.importo_presentato} onChange={(event) => handleFieldChange(row.localKey, 'importo_presentato', event.target.value)} /></td>
                          <td></td>
                        </tr>
                      );
                    })}

                    <tr className="macro-total-row">
                      <td colSpan="4">Totale Macrovoce {macrovoce}</td>
                      <td>{fmtCurrency(macroSummary?.importo_consuntivo || 0)}</td>
                      <td>{macroSummary?.limite_percentuale ? fmtPercent(macroSummary.percentuale_consuntivo) : 'n/a'}</td>
                      <td>{fmtCurrency(macroSummary?.importo_preventivo || 0)}</td>
                      <td>{fmtCurrency(macroSummary?.importo_presentato || 0)}</td>
                      <td>
                        <span className={`badge ${macroSummary?.alert_level || 'ok'}`}>
                          {macroSummary?.alert_level === 'danger' ? 'Sforato' : macroSummary?.alert_level === 'warning' ? 'Vicino limite' : 'OK'}
                        </span>
                      </td>
                    </tr>
                  </React.Fragment>
                );
              })}
            </tbody>
            <tfoot>
              <tr>
                <td colSpan="4">Totale consuntivo / preventivo</td>
                <td>{fmtCurrency(clientSummary.totale_consuntivo)}</td>
                <td>{clientSummary.totale_consuntivo ? fmtPercent(100) : fmtPercent(0)}</td>
                <td>{fmtCurrency(clientSummary.totale_preventivo)}</td>
                <td>{fmtCurrency(clientSummary.totale_presentato)}</td>
                <td></td>
              </tr>
              <tr>
                <td colSpan="4">Contributo richiesto</td>
                <td>{fmtCurrency(clientSummary.contributo_richiesto)}</td>
                <td></td>
                <td></td>
                <td></td>
                <td></td>
              </tr>
              <tr>
                <td colSpan="4">Cofinanziamento</td>
                <td>{fmtCurrency(clientSummary.cofinanziamento)}</td>
                <td></td>
                <td></td>
                <td></td>
                <td></td>
              </tr>
            </tfoot>
          </table>
        </div>
      )}

      {serverSummary && (
        <div className="server-note">
          <strong>Riepilogo server aggiornato.</strong>
          <span>Totale consuntivo {fmtCurrency(serverSummary.totale_consuntivo)} · Totale preventivo {fmtCurrency(serverSummary.totale_preventivo)}</span>
        </div>
      )}

      {serverSummary && serverSummary.ore_per_ruolo && serverSummary.ore_per_ruolo.length > 0 && (
        <div className="pf-ore-presenze">
          <h4>Ore presenze effettive collegate alle voci piano</h4>
          <table className="pf-ore-table">
            <thead>
              <tr>
                <th>Collaboratore</th>
                <th>Ruolo origine / Voce piano</th>
                <th>Presenze</th>
                <th>Ore effettive</th>
                <th>Costo effettivo</th>
              </tr>
            </thead>
            <tbody>
              {serverSummary.ore_per_ruolo.map((item, idx) => (
                <tr key={idx}>
                  <td>
                    {item.collaborator_name || 'N/D'}
                  </td>
                  <td>
                    {item.voce_codice && (
                      <span className="pf-voce-badge">{item.voce_codice}</span>
                    )}
                    {item.voce_label || item.role}
                    {item.voce_label && item.role !== item.voce_label && (
                      <div><small>Origine: {item.role}</small></div>
                    )}
                  </td>
                  <td>{item.n_presenze}</td>
                  <td>{item.ore_effettive.toFixed(1)} h</td>
                  <td>{fmtCurrency(item.costo_effettivo)}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <td colSpan={3}><strong>Totale</strong></td>
                <td><strong>{serverSummary.ore_effettive_totali.toFixed(1)} h</strong></td>
                <td><strong>{fmtCurrency(serverSummary.ore_per_ruolo.reduce((s, r) => s + r.costo_effettivo, 0))}</strong></td>
              </tr>
            </tfoot>
          </table>
        </div>
      )}
    </div>
  );
}
