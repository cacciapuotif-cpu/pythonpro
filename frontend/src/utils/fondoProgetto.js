/**
 * Rilevamento fondo condiviso: unico punto che calcola "e' un progetto FAPI?"
 * invece della stessa logica reimplementata in piu' componenti.
 */

export function fundKey(project) {
  return String(project?.ente_erogatore || '').trim().toLowerCase();
}

export function isFapiProject(project) {
  return fundKey(project) === 'fapi' || Boolean(project?.codice_fapi);
}
