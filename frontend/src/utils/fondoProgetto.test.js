/**
 * Test per fondoProgetto utility
 */

import { fundKey, isFapiProject } from './fondoProgetto';

describe('fondoProgetto', () => {
  describe('fundKey', () => {
    it('normalizza a lowercase e trim', () => {
      expect(fundKey({ ente_erogatore: '  FAPI  ' })).toBe('fapi');
      expect(fundKey({ ente_erogatore: 'Formazienda' })).toBe('formazienda');
    });

    it('restituisce stringa vuota se ente_erogatore assente', () => {
      expect(fundKey({})).toBe('');
      expect(fundKey(null)).toBe('');
      expect(fundKey(undefined)).toBe('');
    });
  });

  describe('isFapiProject', () => {
    it('e vero per ente_erogatore FAPI (case/spazi insensitive)', () => {
      expect(isFapiProject({ ente_erogatore: 'FAPI' })).toBe(true);
      expect(isFapiProject({ ente_erogatore: ' fapi ' })).toBe(true);
    });

    it('e vero se codice_fapi e valorizzato anche senza ente_erogatore', () => {
      expect(isFapiProject({ codice_fapi: 'FAPI-2024-001' })).toBe(true);
    });

    it('e falso per altri fondi', () => {
      expect(isFapiProject({ ente_erogatore: 'Formazienda' })).toBe(false);
      expect(isFapiProject({ ente_erogatore: 'Fondimpresa' })).toBe(false);
      expect(isFapiProject({ ente_erogatore: 'Altro' })).toBe(false);
    });

    it('e falso per progetto assente o senza dati', () => {
      expect(isFapiProject(null)).toBe(false);
      expect(isFapiProject({})).toBe(false);
    });
  });
});
