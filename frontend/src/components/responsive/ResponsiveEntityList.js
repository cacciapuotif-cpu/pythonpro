import React from 'react';
import useMobileLayout from '../../hooks/useMobileLayout';
import './ResponsiveEntityList.scss';

/**
 * Un'unica fonte dati con due rappresentazioni puramente responsive.
 * La logica di caricamento, filtro, paginazione e RBAC resta nel chiamante.
 */
const ResponsiveEntityList = ({
  listId,
  items,
  getItemKey = (item) => item.id,
  renderDesktop,
  renderCard,
  emptyIcon = '📋',
  emptyMessage = 'Nessun elemento trovato.',
  entityLabel = 'elementi',
  className = '',
}) => {
  const isMobile = useMobileLayout();
  if (!items.length) {
    return (
      <div className={`responsive-list-empty ${className}`} role="status">
        <span aria-hidden="true">{emptyIcon}</span>
        <p>{emptyMessage}</p>
      </div>
    );
  }

  return (
    <section
      className={`responsive-entity-list ${className}`.trim()}
      data-responsive-list={listId || entityLabel}
      aria-label={`Elenco ${entityLabel}`}
    >
      {isMobile ? (
        <ul className="responsive-list-mobile" data-responsive-layout="mobile">
          {items.map((item) => (
            <li key={getItemKey(item)} data-entity-id={getItemKey(item)}>
              {renderCard(item)}
            </li>
          ))}
        </ul>
      ) : (
        <div className="responsive-list-desktop" data-responsive-layout="desktop">
          {renderDesktop(items)}
        </div>
      )}
    </section>
  );
};

export default ResponsiveEntityList;
