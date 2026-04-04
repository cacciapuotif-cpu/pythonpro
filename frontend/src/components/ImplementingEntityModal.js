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
import './ImplementingEntityModal.css';

const ImplementingEntityModal = ({ entity, onClose, onSave }) => {
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
    { id: 'payment', title: 'Pagamento', icon: '💳' },
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
        iban: entity.iban || '',
        intestatario_conto: entity.intestatario_conto || '',
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

  /**
   * GESTISCE LA SELEZIONE DEL FILE LOGO
   */
  const handleLogoSelect = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    // Valida tipo file
    const allowedTypes = ['image/png', 'image/jpeg', 'image/jpg', 'image/svg+xml', 'image/gif'];
    if (!allowedTypes.includes(file.type)) {
      alert('Formato file non supportato. Usa PNG, JPG, SVG o GIF.');
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

    if (formData.iban && formData.iban.trim()) {
      const iban = formData.iban.replace(/\s/g, '');
      if (!/^IT\d{2}[A-Z]\d{10}[A-Z0-9]{12}$/.test(iban)) {
        newErrors.iban = 'IBAN italiano non valido (deve iniziare con IT e avere 27 caratteri)';
      }
    }

    if (formData.pec && formData.pec.trim() && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.pec)) {
      newErrors.pec = 'Formato PEC non valido';
    }

    if (formData.email && formData.email.trim() && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      newErrors.email = 'Formato email non valido';
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
        } else if (['pec', 'email', 'telefono', 'sdi'].includes(firstError)) {
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
          </div>
        );

      case 3: // Pagamento
        return (
          <div className="form-section">
            <div className="form-group">
              <label htmlFor="iban">IBAN</label>
              <input
                type="text"
                id="iban"
                name="iban"
                value={formData.iban}
                onChange={handleChange}
                placeholder="IT60 X054 2811 1010 0000 0123 456"
                maxLength="27"
                className={errors.iban ? 'error' : ''}
              />
              {errors.iban && <span className="error-text">{errors.iban}</span>}
            </div>

            <div className="form-group">
              <label htmlFor="intestatario_conto">Intestatario Conto</label>
              <input
                type="text"
                id="intestatario_conto"
                name="intestatario_conto"
                value={formData.intestatario_conto}
                onChange={handleChange}
                placeholder="Nome intestatario"
              />
            </div>
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
              <label>Logo o Carta Intestata Ente</label>
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
                      accept="image/png,image/jpeg,image/jpg,image/svg+xml,image/gif"
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
                      Formati: PNG, JPG, SVG, GIF • Max 5MB
                      <br />
                      Puoi usare un logo oppure un'immagine di carta intestata dell'ente
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

        {/* Indicatore sezioni */}
        <div className="sections-indicator">
          {sections.map((section, index) => (
            <div
              key={section.id}
              className={`section-step ${currentSection === index ? 'active' : ''} ${currentSection > index ? 'completed' : ''}`}
              onClick={handleSectionStepClick(index)}
            >
              <div className="step-icon">{section.icon}</div>
              <div className="step-title">{section.title}</div>
            </div>
          ))}
        </div>

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
      </div>
    </div>
  );
};

export default ImplementingEntityModal;
