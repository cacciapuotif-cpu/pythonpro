import { isValidNormalizedDate, normalizeDateValue } from './AllieviBulkImport';

describe('date import XLSX allievi', () => {
  test('normalizza una cella ExcelJS Date', () => {
    expect(normalizeDateValue(new Date(Date.UTC(1990, 4, 12)))).toBe('1990-05-12');
  });

  test.each([
    ['12/05/1990', '1990-05-12'],
    ['12.05.1990', '1990-05-12'],
    ['1990-05-12', '1990-05-12'],
    ['1990-05-12T00:00:00Z', '1990-05-12'],
  ])('normalizza %s in %s', (input, expected) => {
    expect(normalizeDateValue(input)).toBe(expected);
    expect(isValidNormalizedDate(expected)).toBe(true);
  });

  test('non considera valida una data impossibile', () => {
    const normalized = normalizeDateValue('31/02/1990');
    expect(normalized).toBe('31/02/1990');
    expect(isValidNormalizedDate(normalized)).toBe(false);
  });
});
