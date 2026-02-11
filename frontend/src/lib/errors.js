/**
 * Error handling utility to prevent React #31 (rendering non-string objects)
 * Converts errors to user-friendly messages
 */

/**
 * Converts any error to a user-friendly string message
 * @param {unknown} err - The error to convert
 * @returns {string} - User-friendly error message
 */
export function toUserMessage(err) {
  // Handle Axios errors
  if (err?.isAxiosError) {
    const status = err.response?.status;
    const detail = err.response?.data?.detail;
    const message = err.response?.data?.message;
    const errorMsg = detail || message || err.message || 'Richiesta fallita';

    if (status) {
      return `${status} – ${errorMsg}`;
    }
    return errorMsg;
  }

  // Handle standard Error objects
  if (err instanceof Error) {
    return err.message;
  }

  // Handle objects with message property
  if (err && typeof err === 'object' && 'message' in err) {
    return String(err.message);
  }

  // Handle strings
  if (typeof err === 'string') {
    return err;
  }

  // Fallback: try to stringify or convert to string
  try {
    return JSON.stringify(err);
  } catch {
    return String(err);
  }
}

/**
 * Safe error renderer for React components
 * Usage: {error && <div>{renderError(error)}</div>}
 */
export function renderError(err) {
  return toUserMessage(err);
}

export default { toUserMessage, renderError };
