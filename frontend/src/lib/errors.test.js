/**
 * Test UI-12: mappatura degli errori API in messaggi operativi italiani.
 *
 * `formatApiError` deve:
 * - preferire un `detail` sensato del backend (italiano/operativo)
 * - tradurre i codici di stato comuni (401/403/404/422/5xx) in italiano
 * - sintetizzare la lista di validazione Pydantic (422) in una riga
 * - restituire un messaggio di rete quando manca la risposta
 * - restituire sempre una stringa (mai un oggetto -> React #31)
 */

import { formatApiError, toUserMessage, renderError } from './errors';

const axiosError = ({ status, data, code, message = 'Request failed' }) => ({
  isAxiosError: true,
  code,
  message: status ? `Request failed with status code ${status}` : message,
  response: status ? { status, data } : undefined,
  request: {},
});

describe('formatApiError - mappatura per codice di stato', () => {
  test('401 senza detail -> sessione scaduta', () => {
    expect(formatApiError(axiosError({ status: 401, data: {} }))).toBe(
      'Sessione scaduta, effettua di nuovo l’accesso.'
    );
  });

  test('403 senza detail -> permessi', () => {
    expect(formatApiError(axiosError({ status: 403, data: {} }))).toBe(
      'Non hai i permessi per questa operazione.'
    );
  });

  test('404 -> risorsa non trovata', () => {
    expect(formatApiError(axiosError({ status: 404, data: {} }))).toBe(
      'Risorsa non trovata.'
    );
  });

  test('500 -> errore del server', () => {
    expect(formatApiError(axiosError({ status: 500, data: {} }))).toBe(
      'Errore del server, riprova più tardi.'
    );
  });

  test('503 -> errore del server', () => {
    expect(formatApiError(axiosError({ status: 503, data: {} }))).toBe(
      'Errore del server, riprova più tardi.'
    );
  });

  test('status non mappato -> messaggio generico col codice', () => {
    expect(formatApiError(axiosError({ status: 418, data: {} }))).toBe(
      'Si è verificato un errore (codice 418).'
    );
  });
});

describe('formatApiError - preferenza per il detail del backend', () => {
  test('detail italiano sensato viene mostrato as-is (403 RBAC)', () => {
    expect(
      formatApiError(axiosError({ status: 403, data: { detail: 'Permessi insufficienti' } }))
    ).toBe('Permessi insufficienti');
  });

  test('detail login italiano ha la precedenza sul 401 generico', () => {
    expect(
      formatApiError(axiosError({ status: 401, data: { detail: 'Username o password non validi' } }))
    ).toBe('Username o password non validi');
  });

  test('detail generico inglese (Forbidden) NON viene mostrato: si usa la mappatura', () => {
    expect(
      formatApiError(axiosError({ status: 403, data: { detail: 'Forbidden' } }))
    ).toBe('Non hai i permessi per questa operazione.');
  });

  test('detail "Not authenticated" -> mappatura 401', () => {
    expect(
      formatApiError(axiosError({ status: 401, data: { detail: 'Not authenticated' } }))
    ).toBe('Sessione scaduta, effettua di nuovo l’accesso.');
  });

  test('422 del gestore centralizzato usa details e indica i campi', () => {
    expect(
      formatApiError(axiosError({
        status: 422,
        data: {
          error: 'Errori di validazione',
          details: [
            {
              field: 'body.0.data_nascita',
              message: 'Input should be a valid datetime',
              type: 'datetime_from_date_parsing',
            },
          ],
        },
      }))
    ).toBe('Dati non validi: riga 2 · data_nascita.');
  });

  test('campo message del backend usato come detail alternativo', () => {
    expect(
      formatApiError(axiosError({ status: 400, data: { message: 'Il codice fiscale è duplicato.' } }))
    ).toBe('Il codice fiscale è duplicato.');
  });
});

describe('formatApiError - validazione Pydantic 422', () => {
  test('lista con più campi -> sintesi "Dati non validi: ..."', () => {
    const detail = [
      { loc: ['body', 'email'], msg: 'field required', type: 'value_error.missing' },
      { loc: ['body', 'codice_fiscale'], msg: 'invalid', type: 'value_error' },
    ];
    expect(formatApiError(axiosError({ status: 422, data: { detail } }))).toBe(
      'Dati non validi: email, codice_fiscale.'
    );
  });

  test('lista con campi duplicati -> deduplica', () => {
    const detail = [
      { loc: ['body', 'importo'], msg: 'a' },
      { loc: ['body', 'importo'], msg: 'b' },
    ];
    expect(formatApiError(axiosError({ status: 422, data: { detail } }))).toBe(
      'Dati non validi: importo.'
    );
  });

  test('lista senza loc utile -> messaggio 422 generico', () => {
    expect(
      formatApiError(axiosError({ status: 422, data: { detail: [{ msg: 'x' }] } }))
    ).toBe('Dati non validi. Controlla i campi e riprova.');
  });
});

describe('formatApiError - errori di rete e casi limite', () => {
  test('nessuna risposta (server down) -> Server non raggiungibile', () => {
    expect(
      formatApiError({ isAxiosError: true, request: {}, message: 'Network Error' })
    ).toBe('Server non raggiungibile.');
  });

  test('ERR_NETWORK -> Server non raggiungibile', () => {
    expect(
      formatApiError({ isAxiosError: true, code: 'ERR_NETWORK', message: 'Network Error' })
    ).toBe('Server non raggiungibile.');
  });

  test('timeout (ECONNABORTED) -> messaggio dedicato', () => {
    expect(
      formatApiError({ isAxiosError: true, code: 'ECONNABORTED', message: 'timeout of 30000ms exceeded' })
    ).toBe('Il server non ha risposto in tempo. Riprova.');
  });

  test('Error JS semplice -> il suo message', () => {
    expect(formatApiError(new Error('Le credenziali non corrispondono al profilo.'))).toBe(
      'Le credenziali non corrispondono al profilo.'
    );
  });

  test('stringa -> se stessa', () => {
    expect(formatApiError('Errore custom')).toBe('Errore custom');
  });

  test('null/undefined -> messaggio generico, mai crash', () => {
    expect(formatApiError(null)).toBe('Si è verificato un errore. Riprova.');
    expect(formatApiError(undefined)).toBe('Si è verificato un errore. Riprova.');
  });

  test('restituisce sempre una stringa (no React #31)', () => {
    expect(typeof formatApiError({ foo: 'bar' })).toBe('string');
    expect(typeof formatApiError(axiosError({ status: 500, data: {} }))).toBe('string');
  });
});

describe('compatibilità: toUserMessage e renderError delegano a formatApiError', () => {
  test('toUserMessage', () => {
    expect(toUserMessage(axiosError({ status: 404, data: {} }))).toBe('Risorsa non trovata.');
  });

  test('renderError', () => {
    expect(renderError(axiosError({ status: 403, data: {} }))).toBe(
      'Non hai i permessi per questa operazione.'
    );
  });
});
