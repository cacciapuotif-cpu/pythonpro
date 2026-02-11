/**
 * MODAL PER CREARE/MODIFICARE TEMPLATE CONTRATTI
 *
 * Form completo per gestire tutti i campi di un template contratto:
 * - Dati base (nome, tipo, descrizione)
 * - Contenuto HTML con variabili
 * - Configurazione logo
 * - Clausole standard
 * - Formati e opzioni
 */

import React, { useState, useEffect } from 'react';
import './ContractTemplateModal.css';

// Costanti per le opzioni
const TIPI_CONTRATTO = [
  { value: 'professionale', label: '👔 Professionale' },
  { value: 'occasionale', label: '📝 Occasionale' },
  { value: 'ordine_servizio', label: '📋 Ordine di Servizio' },
  { value: 'contratto_progetto', label: '📄 Contratto a Progetto' }
];

const POSIZIONI_LOGO = [
  { value: 'header', label: 'Intestazione' },
  { value: 'footer', label: 'Piè di pagina' },
  { value: 'none', label: 'Nessuno' }
];

const DIMENSIONI_LOGO = [
  { value: 'small', label: 'Piccolo' },
  { value: 'medium', label: 'Medio' },
  { value: 'large', label: 'Grande' }
];

// Template HTML di esempio con variabili
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

  <p style="margin-top: 50px;">Data: {{data_oggi}}</p>

  <div style="display: flex; justify-content: space-between; margin-top: 50px;">
    <div>
      <p>____________________<br/>Firma Ente</p>
    </div>
    <div>
      <p>____________________<br/>Firma Collaboratore</p>
    </div>
  </div>
