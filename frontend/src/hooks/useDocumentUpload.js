import { useState } from 'react';
import apiService from '../services/apiService';

/**
 * Custom hook per gestire upload documenti collaboratori
 * Gestisce upload, download e delete di documenti e curriculum
 */
const useDocumentUpload = (showSuccess, showError, refreshCollaborators) => {
  const [uploadingDocumento, setUploadingDocumento] = useState(false);
  const [uploadingCurriculum, setUploadingCurriculum] = useState(false);

  // Validazione file generica
  const validateFile = (file, allowedExtensions, maxSizeMB = 10) => {
    if (!file) {
      showError('Seleziona un file da caricare');
      return false;
    }

    // Validazione dimensione
    if (file.size > maxSizeMB * 1024 * 1024) {
      showError(`File troppo grande. Massimo ${maxSizeMB}MB`);
      return false;
    }

    // Validazione estensione
    const fileExtension = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
    if (!allowedExtensions.includes(fileExtension)) {
      showError(`Estensione non permessa. Permesse: ${allowedExtensions.join(', ')}`);
      return false;
    }

    return true;
  };

  // Upload Documento Identità
  const uploadDocumento = async (collaboratorId, file, dataScadenza = null) => {
    const allowedExtensions = ['.pdf', '.jpg', '.jpeg', '.png'];

    if (!validateFile(file, allowedExtensions)) {
      return;
    }

    try {
      setUploadingDocumento(true);
      await apiService.uploadDocumentoIdentita(collaboratorId, file, dataScadenza);
      showSuccess('Documento identità caricato con successo!');
      await refreshCollaborators();
    } catch (err) {
      console.error('Errore upload documento:', err);
      showError(err.response?.data?.detail || 'Errore nel caricamento del documento');
    } finally {
      setUploadingDocumento(false);
    }
  };

  // Upload Curriculum
  const uploadCurriculum = async (collaboratorId, file) => {
    const allowedExtensions = ['.pdf', '.doc', '.docx'];

    if (!validateFile(file, allowedExtensions)) {
      return;
    }

    try {
      setUploadingCurriculum(true);
      await apiService.uploadCurriculum(collaboratorId, file);
      showSuccess('Curriculum caricato con successo!');
      await refreshCollaborators();
    } catch (err) {
      console.error('Errore upload curriculum:', err);
      showError(err.response?.data?.detail || 'Errore nel caricamento del curriculum');
    } finally {
      setUploadingCurriculum(false);
    }
  };

  // Download Documento
  const downloadDocumento = async (collaboratorId, filename) => {
    try {
      const response = await apiService.downloadDocumentoIdentita(collaboratorId);

      // Sanitizza filename
      const safeFilename = (filename && filename !== 'null' && filename !== 'undefined')
        ? filename
        : `documento_identita_${collaboratorId}_${Date.now()}.pdf`;

      // Crea blob e download
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', safeFilename);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Errore download documento:', err);
      showError('Errore nel download del documento');
    }
  };

  const previewDocumento = async (collaboratorId, filename) => {
    const previewWindow = window.open('', '_blank');
    try {
      const response = await apiService.downloadDocumentoIdentita(collaboratorId);
      const extension = (filename || '').split('.').pop()?.toLowerCase();
      const fallbackType = extension === 'pdf'
        ? 'application/pdf'
        : ['jpg', 'jpeg'].includes(extension)
          ? 'image/jpeg'
          : extension === 'png'
            ? 'image/png'
            : 'application/octet-stream';
      const headerType = response.headers?.['content-type'];
      const contentType = !headerType || headerType === 'application/octet-stream'
        ? fallbackType
        : headerType;
      const blob = new Blob([response.data], { type: contentType });
      const url = window.URL.createObjectURL(blob);
      if (previewWindow) {
        previewWindow.location.href = url;
      } else {
        window.open(url, '_blank', 'noopener,noreferrer');
      }
      window.setTimeout(() => window.URL.revokeObjectURL(url), 60000);
    } catch (err) {
      if (previewWindow && !previewWindow.closed) {
        previewWindow.close();
      }
      console.error('Errore anteprima documento:', err);
      showError('Errore nell’anteprima del documento');
    }
  };

  // Download Curriculum
  const downloadCurriculum = async (collaboratorId, filename) => {
    try {
      const response = await apiService.downloadCurriculum(collaboratorId);

      // Sanitizza filename
      const safeFilename = (filename && filename !== 'null' && filename !== 'undefined')
        ? filename
        : `curriculum_${collaboratorId}_${Date.now()}.pdf`;

      // Crea blob e download
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', safeFilename);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Errore download curriculum:', err);
      showError('Errore nel download del curriculum');
    }
  };

  const previewCurriculum = async (collaboratorId, filename) => {
    const previewWindow = window.open('', '_blank');
    try {
      const response = await apiService.downloadCurriculum(collaboratorId);
      const extension = (filename || '').split('.').pop()?.toLowerCase();
      const fallbackType = extension === 'pdf'
        ? 'application/pdf'
        : 'application/octet-stream';
      const headerType = response.headers?.['content-type'];
      const contentType = !headerType || headerType === 'application/octet-stream'
        ? fallbackType
        : headerType;
      const blob = new Blob([response.data], { type: contentType });
      const url = window.URL.createObjectURL(blob);
      if (previewWindow) {
        previewWindow.location.href = url;
      } else {
        window.open(url, '_blank', 'noopener,noreferrer');
      }
      window.setTimeout(() => window.URL.revokeObjectURL(url), 60000);
    } catch (err) {
      if (previewWindow && !previewWindow.closed) {
        previewWindow.close();
      }
      console.error('Errore anteprima curriculum:', err);
      showError('Errore nell’anteprima del curriculum');
    }
  };

  // Delete Documento Identità
  const deleteDocumento = async (collaboratorId) => {
    try {
      await apiService.deleteDocumentoIdentita(collaboratorId);
      showSuccess('Documento identità eliminato con successo!');
      await refreshCollaborators();
    } catch (err) {
      console.error('Errore eliminazione documento:', err);
      showError("Errore nell'eliminazione del documento");
    }
  };

  // Delete Curriculum
  const deleteCurriculum = async (collaboratorId) => {
    try {
      await apiService.deleteCurriculum(collaboratorId);
      showSuccess('Curriculum eliminato con successo!');
      await refreshCollaborators();
    } catch (err) {
      console.error('Errore eliminazione curriculum:', err);
      showError("Errore nell'eliminazione del curriculum");
    }
  };

  return {
    uploadingDocumento,
    uploadingCurriculum,
    uploadDocumento,
    uploadCurriculum,
    downloadDocumento,
    previewDocumento,
    downloadCurriculum,
    previewCurriculum,
    deleteDocumento,
    deleteCurriculum
  };
};

export default useDocumentUpload;
