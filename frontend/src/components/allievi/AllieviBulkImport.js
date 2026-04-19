import React, { useMemo, useState } from 'react';
import * as XLSX from 'xlsx';
import '../collaborators/CollaboratorBulkImport.css';

const COLUMN_MAPPING = {
  Nome: 'nome',
  Cognome: 'cognome',
  'Codice Fiscale': 'codice_fiscale',
  Email: 'email',
  Telefono: 'telefono',
  'Luogo di Nascita': 'luogo_nascita',
  'Data di Nascita': 'data_nascita',
  Residenza: 'residenza',
  CAP: 'cap',
  Città: 'citta',
  Provincia: 'provincia',
  Occupato: 'occupato',
  'Azienda Cliente': 'azienda_cliente',
  'Sede Operativa': 'sede_operativa',
  'Data Assunzione': 'data_assunzione',
  Contratto: 'tipo_contratto',
  CCNL: 'ccnl',
  Mansione: 'mansione',
  Livello: 'livello_inquadramento',
  Note: 'note',
};

const REQUIRED_FIELDS = ['nome', 'cognome'];

const normalizeDateValue = (value) => {
  if (!value) return '';
  if (typeof value === 'number') {
    const date = XLSX.SSF.parse_date_code(value);
    return `${date.y}-${String(date.m).padStart(2, '0')}-${String(date.d).padStart(2, '0')}`;
  }
  return value.toString().trim();
};

const normalizeBoolean = (value) => {
  const normalized = `${value || ''}`.trim().toLowerCase();
  return ['si', 'sì', 'yes', 'true', '1', 'x'].includes(normalized);
};

