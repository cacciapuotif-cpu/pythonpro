/**
 * Error handling utility to prevent React #31 (rendering non-string objects)
 * Converts errors to user-friendly messages.
 *
 * `formatApiError` is the centralized entry point: it turns any error
 * (Axios/API, network, plain JS) into an operational message in Italian,
 * suitable for a non-technical administrative user. It prefers a sensible
 * backend `detail` (Italian) and falls back to a status-code mapping, then
 * to a network message.
 */

// Operational messages per HTTP status code (Italian, non-technical).
const STATUS_MESSAGES = {
  400: 'Dati non validi. Controlla i campi e riprova.',
  401: 'Sessione scaduta, effettua di nuovo l’accesso.',
  403: 'Non hai i permessi per questa operazione.',
  404: 'Risorsa non trovata.',
  405: 'Operazione non consentita.',
  409: 'Operazione in conflitto con lo stato attuale dei dati.',
  413: 'Il file o i dati inviati sono troppo grandi.',
  422: 'Dati non validi. Controlla i campi e riprova.',
  429: 'Troppe richieste. Attendi qualche istante e riprova.',
};

const SERVER_ERROR_MESSAGE = 'Errore del server, riprova più tardi.';
const NETWORK_ERROR_MESSAGE = 'Server non raggiungibile.';
const TIMEOUT_ERROR_MESSAGE = 'Il server non ha risposto in tempo. Riprova.';
const UNKNOWN_ERROR_MESSAGE = 'Si è verificato un errore. Riprova.';

// Generic English defaults emitted by FastAPI/Starlette that we never want to
// show to the user verbatim: we translate them via the status-code mapping.
const GENERIC_BACKEND_DETAILS = new Set([
  'not authenticated',
  'not enough permissions',
  'could not validate credentials',
  'forbidden',
  'unauthorized',
  'not found',
  'internal server error',
  'method not allowed',
  'unprocessable entity',
  'bad request',
  'conflict',
]);

/**
 * A backend `detail` string is "sensible" (worth showing as-is) when it is a
 * non-empty string that is not a known generic English default and not the
 * raw axios message ("Request failed with status code N").
 */
function isSensibleDetail(detail) {
  if (typeof detail !== 'string') return false;
  const normalized = detail.trim().toLowerCase();
  if (!normalized) return false;
  if (GENERIC_BACKEND_DETAILS.has(normalized)) return false;
  if (/^request failed with status code \d+$/.test(normalized)) return false;
  return true;
}

/**
 * Synthesizes a Pydantic 422 validation error list into a single Italian line,
 * e.g. [{loc:['body','email']}, {loc:['body','codice_fiscale']}] ->
 * "Dati non validi: email, codice_fiscale."
 */
function summarizeValidationList(detail) {
  const fields = detail
    .map((item) => {
      if (typeof item?.field === 'string' && item.field.trim()) {
        return item.field
          .replace(/^body\./, '')
          .replace(/^(\d+)\./, (_, index) => `riga ${Number(index) + 2} · `);
      }
      const loc = Array.isArray(item?.loc)
        ? item.loc.filter((part) => part !== 'body' && part !== 'query' && part !== 'path')
        : [];
      return loc.length ? String(loc[loc.length - 1]) : null;
    })
    .filter(Boolean);

  if (!fields.length) {
    return STATUS_MESSAGES[422];
  }

  const uniqueFields = [...new Set(fields)];
  return `Dati non validi: ${uniqueFields.join(', ')}.`;
}

/**
 * Central mapper: any error -> operational Italian message (always a string).
 * @param {unknown} error
 * @returns {string}
 */
export function formatApiError(error) {
  if (!error) return UNKNOWN_ERROR_MESSAGE;
  if (typeof error === 'string') return error.trim() || UNKNOWN_ERROR_MESSAGE;

  const response = error.response;

  // No HTTP response: network error, timeout, CORS, or a plain JS error.
  if (!response) {
    if (error.code === 'ECONNABORTED' || /timeout/i.test(error.message || '')) {
      return TIMEOUT_ERROR_MESSAGE;
    }
    // Axios network failure (server down, DNS, CORS) or a request without reply.
    if (error.isAxiosError || error.request || error.code === 'ERR_NETWORK') {
      return NETWORK_ERROR_MESSAGE;
    }
    // Plain Error / object carrying an already user-facing message.
    if (error instanceof Error && error.message) return error.message;
    if (typeof error.message === 'string' && error.message) return error.message;
    return UNKNOWN_ERROR_MESSAGE;
  }

  const status = response.status;
  const data = response.data;
  const detail = data?.detail ?? data?.message ?? data?.error;
  const validationDetails = Array.isArray(data?.details) ? data.details : null;

  // Il gestore FastAPI centralizzato usa `details`, mentre FastAPI standard
  // usa `detail`: supportiamo entrambi senza perdere i campi che hanno fallito.
  if (validationDetails) {
    return summarizeValidationList(validationDetails);
  }

  // Pydantic validation list (typically 422).
  if (Array.isArray(detail)) {
    return summarizeValidationList(detail);
  }

  // Prefer a sensible (Italian / operational) backend detail.
  if (isSensibleDetail(detail)) {
    return detail.trim();
  }

  // Otherwise map by status code.
  if (typeof status === 'number' && status >= 500) {
    return SERVER_ERROR_MESSAGE;
  }
  if (STATUS_MESSAGES[status]) {
    return STATUS_MESSAGES[status];
  }

  return status
    ? `Si è verificato un errore (codice ${status}).`
    : UNKNOWN_ERROR_MESSAGE;
}

/**
 * Converts any error to a user-friendly string message.
 * Kept for backward compatibility; delegates to formatApiError.
 * @param {unknown} err - The error to convert
 * @returns {string} - User-friendly error message
 */
export function toUserMessage(err) {
  return formatApiError(err);
}

/**
 * Safe error renderer for React components
 * Usage: {error && <div>{renderError(error)}</div>}
 */
export function renderError(err) {
  return formatApiError(err);
}

const errorUtils = { formatApiError, toUserMessage, renderError };

export default errorUtils;
