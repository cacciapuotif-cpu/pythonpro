import React, { useEffect, useMemo, useState } from 'react';
import useForm from '../../hooks/useForm';

const FORM_STEPS = [
  {
    id: 'identity',
    title: 'Identita',
    description: 'Dati principali per creare l anagrafica del collaboratore.',
    fields: ['first_name', 'last_name', 'email', 'fiscal_code', 'partita_iva', 'phone', 'position', 'is_agency', 'is_consultant'],
  },
  {
    id: 'profile',
    title: 'Profilo',
    description: 'Informazioni personali, professionali e canali utili a profilare il collaboratore.',
    fields: ['birthplace', 'birth_date', 'gender', 'city', 'address', 'education', 'profilo_professionale', 'competenze_principali', 'certificazioni', 'sito_web', 'portfolio_url', 'linkedin_url', 'facebook_url', 'instagram_url', 'tiktok_url'],
  },
  {
    id: 'documents',
    title: 'Documenti',
    description: 'Documentazione necessaria per operare e generare contratti.',
    fields: ['documento_identita_scadenza'],
  },
];

const defaultValues = {
  first_name: '',
  last_name: '',
  email: '',
  phone: '',
  position: '',
  partita_iva: '',
  birthplace: '',
  birth_date: '',
  gender: '',
  fiscal_code: '',
  city: '',
  address: '',
  education: '',
  profilo_professionale: '',
  competenze_principali: '',
  certificazioni: '',
  sito_web: '',
  portfolio_url: '',
  linkedin_url: '',
  facebook_url: '',
  instagram_url: '',
  tiktok_url: '',
  is_agency: false,
  is_consultant: false,
  documento_identita_scadenza: '',
  documento_identita_filename: '',
  curriculum_filename: '',
};

const asTrimmedString = (value) => `${value || ''}`.trim();

const getCompletedFieldsCount = (values) => {
  const fieldsToCount = [
    'first_name',
    'last_name',
    'email',
    'phone',
    'position',
    'partita_iva',
    'birthplace',
    'birth_date',
    'gender',
    'fiscal_code',
    'city',
    'address',
    'education',
    'profilo_professionale',
    'competenze_principali',
    'certificazioni',
    'sito_web',
    'portfolio_url',
    'linkedin_url',
    'facebook_url',
    'instagram_url',
    'tiktok_url',
    'documento_identita_scadenza',
  ];

  return fieldsToCount.filter((field) => `${values[field] || ''}`.trim() !== '').length;
};

