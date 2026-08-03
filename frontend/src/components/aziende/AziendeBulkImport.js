import React, { useState } from 'react';
import {
  downloadAziendaImportTemplate,
  executeAziendaImport,
  previewAziendaImport,
} from '../../services/apiService';
import '../collaborators/CollaboratorBulkImport.scss';

const saveBlob = (blob, filename, type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet') => {
  const url = URL.createObjectURL(blob instanceof Blob ? blob : new Blob([blob], { type }));
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
};

const csvCell = (value) => `"${String(value ?? '').replace(/"/g, '""')}"`;

export default function AziendeBulkImport({ onImported, onClose }) {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const downloadTemplate = async () => {
    setError('');
    try {
      saveBlob(await downloadAziendaImportTemplate(), 'template_aziende_clienti.xlsx');
    } catch (requestError) {
      setError(requestError?.response?.data?.detail || 'Download del template non riuscito');
    }
  };

  const handleFileChange = async (event) => {
    const selected = event.target.files?.[0];
    if (!selected) return;
    setFile(selected);
    setPreview(null);
    setResult(null);
    setError('');
    setLoading(true);
    try {
      setPreview(await previewAziendaImport(selected));
    } catch (requestError) {
      setError(requestError?.response?.data?.detail || 'Anteprima non disponibile: controlla il file Excel');
    } finally {
      setLoading(false);
    }
  };

  const executeImport = async () => {
    if (!file || !preview?.summary?.valid) return;
    setLoading(true);
    setError('');
    try {
      const imported = await executeAziendaImport(file);
      setResult(imported);
      if (onImported) await onImported(imported);
    } catch (requestError) {
      setError(requestError?.response?.data?.detail || 'Importazione non completata');
    } finally {
      setLoading(false);
    }
  };

  const downloadReport = () => {
    const rows = result?.report_rows || [];
    const csv = [
      ['Riga', 'Partita IVA', 'Ragione sociale', 'Esito', 'Messaggio'],
      ...rows.map((row) => [row.row, row.partita_iva, row.ragione_sociale, row.outcome, row.message]),
    ].map((row) => row.map(csvCell).join(';')).join('\n');
    saveBlob(new Blob([`\ufeff${csv}`], { type: 'text/csv;charset=utf-8' }), 'report_import_aziende.csv', 'text/csv;charset=utf-8');
  };

  return (
    <section className="bulk-import-container" aria-labelledby="aziende-import-title">
      <div className="bulk-import-header">
        <div>
          <h2 id="aziende-import-title">Importazione aziende da Excel</h2>
          <p>Anteprima obbligatoria, errori isolati per riga e aggiornamento tramite Partita IVA.</p>
        </div>
        <button className="close-button" onClick={onClose} disabled={loading} aria-label="Chiudi importazione">×</button>
      </div>

      <div className="info-box">
        <h3>Template multi-foglio</h3>
        <p>I fogli Aziende, Sedi, Conti e Fondi condividono la Partita IVA. Inserisci una riga per ogni sede o conto.</p>
        <button className="download-template-button" onClick={downloadTemplate} disabled={loading}>Scarica template Excel</button>
      </div>

      <div className="file-upload">
        <label htmlFor="aziende-file-input" className="file-label">
          {file ? `File: ${file.name}` : 'Seleziona file Excel (.xlsx)'}
        </label>
        <input id="aziende-file-input" type="file" accept=".xlsx,.xlsm" onChange={handleFileChange} disabled={loading} />
      </div>

      {loading && <p role="status">Elaborazione in corso…</p>}
      {error && <div className="errors-box" role="alert">{error}</div>}

      {preview && !result && (
        <div className="preview-section">
          <h3>Anteprima importazione</h3>
          <div className="azienda-import-summary" aria-label="Riepilogo anteprima">
            <div><strong>{preview.summary.create}</strong><span>da creare</span></div>
            <div><strong>{preview.summary.update}</strong><span>da aggiornare</span></div>
            <div><strong>{preview.summary.reject}</strong><span>da scartare</span></div>
          </div>
          {(preview.warnings || []).map((warning) => <p className="import-warning" key={warning}>{warning}</p>)}
          {preview.errors?.length > 0 && (
            <div className="errors-box">
              <h4>Errori rilevati</h4>
              <ul>{preview.errors.map((item, index) => (
                <li key={`${item.sheet}-${item.row}-${item.column}-${index}`}>
                  {item.sheet}, riga {item.row}, colonna {item.column}: {item.message}
                </li>
              ))}</ul>
            </div>
          )}
          <div className="preview-actions">
            <button className="cancel-button" onClick={onClose} disabled={loading}>Annulla</button>
            <button className="import-button" onClick={executeImport} disabled={loading || preview.summary.valid === 0}>
              Importa {preview.summary.valid} righe valide
            </button>
          </div>
        </div>
      )}

      {result && (
        <div className="import-result" role="status">
          <h3>Importazione completata</h3>
          <p>{result.created} create, {result.updated} aggiornate, {result.rejected} scartate.</p>
          <button className="download-template-button" onClick={downloadReport}>Scarica report esito CSV</button>
          <button className="btn-secondary" onClick={onClose}>Chiudi</button>
        </div>
      )}
    </section>
  );
}
