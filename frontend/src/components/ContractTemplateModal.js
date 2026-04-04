/**
 * MODAL PER CREARE/MODIFICARE TEMPLATE DOCUMENTI
 *
 * Form adattivo per ambito:
 * - contratto          → tipo contratto, HTML editor, logo, clausole, formati
 * - piano_finanziario  → ente erogatore + avviso + macrovoci/massimali + voci di piano
 * - preventivo / listino / timesheet / ordine / generico → HTML editor base
 */

import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { apiRootUrl } from '../lib/http';
import { createAvviso, getAvvisi } from '../services/apiService';
import './ContractTemplateModal.css';

// ============================================================
// COSTANTI
// ============================================================

const TIPI_CONTRATTO = [
  { value: 'professionale',      label: '👔 Professionale' },
  { value: 'occasionale',        label: '📝 Occasionale' },
  { value: 'ordine_servizio',    label: '📋 Ordine di Servizio' },
  { value: 'contratto_progetto', label: '📄 Contratto a Progetto' },
];

const AMBITI_TEMPLATE = [
  { value: 'contratto',        label: '📄 Contratto' },
  { value: 'preventivo',       label: '🧾 Preventivo' },
  { value: 'listino',          label: '🏷️ Listino' },
  { value: 'piano_finanziario',label: '💼 Piano Finanziario' },
  { value: 'timesheet',        label: '🕒 Timesheet' },
  { value: 'ordine',           label: '🛒 Ordine' },
  { value: 'generico',         label: '🗂️ Generico' },
];

const STANDARD_DOCUMENT_KEYS = {
  contratto:        ['contratto_professionale', 'contratto_occasionale', 'ordine_di_servizio', 'contratto_a_progetto'],
  preventivo:       ['preventivo_standard', 'preventivo_formazione', 'preventivo_consulenza'],
  listino:          ['listino_standard', 'listino_formazione', 'listino_consulenza'],
  piano_finanziario:['piano_finanziario_formazienda', 'piano_finanziario_fapi', 'piano_finanziario_fondimpresa'],
  timesheet:        ['timesheet_standard', 'timesheet_mensile', 'timesheet_docente', 'timesheet_tutor'],
  ordine:           ['ordine_standard', 'ordine_servizio', 'ordine_acquisto'],
  generico:         ['documento_generico', 'verbale_standard', 'modulo_generico'],
};

const POSIZIONI_LOGO = [
  { value: 'header', label: 'Intestazione' },
  { value: 'footer', label: 'Piè di pagina' },
  { value: 'none',   label: 'Nessuno' },
];

const DIMENSIONI_LOGO = [
  { value: 'small',  label: 'Piccolo' },
  { value: 'medium', label: 'Medio' },
  { value: 'large',  label: 'Grande' },
];

const TEMPLATE_HTML_ESEMPIO = `<div style="font-family: Arial, sans-serif; padding: 20px;">
  <h1 style="text-align: center;">CONTRATTO DI COLLABORAZIONE</h1>

  <p>Tra:</p>
  <p><strong>{{ente_ragione_sociale}}</strong><br/>
  P.IVA: {{ente_piva}}<br/>
  Sede: {{ente_indirizzo_completo}}</p>

  <p>E:</p>
  <p><strong>{{collaboratore_nome}} {{collaboratore_cognome}}</strong><br/>
  C.F.: {{collaboratore_codice_fiscale}}<br/>
  Nato a: {{collaboratore_luogo_nascita}} il {{collaboratore_data_nascita}}</p>

  <h2>OGGETTO DEL CONTRATTO</h2>
  <p>Progetto: <strong>{{progetto_nome}}</strong></p>
  <p>Mansione: <strong>{{mansione}}</strong></p>

  <h2>COMPENSO</h2>
  <p>Ore previste: {{ore_previste}}<br/>
  Tariffa oraria: €{{tariffa_oraria}}<br/>
  Compenso totale: €{{compenso_totale}}</p>

  <h2>DURATA</h2>
  <p>Dal {{data_inizio}} al {{data_fine}}</p>

  <p style="margin-top: 50px;">Data: {{data_firma_contratto}}</p>

  <div style="display: flex; justify-content: space-between; margin-top: 50px;">
    <div><p>____________________<br/>Firma Ente</p></div>
    <div><p>____________________<br/>Firma Collaboratore</p></div>
  </div>
</div>`;

// Piano Finanziario: catalogo voci (specchio di piano_finanziario_config.py)
const VOCI_PIANO = [
  { macrovoce: 'A', codice: 'A.1', descrizione: 'Progettazione esecutiva',              is_dynamic: false },
  { macrovoce: 'A', codice: 'A.2', descrizione: 'Rilevazione fabbisogni',               is_dynamic: false },
  { macrovoce: 'A', codice: 'A.3', descrizione: 'Promozione',                           is_dynamic: false },
  { macrovoce: 'A', codice: 'A.4', descrizione: 'Monitoraggio e valutazione',           is_dynamic: false },
  { macrovoce: 'A', codice: 'A.5', descrizione: 'Diffusione',                           is_dynamic: false },
  { macrovoce: 'A', codice: 'A.6', descrizione: 'Viaggi e trasferte',                   is_dynamic: false },
  { macrovoce: 'A', codice: 'A.7', descrizione: 'Altro',                                is_dynamic: false },
  { macrovoce: 'B', codice: 'B.1', descrizione: 'Coordinamento',                        is_dynamic: false },
  { macrovoce: 'B', codice: 'B.2', descrizione: 'Docenza',                              is_dynamic: true  },
  { macrovoce: 'B', codice: 'B.3', descrizione: 'Tutor',                                is_dynamic: true  },
  { macrovoce: 'B', codice: 'B.4', descrizione: 'Materiali didattici',                  is_dynamic: false },
  { macrovoce: 'B', codice: 'B.5', descrizione: 'Materiali di consumo',                 is_dynamic: false },
  { macrovoce: 'B', codice: 'B.6', descrizione: 'Aule didattiche',                      is_dynamic: false },
  { macrovoce: 'B', codice: 'B.7', descrizione: 'Attrezzature',                         is_dynamic: false },
  { macrovoce: 'B', codice: 'B.8', descrizione: 'Certificazione delle competenze',      is_dynamic: false },
  { macrovoce: 'B', codice: 'B.9', descrizione: 'Viaggi e trasferte',                   is_dynamic: false },
  { macrovoce: 'B', codice: 'B.10',descrizione: 'Altro',                                is_dynamic: false },
  { macrovoce: 'C', codice: 'C.1', descrizione: 'Designer',                             is_dynamic: false },
  { macrovoce: 'C', codice: 'C.2', descrizione: 'Personale amministrativo',             is_dynamic: false },
  { macrovoce: 'C', codice: 'C.3', descrizione: 'Rendicontazione',                      is_dynamic: false },
  { macrovoce: 'C', codice: 'C.4', descrizione: 'Revisione dei conti',                  is_dynamic: false },
  { macrovoce: 'C', codice: 'C.5', descrizione: 'Fidejussione',                         is_dynamic: false },
  { macrovoce: 'C', codice: 'C.6', descrizione: 'Costi generali e amministrativi (forfait)', is_dynamic: false },
  { macrovoce: 'C', codice: 'C.7', descrizione: 'Viaggi e trasferte',                   is_dynamic: false },
  { macrovoce: 'C', codice: 'C.8', descrizione: 'Altro',                                is_dynamic: false },
  { macrovoce: 'D', codice: 'D.1', descrizione: 'Retribuzione ed oneri del personale',  is_dynamic: false },
  { macrovoce: 'D', codice: 'D.2', descrizione: 'Assicurazioni',                        is_dynamic: false },
  { macrovoce: 'D', codice: 'D.3', descrizione: 'Rimborsi viaggi e trasferte',          is_dynamic: false },
  { macrovoce: 'D', codice: 'D.4', descrizione: 'Altro',                                is_dynamic: false },
];

