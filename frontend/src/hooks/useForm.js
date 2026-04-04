import { useState, useCallback, useEffect } from 'react';

/**
 * Custom hook per gestione form generica
 * Gestisce form state, validazione, submit e reset
 */
const useForm = (initialValues = {}, onSubmit, validate) => {
  const [values, setValues] = useState(initialValues);
  const [errors, setErrors] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [touched, setTouched] = useState({});

  useEffect(() => {
    setValues(initialValues);
    setErrors({});
    setTouched({});
    setIsSubmitting(false);
  }, [initialValues]);

  // Gestisce cambio valori input
  const handleChange = useCallback((e) => {
    const { name, value, type, checked } = e.target;
    setValues(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));
  }, []);

  // Gestisce blur per mostrare errori solo dopo interazione
  const handleBlur = useCallback((e) => {
    const { name } = e.target;
    setTouched(prev => ({
      ...prev,
      [name]: true
    }));
  }, []);

  // Valida e submit del form
  const handleSubmit = useCallback(async (e) => {
    e.preventDefault();

    // Valida tutti i campi
    if (validate) {
      const validationErrors = validate(values);
      setErrors(validationErrors);

      // Se ci sono errori, non submitta
      if (Object.keys(validationErrors).length > 0) {
        // Marca tutti i campi come touched per mostrare errori
        const allTouched = Object.keys(values).reduce((acc, key) => {
          acc[key] = true;
          return acc;
        }, {});
        setTouched(allTouched);
        return;
      }
    }

    // Submit
    setIsSubmitting(true);
    try {
      await onSubmit(values);
    } catch (error) {
      console.error('Submit error:', error);
    } finally {
      setIsSubmitting(false);
    }
  }, [values, validate, onSubmit]);

  // Reset del form
  const reset = useCallback(() => {
    setValues(initialValues);
    setErrors({});
    setTouched({});
    setIsSubmitting(false);
  }, [initialValues]);

  // Imposta valori manualmente (per edit mode)
  const setFormValues = useCallback((newValues) => {
    setValues(newValues);
  }, []);

  // Imposta singolo valore
  const setValue = useCallback((name, value) => {
    setValues(prev => ({
      ...prev,
      [name]: value
    }));
  }, []);

  // Getter per sapere se un campo è valido
  const isFieldValid = useCallback((fieldName) => {
    return touched[fieldName] && !errors[fieldName];
  }, [touched, errors]);

  // Getter per sapere se un campo ha errori
  const hasFieldError = useCallback((fieldName) => {
    return touched[fieldName] && errors[fieldName];
  }, [touched, errors]);

  return {
    values,
    errors,
    touched,
    isSubmitting,
    handleChange,
    handleBlur,
    handleSubmit,
    reset,
    setValues: setFormValues,
    setValue,
    isFieldValid,
    hasFieldError
  };
};

export default useForm;
