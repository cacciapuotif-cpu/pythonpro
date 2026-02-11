import React from 'react';
import useForm from '../../hooks/useForm';

/**
 * Form per creazione/modifica collaboratore
 * Componente controllato con validazione
 */
const CollaboratorForm = ({
  initialData = null,
  onSubmit,
  onCancel,
  isLoading = false
}) => {
  // Valori iniziali del form
  const defaultValues = {
    first_name: '',
    last_name: '',
    email: '',
    phone: '',
    position: '',
    birthplace: '',
    birth_date: '',
    gender: '',
    fiscal_code: '',
    city: '',
    address: '',
    education: ''
  };

  // Funzione di validazione
  const validate = (values) => {
    const errors = {};

    if (!values.first_name.trim()) {
      errors.first_name = 'Il nome è obbligatorio';
    }

    if (!values.last_name.trim()) {
      errors.last_name = 'Il cognome è obbligatorio';
    }

    if (!values.email.trim()) {
      errors.email = "L'email è obbligatoria";
    } else {
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailRegex.test(values.email)) {
        errors.email = 'Formato email non valido';
      }
    }

    if (!values.fiscal_code.trim()) {
      errors.fiscal_code = 'Il codice fiscale è obbligatorio';
    } else if (values.fiscal_code.trim().length !== 16) {
      errors.fiscal_code = 'Il codice fiscale deve essere di 16 caratteri';
    }

    return errors;
  };

  // Gestione submit
  const handleFormSubmit = async (values) => {
    const collaboratorData = {
      ...values,
      birth_date: values.birth_date ? `${values.birth_date}T00:00:00Z` : null
    };
    await onSubmit(collaboratorData);
  };

  // Hook form personalizzato
  const {
    values,
    errors,
    handleChange,
    handleBlur,
    handleSubmit,
    hasFieldError
  } = useForm(
    initialData || defaultValues,
    handleFormSubmit,
    validate
  );

  const isEditMode = !!initialData;

  return (
    <div className="form-section">
      <h2>{isEditMode ? '✏️ Modifica Collaboratore' : '➕ Nuovo Collaboratore'}</h2>

      <form onSubmit={handleSubmit} className="collaborator-form">
        <div className="form-grid">
          {/* Nome */}
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
            {hasFieldError('first_name') && (
              <span className="error-text">{errors.first_name}</span>
            )}
          </div>

          {/* Cognome */}
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
            {hasFieldError('last_name') && (
              <span className="error-text">{errors.last_name}</span>
            )}
          </div>

          {/* Email */}
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
            {hasFieldError('email') && (
              <span className="error-text">{errors.email}</span>
            )}
          </div>

          {/* Telefono */}
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

          {/* Posizione */}
          <div className="form-group">
            <label htmlFor="position">Posizione Lavorativa</label>
            <input
              type="text"
              id="position"
              name="position"
              value={values.position}
              onChange={handleChange}
              onBlur={handleBlur}
              placeholder="Es: Sviluppatore Senior, Project Manager"
            />
          </div>

          {/* Luogo di Nascita */}
          <div className="form-group">
            <label htmlFor="birthplace">Luogo di Nascita</label>
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

          {/* Data di Nascita */}
          <div className="form-group">
            <label htmlFor="birth_date">Data di Nascita</label>
            <input
              type="date"
              id="birth_date"
              name="birth_date"
              value={values.birth_date}
              onChange={handleChange}
              onBlur={handleBlur}
            />
          </div>

          {/* Sesso */}
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

          {/* Codice Fiscale */}
          <div className="form-group">
            <label htmlFor="fiscal_code">Codice Fiscale *</label>
            <input
              type="text"
              id="fiscal_code"
              name="fiscal_code"
              value={values.fiscal_code}
              onChange={handleChange}
              onBlur={handleBlur}
              placeholder="RSSMRA80A01H501Z"
              maxLength="16"
              style={{textTransform: 'uppercase'}}
              className={hasFieldError('fiscal_code') ? 'error' : ''}
              required
            />
            {hasFieldError('fiscal_code') && (
              <span className="error-text">{errors.fiscal_code}</span>
            )}
          </div>

          {/* Città */}
          <div className="form-group">
            <label htmlFor="city">Città</label>
            <input
              type="text"
              id="city"
              name="city"
              value={values.city}
              onChange={handleChange}
              onBlur={handleBlur}
              placeholder="Es: Roma, Milano"
            />
          </div>

          {/* Indirizzo */}
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

          {/* Titolo di Studio */}
          <div className="form-group">
            <label htmlFor="education">Titolo di Studio</label>
            <select
              id="education"
              name="education"
              value={values.education}
              onChange={handleChange}
              onBlur={handleBlur}
            >
              <option value="">Seleziona titolo di studio</option>
              <option value="licenza media">Licenza Media</option>
              <option value="diploma">Diploma</option>
              <option value="laurea">Laurea</option>
              <option value="master">Master</option>
            </select>
          </div>
        </div>

        {/* Pulsanti Form */}
        <div className="form-buttons">
          <button
            type="button"
            onClick={onCancel}
            className="cancel-button"
            disabled={isLoading}
          >
            Annulla
          </button>
          <button
            type="submit"
            className="submit-button"
            disabled={isLoading}
          >
            {isLoading ? '⏳ Salvando...' : (isEditMode ? '✏️ Aggiorna' : '➕ Aggiungi')}
          </button>
        </div>
      </form>
    </div>
  );
};

export default CollaboratorForm;