</div>`;

const ContractTemplateModal = ({ template, onClose, onSave }) => {
  // ==========================================
  // STATE MANAGEMENT
  // ==========================================

  // Dati base
  const [nomeTemplate, setNomeTemplate] = useState('');
  const [descrizione, setDescrizione] = useState('');
  const [tipoContratto, setTipoContratto] = useState('professionale');
  const [contenutoHtml, setContenutoHtml] = useState('');

  // Configurazione intestazione/piè di pagina
  const [intestazione, setIntestazione] = useState('');
  const [piePagina, setPiePagina] = useState('');

  // Configurazione logo
  const [includeLogoEnte, setIncludeLogoEnte] = useState(true);
  const [posizioneLogo, setPosizioneLogo] = useState('header');
  const [dimensioneLogo, setDimensioneLogo] = useState('medium');

  // Clausole standard
  const [includeClausolaPrivacy, setIncludeClausolaPrivacy] = useState(true);
  const [includeClausolaRiservatezza, setIncludeClausolaRiservatezza] = useState(false);
  const [includeClausolaProprietaIntellettuale, setIncludeClausolaProprietaIntellettuale] = useState(false);

  // Formati
  const [formatoData, setFormatoData] = useState('%d/%m/%Y');
  const [formatoImporto, setFormatoImporto] = useState('€ {:.2f}');

  // Opzioni
  const [isDefault, setIsDefault] = useState(false);
  const [isActive, setIsActive] = useState(true);
  const [versione, setVersione] = useState('1.0');
  const [noteInterne, setNoteInterne] = useState('');

  // Stati UI
  const [errors, setErrors] = useState({});
  const [showVariables, setShowVariables] = useState(false);
  const [uploadingFile, setUploadingFile] = useState(false);
  const [uploadError, setUploadError] = useState(null);

  // ==========================================
  // INIZIALIZZAZIONE DA TEMPLATE ESISTENTE
  // ==========================================

  useEffect(() => {
    if (template) {
      // Popolamento campi per modifica
      setNomeTemplate(template.nome_template || '');
      setDescrizione(template.descrizione || '');
      setTipoContratto(template.tipo_contratto || 'professionale');
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
      setIsDefault(template.is_default || false);
      setIsActive(template.is_active !== false);
      setVersione(template.versione || '1.0');
      setNoteInterne(template.note_interne || '');
    } else {
      // Nuovo template: usa l'esempio come default
      setContenutoHtml(TEMPLATE_HTML_ESEMPIO);
    }
  }, [template]);

  // ==========================================
  // VALIDAZIONE
  // ==========================================

  const validateForm = () => {
    const newErrors = {};

    if (!nomeTemplate.trim()) {
      newErrors.nomeTemplate = 'Il nome del template è obbligatorio';
    }

    if (!tipoContratto) {
      newErrors.tipoContratto = 'Il tipo di contratto è obbligatorio';
    }

    if (!contenutoHtml.trim()) {
      newErrors.contenutoHtml = 'Il contenuto HTML è obbligatorio';
    }

    if (!versione.trim()) {
      newErrors.versione = 'La versione è obbligatoria';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  // ==========================================
  // GESTIONE SALVATAGGIO
  // ==========================================

  const handleSubmit = () => {
    if (!validateForm()) {
      return;
    }

    const templateData = {
      nome_template: nomeTemplate.trim(),
      descrizione: descrizione.trim() || null,
      tipo_contratto: tipoContratto,
      contenuto_html: contenutoHtml.trim(),
      intestazione: intestazione.trim() || null,
      pie_pagina: piePagina.trim() || null,
      include_logo_ente: includeLogoEnte,
      posizione_logo: posizioneLogo,
      dimensione_logo: dimensioneLogo,
      include_clausola_privacy: includeClausolaPrivacy,
      include_clausola_riservatezza: includeClausolaRiservatezza,
      include_clausola_proprieta_intellettuale: includeClausolaProprietaIntellettuale,
      formato_data: formatoData,
      formato_importo: formatoImporto,
      is_default: isDefault,
      is_active: isActive,
      versione: versione.trim(),
      note_interne: noteInterne.trim() || null
    };

    onSave(templateData);
  };

  // ==========================================
  // UTILITY: INSERISCI VARIABILE NEL TESTO
  // ==========================================

  const insertVariable = (variable) => {
    const textarea = document.getElementById('contenuto-html');
    if (textarea) {
      const start = textarea.selectionStart;
      const end = textarea.selectionEnd;
      const text = contenutoHtml;
      const before = text.substring(0, start);
      const after = text.substring(end);
      const newText = before + `{{${variable}}}` + after;
      setContenutoHtml(newText);

      // Riposiziona il cursore dopo la variabile inserita
      setTimeout(() => {
        textarea.focus();
        textarea.setSelectionRange(start + variable.length + 4, start + variable.length + 4);
      }, 0);
    }
  };

  // ==========================================
  // GESTIONE UPLOAD FILE DOCX
  // ==========================================

  /**
   * GESTISCE L'UPLOAD E CONVERSIONE DI UN FILE DOCX
   */
  const handleFileUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    // Valida che sia un file DOCX
    if (!file.name.toLowerCase().endsWith('.docx')) {
      setUploadError('Il file deve essere in formato .docx');
      return;
    }

    setUploadingFile(true);
    setUploadError(null);

    try {
      // Crea FormData per l'upload
      const formData = new FormData();
      formData.append('file', file);

      // Chiama l'endpoint di conversione
      const apiUrl = process.env.REACT_APP_API_URL || 'http://localhost:8001';
      const response = await fetch(`${apiUrl}/api/v1/contracts/convert-docx-to-html`, {
        method: 'POST',
        body: formData
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Errore nella conversione del file');
      }

      const data = await response.json();

      // Imposta l'HTML convertito nel contenuto
      setContenutoHtml(data.html);

      // Se il nome del template è vuoto, usa il nome del file
      if (!nomeTemplate) {
        const fileName = file.name.replace('.docx', '');
        setNomeTemplate(fileName);
      }

      // Mostra eventuali messaggi dalla conversione
      if (data.messages && data.messages.length > 0) {
        console.log('Messaggi dalla conversione:', data.messages);
      }

    } catch (error) {
      console.error('Errore upload file:', error);
      setUploadError(error.message || 'Errore nel caricamento del file');
    } finally {
      setUploadingFile(false);
      // Reset input file
      event.target.value = '';
    }
  };

  // ==========================================
  // VARIABILI DISPONIBILI
  // ==========================================

  const variabiliDisponibili = [
    { categoria: 'Collaboratore', vars: [
      'collaboratore_nome',
      'collaboratore_cognome',
      'collaboratore_nome_completo',
      'collaboratore_email',
      'collaboratore_codice_fiscale',
      'collaboratore_telefono',
      'collaboratore_luogo_nascita',
      'collaboratore_data_nascita',
      'collaboratore_indirizzo',
      'collaboratore_citta'
    ]},
    { categoria: 'Ente Attuatore', vars: [
      'ente_ragione_sociale',
      'ente_forma_giuridica',
      'ente_piva',
      'ente_codice_fiscale',
      'ente_indirizzo_completo',
      'ente_pec',
      'ente_email',
      'ente_telefono',
      'ente_referente_nome_completo'
    ]},
    { categoria: 'Progetto', vars: [
      'progetto_nome',
      'progetto_descrizione',
      'progetto_cup',
      'progetto_data_inizio',
      'progetto_data_fine'
    ]},
    { categoria: 'Contratto', vars: [
      'mansione',
      'ore_previste',
      'tariffa_oraria',
      'compenso_totale',
      'data_inizio',
      'data_fine'
    ]},
    { categoria: 'Sistema', vars: [
      'data_oggi'
    ]}
  ];

  // ==========================================
  // RENDER
  // ==========================================

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="template-modal" onClick={(e) => e.stopPropagation()}>
        {/* HEADER */}
        <div className="modal-header">
          <h2>{template ? 'Modifica Template Contratto' : 'Nuovo Template Contratto'}</h2>
          <button className="close-button" onClick={onClose}>×</button>
        </div>

        {/* BODY */}
        <div className="modal-body">
          {/* SEZIONE 1: DATI BASE */}
          <div className="form-section">
            <h3 className="section-title">📋 Dati Base</h3>

            <div className="form-group">
              <label>
                Nome Template <span className="required">*</span>
              </label>
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
                placeholder="Breve descrizione del template..."
                rows="2"
              />
            </div>

            <div className="form-row">
              <div className="form-group">
                <label>
                  Tipo Contratto <span className="required">*</span>
                </label>
                <select
                  value={tipoContratto}
                  onChange={(e) => setTipoContratto(e.target.value)}
                  className={errors.tipoContratto ? 'error' : ''}
                >
                  {TIPI_CONTRATTO.map(tipo => (
                    <option key={tipo.value} value={tipo.value}>{tipo.label}</option>
                  ))}
                </select>
                {errors.tipoContratto && <span className="error-text">{errors.tipoContratto}</span>}
              </div>

              <div className="form-group">
                <label>
                  Versione <span className="required">*</span>
                </label>
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

          {/* SEZIONE 2: CONTENUTO HTML */}
          <div className="form-section">
            <div className="section-header">
              <h3 className="section-title">💻 Contenuto HTML</h3>
              <button
                type="button"
                className="btn-secondary btn-small"
                onClick={() => setShowVariables(!showVariables)}
              >
                {showVariables ? '🔽 Nascondi' : '📌 Mostra'} Variabili
              </button>
            </div>

            {/* AREA UPLOAD FILE DOCX */}
            <div className="upload-section">
              <label className="upload-label">
                📄 Carica un file DOCX
                <input
                  type="file"
                  accept=".docx"
                  onChange={handleFileUpload}
                  disabled={uploadingFile}
                  style={{ display: 'none' }}
                  id="docx-upload"
                />
              </label>
              <button
                type="button"
                className="btn-secondary btn-small"
                onClick={() => document.getElementById('docx-upload').click()}
                disabled={uploadingFile}
              >
                {uploadingFile ? '⏳ Caricamento...' : '📤 Carica DOCX'}
              </button>
              <small className="help-text">
                Carica un file Word (.docx) che verrà automaticamente convertito in HTML
              </small>
              {uploadError && (
                <div className="upload-error" style={{ color: 'red', marginTop: '5px' }}>
                  ⚠️ {uploadError}
                </div>
              )}
            </div>

            {showVariables && (
              <div className="variables-panel">
                <p className="variables-intro">
                  Clicca su una variabile per inserirla nel testo. Le variabili verranno sostituite con i valori reali durante la generazione del contratto.
                </p>
                {variabiliDisponibili.map(gruppo => (
                  <div key={gruppo.categoria} className="variable-group">
                    <h4>{gruppo.categoria}</h4>
                    <div className="variable-buttons">
                      {gruppo.vars.map(varName => (
                        <button
                          key={varName}
                          type="button"
                          className="variable-button"
                          onClick={() => insertVariable(varName)}
                          title={`Inserisci {{${varName}}}`}
                        >
                          {varName}
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}

            <div className="form-group">
              <label>
                Contenuto HTML <span className="required">*</span>
              </label>
              <textarea
                id="contenuto-html"
                value={contenutoHtml}
                onChange={(e) => setContenutoHtml(e.target.value)}
                placeholder="Inserisci qui il contenuto HTML del contratto..."
                rows="15"
                className={`code-editor ${errors.contenutoHtml ? 'error' : ''}`}
              />
              {errors.contenutoHtml && <span className="error-text">{errors.contenutoHtml}</span>}
              <small className="help-text">
                Usa variabili come {'{{collaboratore_nome}}'} che verranno sostituite con i dati reali.
              </small>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label>Intestazione (opzionale)</label>
                <textarea
                  value={intestazione}
                  onChange={(e) => setIntestazione(e.target.value)}
                  placeholder="HTML per l'intestazione..."
                  rows="3"
                />
              </div>

              <div className="form-group">
                <label>Piè di Pagina (opzionale)</label>
                <textarea
                  value={piePagina}
                  onChange={(e) => setPiePagina(e.target.value)}
                  placeholder="HTML per il piè di pagina..."
                  rows="3"
                />
              </div>
            </div>
          </div>

          {/* SEZIONE 3: CONFIGURAZIONE LOGO */}
          <div className="form-section">
            <h3 className="section-title">🖼️ Configurazione Logo</h3>

            <div className="checkbox-group">
              <label>
                <input
                  type="checkbox"
                  checked={includeLogoEnte}
                  onChange={(e) => setIncludeLogoEnte(e.target.checked)}
                />
                Includi logo ente attuatore nel contratto
              </label>
            </div>

            {includeLogoEnte && (
              <div className="form-row">
                <div className="form-group">
                  <label>Posizione Logo</label>
                  <select value={posizioneLogo} onChange={(e) => setPosizioneLogo(e.target.value)}>
                    {POSIZIONI_LOGO.map(pos => (
                      <option key={pos.value} value={pos.value}>{pos.label}</option>
                    ))}
                  </select>
                </div>

                <div className="form-group">
                  <label>Dimensione Logo</label>
                  <select value={dimensioneLogo} onChange={(e) => setDimensioneLogo(e.target.value)}>
                    {DIMENSIONI_LOGO.map(dim => (
                      <option key={dim.value} value={dim.value}>{dim.label}</option>
                    ))}
                  </select>
                </div>
              </div>
            )}
          </div>

          {/* SEZIONE 4: CLAUSOLE STANDARD */}
          <div className="form-section">
            <h3 className="section-title">📜 Clausole Standard</h3>

            <div className="checkbox-group">
              <label>
                <input
                  type="checkbox"
                  checked={includeClausolaPrivacy}
                  onChange={(e) => setIncludeClausolaPrivacy(e.target.checked)}
                />
                Includi clausola privacy (GDPR)
              </label>
            </div>

            <div className="checkbox-group">
              <label>
                <input
                  type="checkbox"
                  checked={includeClausolaRiservatezza}
                  onChange={(e) => setIncludeClausolaRiservatezza(e.target.checked)}
                />
                Includi clausola riservatezza
              </label>
            </div>

            <div className="checkbox-group">
              <label>
                <input
                  type="checkbox"
                  checked={includeClausolaProprietaIntellettuale}
                  onChange={(e) => setIncludeClausolaProprietaIntellettuale(e.target.checked)}
                />
                Includi clausola proprietà intellettuale
              </label>
            </div>
          </div>

          {/* SEZIONE 5: FORMATI E OPZIONI */}
          <div className="form-section">
            <h3 className="section-title">⚙️ Formati e Opzioni</h3>

            <div className="form-row">
              <div className="form-group">
                <label>Formato Data</label>
                <input
                  type="text"
                  value={formatoData}
                  onChange={(e) => setFormatoData(e.target.value)}
                  placeholder="%d/%m/%Y"
                />
                <small className="help-text">Python strftime format (es: %d/%m/%Y)</small>
              </div>

              <div className="form-group">
                <label>Formato Importo</label>
                <input
                  type="text"
                  value={formatoImporto}
                  onChange={(e) => setFormatoImporto(e.target.value)}
                  placeholder="€ {:.2f}"
                />
                <small className="help-text">Python format string (es: € {'{:.2f}'})</small>
              </div>
            </div>

            <div className="form-row">
              <div className="checkbox-group">
                <label>
                  <input
                    type="checkbox"
                    checked={isDefault}
                    onChange={(e) => setIsDefault(e.target.checked)}
                  />
                  ⭐ Imposta come template predefinito per questo tipo di contratto
                </label>
              </div>

              <div className="checkbox-group">
                <label>
                  <input
                    type="checkbox"
                    checked={isActive}
                    onChange={(e) => setIsActive(e.target.checked)}
                  />
                  ✅ Template attivo
                </label>
              </div>
            </div>

            <div className="form-group">
              <label>Note Interne</label>
              <textarea
                value={noteInterne}
                onChange={(e) => setNoteInterne(e.target.value)}
                placeholder="Note private per gli amministratori..."
                rows="2"
              />
            </div>
          </div>
        </div>

        {/* FOOTER */}
        <div className="modal-footer">
          <button className="btn-cancel" onClick={onClose}>
            Annulla
          </button>
          <button className="btn-primary" onClick={handleSubmit}>
            {template ? '💾 Salva Modifiche' : '➕ Crea Template'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default ContractTemplateModal;
