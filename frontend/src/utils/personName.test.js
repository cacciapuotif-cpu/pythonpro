import { comparePeople, formatPersonName } from './personName';

test('formatta sempre cognome prima del nome per entrambi i modelli dati', () => {
  expect(formatPersonName({ first_name: 'Mario', last_name: 'Rossi' })).toBe('Rossi Mario');
  expect(formatPersonName({ nome: 'Ada', cognome: 'Lovelace' })).toBe('Lovelace Ada');
});

test('ordina senza distinguere maiuscole, accenti e con parità sul nome', () => {
  const people = [
    { first_name: 'Francesco', last_name: 'Cacciapuoti' },
    { first_name: 'Anna', last_name: 'Cacciapuoti' },
    { first_name: 'Luca', last_name: 'Dè Rossi' },
    { first_name: 'Marco', last_name: "D'Angelo" },
    { first_name: 'Nina', last_name: 'De Pietro' },
    { first_name: 'Zed', last_name: 'CACCIAPUOTI' },
  ];
  expect(people.sort(comparePeople).map(formatPersonName)).toEqual([
    'Cacciapuoti Anna', 'Cacciapuoti Francesco', 'CACCIAPUOTI Zed',
    "D'Angelo Marco", 'De Pietro Nina', 'Dè Rossi Luca',
  ]);
});
