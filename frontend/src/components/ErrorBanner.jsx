/**
 * ErrorBanner Component
 *
 * Gestisce la visualizzazione di errori di qualsiasi tipo in modo sicuro per React.
 * Previene React error #31 (Objects are not valid as a React child).
 *
 * Supporta:
 * - AxiosError (errori API)
 * - Error standard JavaScript
 * - Stringhe
 * - Oggetti generici (stringify fallback)
 *
 * Usage:
 *   import ErrorBanner from './ErrorBanner';
 *
 *   {error && (
 *     <div className="error-message">
 *       <ErrorBanner error={error} />
 *     </div>
 *   )}
 */

// eslint-disable-next-line no-restricted-imports
import { isAxiosError } from 'axios';

export default function ErrorBanner({ error }) {
  let message = 'Errore sconosciuto';

  if (!error) {
    return null;
  }

  // Caso 1: AxiosError (errori API)
  if (isAxiosError(error)) {
    // Prova ad estrarre messaggio dal backend
    const backendMessage = error.response?.data?.message
                        || error.response?.data?.detail
                        || error.response?.data?.error;

    if (backendMessage) {
      message = backendMessage;
    } else if (error.response) {
      // Errore HTTP con risposta
      message = `Errore ${error.response.status}: ${error.response.statusText}`;
    } else if (error.request) {
      // Richiesta fatta ma nessuna risposta (es. backend down)
      message = 'Impossibile connettersi al server. Verifica che il backend sia avviato.';
    } else {
      // Errore nella configurazione della richiesta
      message = error.message || 'Errore nella configurazione della richiesta';
    }
  }
  // Caso 2: Error standard JavaScript
  else if (error instanceof Error) {
    message = error.message;
  }
  // Caso 3: Stringa
  else if (typeof error === 'string') {
    message = error;
  }
  // Caso 4: Oggetto generico (ultimo resort)
  else {
    try {
      // Tenta stringify
      const stringified = JSON.stringify(error);
      message = stringified !== '{}' ? stringified : 'Errore sconosciuto';
    } catch (e) {
      // Stringify fallito (es. circular reference)
      message = String(error);
    }
  }

  // Log completo in console per debugging (solo in dev)
  if (process.env.NODE_ENV === 'development') {
    console.error('[ErrorBanner] Error details:', {
      type: error?.constructor?.name,
      message: message,
      fullError: error
    });
  }

  return <>{message}</>;
}