const DEFAULT_MACROVOCI = [
  { codice: 'A', titolo: 'Progettazione della formazione',          massimale_pct: 20.0, solo_cofinanziamento: false },
  { codice: 'B', titolo: 'Erogazione della formazione',             massimale_pct: 50.0, solo_cofinanziamento: false },
  { codice: 'C', titolo: 'Gestione e amministrazione',              massimale_pct: 30.0, solo_cofinanziamento: false },
  { codice: 'D', titolo: 'Costo del personale in formazione',       massimale_pct: null, solo_cofinanziamento: true  },
];

// ============================================================
// COMPONENTE
// ============================================================

const ContractTemplateModal = ({ template, onClose, onSave }) => {

  // --- Dati base (tutti gli ambiti) ---
  const [nomeTemplate, setNomeTemplate]   = useState('');
  const [descrizione, setDescrizione]     = useState('');
  const [ambitoTemplate, setAmbitoTemplate] = useState('contratto');
  const [versione, setVersione]           = useState('1.0');
  const [isActive, setIsActive]           = useState(true);
  const [noteInterne, setNoteInterne]     = useState('');

  // --- Scope / classificazione ---
  const [chiaveDocumento, setChiaveDocumento]       = useState('');
  const [chiavePersonalizzata, setChiavePersonalizzata] = useState(false);
  const [enteErogatore, setEnteErogatore]           = useState('');
  const [avvisoRiferimento, setAvvisoRiferimento]   = useState('');
  const [linkedAvvisoIds, setLinkedAvvisoIds]       = useState([]);
  const [avvisiOptions, setAvvisiOptions]           = useState([]);
  const [newAvvisoCode, setNewAvvisoCode]           = useState('');
  const [avvisiError, setAvvisiError]               = useState('');
  const [enteAttuatoreId, setEnteAttuatoreId]       = useState('');
  const [progettoId, setProgettoId]                 = useState('');

  // --- Solo contratto ---
  const [tipoContratto, setTipoContratto]           = useState('professionale');
  const [isDefault, setIsDefault]                   = useState(false);
  const [contenutoHtml, setContenutoHtml]           = useState('');
  const [intestazione, setIntestazione]             = useState('');
  const [piePagina, setPiePagina]                   = useState('');
  const [includeLogoEnte, setIncludeLogoEnte]       = useState(true);
  const [posizioneLogo, setPosizioneLogo]           = useState('header');
  const [dimensioneLogo, setDimensioneLogo]         = useState('medium');
  const [includeClausolaPrivacy, setIncludeClausolaPrivacy]                         = useState(true);
  const [includeClausolaRiservatezza, setIncludeClausolaRiservatezza]               = useState(false);
  const [includeClausolaProprietaIntellettuale, setIncludeClausolaProprietaIntellettuale] = useState(false);
  const [formatoData, setFormatoData]               = useState('%d/%m/%Y');
  const [formatoImporto, setFormatoImporto]         = useState('€ {:.2f}');

  // --- Documenti generici (preventivo, listino, timesheet, ordine, generico) ---
  const [contenutoHtmlDoc, setContenutoHtmlDoc] = useState('');

  // --- Piano Finanziario ---
  const [macrovoceConfig, setMacrovoceConfig] = useState(() => DEFAULT_MACROVOCI.map(m => ({ ...m })));
  const [c6MaxPct, setC6MaxPct]               = useState(10.0);
  const [noteFondo, setNoteFondo]             = useState('');
  const [vociIncluse, setVociIncluse]         = useState(() => new Set(VOCI_PIANO.map(v => v.codice)));

  // --- UI ---
  const [errors, setErrors]             = useState({});
  const [showVariables, setShowVariables] = useState(false);
  const [uploadingFile, setUploadingFile] = useState(false);
  const [uploadError, setUploadError]   = useState(null);
  const [entiOptions, setEntiOptions]   = useState([]);
  const [progettiOptions, setProgettiOptions] = useState([]);

  // Flag ambito
  const isContractScope = ambitoTemplate === 'contratto';
  const isPianoScope    = ambitoTemplate === 'piano_finanziario';
  const isDocScope      = !isContractScope && !isPianoScope;

  const chiaviDocumentoStandard = useMemo(
    () => STANDARD_DOCUMENT_KEYS[ambitoTemplate] || STANDARD_DOCUMENT_KEYS.generico,
    [ambitoTemplate]
  );

  // ============================================================
  // PIANO: serializza / deserializza schema JSON → contenuto_html
  // ============================================================

  const serializePianoSchema = useCallback(() => {
    return JSON.stringify({
      tipo: 'piano_finanziario',
      macrovoci: macrovoceConfig,
      voci_incluse: Array.from(vociIncluse),
      c6_massimale_pct: c6MaxPct,
      note_fondo: noteFondo,
    }, null, 2);
  }, [macrovoceConfig, vociIncluse, c6MaxPct, noteFondo]);

  const parsePianoSchema = useCallback((html) => {
    if (!html) return;
    try {
      const schema = JSON.parse(html);
      if (schema.tipo === 'piano_finanziario') {
        if (Array.isArray(schema.macrovoci)) setMacrovoceConfig(schema.macrovoci);
        if (Array.isArray(schema.voci_incluse)) setVociIncluse(new Set(schema.voci_incluse));
        if (schema.c6_massimale_pct != null) setC6MaxPct(schema.c6_massimale_pct);
        if (schema.note_fondo) setNoteFondo(schema.note_fondo);
      }
    } catch { /* usa valori di default */ }
  }, []);

  // ============================================================
  // INIZIALIZZAZIONE
  // ============================================================

  useEffect(() => {
    if (template) {
      const ambito = template.ambito_template || 'contratto';
      setNomeTemplate(template.nome_template || '');
      setDescrizione(template.descrizione || '');
      setAmbitoTemplate(ambito);
      setVersione(template.versione || '1.0');
      setIsActive(template.is_active !== false);
      setNoteInterne(template.note_interne || '');
      setEnteErogatore(template.ente_erogatore || '');
      setAvvisoRiferimento(template.avviso || '');
      setEnteAttuatoreId(template.ente_attuatore_id ? String(template.ente_attuatore_id) : '');
      setProgettoId(template.progetto_id ? String(template.progetto_id) : '');

      const chiave = template.chiave_documento || '';
      const standardKeys = STANDARD_DOCUMENT_KEYS[ambito] || STANDARD_DOCUMENT_KEYS.generico;
      setChiaveDocumento(chiave);
      setChiavePersonalizzata(Boolean(chiave) && !standardKeys.includes(chiave));

      if (ambito === 'contratto') {
        setTipoContratto(template.tipo_contratto || 'professionale');
        setIsDefault(template.is_default || false);
        setContenutoHtml(template.contenuto_html || '');
        setIntestazione(template.intestazione || '');
        setPiePagina(template.pie_pagina || '');
        setIncludeLogoEnte(template.include_logo_ente !== false);
        setPosizioneLogo(template.posizione_logo || 'header');
        setDimensioneLogo(template.dimensione_logo || 'medium');
        setIncludeClausolaPrivacy(template.include_clausola_privacy !== false);
        setIncludeClausolaRiservatezza(template.include_clausola_riservatezza || false);
        setIncludeClausolaProprietaIntellettuale(template.include_clausola_proprieta_intellettuale || false);
        setFormatoData(template.formato_data || '%d/%m/%Y');
        setFormatoImporto(template.formato_importo || '€ {:.2f}');
      } else if (ambito === 'piano_finanziario') {
        parsePianoSchema(template.contenuto_html);
      } else {
        setContenutoHtmlDoc(template.contenuto_html || '');
      }
    } else {
      // Nuovo template: reset a contratto con esempio HTML
      setAmbitoTemplate('contratto');
      setTipoContratto('professionale');
      setContenutoHtml(TEMPLATE_HTML_ESEMPIO);
      setMacrovoceConfig(DEFAULT_MACROVOCI.map(m => ({ ...m })));
      setVociIncluse(new Set(VOCI_PIANO.map(v => v.codice)));
      setC6MaxPct(10.0);
      setNoteFondo('');
    }
  }, [template, parsePianoSchema]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!template || avvisiOptions.length === 0) {
      if (!template) setLinkedAvvisoIds([]);
      return;
    }
    const linked = avvisiOptions
      .filter((a) => String(a.template_id || '') === String(template.id))
      .map((a) => String(a.id));
    setLinkedAvvisoIds(linked);
  }, [template, avvisiOptions]);

  // Reset chiave quando cambia ambito
  useEffect(() => {
    setChiaveDocumento('');
    setChiavePersonalizzata(false);
    setErrors({});
  }, [ambitoTemplate]);

  // Carica enti e progetti per i select di scope
  useEffect(() => {
    let cancelled = false;
    const loadOptions = async () => {
      try {
        const [entiRes, progettiRes, avvisiData] = await Promise.all([
          fetch(`${apiRootUrl}/api/v1/entities/?limit=300`),
          fetch(`${apiRootUrl}/api/v1/projects/?limit=300`),
          getAvvisi({ active_only: true, limit: 1000 }),
        ]);
        const [entiData, progettiData] = await Promise.all([
          entiRes.ok ? entiRes.json() : [],
          progettiRes.ok ? progettiRes.json() : [],
        ]);
        if (!cancelled) {
          setEntiOptions(Array.isArray(entiData) ? entiData : []);
          setProgettiOptions(Array.isArray(progettiData) ? progettiData : []);
          setAvvisiOptions(Array.isArray(avvisiData) ? avvisiData : []);
        }
      } catch {
        if (!cancelled) { setEntiOptions([]); setProgettiOptions([]); setAvvisiOptions([]); }
      }
    };
    loadOptions();
    return () => { cancelled = true; };
  }, []);

  // ============================================================
  // VALIDAZIONE
  // ============================================================

  const validateForm = () => {
    const newErrors = {};

    if (!nomeTemplate.trim()) newErrors.nomeTemplate = 'Il nome del template è obbligatorio';
    if (!versione.trim()) newErrors.versione = 'La versione è obbligatoria';

    if (isContractScope) {
      if (!tipoContratto) newErrors.tipoContratto = 'Il tipo di contratto è obbligatorio';
      if (!contenutoHtml.trim()) newErrors.contenutoHtml = 'Il contenuto HTML è obbligatorio';
    } else if (isPianoScope) {
      if (!enteErogatore.trim()) newErrors.enteErogatore = "Ente erogatore obbligatorio per piano finanziario";
      if (!avvisoRiferimento.trim() && linkedAvvisoIds.length === 0) newErrors.avvisoRiferimento = "Avviso obbligatorio per piano finanziario";
      if (!chiaveDocumento.trim()) newErrors.chiaveDocumento = "Chiave documento obbligatoria per piano finanziario";
    } else {
      if (!chiaveDocumento.trim()) newErrors.chiaveDocumento = "Chiave documento obbligatoria";
      if (!contenutoHtmlDoc.trim()) newErrors.contenutoHtml = "Il contenuto HTML è obbligatorio";
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  // ============================================================
  // SALVATAGGIO
  // ============================================================

  const handleSubmit = () => {
    if (!validateForm()) return;

    let contenutoFinale;
    let tipoContrattoFinale;

    if (isContractScope) {
      contenutoFinale = contenutoHtml.trim();
      tipoContrattoFinale = tipoContratto;
    } else if (isPianoScope) {
      contenutoFinale = serializePianoSchema();
      tipoContrattoFinale = 'documento_generico';
    } else {
      contenutoFinale = contenutoHtmlDoc.trim();
      tipoContrattoFinale = 'documento_generico';
    }

    onSave({
      nome_template:     nomeTemplate.trim(),
      descrizione:       descrizione.trim() || null,
      ambito_template:   ambitoTemplate,
      chiave_documento:  chiaveDocumento.trim() || null,
      ente_attuatore_id: enteAttuatoreId ? parseInt(enteAttuatoreId, 10) : null,
      progetto_id:       progettoId ? parseInt(progettoId, 10) : null,
      ente_erogatore:    enteErogatore.trim() || null,
      avviso:            avvisoRiferimento.trim() || null,
      linked_avviso_ids: linkedAvvisoIds.map((id) => parseInt(id, 10)).filter((n) => Number.isFinite(n)),
      tipo_contratto:    tipoContrattoFinale,
      contenuto_html:    contenutoFinale,
      intestazione:      isContractScope ? (intestazione.trim() || null) : null,
      pie_pagina:        isContractScope ? (piePagina.trim() || null) : null,
      include_logo_ente: isContractScope ? includeLogoEnte : false,
      posizione_logo:    isContractScope ? posizioneLogo : 'none',
      dimensione_logo:   isContractScope ? dimensioneLogo : 'medium',
      include_clausola_privacy:               isContractScope ? includeClausolaPrivacy : false,
      include_clausola_riservatezza:          isContractScope ? includeClausolaRiservatezza : false,
      include_clausola_proprieta_intellettuale: isContractScope ? includeClausolaProprietaIntellettuale : false,
      formato_data:    isContractScope ? formatoData : '%d/%m/%Y',
      formato_importo: isContractScope ? formatoImporto : '€ {:.2f}',
      is_default:  isContractScope ? isDefault : false,
      is_active:   isActive,
      versione:    versione.trim(),
      note_interne: noteInterne.trim() || null,
    });
  };

  // ============================================================
  // UPLOAD DOCX (solo contratto)
  // ============================================================

  const handleFileUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;
    if (!file.name.toLowerCase().endsWith('.docx')) {
      setUploadError('Il file deve essere in formato .docx');
      return;
    }
    setUploadingFile(true);
    setUploadError(null);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const response = await fetch(`${apiRootUrl}/api/v1/contracts/convert-docx-to-html`, {
        method: 'POST',
        body: formData,
      });
      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || 'Errore nella conversione del file');
      }
      const data = await response.json();
      setContenutoHtml(data.html);
      if (!nomeTemplate) setNomeTemplate(file.name.replace('.docx', ''));
    } catch (error) {
      setUploadError(error.message || 'Errore nel caricamento del file');
    } finally {
      setUploadingFile(false);
      event.target.value = '';
    }
  };

  // ============================================================
  // PIANO: aggiornamento macrovoci e voci
  // ============================================================

  const updateMacrovoce = (codice, field, value) => {
    setMacrovoceConfig(prev =>
      prev.map(m => m.codice === codice ? { ...m, [field]: value } : m)
    );
  };

  const toggleVoce = (codice) => {
    setVociIncluse(prev => {
      const next = new Set(prev);
      if (next.has(codice)) next.delete(codice); else next.add(codice);
      return next;
    });
  };

  const avvisiFiltratiByEnte = useMemo(() => {
    const ente = String(enteErogatore || '').trim().toLowerCase();
    if (!ente) return avvisiOptions;
    return avvisiOptions.filter((a) => String(a.ente_erogatore || '').trim().toLowerCase() === ente);
  }, [avvisiOptions, enteErogatore]);
  const avvisiCollegatiCount = linkedAvvisoIds.length;

  const toggleLinkedAvviso = (avvisoId) => {
    setLinkedAvvisoIds((prev) => {
      const key = String(avvisoId);
      const exists = prev.includes(key);
      const next = exists ? prev.filter((id) => id !== key) : [...prev, key];
      const first = avvisiOptions.find((a) => String(a.id) === String(next[0] || ''));
      if (first?.codice) setAvvisoRiferimento(first.codice);
      return next;
    });
  };

  const handleCreateAvvisoInline = async () => {
    const code = String(newAvvisoCode || '').trim();
    const ente = String(enteErogatore || '').trim();
    if (!code || !ente) {
      setAvvisiError('Per creare un avviso serve ente erogatore e codice avviso.');
      return;
    }
    setAvvisiError('');
    try {
      const created = await createAvviso({
        codice: code,
        ente_erogatore: ente,
        descrizione: null,
        template_id: null,
        is_active: true,
      });
      setAvvisiOptions((prev) => [...prev, created]);
      setLinkedAvvisoIds((prev) => Array.from(new Set([...prev, String(created.id)])));
      setAvvisoRiferimento(created.codice);
      setNewAvvisoCode('');
    } catch (e) {
      setAvvisiError(e?.response?.data?.detail || e?.message || 'Errore creazione avviso');
    }
  };

  const toggleAllVociMacrovoce = (lettera, checked) => {
    setVociIncluse(prev => {
      const next = new Set(prev);
      VOCI_PIANO.filter(v => v.macrovoce === lettera).forEach(v => {
        if (checked) next.add(v.codice); else next.delete(v.codice);
      });
      return next;
    });
  };

  // ============================================================
  // VARIABILI CONTRATTO
  // ============================================================

  const insertVariable = (variable) => {
    const textarea = document.getElementById('contenuto-html');
    if (!textarea) return;
    const start = textarea.selectionStart;
    const end   = textarea.selectionEnd;
    const before = contenutoHtml.substring(0, start);
    const after  = contenutoHtml.substring(end);
    setContenutoHtml(before + `{{${variable}}}` + after);
    setTimeout(() => {
      textarea.focus();
      textarea.setSelectionRange(start + variable.length + 4, start + variable.length + 4);
    }, 0);
  };

  const variabiliDisponibili = [
    { categoria: 'Collaboratore', vars: [
      'collaboratore_nome','collaboratore_cognome','collaboratore_nome_completo',
      'collaboratore_email','collaboratore_codice_fiscale','collaboratore_telefono',
      'collaboratore_luogo_nascita','collaboratore_data_nascita',
      'collaboratore_indirizzo','collaboratore_citta','collaboratore_titolo_studio',
    ]},
    { categoria: 'Ente Attuatore', vars: [
      'ente_ragione_sociale','ente_forma_giuridica','ente_piva','ente_codice_fiscale',
      'ente_indirizzo_completo','ente_sede_comune','ente_sede_via','ente_sede_numero_civico',
      'ente_pec','ente_email','ente_telefono',
      'ente_legale_rappresentante_nome','ente_legale_rappresentante_cognome',
      'ente_legale_rappresentante_nome_completo','ente_legale_rappresentante_luogo_nascita',
      'ente_legale_rappresentante_data_nascita','ente_legale_rappresentante_comune_residenza',
      'ente_legale_rappresentante_via_residenza','ente_legale_rappresentante_codice_fiscale',
    ]},
    { categoria: 'Progetto', vars: [
      'progetto_nome','progetto_descrizione','progetto_cup','progetto_atto_approvazione',
      'progetto_data_inizio','progetto_data_fine',
      'progetto_sede_aziendale_comune','progetto_sede_aziendale_via',
      'progetto_sede_aziendale_numero_civico','progetto_sede_aziendale_completa',
    ]},
    { categoria: 'Contratto', vars: [
      'mansione','ore_previste','tariffa_oraria','compenso_totale','data_inizio','data_fine',
    ]},
    { categoria: 'Sistema', vars: [
      'data_oggi','data_firma_contratto','data_sottoscrizione_contratto','contract_signed_date',
    ]},
  ];

  // ============================================================
  // HELPER: campo chiave documento (riusabile)
  // ============================================================

  const renderChiaveDocumentoField = (required = false) => (
    <div className="form-group">
      <label>Chiave Documento {required && <span className="required">*</span>}</label>
      <select
        value={chiavePersonalizzata ? '__custom__' : chiaveDocumento}
        onChange={(e) => {
          const v = e.target.value;
          if (v === '__custom__') { setChiavePersonalizzata(true); setChiaveDocumento(''); }
          else { setChiavePersonalizzata(false); setChiaveDocumento(v); }
        }}
        className={errors.chiaveDocumento ? 'error' : ''}
      >
        <option value="">Seleziona chiave documento</option>
        {chiaviDocumentoStandard.map(k => <option key={k} value={k}>{k}</option>)}
        <option value="__custom__">Personalizzata...</option>
      </select>
      {chiavePersonalizzata && (
        <input
          type="text"
          value={chiaveDocumento}
          onChange={(e) => setChiaveDocumento(e.target.value)}
          placeholder="Es: listino_custom_2026"
          className={errors.chiaveDocumento ? 'error' : ''}
          style={{ marginTop: '8px' }}
        />
      )}
      {errors.chiaveDocumento && <span className="error-text">{errors.chiaveDocumento}</span>}
    </div>
  );

  // Voci raggruppate per macrovoce (render tabella piano)
  const vociPerMacrovoce = useMemo(() => {
    const groups = {};
    VOCI_PIANO.forEach(v => {
      if (!groups[v.macrovoce]) groups[v.macrovoce] = [];
      groups[v.macrovoce].push(v);
    });
    return groups;
  }, []);

  // ============================================================
  // RENDER
  // ============================================================

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="template-modal" onClick={(e) => e.stopPropagation()}>

        {/* HEADER */}
        <div className="modal-header">
          <h2>{template ? 'Modifica Template' : 'Nuovo Template'}</h2>
          <button className="close-button" onClick={onClose}>×</button>
        </div>

        {/* BODY */}
        <div className="modal-body">

          {/* ── SEZIONE 1: DATI BASE (tutti gli ambiti) ── */}
          <div className="form-section">
            <h3 className="section-title">📋 Dati Base</h3>

            <div className="form-group">
              <label>Nome Template <span className="required">*</span></label>
              <input
                type="text"
                value={nomeTemplate}
                onChange={(e) => setNomeTemplate(e.target.value)}
                placeholder="Es: Contratto Standard Professionale"
                className={errors.nomeTemplate ? 'error' : ''}
              />
              {errors.nomeTemplate && <span className="error-text">{errors.nomeTemplate}</span>}
            </div>

            <div className="form-group">
              <label>Descrizione</label>
              <textarea
                value={descrizione}
                onChange={(e) => setDescrizione(e.target.value)}
                placeholder="Breve descrizione del template e del suo utilizzo..."
                rows="2"
              />
            </div>

            <div className="form-row">
              <div className="form-group">
                <label>Ambito Documento</label>
                <select value={ambitoTemplate} onChange={(e) => setAmbitoTemplate(e.target.value)}>
                  {AMBITI_TEMPLATE.map(a => (
                    <option key={a.value} value={a.value}>{a.label}</option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label>Versione <span className="required">*</span></label>
                <input
                  type="text"
                  value={versione}
                  onChange={(e) => setVersione(e.target.value)}
                  placeholder="1.0"
                  className={errors.versione ? 'error' : ''}
                />
                {errors.versione && <span className="error-text">{errors.versione}</span>}
              </div>
            </div>
          </div>

          {/* ================================================================
              CONTRATTO
          ================================================================ */}
          {isContractScope && (
            <>
              {/* 2-CONTRATTO: Tipo e scope */}
              <div className="form-section">
                <h3 className="section-title">📝 Tipo Contratto e Scope</h3>

                <div className="form-row">
                  <div className="form-group">
                    <label>Tipo Contratto <span className="required">*</span></label>
                    <select
                      value={tipoContratto}
                      onChange={(e) => setTipoContratto(e.target.value)}
                      className={errors.tipoContratto ? 'error' : ''}
                    >
                      {TIPI_CONTRATTO.map(t => (
                        <option key={t.value} value={t.value}>{t.label}</option>
                      ))}
                    </select>
                    {errors.tipoContratto && <span className="error-text">{errors.tipoContratto}</span>}
                    <small className="help-text">Usato dal motore contratti per scegliere automaticamente il template corretto.</small>
                  </div>
                  {renderChiaveDocumentoField(false)}
                </div>

                <div className="form-row">
                  <div className="form-group">
                    <label>Ente Erogatore</label>
                    <input
                      type="text"
                      value={enteErogatore}
                      onChange={(e) => setEnteErogatore(e.target.value)}
                      placeholder="Es: Formazienda, FAPI"
                    />
                  </div>
                  <div className="form-group">
                    <label>Avviso</label>
                    <input
                      type="text"
                      value={avvisoRiferimento}
                      onChange={(e) => setAvvisoRiferimento(e.target.value)}
                      placeholder="Es: 2/2022"
                    />
                  </div>
                </div>

                <div className="form-row">
                  <div className="form-group">
                    <label>Ente Applicabile</label>
                    <select value={enteAttuatoreId} onChange={(e) => setEnteAttuatoreId(e.target.value)}>
                      <option value="">Template globale</option>
                      {entiOptions.map(e => <option key={e.id} value={e.id}>{e.ragione_sociale}</option>)}
                    </select>
                  </div>
                  <div className="form-group">
                    <label>Progetto Applicabile</label>
                    <select value={progettoId} onChange={(e) => setProgettoId(e.target.value)}>
                      <option value="">Tutti i progetti</option>
                      {progettiOptions.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                    </select>
                  </div>
                </div>
              </div>

              {/* 3-CONTRATTO: Contenuto HTML */}
              <div className="form-section">
                <div className="section-header">
                  <h3 className="section-title">💻 Contenuto HTML</h3>
                  <button type="button" className="btn-secondary btn-small" onClick={() => setShowVariables(!showVariables)}>
                    {showVariables ? '🔽 Nascondi' : '📌 Mostra'} Variabili
                  </button>
                </div>

                <div className="upload-section">
                  <input type="file" accept=".docx" onChange={handleFileUpload} disabled={uploadingFile} style={{ display: 'none' }} id="docx-upload" />
                  <button type="button" className="btn-secondary btn-small" onClick={() => document.getElementById('docx-upload').click()} disabled={uploadingFile}>
                    {uploadingFile ? '⏳ Caricamento...' : '📤 Carica DOCX'}
                  </button>
                  <small className="help-text">Carica un file Word (.docx) che verrà convertito automaticamente in HTML</small>
                  {uploadError && <div className="upload-error" style={{ color: 'red', marginTop: '5px' }}>⚠️ {uploadError}</div>}
                </div>

                {showVariables && (
                  <div className="variables-panel">
                    <p className="variables-intro">Clicca su una variabile per inserirla nel punto corrente del cursore.</p>
                    {variabiliDisponibili.map(gruppo => (
                      <div key={gruppo.categoria} className="variable-group">
                        <h4>{gruppo.categoria}</h4>
                        <div className="variable-buttons">
                          {gruppo.vars.map(varName => (
                            <button key={varName} type="button" className="variable-button" onClick={() => insertVariable(varName)} title={`Inserisci {{${varName}}}`}>
                              {varName}
                            </button>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                <div className="form-group">
                  <label>Contenuto HTML <span className="required">*</span></label>
                  <textarea
                    id="contenuto-html"
                    value={contenutoHtml}
                    onChange={(e) => setContenutoHtml(e.target.value)}
                    placeholder="Inserisci il contenuto HTML del contratto..."
                    rows="15"
                    className={`code-editor ${errors.contenutoHtml ? 'error' : ''}`}
                  />
                  {errors.contenutoHtml && <span className="error-text">{errors.contenutoHtml}</span>}
                  <small className="help-text">Usa variabili {'{{collaboratore_nome}}'} che verranno sostituite con i dati reali durante la generazione.</small>
                </div>

                <div className="form-row">
                  <div className="form-group">
                    <label>Intestazione (opzionale)</label>
                    <textarea value={intestazione} onChange={(e) => setIntestazione(e.target.value)} placeholder="HTML per l'intestazione..." rows="3" />
                  </div>
                  <div className="form-group">
                    <label>Piè di Pagina (opzionale)</label>
                    <textarea value={piePagina} onChange={(e) => setPiePagina(e.target.value)} placeholder="HTML per il piè di pagina..." rows="3" />
                  </div>
                </div>
              </div>

              {/* 4-CONTRATTO: Logo */}
              <div className="form-section">
                <h3 className="section-title">🖼️ Configurazione Logo</h3>
                <div className="checkbox-group">
                  <label>
                    <input type="checkbox" checked={includeLogoEnte} onChange={(e) => setIncludeLogoEnte(e.target.checked)} />
                    Includi logo ente attuatore nel documento
                  </label>
                </div>
                {includeLogoEnte && (
                  <div className="form-row" style={{ marginTop: '12px' }}>
                    <div className="form-group">
                      <label>Posizione Logo</label>
                      <select value={posizioneLogo} onChange={(e) => setPosizioneLogo(e.target.value)}>
                        {POSIZIONI_LOGO.map(pos => <option key={pos.value} value={pos.value}>{pos.label}</option>)}
                      </select>
                    </div>
                    <div className="form-group">
                      <label>Dimensione Logo</label>
                      <select value={dimensioneLogo} onChange={(e) => setDimensioneLogo(e.target.value)}>
                        {DIMENSIONI_LOGO.map(dim => <option key={dim.value} value={dim.value}>{dim.label}</option>)}
                      </select>
                    </div>
                  </div>
                )}
              </div>

              {/* 5-CONTRATTO: Clausole */}
              <div className="form-section">
                <h3 className="section-title">📜 Clausole Standard</h3>
                <div className="checkbox-group">
                  <label><input type="checkbox" checked={includeClausolaPrivacy} onChange={(e) => setIncludeClausolaPrivacy(e.target.checked)} /> Includi clausola privacy (GDPR)</label>
                </div>
                <div className="checkbox-group">
                  <label><input type="checkbox" checked={includeClausolaRiservatezza} onChange={(e) => setIncludeClausolaRiservatezza(e.target.checked)} /> Includi clausola riservatezza</label>
                </div>
                <div className="checkbox-group">
                  <label><input type="checkbox" checked={includeClausolaProprietaIntellettuale} onChange={(e) => setIncludeClausolaProprietaIntellettuale(e.target.checked)} /> Includi clausola proprietà intellettuale</label>
                </div>
              </div>

              {/* 6-CONTRATTO: Formati */}
              <div className="form-section">
                <h3 className="section-title">⚙️ Formati e Opzioni</h3>
                <div className="form-row">
                  <div className="form-group">
                    <label>Formato Data</label>
                    <input type="text" value={formatoData} onChange={(e) => setFormatoData(e.target.value)} placeholder="%d/%m/%Y" />
                    <small className="help-text">Python strftime format (es: %d/%m/%Y)</small>
                  </div>
                  <div className="form-group">
                    <label>Formato Importo</label>
                    <input type="text" value={formatoImporto} onChange={(e) => setFormatoImporto(e.target.value)} placeholder="€ {:.2f}" />
                    <small className="help-text">Python format string (es: € {'{:.2f}'})</small>
                  </div>
                </div>
                <div className="checkbox-group">
                  <label>
                    <input type="checkbox" checked={isDefault} onChange={(e) => setIsDefault(e.target.checked)} />
                    ⭐ Imposta come template predefinito per questo tipo contratto
                  </label>
                </div>
              </div>
            </>
          )}

          {/* ================================================================
              PIANO FINANZIARIO
          ================================================================ */}
          {isPianoScope && (
            <>
              {/* 2-PIANO: Riferimento Fondo */}
              <div className="form-section">
                <h3 className="section-title">🏛️ Riferimento Fondo</h3>

                <div className="form-row">
                  <div className="form-group">
                    <label>Ente Erogatore <span className="required">*</span></label>
                    <input
                      type="text"
                      value={enteErogatore}
                      onChange={(e) => setEnteErogatore(e.target.value)}
                      placeholder="Es: FORMAZIENDA, FAPI, FONDIMPRESA, Regione Campania"
                      className={errors.enteErogatore ? 'error' : ''}
                    />
                    {errors.enteErogatore && <span className="error-text">{errors.enteErogatore}</span>}
                    <small className="help-text">Fondo a cui si applica questo template piano.</small>
                  </div>
                  <div className="form-group">
                    <label>Avviso <span className="required">*</span></label>
                    <input
                      type="text"
                      value={avvisoRiferimento}
                      onChange={(e) => setAvvisoRiferimento(e.target.value)}
                      placeholder="Es: 9/2026"
                      className={errors.avvisoRiferimento ? 'error' : ''}
                    />
                    {errors.avvisoRiferimento && <span className="error-text">{errors.avvisoRiferimento}</span>}
                    <small className="help-text">Numero di avviso del fondo a cui si applica il piano.</small>
                    <small className="help-text">Campo primario legacy; i link reali sono nella lista avvisi qui sotto.</small>
                  </div>
                </div>

                <div className="form-group">
                  <label>Avvisi Collegati</label>
                  <div className="avvisi-linked-summary">
                    <strong>{avvisiCollegatiCount}</strong>
                    <span>{avvisiCollegatiCount === 1 ? 'avviso collegato a questo template' : 'avvisi collegati a questo template'}</span>
                  </div>
                  <div className="avvisi-table-shell">
                    {avvisiFiltratiByEnte.length === 0 ? (
                      <small className="help-text">Nessun avviso disponibile per questo ente erogatore.</small>
                    ) : (
                      <table className="avvisi-linked-table">
                        <thead>
                          <tr>
                            <th style={{ width: '90px' }}>Collega</th>
                            <th style={{ width: '180px' }}>Codice</th>
                            <th>Descrizione</th>
                            <th style={{ width: '140px' }}>Stato</th>
                          </tr>
                        </thead>
                        <tbody>
                          {avvisiFiltratiByEnte.map((a) => {
                            const isLinked = linkedAvvisoIds.includes(String(a.id));
                            return (
                              <tr key={a.id} className={isLinked ? 'is-linked' : ''}>
                                <td>
                                  <label className="avviso-checkbox-cell">
                                    <input
                                      type="checkbox"
                                      checked={isLinked}
                                      onChange={() => toggleLinkedAvviso(a.id)}
                                    />
                                    <span>{isLinked ? 'Si' : 'No'}</span>
                                  </label>
                                </td>
                                <td>
                                  <strong>{a.codice}</strong>
                                </td>
                                <td>{a.descrizione || 'Nessuna descrizione'}</td>
                                <td>
                                  <span className={`avviso-link-badge ${isLinked ? 'linked' : 'not-linked'}`}>
                                    {isLinked ? 'Collegato' : 'Disponibile'}
                                  </span>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    )}
                  </div>
                  <small className="help-text">Puoi selezionare più avvisi per lo stesso template piano finanziario.</small>
                </div>

                <div className="form-row">
                  <div className="form-group">
                    <label>Nuovo avviso (incrementale)</label>
                    <input
                      type="text"
                      value={newAvvisoCode}
                      onChange={(e) => setNewAvvisoCode(e.target.value)}
                      placeholder="Es: 10/2026"
                    />
                  </div>
                  <div className="form-group" style={{ display: 'flex', alignItems: 'flex-end' }}>
                    <button type="button" className="btn-secondary" onClick={handleCreateAvvisoInline}>
                      + Aggiungi Avviso
                    </button>
                  </div>
                </div>
                {avvisiError ? <span className="error-text">{avvisiError}</span> : null}

                {renderChiaveDocumentoField(true)}

                <div className="form-group">
                  <label>Note Fondo</label>
                  <textarea
                    value={noteFondo}
                    onChange={(e) => setNoteFondo(e.target.value)}
                    placeholder="Note specifiche su questo fondo / avviso (opzionale)..."
                    rows="2"
                  />
                </div>
              </div>

              {/* 3-PIANO: Macrovoci e Massimali */}
              <div className="form-section">
                <h3 className="section-title">📊 Macrovoci e Massimali</h3>
                <small className="help-text" style={{ display: 'block', marginBottom: '14px' }}>
                  Definisci i massimali percentuali sul totale preventivo per ogni macrovoce. Vengono usati come soglie di validazione nel piano.
                </small>

                <table className="piano-macrovoci-table">
                  <thead>
                    <tr>
                      <th style={{ width: '60px' }}>Macrovoce</th>
                      <th>Titolo</th>
                      <th style={{ width: '160px' }}>Massimale %</th>
                    </tr>
                  </thead>
                  <tbody>
                    {macrovoceConfig.map(m => (
                      <tr key={m.codice}>
                        <td className="piano-mv-codice"><strong>{m.codice}</strong></td>
                        <td>
                          <input
                            type="text"
                            value={m.titolo}
                            onChange={(e) => updateMacrovoce(m.codice, 'titolo', e.target.value)}
                            className="piano-titolo-input"
                          />
                        </td>
                        <td>
                          {m.solo_cofinanziamento ? (
                            <span className="badge-cofinanziamento">Solo cofinanziamento</span>
                          ) : (
                            <div className="piano-pct-input-row">
                              <input
                                type="number"
                                min="0"
                                max="100"
                                step="0.5"
                                value={m.massimale_pct ?? ''}
                                onChange={(e) => updateMacrovoce(m.codice, 'massimale_pct', e.target.value ? parseFloat(e.target.value) : null)}
                                className="piano-pct-input"
                              />
                              <span>%</span>
                            </div>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>

                <div className="form-group piano-c6-row">
                  <label>
                    Massimale C.6 – Costi generali (forfait)
                    <small style={{ fontWeight: 'normal', marginLeft: '6px' }}>% sul totale preventivo</small>
                  </label>
                  <div className="piano-pct-input-row">
                    <input
                      type="number"
                      min="0"
                      max="100"
                      step="0.5"
                      value={c6MaxPct}
                      onChange={(e) => setC6MaxPct(parseFloat(e.target.value) || 0)}
                      className="piano-pct-input"
                    />
                    <span>%</span>
                  </div>
                  <small className="help-text">Limite speciale per la voce C.6 – Costi generali e amministrativi (forfait).</small>
                </div>
              </div>

              {/* 4-PIANO: Voci di Piano */}
              <div className="form-section">
                <h3 className="section-title">📋 Voci di Piano</h3>
                <small className="help-text" style={{ display: 'block', marginBottom: '14px' }}>
                  Seleziona le voci incluse in questo template. Le voci deselezionate non verranno generate nel piano finanziario.
                  Le voci <strong>dinamiche</strong> (B.2 Docenza, B.3 Tutor) vengono create in multipli per ogni edizione.
                </small>

                <div className="piano-voci-grid">
                  {['A', 'B', 'C', 'D'].map(lettera => {
                    const macroInfo = macrovoceConfig.find(m => m.codice === lettera);
                    const voceList  = vociPerMacrovoce[lettera] || [];
                    const tutteSelezionate = voceList.every(v => vociIncluse.has(v.codice));
                    return (
                      <div key={lettera} className="piano-voci-gruppo">
                        <div className="piano-voci-gruppo-header">
                          <label className="piano-mv-select-all">
                            <input
                              type="checkbox"
                              checked={tutteSelezionate}
                              onChange={(e) => toggleAllVociMacrovoce(lettera, e.target.checked)}
                            />
                            <strong>Macrovoce {lettera}</strong>
                          </label>
                          <span className="piano-mv-titolo">— {macroInfo?.titolo}</span>
                          {macroInfo && !macroInfo.solo_cofinanziamento && macroInfo.massimale_pct != null && (
                            <span className="piano-mv-badge-pct">max {macroInfo.massimale_pct}%</span>
                          )}
                          {macroInfo?.solo_cofinanziamento && (
                            <span className="badge-cofinanziamento">cofinanziamento</span>
                          )}
                        </div>
                        <div className="piano-voci-lista">
                          {voceList.map(voce => (
                            <label key={voce.codice} className="piano-voce-check">
                              <input
                                type="checkbox"
                                checked={vociIncluse.has(voce.codice)}
                                onChange={() => toggleVoce(voce.codice)}
                              />
                              <span className="voce-codice">{voce.codice}</span>
                              <span className="voce-descr">{voce.descrizione}</span>
                              {voce.is_dynamic && <span className="badge-dynamic">dinamica</span>}
                            </label>
                          ))}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </>
          )}

          {/* ================================================================
              DOCUMENTI (preventivo, listino, timesheet, ordine, generico)
          ================================================================ */}
          {isDocScope && (
            <>
              {/* 2-DOC: Identificazione e scope */}
              <div className="form-section">
                <h3 className="section-title">🔑 Identificazione e Scope</h3>

                <div className="form-row">
                  {renderChiaveDocumentoField(true)}
                  <div className="form-group">
                    <label>Ente Applicabile</label>
                    <select value={enteAttuatoreId} onChange={(e) => setEnteAttuatoreId(e.target.value)}>
                      <option value="">Template globale</option>
                      {entiOptions.map(e => <option key={e.id} value={e.id}>{e.ragione_sociale}</option>)}
                    </select>
                  </div>
                </div>

                <div className="form-row">
                  <div className="form-group">
                    <label>Progetto Applicabile</label>
                    <select value={progettoId} onChange={(e) => setProgettoId(e.target.value)}>
                      <option value="">Tutti i progetti</option>
                      {progettiOptions.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                    </select>
                  </div>
                </div>
              </div>

              {/* 3-DOC: Contenuto HTML */}
              <div className="form-section">
                <h3 className="section-title">💻 Contenuto HTML</h3>

                <div className="form-group">
                  <label>Contenuto HTML <span className="required">*</span></label>
                  <textarea
                    id="contenuto-html-doc"
                    value={contenutoHtmlDoc}
                    onChange={(e) => setContenutoHtmlDoc(e.target.value)}
                    placeholder={`Inserisci il contenuto HTML per il template ${AMBITI_TEMPLATE.find(a => a.value === ambitoTemplate)?.label || ambitoTemplate}...`}
                    rows="15"
                    className={`code-editor ${errors.contenutoHtml ? 'error' : ''}`}
                  />
                  {errors.contenutoHtml && <span className="error-text">{errors.contenutoHtml}</span>}
                  <small className="help-text">Puoi usare le stesse variabili {`{{collaboratore_nome}}`} disponibili per i contratti.</small>
                </div>
              </div>
            </>
          )}

          {/* ── SEZIONE FINALE: STATO (tutti gli ambiti) ── */}
          <div className="form-section">
            <h3 className="section-title">⚙️ Stato Template</h3>
            <div className="checkbox-group">
              <label>
                <input type="checkbox" checked={isActive} onChange={(e) => setIsActive(e.target.checked)} />
                ✅ Template attivo
              </label>
            </div>
            <div className="form-group" style={{ marginTop: '12px' }}>
              <label>Note Interne</label>
              <textarea
                value={noteInterne}
                onChange={(e) => setNoteInterne(e.target.value)}
                placeholder="Note private per gli amministratori..."
                rows="2"
              />
            </div>
          </div>

        </div>{/* end modal-body */}

        {/* FOOTER */}
        <div className="modal-footer">
          <button className="btn-cancel" onClick={onClose}>Annulla</button>
          <button className="btn-primary" onClick={handleSubmit}>
            {template ? '💾 Salva Modifiche' : '➕ Crea Template'}
          </button>
        </div>

      </div>
    </div>
  );
};

export default ContractTemplateModal;
