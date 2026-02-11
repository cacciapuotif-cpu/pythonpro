/**
 * Test per fileNameValidator utility
 */

import {
  isValidFileName,
  sanitizeFileName,
  generateSafeFileName,
  createDownloadFileName,
  sanitizePath,
  extractSafeName,
  INVALID_VALUES
} from './fileNameValidator';

describe('fileNameValidator', () => {
  describe('isValidFileName', () => {
    it('dovrebbe validare nomi validi', () => {
      expect(isValidFileName('documento.pdf')).toBe(true);
      expect(isValidFileName('report_2023.xlsx')).toBe(true);
      expect(isValidFileName('file-123.txt')).toBe(true);
    });

    it('dovrebbe rigettare valori null/undefined', () => {
      expect(isValidFileName(null)).toBe(false);
      expect(isValidFileName(undefined)).toBe(false);
    });

    it('dovrebbe rigettare stringhe "null", "undefined", "None"', () => {
      expect(isValidFileName('null')).toBe(false);
      expect(isValidFileName('NULL')).toBe(false);
      expect(isValidFileName('undefined')).toBe(false);
      expect(isValidFileName('None')).toBe(false);
      expect(isValidFileName('NONE')).toBe(false);
    });

    it('dovrebbe rigettare stringhe vuote', () => {
      expect(isValidFileName('')).toBe(false);
      expect(isValidFileName('   ')).toBe(false);
    });
  });

  describe('sanitizeFileName', () => {
    it('dovrebbe restituire nomi validi senza modifiche', () => {
      expect(sanitizeFileName('documento.pdf')).toBe('documento.pdf');
      expect(sanitizeFileName('report.xlsx')).toBe('report.xlsx');
    });

    it('dovrebbe usare default per valori invalidi', () => {
      expect(sanitizeFileName(null, 'default.pdf')).toBe('default.pdf');
      expect(sanitizeFileName('null', 'default.pdf')).toBe('default.pdf');
      expect(sanitizeFileName(undefined, 'default.pdf')).toBe('default.pdf');
    });

    it('dovrebbe usare "unnamed" come default se non specificato', () => {
      expect(sanitizeFileName(null)).toBe('unnamed');
      expect(sanitizeFileName('null')).toBe('unnamed');
    });

    it('dovrebbe rimuovere spazi iniziali/finali', () => {
      expect(sanitizeFileName('  documento.pdf  ')).toBe('documento.pdf');
    });
  });

  describe('generateSafeFileName', () => {
    it('dovrebbe generare nome con timestamp per nome valido', () => {
      const result = generateSafeFileName('documento', '.pdf');
      expect(result).toMatch(/^documento_\d+\.pdf$/);
    });

    it('dovrebbe usare prefix per nome invalido', () => {
      const result = generateSafeFileName(null, '.pdf', 'contract');
      expect(result).toMatch(/^contract_\d+\.pdf$/);
    });

    it('dovrebbe usare "file" come prefix di default', () => {
      const result = generateSafeFileName('null', '.pdf');
      expect(result).toMatch(/^file_\d+\.pdf$/);
    });

    it('dovrebbe gestire estensioni con e senza punto', () => {
      const result1 = generateSafeFileName('doc', '.pdf');
      const result2 = generateSafeFileName('doc', 'pdf');
      expect(result1).toMatch(/\.pdf$/);
      expect(result2).toMatch(/\.pdf$/);
    });
  });

  describe('createDownloadFileName', () => {
    it('dovrebbe usare filename se valido', () => {
      const result = createDownloadFileName({
        filename: 'documento.pdf',
        fallbackName: 'report',
        extension: 'pdf',
        id: 123
      });
      expect(result).toBe('documento.pdf');
    });

    it('dovrebbe usare fallbackName se filename invalido', () => {
      const result = createDownloadFileName({
        filename: null,
        fallbackName: 'report',
        extension: 'pdf',
        id: 123
      });
      expect(result).toBe('report_123.pdf');
    });

    it('dovrebbe generare nome con timestamp se tutto invalido', () => {
      const result = createDownloadFileName({
        filename: 'null',
        fallbackName: null,
        extension: 'pdf',
        id: 123
      });
      expect(result).toMatch(/^documento_\d+\.pdf$/);
    });

    it('dovrebbe gestire estensioni con e senza punto', () => {
      const result1 = createDownloadFileName({
        filename: null,
        fallbackName: 'report',
        extension: '.pdf',
        id: 123
      });
      const result2 = createDownloadFileName({
        filename: null,
        fallbackName: 'report',
        extension: 'pdf',
        id: 123
      });
      expect(result1).toBe('report_123.pdf');
      expect(result2).toBe('report_123.pdf');
    });
  });

  describe('sanitizePath', () => {
    it('dovrebbe sanitizzare path Unix', () => {
      const result = sanitizePath('uploads/null/file.pdf', '/');
      expect(result).toBe('uploads/unnamed/file.pdf');
    });

    it('dovrebbe sanitizzare path Windows', () => {
      const result = sanitizePath('docs\\undefined\\file.pdf', '\\');
      expect(result).toBe('docs\\unnamed\\file.pdf');
    });

    it('dovrebbe mantenere segmenti validi', () => {
      const result = sanitizePath('uploads/docs/file.pdf', '/');
      expect(result).toBe('uploads/docs/file.pdf');
    });

    it('dovrebbe usare "/" come separatore di default', () => {
      const result = sanitizePath('uploads/null/file.pdf');
      expect(result).toBe('uploads/unnamed/file.pdf');
    });
  });

  describe('extractSafeName', () => {
    it('dovrebbe estrarre nome da campo singolo', () => {
      const obj = { name: 'Mario Rossi' };
      const result = extractSafeName(obj, 'name', 'default');
      expect(result).toBe('Mario Rossi');
    });

    it('dovrebbe estrarre nome da campi multipli', () => {
      const obj = { first_name: 'Mario', last_name: 'Rossi' };
      const result = extractSafeName(obj, ['first_name', 'last_name'], 'default');
      expect(result).toBe('Mario Rossi');
    });

    it('dovrebbe usare default per oggetto null', () => {
      const result = extractSafeName(null, 'name', 'default');
      expect(result).toBe('default');
    });

    it('dovrebbe usare default per campi invalidi', () => {
      const obj = { name: null };
      const result = extractSafeName(obj, 'name', 'default');
      expect(result).toBe('default');
    });

    it('dovrebbe saltare campi invalidi in array', () => {
      const obj = { first_name: null, last_name: 'Rossi', middle_name: 'null' };
      const result = extractSafeName(obj, ['first_name', 'last_name', 'middle_name'], 'default');
      expect(result).toBe('Rossi');
    });

    it('dovrebbe usare "unnamed" come default se non specificato', () => {
      const result = extractSafeName(null, 'name');
      expect(result).toBe('unnamed');
    });
  });

  describe('INVALID_VALUES', () => {
    it('dovrebbe contenere tutti i valori problematici', () => {
      expect(INVALID_VALUES).toContain(null);
      expect(INVALID_VALUES).toContain(undefined);
      expect(INVALID_VALUES).toContain('');
      expect(INVALID_VALUES).toContain('null');
      expect(INVALID_VALUES).toContain('NULL');
      expect(INVALID_VALUES).toContain('undefined');
      expect(INVALID_VALUES).toContain('None');
    });
  });

  describe('Integrazione - Casi d\'uso reali', () => {
    it('dovrebbe gestire download documento identità', () => {
      // Simula dati da API
      const collaborator = {
        id: 123,
        first_name: 'Mario',
        last_name: 'Rossi',
        documento_identita: 'documento.pdf'
      };

      const filename = createDownloadFileName({
        filename: collaborator.documento_identita,
        fallbackName: 'documento_identita',
        extension: 'pdf',
        id: collaborator.id
      });

      expect(filename).toBe('documento.pdf');
    });

    it('dovrebbe gestire download curriculum con nome null', () => {
      const collaborator = {
        id: 456,
        first_name: 'null',
        last_name: 'Bianchi',
        curriculum: null
      };

      const filename = createDownloadFileName({
        filename: collaborator.curriculum,
        fallbackName: 'curriculum',
        extension: 'pdf',
        id: collaborator.id
      });

      expect(filename).toBe('curriculum_456.pdf');
    });

    it('dovrebbe gestire generazione nome contratto', () => {
      const assignment = {
        collaborator: {
          first_name: 'Mario',
          last_name: 'Rossi'
        },
        project: {
          name: 'Progetto Alpha'
        }
      };

      const collaboratorName = extractSafeName(
        assignment.collaborator,
        ['first_name', 'last_name'],
        'collaboratore'
      ).replace(/\s/g, '_');

      const projectName = extractSafeName(
        assignment.project,
        'name',
        'progetto'
      ).replace(/\s/g, '_');

      const filename = `contratto_${collaboratorName}_${projectName}.pdf`;

      expect(filename).toBe('contratto_Mario_Rossi_Progetto_Alpha.pdf');
    });

    it('dovrebbe gestire generazione nome contratto con valori null', () => {
      const assignment = {
        collaborator: {
          first_name: null,
          last_name: 'null'
        },
        project: {
          name: undefined
        }
      };

      const collaboratorName = extractSafeName(
        assignment.collaborator,
        ['first_name', 'last_name'],
        'collaboratore'
      );

      const projectName = extractSafeName(
        assignment.project,
        'name',
        'progetto'
      );

      const filename = `contratto_${collaboratorName}_${projectName}.pdf`;

      expect(filename).toBe('contratto_collaboratore_progetto.pdf');
    });
  });
});
