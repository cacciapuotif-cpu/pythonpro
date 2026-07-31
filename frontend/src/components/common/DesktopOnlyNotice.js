import React from 'react';

/**
 * MOB-4: guscio per i flussi Livello 3 (MOB-0 gate) — wizard, form
 * completi, import, azioni ad alto rischio. Su mobile non si mostra
 * l'operazione, solo un riepilogo read-only opzionale (children) e un
 * messaggio esplicito che indirizza al desktop.
 */
const DesktopOnlyNotice = ({
  title = 'Disponibile solo da desktop',
  message = 'Questa operazione richiede schermo e strumenti desktop.',
  children,
}) => (
  <div className="flex flex-col gap-4 p-6 text-center">
    <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-blue-100">
      <svg className="h-6 w-6 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
      </svg>
    </div>
    <div>
      <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
      <p className="mt-1 text-sm text-gray-600">{message}</p>
    </div>
    {children && (
      <div className="rounded-lg bg-gray-50 p-4 text-left text-sm text-gray-700">
        {children}
      </div>
    )}
  </div>
);

export default DesktopOnlyNotice;
