import React, { useState } from 'react';
import * as XLSX from 'xlsx';
import './CollaboratorBulkImport.css';

/**
 * Componente per l'importazione massiva di collaboratori da file Excel
 */
const CollaboratorBulkImport = ({ onImport, onClose, isLoading }) => {
  const [file, setFile] = useState(null);
  const [parsedData, setParsedData] = useState([]);
  const [errors, setErrors] = useState([]);
  const [step, setStep] = useState(1); // 1: upload, 2: preview, 3: importing

  // Mappa delle colonne Excel ai campi del database
  const COLUMN_MAPPING = {
    'Nome': 'first_name',
    'Cognome': 'last_name',
    'Email': 'email',
    'Codice Fiscale': 'fiscal_code',
    'Telefono': 'phone',
    'Posizione': 'position',
    'Luogo di Nascita': 'birthplace',
    'Data di Nascita': 'birth_date',
    'Sesso': 'gender',
    'Città': 'city',
    'Indirizzo': 'address',
    'Titolo di Studio': 'education'
  };

  // Campi obbligatori
  const REQUIRED_FIELDS = ['first_name', 'last_name', 'email', 'fiscal_code'];

  /**
   * Valida l'email
   */
  const isValidEmail = (email) => {
    const regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return regex.test(email);
  };

  /**
   * Valida il codice fiscale
   */
  const isValidFiscalCode = (code) => {
    return code && code.length === 16;
  };

  /**
   * Valida la data
   */
  const isValidDate = (dateStr) => {
    if (!dateStr) return true; // Opzionale
    const date = new Date(dateStr);
    return !isNaN(date.getTime());
  };

  /**
   * Valida il genere
   */
  const isValidGender = (gender) => {
    if (!gender) return true; // Opzionale
    return ['maschio', 'femmina', 'M', 'F'].includes(gender.toLowerCase());
  };

  /**
   * Normalizza il genere
   */
  const normalizeGender = (gender) => {
    if (!gender) return '';
    const g = gender.toLowerCase();
    if (g === 'm' || g === 'maschio') return 'maschio';
    if (g === 'f' || g === 'femmina') return 'femmina';
    return gender;
  };

  /**
   * Valida il titolo di studio
   */
  const isValidEducation = (education) => {
    if (!education) return true; // Opzionale
    const validEducation = ['licenza media', 'diploma', 'laurea', 'master'];
    return validEducation.includes(education.toLowerCase());
  };

  /**
   * Valida un singolo collaboratore
   */
  const validateCollaborator = (data, rowIndex) => {
    const errors = [];

    // Controlla campi obbligatori
    REQUIRED_FIELDS.forEach(field => {
      const displayName = Object.keys(COLUMN_MAPPING).find(key => COLUMN_MAPPING[key] === field);
      if (!data[field] || data[field].toString().trim() === '') {
        errors.push(`Riga ${rowIndex}: Campo obbligatorio mancante: ${displayName}`);
      }
    });

    // Valida email
    if (data.email && !isValidEmail(data.email)) {
      errors.push(`Riga ${rowIndex}: Email non valida: ${data.email}`);
    }

    // Valida codice fiscale
    if (data.fiscal_code && !isValidFiscalCode(data.fiscal_code)) {
      errors.push(`Riga ${rowIndex}: Codice fiscale deve essere di 16 caratteri: ${data.fiscal_code}`);
    }

    // Valida data di nascita
    if (data.birth_date && !isValidDate(data.birth_date)) {
      errors.push(`Riga ${rowIndex}: Data di nascita non valida: ${data.birth_date}`);
    }

    // Valida genere
    if (data.gender && !isValidGender(data.gender)) {
      errors.push(`Riga ${rowIndex}: Genere non valido (usare: maschio/femmina/M/F): ${data.gender}`);
    }

    // Valida titolo di studio
    if (data.education && !isValidEducation(data.education)) {
      errors.push(`Riga ${rowIndex}: Titolo di studio non valido (usare: licenza media, diploma, laurea, master): ${data.education}`);
    }

    return errors;
  };

  /**
   * Gestisce il caricamento del file
   */
  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    if (!selectedFile) return;

    // Verifica che sia un file Excel
    const validTypes = [
      'application/vnd.ms-excel',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      'text/csv'
    ];

    if (!validTypes.includes(selectedFile.type) && !selectedFile.name.match(/\.(xlsx|xls|csv)$/)) {
      setErrors(['Il file deve essere in formato Excel (.xlsx, .xls) o CSV']);
      return;
    }

    setFile(selectedFile);
    setErrors([]);
    parseFile(selectedFile);
  };

  /**
   * Parsing del file Excel
   */
  const parseFile = (file) => {
    const reader = new FileReader();

    reader.onload = (e) => {
      try {
        const data = new Uint8Array(e.target.result);
        const workbook = XLSX.read(data, { type: 'array' });

        // Prende il primo foglio
        const sheetName = workbook.SheetNames[0];
        const worksheet = workbook.Sheets[sheetName];

        // Converte in JSON
        const jsonData = XLSX.utils.sheet_to_json(worksheet, { defval: '' });

        if (jsonData.length === 0) {
          setErrors(['Il file Excel è vuoto']);
          return;
        }

        // Mappa i dati e valida
        const mappedData = [];
        const allErrors = [];

        jsonData.forEach((row, index) => {
          const mappedRow = {};

          // Mappa le colonne
          Object.keys(COLUMN_MAPPING).forEach(excelColumn => {
            const dbField = COLUMN_MAPPING[excelColumn];
            const value = row[excelColumn];

            if (value !== undefined && value !== null && value !== '') {
              // Normalizza alcuni campi
              if (dbField === 'fiscal_code') {
                mappedRow[dbField] = value.toString().toUpperCase().trim();
              } else if (dbField === 'email') {
                mappedRow[dbField] = value.toString().toLowerCase().trim();
              } else if (dbField === 'gender') {
                mappedRow[dbField] = normalizeGender(value.toString().trim());
              } else if (dbField === 'education') {
                mappedRow[dbField] = value.toString().toLowerCase().trim();
              } else if (dbField === 'birth_date') {
                // Gestisce date Excel
                if (typeof value === 'number') {
                  // Excel memorizza le date come numeri
                  const date = XLSX.SSF.parse_date_code(value);
                  mappedRow[dbField] = `${date.y}-${String(date.m).padStart(2, '0')}-${String(date.d).padStart(2, '0')}`;
                } else {
                  mappedRow[dbField] = value.toString().trim();
                }
              } else {
                mappedRow[dbField] = value.toString().trim();
              }
            }
          });

          // Valida il collaboratore
          const rowErrors = validateCollaborator(mappedRow, index + 2); // +2 perché Excel inizia da 1 e la prima riga è l'header
          allErrors.push(...rowErrors);

          mappedData.push(mappedRow);
        });

        setParsedData(mappedData);
        setErrors(allErrors);

        if (allErrors.length === 0) {
          setStep(2);
        }

      } catch (err) {
        console.error('Errore parsing file:', err);
        setErrors([`Errore durante la lettura del file: ${err.message}`]);
      }
    };

    reader.onerror = () => {
      setErrors(['Errore durante la lettura del file']);
    };

    reader.readAsArrayBuffer(file);
  };

  /**
   * Gestisce l'importazione
   */
  const handleImport = async () => {
    if (parsedData.length === 0) return;

    setStep(3);
    await onImport(parsedData);
  };

  /**
   * Scarica il template Excel
   */
  const downloadTemplate = () => {
    const templateData = [{
      'Nome': 'Mario',
      'Cognome': 'Rossi',
      'Email': 'mario.rossi@example.com',
      'Codice Fiscale': 'RSSMRA80A01H501U',
      'Telefono': '3331234567',
      'Posizione': 'Sviluppatore',
      'Luogo di Nascita': 'Roma',
      'Data di Nascita': '1980-01-01',
      'Sesso': 'maschio',
      'Città': 'Roma',
      'Indirizzo': 'Via Roma 1',
      'Titolo di Studio': 'laurea'
    }];

    const ws = XLSX.utils.json_to_sheet(templateData);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, 'Collaboratori');

    // Imposta la larghezza delle colonne
    const colWidths = Object.keys(COLUMN_MAPPING).map(() => ({ wch: 20 }));
    ws['!cols'] = colWidths;

    XLSX.writeFile(wb, 'template_collaboratori.xlsx');
  };

  /**
   * Reset del componente
   */
  const resetImport = () => {
    setFile(null);
    setParsedData([]);
    setErrors([]);
    setStep(1);
  };

  return (
    <div className="bulk-import-container">
      <div className="bulk-import-header">
        <h2>📥 Importazione Massiva Collaboratori</h2>
        <button className="close-button" onClick={onClose} disabled={isLoading}>
          ❌
        </button>
      </div>

      {/* STEP 1: Upload File */}
      {step === 1 && (
        <div className="upload-section">
          <div className="info-box">
            <h3>ℹ️ Istruzioni</h3>
            <p>Carica un file Excel (.xlsx, .xls) o CSV con i dati dei collaboratori.</p>
            <p><strong>Campi obbligatori:</strong> Nome, Cognome, Email, Codice Fiscale</p>
            <p><strong>Campi opzionali:</strong> Telefono, Posizione, Luogo di Nascita, Data di Nascita, Sesso, Città, Indirizzo, Titolo di Studio</p>
          </div>

          <button className="download-template-button" onClick={downloadTemplate}>
            📄 Scarica Template Excel
          </button>

          <div className="file-upload">
            <label htmlFor="file-input" className="file-label">
              {file ? `📎 ${file.name}` : '📁 Seleziona File Excel'}
            </label>
            <input
              id="file-input"
              type="file"
              accept=".xlsx,.xls,.csv"
              onChange={handleFileChange}
              disabled={isLoading}
            />
          </div>

          {errors.length > 0 && (
            <div className="errors-box">
              <h4>⚠️ Errori di Validazione</h4>
              <ul>
                {errors.map((error, index) => (
                  <li key={index}>{error}</li>
                ))}
              </ul>
              <button className="retry-button" onClick={resetImport}>
                🔄 Riprova
              </button>
            </div>
          )}
        </div>
      )}

      {/* STEP 2: Preview */}
      {step === 2 && (
        <div className="preview-section">
          <div className="preview-header">
            <h3>👀 Anteprima Dati ({parsedData.length} collaboratori)</h3>
            <button className="change-file-button" onClick={resetImport} disabled={isLoading}>
              🔄 Cambia File
            </button>
          </div>

          <div className="preview-table-container">
            <table className="preview-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Nome</th>
                  <th>Cognome</th>
                  <th>Email</th>
                  <th>Codice Fiscale</th>
                  <th>Telefono</th>
                  <th>Posizione</th>
                </tr>
              </thead>
              <tbody>
                {parsedData.map((row, index) => (
                  <tr key={index}>
                    <td>{index + 1}</td>
                    <td>{row.first_name}</td>
                    <td>{row.last_name}</td>
                    <td>{row.email}</td>
                    <td>{row.fiscal_code}</td>
                    <td>{row.phone || '-'}</td>
                    <td>{row.position || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="preview-actions">
            <button className="cancel-button" onClick={onClose} disabled={isLoading}>
              Annulla
            </button>
            <button
              className="import-button"
              onClick={handleImport}
              disabled={isLoading || parsedData.length === 0}
            >
              {isLoading ? '⏳ Importazione in corso...' : `✅ Importa ${parsedData.length} Collaboratori`}
            </button>
          </div>
        </div>
      )}

      {/* STEP 3: Importing */}
      {step === 3 && (
        <div className="importing-section">
          <div className="spinner"></div>
          <p>⏳ Importazione in corso...</p>
          <p>Attendere prego, l'operazione potrebbe richiedere alcuni minuti.</p>
        </div>
      )}
    </div>
  );
};

export default CollaboratorBulkImport;
