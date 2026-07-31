/** Convenzione unica per nominativi: COGNOME Nome. */
export const formatPersonName = (personOrFirst, maybeLast) => {
  const person = typeof personOrFirst === 'object' && personOrFirst !== null
    ? personOrFirst
    : { first_name: personOrFirst, last_name: maybeLast };
  let first = person.first_name ?? person.nome ?? '';
  let last = person.last_name ?? person.cognome ?? '';
  if (!first && !last && person.full_name) {
    const parts = String(person.full_name).trim().split(/\s+/);
    first = parts.shift() || '';
    last = parts.join(' ');
  }
  return [last, first].map((value) => String(value || '').trim()).filter(Boolean).join(' ');
};

export const personSortKey = (person) => formatPersonName(person)
  .normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('it-IT');

export const comparePeople = (left, right) => personSortKey(left).localeCompare(
  personSortKey(right), 'it', { sensitivity: 'base', ignorePunctuation: false },
);

export default formatPersonName;
