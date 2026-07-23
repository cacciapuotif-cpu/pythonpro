/**
 * ErrorBanner Component
 *
 * Gestisce la visualizzazione di errori di qualsiasi tipo in modo sicuro per React.
 * Previene React error #31 (Objects are not valid as a React child).
 *
 * La mappatura del messaggio (API/rete/JS) è centralizzata in
 * `lib/errors.js` (`formatApiError`), così ogni punto che usa ErrorBanner
 * mostra un messaggio operativo in italiano coerente.
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

import { formatApiError } from '../lib/errors';

export default function ErrorBanner({ error }) {
  if (!error) {
    return null;
  }

  const message = formatApiError(error);

  // Log completo in console per debugging (solo in dev)
  if (process.env.NODE_ENV === 'development') {
    console.error('[ErrorBanner] Error details:', {
      type: error?.constructor?.name,
      message,
      fullError: error,
    });
  }

  return <>{message}</>;
}
