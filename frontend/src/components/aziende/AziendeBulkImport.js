import React, { useState } from 'react';
import * as XLSX from 'xlsx';
import '../collaborators/CollaboratorBulkImport.css';

const COLUMN_MAPPING = {
  'Ragione Sociale': 'ragione_sociale',
  'Partita IVA': 'partita_iva',
  'Codice Fiscale': 'codice_fiscale',
  'Settore ATECO': 'settore_ateco',
  'Attività Erogate': 'attivita_erogate',
  'Indirizzo Sede Legale': 'indirizzo',
  Città: 'citta',
  CAP: 'cap',
  Provincia: 'provincia',
  Email: 'email',
  PEC: 'pec',
  Telefono: 'telefono',
  'Sito Web': 'sito_web',
  'Sedi Operative': 'sedi_operative_raw',
  Note: 'note',
};

const parseSediOperative = (rawValue) => {
  if (!rawValue) return [];
  return rawValue
    .split(';')
    .map((chunk) => chunk.trim())
    .filter(Boolean)
    .map((chunk) => {
      const [nome = '', indirizzo = '', citta = '', cap = '', provincia = '', note = ''] = chunk.split('|').map((value) => value.trim());
      return { nome, indirizzo, citta, cap, provincia, note };
    });
};

export default function AziendeBulkImport({ onImport, onClose, isLoading }) {
  const [file, setFile] = useState(null);
  const [parsedData, setParsedData] = useState([]);
  const [errors, setErrors] = useState([]);
  const [step, setStep] = useState(1);

  const validateRow = (row, rowIndex) => {
    const rowErrors = [];
    if (!row.ragione_sociale?.trim()) rowErrors.push(`Riga ${rowIndex}: Ragione Sociale obbligatoria`);
    if (!row.partita_iva?.trim()) rowErrors.push(`Riga ${rowIndex}: Partita IVA obbligatoria`);
    if (row.partita_iva && !/^\d{11}$/.test(row.partita_iva)) rowErrors.push(`Riga ${rowIndex}: Partita IVA non valida`);
    if (row.cap && !/^\d{5}$/.test(row.cap)) rowErrors.push(`Riga ${rowIndex}: CAP sede legale non valido`);
    if (row.provincia && !/^[A-Za-z]{2}$/.test(row.provincia)) rowErrors.push(`Riga ${rowIndex}: Provincia sede legale non valida`);
    if (row.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(row.email)) rowErrors.push(`Riga ${rowIndex}: Email non valida`);
    if (row.pec && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(row.pec)) rowErrors.push(`Riga ${rowIndex}: PEC non valida`);

    (row.sedi_operative || []).forEach((sede, index) => {
      if (!sede.nome?.trim()) rowErrors.push(`Riga ${rowIndex}: la sede operativa ${index + 1} richiede un nome`);
      if (sede.cap && !/^\d{5}$/.test(sede.cap)) rowErrors.push(`Riga ${rowIndex}: CAP non valido nella sede operativa ${sede.nome || index + 1}`);
      if (sede.provincia && !/^[A-Za-z]{2}$/.test(sede.provincia)) rowErrors.push(`Riga ${rowIndex}: Provincia non valida nella sede operativa ${sede.nome || index + 1}`);
    });

    return rowErrors;
  };

  const parseFile = (selectedFile) => {
    const reader = new FileReader();
    reader.onload = (event) => {
      try {
        const data = new Uint8Array(event.target.result);
        const workbook = XLSX.read(data, { type: 'array' });
        const worksheet = workbook.Sheets[workbook.SheetNames[0]];
        const jsonData = XLSX.utils.sheet_to_json(worksheet, { defval: '' });

        if (jsonData.length === 0) {
          setErrors(['Il file Excel è vuoto']);
          return;
        }

        const mappedRows = [];
        const validationErrors = [];

        jsonData.forEach((excelRow, index) => {
          const row = {};
          Object.entries(COLUMN_MAPPING).forEach(([column, field]) => {
            const value = excelRow[column];
            if (value === undefined || value === null || value === '') return;
            if (field === 'partita_iva') row[field] = value.toString().replace(/\s+/g, '').replace(/^IT/i, '');
            else if (field === 'email' || field === 'pec') row[field] = value.toString().trim().toLowerCase();
            else if (field === 'provincia') row[field] = value.toString().trim().toUpperCase();
            else if (field === 'sedi_operative_raw') row.sedi_operative = parseSediOperative(value.toString());
            else row[field] = value.toString().trim();
          });

          if (!row.sedi_operative) row.sedi_operative = [];
          validationErrors.push(...validateRow(row, index + 2));
          mappedRows.push({
            ...row,
            project_ids: [],
            fund_memberships: [],
            attivo: true,
          });
        });

        setParsedData(mappedRows);
        setErrors(validationErrors);
        if (validationErrors.length === 0) {
          setStep(2);
        }
      } catch (error) {
        setErrors([`Errore durante la lettura del file: ${error.message}`]);
      }
    };
    reader.readAsArrayBuffer(selectedFile);
  };

  const handleFileChange = (event) => {
    const selectedFile = event.target.files[0];
    if (!selectedFile) return;
    setFile(selectedFile);
    setErrors([]);
    parseFile(selectedFile);
  };

  const handleImport = async () => {
    await onImport(parsedData.map((row) => ({
      ...row,
      codice_fiscale: row.codice_fiscale || null,
      settore_ateco: row.settore_ateco || null,
      attivita_erogate: row.attivita_erogate || null,
      indirizzo: row.indirizzo || null,
      citta: row.citta || null,
      cap: row.cap || null,
      provincia: row.provincia || null,
      email: row.email || null,
      pec: row.pec || null,
      telefono: row.telefono || null,
      sito_web: row.sito_web || null,
      note: row.note || null,
      sedi_operative: (row.sedi_operative || []).map((sede) => ({
        nome: sede.nome,
        indirizzo: sede.indirizzo || null,
        citta: sede.citta || null,
        cap: sede.cap || null,
        provincia: sede.provincia ? sede.provincia.toUpperCase() : null,
        note: sede.note || null,
      })),
    })));
    setStep(3);
  };

  const resetImport = () => {
    setFile(null);
    setParsedData([]);
    setErrors([]);
    setStep(1);
  };

  const downloadTemplate = () => {
    const ws = XLSX.utils.json_to_sheet([{
      'Ragione Sociale': 'Azienda Demo Srl',
      'Partita IVA': '12345678901',
      'Codice Fiscale': '12345678901',
      'Settore ATECO': '85.59',
      'Attività Erogate': 'Formazione finanziata e consulenza',
      'Indirizzo Sede Legale': 'Via Roma 1',
      Città: 'Napoli',
      CAP: '80100',
      Provincia: 'NA',
      Email: 'info@aziendademo.it',
      PEC: 'aziendademo@pec.it',
      Telefono: '0811234567',
      'Sito Web': 'https://aziendademo.it',
      'Sedi Operative': 'Sede Napoli Centro|Via Toledo 10|Napoli|80134|NA|Reception 2 piano;Sede Caserta|Viale Europa 5|Caserta|81100|CE|Area aule',
      Note: 'Import demo',
    }]);
    ws['!cols'] = Object.keys(COLUMN_MAPPING).map(() => ({ wch: 24 }));
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, 'Aziende');
    XLSX.writeFile(wb, 'template_aziende_clienti.xlsx');
  };

  return (
    <div className="bulk-import-container">
      <div className="bulk-import-header">
        <h2>📥 Importazione Massiva Aziende Clienti</h2>
        <button className="close-button" onClick={onClose} disabled={isLoading}>❌</button>
      </div>

      {step === 1 && (
        <div className="upload-section">
          <div className="info-box">
            <h3>ℹ️ Istruzioni</h3>
            <p>Carica un file Excel o CSV con le aziende clienti.</p>
            <p><strong>Campi obbligatori:</strong> Ragione Sociale, Partita IVA</p>
            <p><strong>Sedi Operative:</strong> usa il formato `nome|indirizzo|città|cap|provincia|note`, separando più sedi con `;`.</p>
          </div>
          <button className="download-template-button" onClick={downloadTemplate}>📄 Scarica Template Excel</button>
          <div className="file-upload">
            <label htmlFor="aziende-file-input" className="file-label">
              {file ? `📎 ${file.name}` : '📁 Seleziona File Excel'}
            </label>
            <input id="aziende-file-input" type="file" accept=".xlsx,.xls,.csv" onChange={handleFileChange} disabled={isLoading} />
          </div>
          {errors.length > 0 && (
            <div className="errors-box">
              <h4>⚠️ Errori di Validazione</h4>
              <ul>{errors.map((error, index) => <li key={index}>{error}</li>)}</ul>
              <button className="retry-button" onClick={resetImport}>🔄 Riprova</button>
            </div>
          )}
        </div>
      )}

      {step === 2 && (
        <div className="preview-section">
          <div className="preview-header">
            <h3>👀 Anteprima Dati ({parsedData.length} aziende)</h3>
            <button className="change-file-button" onClick={resetImport} disabled={isLoading}>🔄 Cambia File</button>
          </div>
          <div className="preview-table-container">
            <table className="preview-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Ragione Sociale</th>
                  <th>P.IVA</th>
                  <th>Città</th>
                  <th>Sedi Operative</th>
                </tr>
              </thead>
              <tbody>
                {parsedData.map((row, index) => (
                  <tr key={index}>
                    <td>{index + 1}</td>
                    <td>{row.ragione_sociale}</td>
                    <td>{row.partita_iva}</td>
                    <td>{row.citta || '-'}</td>
                    <td>{row.sedi_operative.length > 0 ? row.sedi_operative.map((sede) => sede.nome).join(', ') : '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="preview-actions">
            <button className="cancel-button" onClick={onClose} disabled={isLoading}>Annulla</button>
            <button className="import-button" onClick={handleImport} disabled={isLoading || parsedData.length === 0}>
              {isLoading ? '⏳ Importazione in corso...' : `✅ Importa ${parsedData.length} Aziende`}
            </button>
          </div>
        </div>
      )}

      {step === 3 && (
        <div className="importing-section">
          <div className="spinner"></div>
          <p>⏳ Importazione in corso...</p>
        </div>
      )}
    </div>
  );
}