const CollaboratorForm = ({
  initialData = null,
  onSubmit,
  onCancel,
  isLoading = false,
}) => {
  const [documentoIdentitaFile, setDocumentoIdentitaFile] = useState(null);
  const [curriculumFile, setCurriculumFile] = useState(null);
  const [activeStepIndex, setActiveStepIndex] = useState(0);

  const validate = (values) => {
    const errors = {};

    if (!asTrimmedString(values.first_name)) {
      errors.first_name = 'Il nome e obbligatorio';
    }

    if (!asTrimmedString(values.last_name)) {
      errors.last_name = 'Il cognome e obbligatorio';
    }

    if (!asTrimmedString(values.email)) {
      errors.email = "L'email e obbligatoria";
    } else {
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailRegex.test(values.email)) {
        errors.email = 'Formato email non valido';
      }
    }

    if (!asTrimmedString(values.fiscal_code)) {
      errors.fiscal_code = 'Il codice fiscale e obbligatorio';
    } else if (asTrimmedString(values.fiscal_code).length !== 16) {
      errors.fiscal_code = 'Il codice fiscale deve essere di 16 caratteri';
    }

    if (values.partita_iva && !/^\d{11}$/.test(asTrimmedString(values.partita_iva))) {
      errors.partita_iva = 'La partita IVA deve essere di 11 cifre';
    }

    if (values.is_agency && !asTrimmedString(values.partita_iva)) {
      errors.partita_iva = 'Per un collaboratore agenzia la partita IVA e obbligatoria';
    }

    return errors;
  };

  const handleFormSubmit = async (values) => {
    const collaboratorData = {
      ...values,
      birth_date: values.birth_date ? `${values.birth_date}T00:00:00Z` : null,
      documento_identita_scadenza: values.documento_identita_scadenza || null,
      fiscal_code: asTrimmedString(values.fiscal_code).toUpperCase(),
      partita_iva: asTrimmedString(values.partita_iva) || null,
      profilo_professionale: asTrimmedString(values.profilo_professionale) || null,
      competenze_principali: asTrimmedString(values.competenze_principali) || null,
      certificazioni: asTrimmedString(values.certificazioni) || null,
      sito_web: asTrimmedString(values.sito_web) || null,
      portfolio_url: asTrimmedString(values.portfolio_url) || null,
      linkedin_url: asTrimmedString(values.linkedin_url) || null,
      facebook_url: asTrimmedString(values.facebook_url) || null,
      instagram_url: asTrimmedString(values.instagram_url) || null,
      tiktok_url: asTrimmedString(values.tiktok_url) || null,
      documento_identita_file: documentoIdentitaFile,
      curriculum_file: curriculumFile,
    };

    await onSubmit(collaboratorData);
  };

  const initialFormValues = useMemo(
    () => ({ ...defaultValues, ...(initialData || {}) }),
    [initialData]
  );

  const {
    values,
    errors,
    handleChange,
    handleBlur,
    handleSubmit,
    hasFieldError,
  } = useForm(initialFormValues, handleFormSubmit, validate);

  useEffect(() => {
    setActiveStepIndex(0);
    setDocumentoIdentitaFile(null);
    setCurriculumFile(null);
  }, [initialData]);

  const isEditMode = !!initialData;

  const currentStep = FORM_STEPS[activeStepIndex];
  const totalFields = 24;
  const completedFields = getCompletedFieldsCount(values);
  const completionPercentage = Math.round((completedFields / totalFields) * 100);

  const stepErrors = useMemo(
    () => FORM_STEPS.map((step) => step.fields.filter((field) => errors[field]).length),
    [errors]
  );

  const documentStatus = useMemo(() => {
    if (documentoIdentitaFile) {
      return { tone: 'ok', label: `Nuovo documento: ${documentoIdentitaFile.name}` };
    }

    if (values.documento_identita_filename) {
      return { tone: 'info', label: `Documento presente: ${values.documento_identita_filename}` };
    }

    return { tone: 'warning', label: 'Documento identita non ancora caricato' };
  }, [documentoIdentitaFile, values.documento_identita_filename]);

  const curriculumStatus = useMemo(() => {
    if (curriculumFile) {
      return { tone: 'ok', label: `Nuovo CV: ${curriculumFile.name}` };
    }

    if (values.curriculum_filename) {
      return { tone: 'info', label: `CV presente: ${values.curriculum_filename}` };
    }

    return { tone: 'warning', label: 'Curriculum non ancora caricato' };
  }, [curriculumFile, values.curriculum_filename]);

  const agencyRequirementMissing = Boolean(values.is_agency) && !asTrimmedString(values.partita_iva);

  const goToStep = (index) => {
    if (index < 0 || index >= FORM_STEPS.length) {
      return;
    }

    setActiveStepIndex(index);
  };

  const handleNextStep = () => {
    if (activeStepIndex < FORM_STEPS.length - 1) {
      goToStep(activeStepIndex + 1);
    }
  };

  const handlePreviousStep = () => {
    if (activeStepIndex > 0) {
      goToStep(activeStepIndex - 1);
    }
  };

  return (
    <div className="form-section collaborator-wizard">
      <div className="wizard-header">
        <div>
          <span className="wizard-eyebrow">Wizard collaboratore</span>
          <h2>{isEditMode ? 'Modifica collaboratore' : 'Nuovo collaboratore'}</h2>
          <p>
            Compila il profilo in tre passaggi: identita, profilo amministrativo e documenti.
          </p>
        </div>
        <div className="wizard-progress-card">
          <span>Completamento</span>
          <strong>{completionPercentage}%</strong>
          <small>{completedFields} campi su {totalFields} compilati</small>
        </div>
      </div>

      <div className="wizard-layout">
        <aside className="wizard-sidebar">
          <ol className="wizard-steps">
            {FORM_STEPS.map((step, index) => {
              const isActive = index === activeStepIndex;
              const isDone = index < activeStepIndex;
              const hasErrors = stepErrors[index] > 0;

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
                      {hasErrors ? <em>{stepErrors[index]} campi da correggere</em> : null}
                    </span>
                  </button>
                </li>
              );
            })}
          </ol>

          <div className="wizard-summary-card">
            <h3>Checkpoint operativo</h3>
            <ul>
              <li className={values.first_name && values.last_name ? 'done' : ''}>
                Anagrafica base {values.first_name && values.last_name ? 'pronta' : 'da completare'}
              </li>
              <li className={values.email ? 'done' : ''}>
                Canale email {values.email ? 'presente' : 'mancante'}
              </li>
              <li className={values.fiscal_code ? 'done' : ''}>
                Codice fiscale {values.fiscal_code ? 'presente' : 'mancante'}
              </li>
              <li className={values.is_agency ? 'done' : ''}>
                Profilo agenzia {values.is_agency ? 'attivo' : 'non attivo'}
              </li>
              <li className={values.is_consultant ? 'done' : ''}>
                Profilo consulente {values.is_consultant ? 'attivo' : 'non attivo'}
              </li>
              <li className={values.documento_identita_scadenza ? 'done' : ''}>
                Scadenza documento {values.documento_identita_scadenza ? 'impostata' : 'non impostata'}
              </li>
              <li className={values.linkedin_url || values.portfolio_url ? 'done' : ''}>
                Presenza digitale {values.linkedin_url || values.portfolio_url ? 'profilata' : 'da arricchire'}
              </li>
            </ul>
          </div>
        </aside>

        <form onSubmit={handleSubmit} className="collaborator-form wizard-form">
          <div className="wizard-step-panel">
            <div className="wizard-step-header">
              <div>
                <span className="wizard-step-label">
                  Step {activeStepIndex + 1} di {FORM_STEPS.length}
                </span>
                <h3>{currentStep.title}</h3>
                <p>{currentStep.description}</p>
              </div>
            </div>

            {currentStep.id === 'identity' && (
              <div className="form-grid">
                {agencyRequirementMissing && (
                  <div className="wizard-alert-card agency-alert full-width">
                    <h4>Profilo agenzia selezionato: completa la Partita IVA</h4>
                    <p>
                      Se il collaboratore opera anche come <strong>agenzia</strong>, la
                      <strong> Partita IVA</strong> resta obbligatoria per avere un profilo commerciale coerente.
                    </p>
                  </div>
                )}

                <div className="form-group">
                  <label htmlFor="first_name">Nome *</label>
                  <input
                    type="text"
                    id="first_name"
                    name="first_name"
                    value={values.first_name}
                    onChange={handleChange}
                    onBlur={handleBlur}
                    placeholder="Inserisci il nome"
                    className={hasFieldError('first_name') ? 'error' : ''}
                    required
                  />
                  {hasFieldError('first_name') && <span className="error-text">{errors.first_name}</span>}
                </div>

                <div className="form-group">
                  <label htmlFor="last_name">Cognome *</label>
                  <input
                    type="text"
                    id="last_name"
                    name="last_name"
                    value={values.last_name}
                    onChange={handleChange}
                    onBlur={handleBlur}
                    placeholder="Inserisci il cognome"
                    className={hasFieldError('last_name') ? 'error' : ''}
                    required
                  />
                  {hasFieldError('last_name') && <span className="error-text">{errors.last_name}</span>}
                </div>

                <div className="form-group">
                  <label htmlFor="email">Email *</label>
                  <input
                    type="email"
                    id="email"
                    name="email"
                    value={values.email}
                    onChange={handleChange}
                    onBlur={handleBlur}
                    placeholder="esempio@email.com"
                    className={hasFieldError('email') ? 'error' : ''}
                    required
                  />
                  {hasFieldError('email') && <span className="error-text">{errors.email}</span>}
                </div>

                <div className="form-group">
                  <label htmlFor="phone">Telefono</label>
                  <input
                    type="tel"
                    id="phone"
                    name="phone"
                    value={values.phone}
                    onChange={handleChange}
                    onBlur={handleBlur}
                    placeholder="333-123-4567"
                  />
                </div>

                <div className="form-group">
                  <label>Ruoli commerciali</label>
                  <label className="checkbox-label">
                    <input
                      type="checkbox"
                      id="is_agency"
                      name="is_agency"
                      checked={Boolean(values.is_agency)}
                      onChange={(event) => handleChange({
                        target: {
                          name: 'is_agency',
                          value: event.target.checked,
                          type: 'checkbox',
                          checked: event.target.checked,
                        },
                      })}
                      onBlur={handleBlur}
                    />
                    {' '}Questo collaboratore opera anche come agenzia
                  </label>
                  <label className="checkbox-label">
                    <input
                      type="checkbox"
                      id="is_consultant"
                      name="is_consultant"
                      checked={Boolean(values.is_consultant)}
                      onChange={(event) => handleChange({
                        target: {
                          name: 'is_consultant',
                          value: event.target.checked,
                          type: 'checkbox',
                          checked: event.target.checked,
                        },
                      })}
                      onBlur={handleBlur}
                    />
                    {' '}Questo collaboratore opera anche come consulente
                  </label>
                </div>

                <div className="form-group">
                  <label htmlFor="position">Posizione lavorativa</label>
                  <input
                    type="text"
                    id="position"
                    name="position"
                    value={values.position}
                    onChange={handleChange}
                    onBlur={handleBlur}
                    placeholder="Es: formatore, tutor, project manager"
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="fiscal_code">Codice fiscale *</label>
                  <input
                    type="text"
                    id="fiscal_code"
                    name="fiscal_code"
                    value={values.fiscal_code}
                    onChange={handleChange}
                    onBlur={handleBlur}
                    placeholder="RSSMRA80A01H501Z"
                    maxLength="16"
                    style={{ textTransform: 'uppercase' }}
                    className={hasFieldError('fiscal_code') ? 'error' : ''}
                    required
                  />
                  {hasFieldError('fiscal_code') && <span className="error-text">{errors.fiscal_code}</span>}
                </div>

                <div className="form-group">
                  <label htmlFor="partita_iva">Partita IVA {values.is_agency ? '*' : ''}</label>
                  <input
                    type="text"
                    id="partita_iva"
                    name="partita_iva"
                    value={values.partita_iva}
                    onChange={handleChange}
                    onBlur={handleBlur}
                    placeholder="12345678901"
                    maxLength="11"
                    className={hasFieldError('partita_iva') ? 'error' : ''}
                  />
                  {hasFieldError('partita_iva') && <span className="error-text">{errors.partita_iva}</span>}
                </div>
              </div>
            )}

            {currentStep.id === 'profile' && (
              <div className="form-grid">
                <div className="form-group">
                  <label htmlFor="birthplace">Luogo di nascita</label>
                  <input
                    type="text"
                    id="birthplace"
                    name="birthplace"
                    value={values.birthplace}
                    onChange={handleChange}
                    onBlur={handleBlur}
                    placeholder="Es: Roma, Milano"
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="birth_date">Data di nascita</label>
                  <input
                    type="date"
                    id="birth_date"
                    name="birth_date"
                    value={values.birth_date}
                    onChange={handleChange}
                    onBlur={handleBlur}
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="gender">Sesso</label>
                  <select
                    id="gender"
                    name="gender"
                    value={values.gender}
                    onChange={handleChange}
                    onBlur={handleBlur}
                  >
                    <option value="">Seleziona sesso</option>
                    <option value="maschio">Maschio</option>
                    <option value="femmina">Femmina</option>
                  </select>
                </div>

                <div className="form-group">
                  <label htmlFor="education">Titolo di studio</label>
                  <select
                    id="education"
                    name="education"
                    value={values.education}
                    onChange={handleChange}
                    onBlur={handleBlur}
                  >
                    <option value="">Seleziona titolo di studio</option>
                    <option value="licenza media">Licenza media</option>
                    <option value="diploma">Diploma</option>
                    <option value="laurea">Laurea</option>
                    <option value="master">Master</option>
                  </select>
                </div>

                <div className="form-group">
                  <label htmlFor="city">Citta</label>
                  <input
                    type="text"
                    id="city"
                    name="city"
                    value={values.city}
                    onChange={handleChange}
                    onBlur={handleBlur}
                    placeholder="Comune di residenza"
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="address">Indirizzo</label>
                  <input
                    type="text"
                    id="address"
                    name="address"
                    value={values.address}
                    onChange={handleChange}
                    onBlur={handleBlur}
                    placeholder="Via Roma, 123"
                  />
                </div>

                <div className="form-group full-width">
                  <label htmlFor="profilo_professionale">Profilo professionale</label>
                  <textarea
                    id="profilo_professionale"
                    name="profilo_professionale"
                    value={values.profilo_professionale}
                    onChange={handleChange}
                    onBlur={handleBlur}
                    rows={3}
                    placeholder="Bio sintetica, seniority, ambiti di intervento, taglio operativo..."
                  />
                </div>

                <div className="form-group full-width">
                  <label htmlFor="competenze_principali">Competenze principali</label>
                  <textarea
                    id="competenze_principali"
                    name="competenze_principali"
                    value={values.competenze_principali}
                    onChange={handleChange}
                    onBlur={handleBlur}
                    rows={3}
                    placeholder="Formazione, docenza, tutoring, project management, digital marketing..."
                  />
                </div>

                <div className="form-group full-width">
                  <label htmlFor="certificazioni">Certificazioni / abilitazioni</label>
                  <textarea
                    id="certificazioni"
                    name="certificazioni"
                    value={values.certificazioni}
                    onChange={handleChange}
                    onBlur={handleBlur}
                    rows={2}
                    placeholder="Certificazioni tecniche, iscrizioni albo, patentini, credenziali..."
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="sito_web">Sito web</label>
                  <input
                    type="text"
                    id="sito_web"
                    name="sito_web"
                    value={values.sito_web}
                    onChange={handleChange}
                    onBlur={handleBlur}
                    placeholder="https://..."
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="portfolio_url">Portfolio / showcase</label>
                  <input
                    type="text"
                    id="portfolio_url"
                    name="portfolio_url"
                    value={values.portfolio_url}
                    onChange={handleChange}
                    onBlur={handleBlur}
                    placeholder="https://portfolio..."
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="linkedin_url">LinkedIn</label>
                  <input
                    type="text"
                    id="linkedin_url"
                    name="linkedin_url"
                    value={values.linkedin_url}
                    onChange={handleChange}
                    onBlur={handleBlur}
                    placeholder="https://linkedin.com/in/..."
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="facebook_url">Facebook</label>
                  <input
                    type="text"
                    id="facebook_url"
                    name="facebook_url"
                    value={values.facebook_url}
                    onChange={handleChange}
                    onBlur={handleBlur}
                    placeholder="https://facebook.com/..."
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="instagram_url">Instagram</label>
                  <input
                    type="text"
                    id="instagram_url"
                    name="instagram_url"
                    value={values.instagram_url}
                    onChange={handleChange}
                    onBlur={handleBlur}
                    placeholder="https://instagram.com/..."
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="tiktok_url">TikTok</label>
                  <input
                    type="text"
                    id="tiktok_url"
                    name="tiktok_url"
                    value={values.tiktok_url}
                    onChange={handleChange}
                    onBlur={handleBlur}
                    placeholder="https://tiktok.com/@..."
                  />
                </div>
              </div>
            )}

            {currentStep.id === 'documents' && (
              <div className="wizard-documents-grid">
                <div className="form-grid">
                  <div className="form-group">
                    <label htmlFor="documento_identita_scadenza">Scadenza documento identita</label>
                    <input
                      type="date"
                      id="documento_identita_scadenza"
                      name="documento_identita_scadenza"
                      value={values.documento_identita_scadenza}
                      onChange={handleChange}
                      onBlur={handleBlur}
                    />
                  </div>

                  <div className="wizard-hint-card">
                    <h4>Preflight documentale</h4>
                    <p>
                      Carica almeno documento identita e curriculum per ridurre blocchi su assegnazioni e contratti.
                    </p>
                  </div>
                </div>

                <div className="wizard-file-panels">
                  <div className="wizard-file-card">
                    <div className="wizard-file-header">
                      <div>
                        <h4>Documento identita</h4>
                        <p>PDF o immagine. Serve per anagrafica e controllo compliance.</p>
                      </div>
                      <span className={`wizard-status-pill ${documentStatus.tone}`}>{documentStatus.label}</span>
                    </div>
                    <input
                      type="file"
                      id="documento_identita_file"
                      name="documento_identita_file"
                      accept=".pdf,.jpg,.jpeg,.png"
                      onChange={(event) => setDocumentoIdentitaFile(event.target.files?.[0] || null)}
                    />
                  </div>

                  <div className="wizard-file-card">
                    <div className="wizard-file-header">
                      <div>
                        <h4>Curriculum vitae</h4>
                        <p>PDF o documento office. Utile per valutazioni e onboarding operativo.</p>
                      </div>
                      <span className={`wizard-status-pill ${curriculumStatus.tone}`}>{curriculumStatus.label}</span>
                    </div>
                    <input
                      type="file"
                      id="curriculum_file"
                      name="curriculum_file"
                      accept=".pdf,.doc,.docx"
                      onChange={(event) => setCurriculumFile(event.target.files?.[0] || null)}
                    />
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="form-buttons wizard-actions">
            <button type="button" onClick={onCancel} className="cancel-button" disabled={isLoading}>
              Annulla
            </button>

            <div className="wizard-actions-right">
              <button
                type="button"
                onClick={handlePreviousStep}
                className="secondary-button"
                disabled={isLoading || activeStepIndex === 0}
              >
                Indietro
              </button>

              {activeStepIndex < FORM_STEPS.length - 1 ? (
                <button
                  type="button"
                  onClick={handleNextStep}
                  className="submit-button"
                  disabled={isLoading || (currentStep.id === 'identity' && agencyRequirementMissing)}
                >
                  {currentStep.id === 'identity' && agencyRequirementMissing ? 'Completa P.IVA' : 'Continua'}
                </button>
              ) : (
                <button type="submit" className="submit-button" disabled={isLoading}>
                  {isLoading ? 'Salvataggio...' : isEditMode ? 'Aggiorna collaboratore' : 'Crea collaboratore'}
                </button>
              )}
            </div>
          </div>
        </form>
      </div>
    </div>
  );
};

export default CollaboratorForm;