export default function AllieviBulkImport({ onImport, onClose, isLoading, aziende = [] }) {
  const [file, setFile] = useState(null);
  const [parsedData, setParsedData] = useState([]);
  const [errors, setErrors] = useState([]);
  const [step, setStep] = useState(1);

  const aziendaIndex = useMemo(
    () => new Map(
      aziende.map((azienda) => [
        (azienda.ragione_sociale || '').trim().toLowerCase(),
        azienda,
      ])
    ),
    [aziende]
  );

  const validateRow = (row, rowIndex) => {
    const rowErrors = [];

    REQUIRED_FIELDS.forEach((field) => {
      if (!row[field] || `${row[field]}`.trim() === '') {
        const label = Object.keys(COLUMN_MAPPING).find((key) => COLUMN_MAPPING[key] === field);
        rowErrors.push(`Riga ${rowIndex}: Campo obbligatorio mancante: ${label}`);
      }
    });

    if (row.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(row.email)) {
      rowErrors.push(`Riga ${rowIndex}: Email non valida: ${row.email}`);
    }
    if (row.codice_fiscale && `${row.codice_fiscale}`.trim().length !== 16) {
      rowErrors.push(`Riga ${rowIndex}: Codice fiscale deve essere di 16 caratteri`);
    }
    if (row.cap && !/^\d{5}$/.test(`${row.cap}`.trim())) {
      rowErrors.push(`Riga ${rowIndex}: CAP non valido`);
    }
    if (row.provincia && !/^[A-Za-z]{2}$/.test(`${row.provincia}`.trim())) {
      rowErrors.push(`Riga ${rowIndex}: Provincia non valida`);
    }
    if (row.occupato && !row.azienda_cliente) {
      rowErrors.push(`Riga ${rowIndex}: se l'allievo è occupato devi indicare l'azienda cliente`);
    }

    const azienda = row.azienda_cliente
      ? aziendaIndex.get(row.azienda_cliente.trim().toLowerCase())
      : null;
    if (row.azienda_cliente && !azienda) {
      rowErrors.push(`Riga ${rowIndex}: azienda cliente non trovata: ${row.azienda_cliente}`);
    }
    if (row.sede_operativa) {
      if (!azienda) {
        rowErrors.push(`Riga ${rowIndex}: la sede operativa richiede un'azienda valida`);
      } else {
        const sede = (azienda.sedi_operative || []).find(
          (item) => (item.nome || '').trim().toLowerCase() === row.sede_operativa.trim().toLowerCase()
        );
        if (!sede) {
          rowErrors.push(`Riga ${rowIndex}: sede operativa non trovata in ${azienda.ragione_sociale}: ${row.sede_operativa}`);
        }
      }
    }

    return rowErrors;
  };

  const mapRowToPayload = (row) => {
    const azienda = row.azienda_cliente
      ? aziendaIndex.get(row.azienda_cliente.trim().toLowerCase())
      : null;
    const sede = row.sede_operativa && azienda
      ? (azienda.sedi_operative || []).find(
        (item) => (item.nome || '').trim().toLowerCase() === row.sede_operativa.trim().toLowerCase()
      )
      : null;

    return {
      nome: row.nome.trim(),
      cognome: row.cognome.trim(),
      codice_fiscale: row.codice_fiscale || null,
      email: row.email || null,
      telefono: row.telefono || null,
      luogo_nascita: row.luogo_nascita || null,
      data_nascita: row.data_nascita ? `${row.data_nascita}T00:00:00Z` : null,
      residenza: row.residenza || null,
      cap: row.cap || null,
      citta: row.citta || null,
      provincia: row.provincia ? row.provincia.toUpperCase() : null,
      occupato: Boolean(row.occupato),
      azienda_cliente_id: azienda?.id || null,
      azienda_sede_operativa_id: sede?.id || null,
      data_assunzione: row.data_assunzione ? `${row.data_assunzione}T00:00:00Z` : null,
      tipo_contratto: row.tipo_contratto || null,
      ccnl: row.ccnl || null,
      mansione: row.mansione || null,
      livello_inquadramento: row.livello_inquadramento || null,
      note: row.note || null,
      project_ids: [],
      attivo: true,
    };
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
            if (field === 'codice_fiscale') row[field] = value.toString().trim().toUpperCase();
            else if (field === 'email') row[field] = value.toString().trim().toLowerCase();
            else if (field === 'provincia') row[field] = value.toString().trim().toUpperCase();
            else if (field === 'occupato') row[field] = normalizeBoolean(value);
            else if (field === 'data_nascita' || field === 'data_assunzione') row[field] = normalizeDateValue(value);
            else row[field] = value.toString().trim();
          });

          validationErrors.push(...validateRow(row, index + 2));
          mappedRows.push(row);
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
    await onImport(parsedData.map(mapRowToPayload));
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
      Nome: 'Mario',
      Cognome: 'Rossi',
      'Codice Fiscale': 'RSSMRA80A01H501U',
      Email: 'mario.rossi@example.com',
      Telefono: '3331234567',
      'Luogo di Nascita': 'Napoli',
      'Data di Nascita': '1990-05-12',
      Residenza: 'Via Roma 1',
      CAP: '80100',
      Città: 'Napoli',
      Provincia: 'NA',
      Occupato: 'SI',
      'Azienda Cliente': 'Azienda Demo',
      'Sede Operativa': 'Sede Napoli Centro',
      'Data Assunzione': '2026-01-10',
      Contratto: 'tempo indeterminato',
      CCNL: 'Commercio',
      Mansione: 'Addetto formazione',
      Livello: '3',
      Note: 'Import prova',
    }]);
    ws['!cols'] = Object.keys(COLUMN_MAPPING).map(() => ({ wch: 22 }));
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, 'Allievi');
    XLSX.writeFile(wb, 'template_allievi.xlsx');
  };

  return (
    <div className="bulk-import-container">
      <div className="bulk-import-header">
        <h2>📥 Importazione Massiva Allievi</h2>
        <button className="close-button" onClick={onClose} disabled={isLoading}>❌</button>
      </div>

      {step === 1 && (
        <div className="upload-section">
          <div className="info-box">
            <h3>ℹ️ Istruzioni</h3>
            <p>Carica un file Excel o CSV con gli allievi.</p>
            <p><strong>Campi obbligatori:</strong> Nome, Cognome</p>
            <p><strong>Occupato:</strong> usa `SI`/`NO`. Se compili azienda o sede, i nomi devono esistere già nel gestionale.</p>
          </div>
          <button className="download-template-button" onClick={downloadTemplate}>📄 Scarica Template Excel</button>
          <div className="file-upload">
            <label htmlFor="allievi-file-input" className="file-label">
              {file ? `📎 ${file.name}` : '📁 Seleziona File Excel'}
            </label>
            <input id="allievi-file-input" type="file" accept=".xlsx,.xls,.csv" onChange={handleFileChange} disabled={isLoading} />
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
            <h3>👀 Anteprima Dati ({parsedData.length} allievi)</h3>
            <button className="change-file-button" onClick={resetImport} disabled={isLoading}>🔄 Cambia File</button>
          </div>
          <div className="preview-table-container">
            <table className="preview-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Cognome</th>
                  <th>Nome</th>
                  <th>Email</th>
                  <th>Azienda</th>
                  <th>Sede Operativa</th>
                </tr>
              </thead>
              <tbody>
                {parsedData.map((row, index) => (
                  <tr key={index}>
                    <td>{index + 1}</td>
                    <td>{row.cognome}</td>
                    <td>{row.nome}</td>
                    <td>{row.email || '-'}</td>
                    <td>{row.azienda_cliente || '-'}</td>
                    <td>{row.sede_operativa || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="preview-actions">
            <button className="cancel-button" onClick={onClose} disabled={isLoading}>Annulla</button>
            <button className="import-button" onClick={handleImport} disabled={isLoading || parsedData.length === 0}>
              {isLoading ? '⏳ Importazione in corso...' : `✅ Importa ${parsedData.length} Allievi`}
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
