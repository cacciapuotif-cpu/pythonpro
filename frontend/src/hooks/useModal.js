import { useState, useCallback } from 'react';

/**
 * Custom hook per gestione modale generica
 * Gestisce apertura/chiusura e dati associati al modale
 */
const useModal = (initialState = false) => {
  const [isOpen, setIsOpen] = useState(initialState);
  const [modalData, setModalData] = useState(null);

  // Apri modale
  const openModal = useCallback((data = null) => {
    setModalData(data);
    setIsOpen(true);
  }, []);

  // Chiudi modale
  const closeModal = useCallback(() => {
    setIsOpen(false);
    // Reset data dopo animazione chiusura
    setTimeout(() => setModalData(null), 300);
  }, []);

  // Toggle modale
  const toggleModal = useCallback(() => {
    setIsOpen(prev => !prev);
  }, []);

  return {
    isOpen,
    modalData,
    openModal,
    closeModal,
    toggleModal
  };
};

export default useModal;
