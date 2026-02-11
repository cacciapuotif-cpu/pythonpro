/**
 * Utility per validazione e sanitizzazione nomi file
 *
 * Previene problemi di sincronizzazione con OneDrive causati da
 * nomi di file contenenti "null", "undefined", "None" o valori vuoti.
 *
 * @module fileNameValidator
 */

/**
 * Lista di valori considerati invalidi per nomi di file/cartelle
 */
const INVALID_VALUES = [
  null,
  undefined,
  '',
  'null',
  'NULL',
  'Null',
  'undefined',
  'UNDEFINED',
  'Undefined',
  'None',
  'NONE',
  'none'
];

/**
 * Verifica se un nome è valido per file/cartelle
 *
 * @param {string|null|undefined} name - Nome da validare
 * @returns {boolean} - true se valido, false altrimenti
 *
 * @example
 * isValidFileName('documento.pdf')  // true
 * isValidFileName(null)             // false
 * isValidFileName('null')           // false
 * isValidFileName('')               // false
 */
export function isValidFileName(name) {
  // Converti in stringa per confronto sicuro
  const nameStr = String(name ?? '');

  // Controlla se il nome è nella lista degli invalidi
  return !INVALID_VALUES.includes(name) &&
         !INVALID_VALUES.includes(nameStr.trim()) &&
         nameStr.trim().length > 0;
}

/**
 * Sanitizza un nome di file, sostituendo valori invalidi con un default
 *
 * @param {string|null|undefined} name - Nome da sanitizzare
 * @param {string} defaultName - Nome di default da usare se il nome è invalido
 * @returns {string} - Nome sanitizzato
 *
 * @example
 * sanitizeFileName('documento.pdf', 'unnamed')  // 'documento.pdf'
 * sanitizeFileName(null, 'unnamed')             // 'unnamed'
 * sanitizeFileName('null', 'unnamed')           // 'unnamed'
 * sanitizeFileName('', 'file')                  // 'file'
 */
export function sanitizeFileName(name, defaultName = 'unnamed') {
  if (!isValidFileName(name)) {
    console.warn(`Nome file invalido: "${name}", uso default: "${defaultName}"`);
    return defaultName;
  }

  return String(name).trim();
}

/**
 * Genera un nome di file sicuro con timestamp
 *
 * Utile quando serve un nome univoco e garantito valido
 *
 * @param {string|null|undefined} baseName - Nome base (opzionale)
 * @param {string} extension - Estensione file (con o senza punto)
 * @param {string} prefix - Prefisso da aggiungere (default: 'file')
 * @returns {string} - Nome file con timestamp
 *
 * @example
 * generateSafeFileName('documento', '.pdf')           // 'documento_1234567890.pdf'
 * generateSafeFileName(null, '.pdf', 'contract')      // 'contract_1234567890.pdf'
 * generateSafeFileName('null', '.pdf')                // 'file_1234567890.pdf'
 */
export function generateSafeFileName(baseName, extension, prefix = 'file') {
  // Sanitizza il nome base
  const safeName = isValidFileName(baseName)
    ? sanitizeFileName(baseName)
    : prefix;

  // Assicurati che l'estensione inizi con un punto
  const ext = extension.startsWith('.') ? extension : `.${extension}`;

  // Genera timestamp
  const timestamp = Date.now();

  return `${safeName}_${timestamp}${ext}`;
}

/**
 * Valida e crea un nome di file per il download
 *
 * Questa funzione è ottimizzata per l'uso con download di file,
 * fornendo fallback intelligenti basati su informazioni aggiuntive.
 *
 * @param {Object} options - Opzioni per la generazione del nome
 * @param {string|null} options.filename - Nome file proposto
 * @param {string|null} options.fallbackName - Nome di fallback
 * @param {string} options.extension - Estensione file
 * @param {string|number} options.id - ID per generare un nome univoco
 * @returns {string} - Nome file valido per il download
 *
 * @example
 * createDownloadFileName({
 *   filename: 'documento.pdf',
 *   fallbackName: 'report',
 *   extension: 'pdf',
 *   id: 123
 * })  // 'documento.pdf'
 *
 * createDownloadFileName({
 *   filename: null,
 *   fallbackName: 'report',
 *   extension: 'pdf',
 *   id: 123
 * })  // 'report_123.pdf'
 *
 * createDownloadFileName({
 *   filename: 'null',
 *   fallbackName: null,
 *   extension: 'pdf',
 *   id: 123
 * })  // 'documento_123.pdf'
 */
export function createDownloadFileName({ filename, fallbackName, extension, id }) {
  // Se il filename è valido, usalo
  if (isValidFileName(filename)) {
    return sanitizeFileName(filename);
  }

  // Se c'è un fallback valido, usalo con l'id
  if (isValidFileName(fallbackName)) {
    const ext = extension.startsWith('.') ? extension : `.${extension}`;
    return `${sanitizeFileName(fallbackName)}_${id}${ext}`;
  }

  // Ultimo fallback: nome generico con timestamp
  return generateSafeFileName('documento', extension);
}

/**
 * Valida e sanitizza un path, sostituendo segmenti invalidi
 *
 * @param {string} path - Path da sanitizzare
 * @param {string} separator - Separatore del path ('/' o '\\')
 * @returns {string} - Path sanitizzato
 *
 * @example
 * sanitizePath('uploads/null/file.pdf', '/')  // 'uploads/unnamed/file.pdf'
 * sanitizePath('docs\\undefined\\doc.pdf', '\\')  // 'docs\\unnamed\\doc.pdf'
 */
export function sanitizePath(path, separator = '/') {
  const segments = path.split(separator);
  const safeSegments = segments.map(segment =>
    sanitizeFileName(segment, 'unnamed')
  );
  return safeSegments.join(separator);
}

/**
 * Estrae e valida il nome da un oggetto
 *
 * Utility per estrarre nomi da oggetti (collaboratori, progetti, etc.)
 * con validazione automatica
 *
 * @param {Object} obj - Oggetto da cui estrarre il nome
 * @param {string|string[]} nameFields - Campo/i da cui estrarre il nome
 * @param {string} defaultName - Nome di default
 * @returns {string} - Nome estratto e validato
 *
 * @example
 * extractSafeName(
 *   { first_name: 'Mario', last_name: 'Rossi' },
 *   ['first_name', 'last_name'],
 *   'collaboratore'
 * )  // 'Mario Rossi'
 *
 * extractSafeName(
 *   { name: null },
 *   'name',
 *   'progetto'
 * )  // 'progetto'
 */
export function extractSafeName(obj, nameFields, defaultName = 'unnamed') {
  if (!obj) {
    return defaultName;
  }

  // Se nameFields è una stringa, convertila in array
  const fields = Array.isArray(nameFields) ? nameFields : [nameFields];

  // Estrai i valori dei campi
  const values = fields
    .map(field => obj[field])
    .filter(value => isValidFileName(value))
    .map(value => sanitizeFileName(value));

  // Se ci sono valori validi, uniscili; altrimenti usa il default
  return values.length > 0 ? values.join(' ') : defaultName;
}

export default {
  isValidFileName,
  sanitizeFileName,
  generateSafeFileName,
  createDownloadFileName,
  sanitizePath,
  extractSafeName,
  INVALID_VALUES
};
