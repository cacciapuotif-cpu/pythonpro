/**
 * MODAL CREAZIONE/MODIFICA ENTE ATTUATORE
 *
 * Form completo per gestire tutti i dati di un ente attuatore:
 * - Dati legali (P.IVA, CF, forma giuridica, etc.)
 * - Sede legale (indirizzo, CAP, città, etc.)
 * - Contatti (PEC, email, telefono, SDI)
 * - Dati pagamento (IBAN, intestatario)
 * - Legale rappresentante (nome, cognome, nascita, residenza, CF)
 * - Note
 */

import React, { useState, useEffect, useCallback } from 'react';
import http from '../lib/http';
import apiService from '../services/apiService';
import useMobileLayout from '../hooks/useMobileLayout';
import DesktopOnlyNotice from './common/DesktopOnlyNotice';
import './ImplementingEntityModal.scss';

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

const cleanRelatedPayload = (value) => Object.fromEntries(
  Object.entries(value).map(([key, item]) => [key, item === '' ? null : item])
);

const ImplementingEntityModal = ({ entity, onClose, onSave, onChanged }) => {
  // MOB-4: profilo ente è Livello 3 (MOB-0 gate) — form completo, sedi,
  // conti, reveal IBAN, logo/carta intestata restano desktop-only.
  const isMobile = useMobileLayout();

  // ==========================================
  // STATE MANAGEMENT
  // ==========================================

  const [formData, setFormData] = useState({
    // Dati legali
    ragione_sociale: '',
    forma_giuridica: '',
    partita_iva: '',
    codice_fiscale: '',
    codice_ateco: '',
    rea_numero: '',
    registro_imprese: '',

    // Sede legale
    indirizzo: '',
    cap: '',
    citta: '',
    provincia: '',
    nazione: 'IT',

    // Contatti
    pec: '',
    email: '',
    telefono: '',
    sdi: '',
    sito_web: '',
    social_links: [],

    // Dati pagamento
    iban: '',
    intestatario_conto: '',

    // Legale rappresentante
    legale_rappresentante_nome: '',
    legale_rappresentante_cognome: '',
    legale_rappresentante_luogo_nascita: '',
    legale_rappresentante_data_nascita: '',
    legale_rappresentante_comune_residenza: '',
    legale_rappresentante_via_residenza: '',
    legale_rappresentante_codice_fiscale: '',

    // Altro
    note: '',
    is_active: true
  });

  const [errors, setErrors] = useState({});
  const [currentSection, setCurrentSection] = useState(0);
  const [logoFile, setLogoFile] = useState(null);
  const [logoPreview, setLogoPreview] = useState(null);
  const [uploadingLogo, setUploadingLogo] = useState(false);
  const [locations, setLocations] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [locationForm, setLocationForm] = useState(null);
  const [accountForm, setAccountForm] = useState(null);
  const [relatedBusy, setRelatedBusy] = useState(false);
  const [relatedError, setRelatedError] = useState('');

  const revokeObjectUrl = useCallback((url) => {
    if (url && url.startsWith('blob:')) {
      URL.revokeObjectURL(url);
    }
  }, []);

  const updateLogoPreview = useCallback((nextPreview) => {
    setLogoPreview((previousPreview) => {
      revokeObjectUrl(previousPreview);
      return nextPreview;
    });
  }, [revokeObjectUrl]);

  // Sezioni del form
  const sections = [
    { id: 'legal', title: 'Dati Legali', icon: '📋' },
    { id: 'address', title: 'Sede Legale', icon: '📍' },
    { id: 'contacts', title: 'Contatti', icon: '📧' },
    { id: 'payment', title: 'Conti correnti', icon: '💳' },
    { id: 'legalRepresentative', title: 'Legale Rappresentante', icon: '👤' },
    { id: 'notes', title: 'Note & Logo', icon: '📝' }
  ];

  // ==========================================
  // INIZIALIZZAZIONE
  // ==========================================

  useEffect(() => {
    let cancelled = false;

    const loadExistingLogoPreview = async (entityId) => {
      try {
        const response = await http.get(`/entities/${entityId}/download-logo`, {
          responseType: 'blob'
        });

        if (cancelled) {
          return;
        }

        const previewUrl = URL.createObjectURL(response.data);
        updateLogoPreview(previewUrl);
      } catch (error) {
        if (!cancelled) {
          updateLogoPreview(null);
        }
      }
    };

    if (entity) {
      // Popola il form con i dati dell'ente esistente
      setFormData({
        ragione_sociale: entity.ragione_sociale || '',
        forma_giuridica: entity.forma_giuridica || '',
        partita_iva: entity.partita_iva || '',
        codice_fiscale: entity.codice_fiscale || '',
        codice_ateco: entity.codice_ateco || '',
        rea_numero: entity.rea_numero || '',
        registro_imprese: entity.registro_imprese || '',
        indirizzo: entity.indirizzo || '',
        cap: entity.cap || '',
        citta: entity.citta || '',
        provincia: entity.provincia || '',
        nazione: entity.nazione || 'IT',
        pec: entity.pec || '',
        email: entity.email || '',
        telefono: entity.telefono || '',
        sdi: entity.sdi || '',
        sito_web: entity.sito_web || '',
        social_links: entity.social_links || [],
        iban: '',
        intestatario_conto: '',
        legale_rappresentante_nome: entity.legale_rappresentante_nome || '',
        legale_rappresentante_cognome: entity.legale_rappresentante_cognome || '',
        legale_rappresentante_luogo_nascita: entity.legale_rappresentante_luogo_nascita || '',
        legale_rappresentante_data_nascita: entity.legale_rappresentante_data_nascita
          ? entity.legale_rappresentante_data_nascita.split('T')[0]
          : '',
        legale_rappresentante_comune_residenza: entity.legale_rappresentante_comune_residenza || '',
        legale_rappresentante_via_residenza: entity.legale_rappresentante_via_residenza || '',
        legale_rappresentante_codice_fiscale: entity.legale_rappresentante_codice_fiscale || '',
        note: entity.note || '',
        is_active: entity.is_active ?? true
      });

      // Se l'ente ha già un'immagine intestazione/logo, imposta il preview
      if (entity.id && entity.logo_filename) {
        loadExistingLogoPreview(entity.id);
      } else {
        updateLogoPreview(null);
      }
    } else {
      updateLogoPreview(null);
    }

    return () => {
      cancelled = true;
    };
  }, [entity, updateLogoPreview]);

  const loadRelatedData = useCallback(async () => {
    if (!entity?.id) {
      setLocations([]);
      setAccounts([]);
      return;
    }
    setRelatedError('');
    try {
      const [locationRows, accountRows] = await Promise.all([
        apiService.getEntityLocations(entity.id),
        apiService.getEntityAccounts(entity.id),
      ]);
      setLocations(locationRows);
      setAccounts(accountRows);
    } catch (error) {
      setRelatedError(error.response?.data?.detail || 'Impossibile caricare sedi e conti correnti');
    }
  }, [entity?.id]);

  useEffect(() => {
    loadRelatedData();
  }, [loadRelatedData]);

  useEffect(() => {
    return () => {
      revokeObjectUrl(logoPreview);
    };
  }, [logoPreview, revokeObjectUrl]);

  // ==========================================
  // GESTIONE FORM
  // ==========================================

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));

    // Rimuovi errore quando l'utente modifica il campo
    if (errors[name]) {
      setErrors(prev => {
        const newErrors = { ...prev };
        delete newErrors[name];
        return newErrors;
      });
    }
  };

  const addSocialLink = () => {
    setFormData((current) => ({
      ...current,
      social_links: [...(current.social_links || []), { platform: 'LinkedIn', label: '', url: '' }],
    }));
  };

  const updateSocialLink = (index, field, value) => {
    setFormData((current) => ({
      ...current,
      social_links: current.social_links.map((link, linkIndex) => (
        linkIndex === index ? { ...link, [field]: value } : link
      )),
    }));
  };

  const removeSocialLink = (index) => {
    setFormData((current) => ({
      ...current,
      social_links: current.social_links.filter((_, linkIndex) => linkIndex !== index),
    }));
  };

  /**
   * GESTISCE LA SELEZIONE DEL FILE LOGO
   */
  const handleLogoSelect = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    // Valida tipo file
    const allowedTypes = ['image/png', 'image/jpeg', 'image/jpg', 'image/gif'];
    if (!allowedTypes.includes(file.type)) {
      alert('Formato file non supportato. Usa PNG, JPG o GIF.');
      return;
    }

    // Valida dimensione (max 5MB)
    if (file.size > 5 * 1024 * 1024) {
      alert('Il file è troppo grande. Dimensione massima: 5MB');
      return;
    }

    setLogoFile(file);

    // Crea preview
    const reader = new FileReader();
    reader.onloadend = () => {
      updateLogoPreview(reader.result);
    };
    reader.readAsDataURL(file);
  };

  const uploadLogoForEntity = async (entityId) => {
    if (!entityId || !logoFile) {
      return false;
    }

    setUploadingLogo(true);

    try {
      const uploadData = new FormData();
      uploadData.append('file', logoFile);

      await http.post(`/entities/${entityId}/upload-logo`, uploadData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      });
      setLogoFile(null);

      // Ricarica la preview dal backend passando dal client autenticato
      const previewResponse = await http.get(`/entities/${entityId}/download-logo`, {
        responseType: 'blob'
      });
      updateLogoPreview(URL.createObjectURL(previewResponse.data));
      return true;
    } catch (error) {
      console.error('Errore upload logo:', error);
      alert('Errore durante il caricamento dell\'immagine ente');
      return false;
    } finally {
      setUploadingLogo(false);
    }
  };

  /**
   * UPLOAD MANUALE DEL LOGO/INTESTAZIONE AL BACKEND
   */
  const handleLogoUpload = async () => {
    if (!entity || !entity.id || !logoFile) {
      alert('Seleziona prima un file immagine da caricare');
      return;
    }

    const uploaded = await uploadLogoForEntity(entity.id);
    if (uploaded) {
      alert('Immagine ente caricata con successo!');
    }
  };

  /**
   * ELIMINA IL LOGO
   */
  const handleLogoDelete = async () => {
    if (!entity || !entity.id || !entity.logo_filename) return;

    if (!window.confirm('Vuoi eliminare il logo?')) return;

    try {
      await http.delete(`/entities/${entity.id}/delete-logo`);

      alert('Immagine ente eliminata con successo!');
      updateLogoPreview(null);
      setLogoFile(null);
    } catch (error) {
      console.error('Errore eliminazione logo:', error);
      alert('Errore durante l\'eliminazione dell\'immagine ente');
    }
  };

  const runRelatedOperation = async (operation) => {
    setRelatedBusy(true);
    setRelatedError('');
    try {
      await operation();
      await loadRelatedData();
      await onChanged?.();
      return true;
    } catch (error) {
      setRelatedError(error.response?.data?.detail || 'Operazione non riuscita');
      return false;
    } finally {
      setRelatedBusy(false);
    }
  };

  const saveLocation = async () => {
    if (!entity?.id || !locationForm) return;
    const { id, ...payload } = locationForm;
    const saved = await runRelatedOperation(() => (
      id
        ? apiService.updateEntityLocation(entity.id, id, cleanRelatedPayload(payload))
        : apiService.createEntityLocation(entity.id, cleanRelatedPayload(payload))
    ));
    if (saved) setLocationForm(null);
  };

  const deactivateLocation = (locationId) => runRelatedOperation(
    () => apiService.deactivateEntityLocation(entity.id, locationId)
  );

  const saveAccount = async () => {
    if (!entity?.id || !accountForm) return;
    const { id, ...payload } = accountForm;
    if (id && !payload.iban) delete payload.iban;
    const saved = await runRelatedOperation(() => (
      id
        ? apiService.updateEntityAccount(entity.id, id, cleanRelatedPayload(payload))
        : apiService.createEntityAccount(entity.id, cleanRelatedPayload(payload))
    ));
    if (saved) setAccountForm(null);
  };

  const deactivateAccount = (accountId) => runRelatedOperation(
    () => apiService.deactivateEntityAccount(entity.id, accountId)
  );

  /**
   * VALIDA IL FORM
   */
  const validateForm = () => {
    const newErrors = {};

    // Campi obbligatori
    if (!formData.ragione_sociale.trim()) {
      newErrors.ragione_sociale = 'Ragione sociale obbligatoria';
    }

    if (!formData.partita_iva.trim()) {
      newErrors.partita_iva = 'Partita IVA obbligatoria';
    } else if (!/^\d{11}$/.test(formData.partita_iva.replace(/\s/g, ''))) {
      newErrors.partita_iva = 'Partita IVA deve essere di 11 cifre';
    }

    if (!formData.legale_rappresentante_nome.trim()) {
      newErrors.legale_rappresentante_nome = 'Il nome del legale rappresentante è obbligatorio';
    }

    if (!formData.legale_rappresentante_cognome.trim()) {
      newErrors.legale_rappresentante_cognome = 'Il cognome del legale rappresentante è obbligatorio';
    }

    if (!formData.legale_rappresentante_luogo_nascita.trim()) {
      newErrors.legale_rappresentante_luogo_nascita = 'Il luogo di nascita del legale rappresentante è obbligatorio';
    }

    if (!formData.legale_rappresentante_data_nascita) {
      newErrors.legale_rappresentante_data_nascita = 'La data di nascita del legale rappresentante è obbligatoria';
    }

    if (!formData.legale_rappresentante_comune_residenza.trim()) {
      newErrors.legale_rappresentante_comune_residenza = 'Il comune di residenza del legale rappresentante è obbligatorio';
    }

    if (!formData.legale_rappresentante_via_residenza.trim()) {
      newErrors.legale_rappresentante_via_residenza = 'La via di residenza del legale rappresentante è obbligatoria';
    }

    if (!formData.legale_rappresentante_codice_fiscale.trim()) {
      newErrors.legale_rappresentante_codice_fiscale = 'Il codice fiscale del legale rappresentante è obbligatorio';
    }

    // Validazioni opzionali ma con formato
    if (formData.codice_fiscale && formData.codice_fiscale.trim()) {
      const cf = formData.codice_fiscale.replace(/\s/g, '');
      if (!/^[A-Z0-9]{11,16}$/.test(cf)) {
        newErrors.codice_fiscale = 'Codice fiscale non valido';
      }
    }

    if (formData.cap && !/^\d{5}$/.test(formData.cap)) {
      newErrors.cap = 'CAP deve essere di 5 cifre';
    }

    if (formData.provincia && !/^[A-Z]{2}$/.test(formData.provincia.toUpperCase())) {
      newErrors.provincia = 'Provincia deve essere 2 lettere (es: NA, MI)';
    }

    if (formData.pec && formData.pec.trim() && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.pec)) {
      newErrors.pec = 'Formato PEC non valido';
    }

    if (formData.email && formData.email.trim() && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      newErrors.email = 'Formato email non valido';
    }

    if (formData.sito_web && !/^https?:\/\/[^\s/$.?#].[^\s]*$/i.test(formData.sito_web)) {
      newErrors.sito_web = 'Inserisci un URL completo http:// o https://';
    }

    const invalidSocial = (formData.social_links || []).find(
      (link) => !link.platform?.trim() || !/^https?:\/\/[^\s/$.?#].[^\s]*$/i.test(link.url || '')
    );
    if (invalidSocial) {
      newErrors.social_links = 'Ogni pagina social richiede piattaforma e URL completo';
    }

    if (
      formData.legale_rappresentante_codice_fiscale &&
      formData.legale_rappresentante_codice_fiscale.trim() &&
      !/^[A-Z0-9]{11,16}$/.test(formData.legale_rappresentante_codice_fiscale.replace(/\s/g, '').toUpperCase())
    ) {
      newErrors.legale_rappresentante_codice_fiscale = 'Codice fiscale legale rappresentante non valido';
    }

    setErrors(newErrors);
    return newErrors;
  };

  /**
   * GESTISCE L'INVIO DEL FORM
   */
  const handleSubmit = async (e) => {
    e.preventDefault();
    e.stopPropagation();

    if (currentSection < sections.length - 1) {
      nextSection();
      return;
    }

    const validationErrors = validateForm();
    if (Object.keys(validationErrors).length > 0) {
      alert(Object.values(validationErrors)[0]);

      // Vai alla sezione con il primo errore
      const errorFields = Object.keys(validationErrors);
      if (errorFields.length > 0) {
        const firstError = errorFields[0];
        if (['ragione_sociale', 'forma_giuridica', 'partita_iva', 'codice_fiscale', 'codice_ateco', 'rea_numero', 'registro_imprese'].includes(firstError)) {
          setCurrentSection(0);
        } else if (['indirizzo', 'cap', 'citta', 'provincia', 'nazione'].includes(firstError)) {
          setCurrentSection(1);
        } else if (['pec', 'email', 'telefono', 'sdi', 'sito_web', 'social_links'].includes(firstError)) {
          setCurrentSection(2);
        } else if (['iban', 'intestatario_conto'].includes(firstError)) {
          setCurrentSection(3);
        } else if (firstError.startsWith('legale_rappresentante_')) {
          setCurrentSection(4);
        }
      }
      return;
    }

    // Pulisci dati vuoti (invia null invece di stringhe vuote)
    const cleanData = { ...formData };
    Object.keys(cleanData).forEach(key => {
      if (cleanData[key] === '' && key !== 'ragione_sociale' && key !== 'partita_iva') {
        cleanData[key] = null;
      }
    });
    if (cleanData.legale_rappresentante_data_nascita) {
      cleanData.legale_rappresentante_data_nascita = `${cleanData.legale_rappresentante_data_nascita}T00:00:00Z`;
    }
    // I conti sono entità dedicate e gli IBAN non vengono mai rimandati dal
    // form anagrafico (la scheda li mostra mascherati).
    delete cleanData.iban;
    delete cleanData.intestatario_conto;

    try {
      const savedEntity = await onSave(cleanData);
      const targetEntityId = entity?.id || savedEntity?.id;
      const isCreatingNewEntity = !entity;
      let logoUploaded = false;

      if (targetEntityId && logoFile) {
        logoUploaded = await uploadLogoForEntity(targetEntityId);
      }

      if (logoUploaded) {
        alert('Ente salvato e immagine caricata con successo!');
      }

      if (isCreatingNewEntity && savedEntity?.id && !logoUploaded) {
        setCurrentSection(sections.length - 1);
      }

      // In modifica chiudi solo dopo che eventuale upload logo è terminato.
      // In creazione chiudi solo se anche il logo selezionato è stato caricato.
      if (!isCreatingNewEntity || (logoFile && logoUploaded)) {
        onClose();
      }
    } catch (error) {
      // Error handling is managed by the parent component notifications.
    }
  };

  const handleFormKeyDown = (e) => {
    if (e.key === 'Enter' && e.target.tagName !== 'TEXTAREA') {
      e.preventDefault();
    }
  };

  // ==========================================
  // NAVIGAZIONE SEZIONI
  // ==========================================

  const nextSection = () => {
    if (currentSection < sections.length - 1) {
      setCurrentSection(currentSection + 1);
    }
  };

  const prevSection = () => {
    if (currentSection > 0) {
      setCurrentSection(currentSection - 1);
    }
  };

  const handleOverlayClick = (e) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  const handleSectionStepClick = (index) => (e) => {
    e.preventDefault();
    e.stopPropagation();
    setCurrentSection(index);
  };

  const handleNextSectionClick = (e) => {
    e.preventDefault();
    e.stopPropagation();
    nextSection();
  };

  const handlePrevSectionClick = (e) => {
    e.preventDefault();
    e.stopPropagation();
    prevSection();
  };

  const renderLocationsManager = () => {
    if (!entity?.id) {
      return (
        <div className="info-message">
          Salva prima il nuovo ente; subito dopo potrai aggiungere tutte le sedi da questa stessa finestra.
        </div>
      );
    }

    return (
      <div className="entity-related-editor">
        <div className="related-editor-heading">
          <div>
            <h4>Sedi censite</h4>
            <p>Puoi aggiungere, modificare o disattivare le sedi senza uscire dalla modifica.</p>
          </div>
          <button
            type="button"
            className="btn-primary btn-small"
            onClick={() => setLocationForm({ ...EMPTY_LOCATION })}
          >
            Aggiungi sede
          </button>
        </div>
        {relatedError && <div className="alert alert-error">{relatedError}</div>}
        <div className="related-record-list">
          {locations.map((location) => (
            <article key={location.id} className={`related-record ${!location.is_active ? 'inactive' : ''}`}>
              <div>
                <strong>{location.denominazione}</strong>
                <span>{location.tipo}{location.is_principale ? ' · principale' : ''}{!location.is_active ? ' · dismessa' : ''}</span>
                <small>{location.indirizzo_completo || 'Indirizzo non indicato'}</small>
              </div>
              <div className="related-record-actions">
                <button type="button" className="btn-secondary btn-small" onClick={() => setLocationForm({ ...location })}>Modifica</button>
                {location.is_active && (
                  <button type="button" className="btn-danger btn-small" onClick={() => deactivateLocation(location.id)}>Disattiva</button>
                )}
              </div>
            </article>
          ))}
          {locations.length === 0 && <p className="related-empty">Nessuna sede censita.</p>}
        </div>
        {locationForm && (
          <div className="related-inline-form">
            <h4>{locationForm.id ? 'Modifica sede' : 'Nuova sede'}</h4>
            <div className="form-row">
              <div className="form-group">
                <label>Tipo</label>
                <select value={locationForm.tipo} onChange={(e) => setLocationForm({ ...locationForm, tipo: e.target.value })}>
                  <option value="legale">Legale</option>
                  <option value="operativa">Operativa</option>
                  <option value="amministrativa">Amministrativa</option>
                  <option value="accreditata">Accreditata</option>
                </select>
              </div>
              <div className="form-group">
                <label>Denominazione *</label>
                <input required value={locationForm.denominazione || ''} onChange={(e) => setLocationForm({ ...locationForm, denominazione: e.target.value })} />
              </div>
            </div>
            <div className="form-group">
              <label>Indirizzo</label>
              <input value={locationForm.indirizzo || ''} onChange={(e) => setLocationForm({ ...locationForm, indirizzo: e.target.value })} />
            </div>
            <div className="form-row">
              <div className="form-group"><label>CAP</label><input value={locationForm.cap || ''} onChange={(e) => setLocationForm({ ...locationForm, cap: e.target.value })} /></div>
              <div className="form-group"><label>Città</label><input value={locationForm.citta || ''} onChange={(e) => setLocationForm({ ...locationForm, citta: e.target.value })} /></div>
            </div>
            <div className="form-row">
              <div className="form-group"><label>Provincia</label><input maxLength="2" value={locationForm.provincia || ''} onChange={(e) => setLocationForm({ ...locationForm, provincia: e.target.value.toUpperCase() })} /></div>
              <div className="form-group"><label>Nazione</label><input maxLength="2" value={locationForm.nazione || 'IT'} onChange={(e) => setLocationForm({ ...locationForm, nazione: e.target.value.toUpperCase() })} /></div>
            </div>
            <div className="form-row">
              <div className="form-group"><label>Email</label><input type="email" value={locationForm.email || ''} onChange={(e) => setLocationForm({ ...locationForm, email: e.target.value })} /></div>
              <div className="form-group"><label>PEC</label><input type="email" value={locationForm.pec || ''} onChange={(e) => setLocationForm({ ...locationForm, pec: e.target.value })} /></div>
            </div>
            <div className="form-row">
              <div className="form-group"><label>Telefono</label><input value={locationForm.telefono || ''} onChange={(e) => setLocationForm({ ...locationForm, telefono: e.target.value })} /></div>
              <div className="form-group"><label>Attiva dal</label><input type="date" value={locationForm.attiva_dal || ''} onChange={(e) => setLocationForm({ ...locationForm, attiva_dal: e.target.value })} /></div>
            </div>
            {locationForm.tipo === 'accreditata' && (
              <>
                <div className="form-row">
                  <div className="form-group"><label>Ente accreditante</label><input value={locationForm.accreditamento_ente || ''} onChange={(e) => setLocationForm({ ...locationForm, accreditamento_ente: e.target.value })} /></div>
                  <div className="form-group"><label>Codice accreditamento</label><input value={locationForm.accreditamento_codice || ''} onChange={(e) => setLocationForm({ ...locationForm, accreditamento_codice: e.target.value })} /></div>
                </div>
                <div className="form-row">
                  <div className="form-group"><label>Data accreditamento</label><input type="date" value={locationForm.accreditamento_data || ''} onChange={(e) => setLocationForm({ ...locationForm, accreditamento_data: e.target.value })} /></div>
                  <div className="form-group"><label>Scadenza accreditamento</label><input type="date" value={locationForm.accreditamento_scadenza || ''} onChange={(e) => setLocationForm({ ...locationForm, accreditamento_scadenza: e.target.value })} /></div>
                </div>
              </>
            )}
            <div className="form-group checkbox-group">
              <label><input type="checkbox" checked={Boolean(locationForm.is_principale)} onChange={(e) => setLocationForm({ ...locationForm, is_principale: e.target.checked })} /> Sede principale</label>
            </div>
            <div className="related-record-actions">
              <button type="button" className="btn-secondary" onClick={() => setLocationForm(null)}>Annulla</button>
              <button type="button" className="btn-primary" disabled={relatedBusy || !locationForm.denominazione?.trim()} onClick={saveLocation}>Salva sede</button>
            </div>
          </div>
        )}
      </div>
    );
  };

  const renderAccountsManager = () => {
    if (!entity?.id) {
      return (
        <div className="info-message">
          Salva prima il nuovo ente; subito dopo potrai aggiungere i conti correnti da questa stessa finestra.
        </div>
      );
    }

    return (
      <div className="entity-related-editor">
        <div className="related-editor-heading">
          <div>
            <h4>Conti correnti</h4>
            <p>Gli IBAN restano mascherati. Per modificarne uno inserisci il nuovo valore; lasciandolo vuoto non cambia.</p>
          </div>
          <button
            type="button"
            className="btn-primary btn-small"
            onClick={() => setAccountForm({ ...EMPTY_ACCOUNT, intestatario: formData.ragione_sociale })}
          >
            Aggiungi conto
          </button>
        </div>
        {relatedError && <div className="alert alert-error">{relatedError}</div>}
        <div className="related-record-list">
          {accounts.map((account) => (
            <article key={account.id} className={`related-record ${!account.is_active ? 'inactive' : ''}`}>
              <div>
                <strong>{account.banca || 'Banca non indicata'}{account.agenzia ? ` · ${account.agenzia}` : ''}</strong>
                <span className="iban-value">{account.iban_masked || 'IBAN non disponibile'}</span>
                <small>{account.intestatario}{account.is_predefinito ? ' · predefinito' : ''}{!account.is_active ? ' · disattivato' : ''}</small>
              </div>
              <div className="related-record-actions">
                <button type="button" className="btn-secondary btn-small" onClick={() => setAccountForm({ ...account, iban: '' })}>Modifica</button>
                {account.is_active && (
                  <button type="button" className="btn-danger btn-small" onClick={() => deactivateAccount(account.id)}>Disattiva</button>
                )}
              </div>
            </article>
          ))}
          {accounts.length === 0 && <p className="related-empty">Nessun conto corrente censito.</p>}
        </div>
        {accountForm && (
          <div className="related-inline-form">
            <h4>{accountForm.id ? 'Modifica conto corrente' : 'Nuovo conto corrente'}</h4>
            <div className="form-row">
              <div className="form-group"><label>Banca</label><input value={accountForm.banca || ''} onChange={(e) => setAccountForm({ ...accountForm, banca: e.target.value })} /></div>
              <div className="form-group"><label>Agenzia</label><input value={accountForm.agenzia || ''} onChange={(e) => setAccountForm({ ...accountForm, agenzia: e.target.value })} /></div>
            </div>
            <div className="form-group">
              <label>IBAN {accountForm.id ? '(lascia vuoto per non cambiarlo)' : '*'}</label>
              <input required={!accountForm.id} value={accountForm.iban || ''} onChange={(e) => setAccountForm({ ...accountForm, iban: e.target.value.toUpperCase() })} />
            </div>
            <div className="form-row">
              <div className="form-group"><label>BIC/SWIFT</label><input value={accountForm.bic_swift || ''} onChange={(e) => setAccountForm({ ...accountForm, bic_swift: e.target.value.toUpperCase() })} /></div>
              <div className="form-group"><label>Intestatario *</label><input required value={accountForm.intestatario || ''} onChange={(e) => setAccountForm({ ...accountForm, intestatario: e.target.value })} /></div>
            </div>
            <div className="form-group"><label>Note conto</label><textarea value={accountForm.note || ''} onChange={(e) => setAccountForm({ ...accountForm, note: e.target.value })} /></div>
            <div className="form-group checkbox-group">
              <label><input type="checkbox" checked={Boolean(accountForm.is_predefinito)} onChange={(e) => setAccountForm({ ...accountForm, is_predefinito: e.target.checked })} /> Conto predefinito</label>
            </div>
            <div className="related-record-actions">
              <button type="button" className="btn-secondary" onClick={() => setAccountForm(null)}>Annulla</button>
              <button type="button" className="btn-primary" disabled={relatedBusy || (!accountForm.id && !accountForm.iban?.trim()) || !accountForm.intestatario?.trim()} onClick={saveAccount}>Salva conto</button>
            </div>
          </div>
        )}
      </div>
    );
  };

  // ==========================================
  // RENDER SEZIONI
  // ==========================================

  const renderSection = () => {
    switch (currentSection) {
      case 0: // Dati Legali
        return (
          <div className="form-section">
            <div className="form-group">
              <label htmlFor="ragione_sociale">
                Ragione Sociale <span className="required">*</span>
              </label>
              <input
                type="text"
                id="ragione_sociale"
                name="ragione_sociale"
                value={formData.ragione_sociale}
                onChange={handleChange}
                placeholder="es: piemmei scarl"
                className={errors.ragione_sociale ? 'error' : ''}
              />
              {errors.ragione_sociale && <span className="error-text">{errors.ragione_sociale}</span>}
            </div>

            <div className="form-group">
              <label htmlFor="forma_giuridica">Forma Giuridica</label>
              <select
                id="forma_giuridica"
                name="forma_giuridica"
                value={formData.forma_giuridica}
                onChange={handleChange}
              >
                <option value="">Seleziona...</option>
                <option value="S.r.l.">S.r.l.</option>
                <option value="S.c.a.r.l.">S.c.a.r.l.</option>
                <option value="S.p.A.">S.p.A.</option>
                <option value="S.n.c.">S.n.c.</option>
                <option value="S.a.s.">S.a.s.</option>
                <option value="Cooperativa">Cooperativa</option>
                <option value="Associazione">Associazione</option>
                <option value="Fondazione">Fondazione</option>
                <option value="Altro">Altro</option>
              </select>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label htmlFor="partita_iva">
                  Partita IVA <span className="required">*</span>
                </label>
                <input
                  type="text"
                  id="partita_iva"
                  name="partita_iva"
                  value={formData.partita_iva}
                  onChange={handleChange}
                  placeholder="11 cifre"
                  maxLength="11"
                  className={errors.partita_iva ? 'error' : ''}
                />
                {errors.partita_iva && <span className="error-text">{errors.partita_iva}</span>}
              </div>

              <div className="form-group">
                <label htmlFor="codice_fiscale">Codice Fiscale</label>
                <input
                  type="text"
                  id="codice_fiscale"
                  name="codice_fiscale"
                  value={formData.codice_fiscale}
                  onChange={handleChange}
                  placeholder="11 o 16 caratteri"
                  maxLength="16"
                  className={errors.codice_fiscale ? 'error' : ''}
                />
                {errors.codice_fiscale && <span className="error-text">{errors.codice_fiscale}</span>}
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label htmlFor="codice_ateco">Codice ATECO</label>
                <input
                  type="text"
                  id="codice_ateco"
                  name="codice_ateco"
                  value={formData.codice_ateco}
                  onChange={handleChange}
                  placeholder="es: 85.59.20"
                />
              </div>

              <div className="form-group">
                <label htmlFor="rea_numero">Numero REA</label>
                <input
                  type="text"
                  id="rea_numero"
                  name="rea_numero"
                  value={formData.rea_numero}
                  onChange={handleChange}
                  placeholder="es: NA-123456"
                />
              </div>
            </div>

            <div className="form-group">
              <label htmlFor="registro_imprese">Registro Imprese</label>
              <input
                type="text"
                id="registro_imprese"
                name="registro_imprese"
                value={formData.registro_imprese}
                onChange={handleChange}
                placeholder="es: Napoli"
              />
            </div>
          </div>
        );

      case 1: // Sede Legale
        return (
          <div className="form-section">
            <div className="form-group">
              <label htmlFor="indirizzo">Indirizzo</label>
              <input
                type="text"
                id="indirizzo"
                name="indirizzo"
                value={formData.indirizzo}
                onChange={handleChange}
                placeholder="Via/Piazza e numero civico"
              />
            </div>

            <div className="form-row">
              <div className="form-group">
                <label htmlFor="cap">CAP</label>
                <input
                  type="text"
                  id="cap"
                  name="cap"
                  value={formData.cap}
                  onChange={handleChange}
                  placeholder="5 cifre"
                  maxLength="5"
                  className={errors.cap ? 'error' : ''}
                />
                {errors.cap && <span className="error-text">{errors.cap}</span>}
              </div>

              <div className="form-group">
                <label htmlFor="citta">Città</label>
                <input
                  type="text"
                  id="citta"
                  name="citta"
                  value={formData.citta}
                  onChange={handleChange}
                  placeholder="es: Napoli"
                />
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label htmlFor="provincia">Provincia</label>
                <input
                  type="text"
                  id="provincia"
                  name="provincia"
                  value={formData.provincia}
                  onChange={handleChange}
                  placeholder="2 lettere (es: NA)"
                  maxLength="2"
                  className={errors.provincia ? 'error' : ''}
                />
                {errors.provincia && <span className="error-text">{errors.provincia}</span>}
              </div>

              <div className="form-group">
                <label htmlFor="nazione">Nazione</label>
                <input
                  type="text"
                  id="nazione"
                  name="nazione"
                  value={formData.nazione}
                  onChange={handleChange}
                  placeholder="Codice ISO (es: IT)"
                  maxLength="2"
                />
              </div>
            </div>
            <div className="related-editor-divider" />
            {renderLocationsManager()}
          </div>
        );

      case 2: // Contatti
        return (
          <div className="form-section">
            <div className="form-group">
              <label htmlFor="pec">PEC (Posta Elettronica Certificata)</label>
              <input
                type="email"
                id="pec"
                name="pec"
                value={formData.pec}
                onChange={handleChange}
                placeholder="es: ente@pec.it"
                className={errors.pec ? 'error' : ''}
              />
              {errors.pec && <span className="error-text">{errors.pec}</span>}
            </div>

            <div className="form-group">
              <label htmlFor="email">Email</label>
              <input
                type="email"
                id="email"
                name="email"
                value={formData.email}
                onChange={handleChange}
                placeholder="es: info@ente.it"
                className={errors.email ? 'error' : ''}
              />
              {errors.email && <span className="error-text">{errors.email}</span>}
            </div>

            <div className="form-row">
              <div className="form-group">
                <label htmlFor="telefono">Telefono</label>
                <input
                  type="tel"
                  id="telefono"
                  name="telefono"
                  value={formData.telefono}
                  onChange={handleChange}
                  placeholder="+39 081 1234567"
                />
              </div>

              <div className="form-group">
                <label htmlFor="sdi">Codice SDI</label>
                <input
                  type="text"
                  id="sdi"
                  name="sdi"
                  value={formData.sdi}
                  onChange={handleChange}
                  placeholder="7 caratteri"
                  maxLength="7"
                />
              </div>
            </div>

            <div className="form-group">
              <label htmlFor="sito_web">Sito web</label>
              <input
                type="url"
                id="sito_web"
                name="sito_web"
                value={formData.sito_web}
                onChange={handleChange}
                placeholder="https://www.ente.it"
                className={errors.sito_web ? 'error' : ''}
              />
              {errors.sito_web && <span className="error-text">{errors.sito_web}</span>}
            </div>

            <div className="form-group">
              <div className="social-links-heading">
                <label>Pagine social</label>
                <button type="button" className="btn-secondary btn-small" onClick={addSocialLink}>
                  Aggiungi pagina
                </button>
              </div>
              {(formData.social_links || []).map((link, index) => (
                <div className="form-row social-link-row" key={`social-${index}`}>
                  <input
                    aria-label={`Piattaforma social ${index + 1}`}
                    value={link.platform}
                    onChange={(e) => updateSocialLink(index, 'platform', e.target.value)}
                    placeholder="LinkedIn, Facebook, Instagram, YouTube, altro"
                  />
                  <input
                    type="url"
                    aria-label={`URL social ${index + 1}`}
                    value={link.url}
                    onChange={(e) => updateSocialLink(index, 'url', e.target.value)}
                    placeholder="https://..."
                  />
                  <button type="button" className="btn-danger btn-small" onClick={() => removeSocialLink(index)}>
                    Rimuovi
                  </button>
                </div>
              ))}
              {errors.social_links && <span className="error-text">{errors.social_links}</span>}
            </div>
          </div>
        );

      case 3: // Conti correnti
        return (
          <div className="form-section">
            {renderAccountsManager()}
          </div>
        );

      case 4: // Legale rappresentante
        return (
          <div className="form-section">
            <div className="form-row">
              <div className="form-group">
                <label htmlFor="legale_rappresentante_nome">Nome *</label>
                <input
                  type="text"
                  id="legale_rappresentante_nome"
                  name="legale_rappresentante_nome"
                  value={formData.legale_rappresentante_nome}
                  onChange={handleChange}
                  placeholder="Nome"
                  required
                  className={errors.legale_rappresentante_nome ? 'error' : ''}
                />
                {errors.legale_rappresentante_nome && <span className="error-text">{errors.legale_rappresentante_nome}</span>}
              </div>

              <div className="form-group">
                <label htmlFor="legale_rappresentante_cognome">Cognome *</label>
                <input
                  type="text"
                  id="legale_rappresentante_cognome"
                  name="legale_rappresentante_cognome"
                  value={formData.legale_rappresentante_cognome}
                  onChange={handleChange}
                  placeholder="Cognome"
                  required
                  className={errors.legale_rappresentante_cognome ? 'error' : ''}
                />
                {errors.legale_rappresentante_cognome && <span className="error-text">{errors.legale_rappresentante_cognome}</span>}
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label htmlFor="legale_rappresentante_luogo_nascita">Luogo di Nascita *</label>
                <input
                  type="text"
                  id="legale_rappresentante_luogo_nascita"
                  name="legale_rappresentante_luogo_nascita"
                  value={formData.legale_rappresentante_luogo_nascita}
                  onChange={handleChange}
                  placeholder="Es: Napoli"
                  required
                  className={errors.legale_rappresentante_luogo_nascita ? 'error' : ''}
                />
                {errors.legale_rappresentante_luogo_nascita && <span className="error-text">{errors.legale_rappresentante_luogo_nascita}</span>}
              </div>

              <div className="form-group">
                <label htmlFor="legale_rappresentante_data_nascita">Data di Nascita *</label>
                <input
                  type="date"
                  id="legale_rappresentante_data_nascita"
                  name="legale_rappresentante_data_nascita"
                  value={formData.legale_rappresentante_data_nascita}
                  onChange={handleChange}
                  required
                  className={errors.legale_rappresentante_data_nascita ? 'error' : ''}
                />
                {errors.legale_rappresentante_data_nascita && <span className="error-text">{errors.legale_rappresentante_data_nascita}</span>}
              </div>
            </div>

            <div className="form-group">
              <label htmlFor="legale_rappresentante_comune_residenza">Comune di Residenza *</label>
              <input
                type="text"
                id="legale_rappresentante_comune_residenza"
                name="legale_rappresentante_comune_residenza"
                value={formData.legale_rappresentante_comune_residenza}
                onChange={handleChange}
                placeholder="Es: Roma"
                required
                className={errors.legale_rappresentante_comune_residenza ? 'error' : ''}
              />
              {errors.legale_rappresentante_comune_residenza && <span className="error-text">{errors.legale_rappresentante_comune_residenza}</span>}
            </div>

            <div className="form-group">
              <label htmlFor="legale_rappresentante_via_residenza">Via di Residenza *</label>
              <input
                type="text"
                id="legale_rappresentante_via_residenza"
                name="legale_rappresentante_via_residenza"
                value={formData.legale_rappresentante_via_residenza}
                onChange={handleChange}
                placeholder="Es: Via Garibaldi 12"
                required
                className={errors.legale_rappresentante_via_residenza ? 'error' : ''}
              />
              {errors.legale_rappresentante_via_residenza && <span className="error-text">{errors.legale_rappresentante_via_residenza}</span>}
            </div>

            <div className="form-group">
              <label htmlFor="legale_rappresentante_codice_fiscale">Codice Fiscale *</label>
              <input
                type="text"
                id="legale_rappresentante_codice_fiscale"
                name="legale_rappresentante_codice_fiscale"
                value={formData.legale_rappresentante_codice_fiscale}
                onChange={handleChange}
                placeholder="11 o 16 caratteri"
                maxLength="16"
                className={errors.legale_rappresentante_codice_fiscale ? 'error' : ''}
              />
              {errors.legale_rappresentante_codice_fiscale && <span className="error-text">{errors.legale_rappresentante_codice_fiscale}</span>}
            </div>
          </div>
        );

      case 5: // Note e Logo
        return (
          <div className="form-section">
            <div className="form-group">
              <label htmlFor="note">Note</label>
              <textarea
                id="note"
                name="note"
                value={formData.note}
                onChange={handleChange}
                placeholder="Note aggiuntive sull'ente..."
                rows="6"
              />
            </div>

            {/* Upload Logo */}
            <div className="form-group">
              <label>Logo ente</label>
              <div className="logo-upload-container">
                {logoPreview && (
                  <div className="logo-preview">
                    <img src={logoPreview} alt="Immagine ente" />
                    {entity && entity.id && !logoFile && (
                      <button
                        type="button"
                        className="btn-danger btn-small"
                        onClick={handleLogoDelete}
                      >
                        🗑️ Elimina
                      </button>
                    )}
                  </div>
                )}

                {entity && entity.id ? (
                  <div className="logo-upload-controls">
                    <input
                      type="file"
                      accept="image/png,image/jpeg,image/jpg,image/gif"
                      onChange={handleLogoSelect}
                      id="logo-input"
                      style={{ display: 'none' }}
                    />
                    <label htmlFor="logo-input" className="btn-secondary">
                      📁 Seleziona Immagine
                    </label>

                    {logoFile && (
                      <button
                        type="button"
                        className="btn-primary"
                        onClick={handleLogoUpload}
                        disabled={uploadingLogo}
                      >
                        {uploadingLogo ? '⏳ Caricamento...' : '⬆️ Carica Immagine'}
                      </button>
                    )}

                    <small className="help-text">
                      Formati: PNG, JPG, GIF • Max 5MB
                      <br />
                      La carta intestata è un file indipendente e si gestisce dalla scheda completa.
                    </small>
                  </div>
                ) : (
                  <small className="help-text info-message">
                    💡 Se selezioni l'immagine ora, verrà caricata automaticamente quando crei l'ente
                  </small>
                )}
              </div>
            </div>

            <div className="form-group checkbox-group">
              <label>
                <input
                  type="checkbox"
                  name="is_active"
                  checked={formData.is_active}
                  onChange={handleChange}
                />
                <span>Ente attivo</span>
              </label>
            </div>
          </div>
        );

      default:
        return null;
    }
  };

  // ==========================================
  // RENDER PRINCIPALE
  // ==========================================

  return (
    <div className="modal-overlay" onClick={handleOverlayClick}>
      <div className="modal-content entity-modal" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="modal-header">
          <h2>
            {entity ? '✏️ Modifica Ente Attuatore' : '➕ Nuovo Ente Attuatore'}
          </h2>
          <button className="close-button" onClick={onClose}>✕</button>
        </div>

        {isMobile ? (
          <DesktopOnlyNotice
            title="Profilo ente: solo desktop"
            message="Form completo, sedi, conti correnti, IBAN e carta intestata si gestiscono da desktop."
          >
            {entity && (
              <>
                <strong>{entity.ragione_sociale}</strong>
                {entity.forma_giuridica && <div>{entity.forma_giuridica}</div>}
              </>
            )}
          </DesktopOnlyNotice>
        ) : (
          <>
            {/* Indicatore sezioni */}
            <nav className="sections-indicator" aria-label="Sezioni modifica ente">
              {sections.map((section, index) => (
                <button
                  type="button"
                  key={section.id}
                  className={`section-step ${currentSection === index ? 'active' : ''} ${currentSection > index ? 'completed' : ''}`}
                  onClick={handleSectionStepClick(index)}
                  aria-current={currentSection === index ? 'step' : undefined}
                >
                  <span className="step-icon" aria-hidden="true">{section.icon}</span>
                  <span className="step-title">{section.title}</span>
                </button>
              ))}
            </nav>

            {/* Form */}
            <form onSubmit={handleSubmit} onKeyDown={handleFormKeyDown}>
              <div className="modal-body">
                <h3 className="section-title">
                  {sections[currentSection].icon} {sections[currentSection].title}
                </h3>
                {renderSection()}
              </div>

              {/* Footer con navigazione */}
              <div className="modal-footer">
                <div className="navigation-buttons">
                  {currentSection > 0 && (
                    <button type="button" className="btn-secondary" onClick={handlePrevSectionClick}>
                      ← Indietro
                    </button>
                  )}

                  {currentSection < sections.length - 1 ? (
                    <button type="button" className="btn-primary" onClick={handleNextSectionClick}>
                      Avanti →
                    </button>
                  ) : (
                    <button type="submit" className="btn-success">
                      {entity ? '💾 Salva Modifiche' : '➕ Crea Ente'}
                    </button>
                  )}
                </div>

                <button type="button" className="btn-cancel" onClick={onClose}>
                  Annulla
                </button>
              </div>
            </form>
          </>
        )}
      </div>
    </div>
  );
};

export default ImplementingEntityModal;
