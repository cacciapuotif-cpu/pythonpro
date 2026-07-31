import React from 'react';
import useMobileLayout from '../../hooks/useMobileLayout';
import './ResponsivePagination.scss';

const ResponsivePagination = ({
  page,
  pages,
  total,
  visibleCount,
  loading = false,
  onPageChange,
  pageSize,
  pageSizeOptions = [10, 20, 50, 100],
  onPageSizeChange,
  entityLabel = 'elementi',
}) => {
  const isMobile = useMobileLayout();
  if (pages <= 1) return null;

  if (isMobile) {
    const hasMore = page < pages;
    return (
      <div className="responsive-pagination mobile-pagination" data-pagination-layout="mobile">
        <p aria-live="polite">
          {visibleCount} di {total} {entityLabel}
        </p>
        {hasMore ? (
          <button
            type="button"
            className="btn-secondary load-more-button"
            data-load-more
            disabled={loading}
            onClick={() => onPageChange(page + 1)}
          >
            {loading ? 'Caricamento…' : 'Carica altri'}
          </button>
        ) : (
          <span className="pagination-end">Hai raggiunto la fine dell’elenco.</span>
        )}
      </div>
    );
  }

  return (
    <div className="responsive-pagination desktop-pagination" data-pagination-layout="desktop">
      <button type="button" disabled={page <= 1} onClick={() => onPageChange(1)} aria-label="Prima pagina">⏮</button>
      <button type="button" disabled={page <= 1} onClick={() => onPageChange(page - 1)} aria-label="Pagina precedente">‹</button>
      <span>Pag. {page} / {pages}</span>
      <button type="button" disabled={page >= pages} onClick={() => onPageChange(page + 1)} aria-label="Pagina successiva">›</button>
      <button type="button" disabled={page >= pages} onClick={() => onPageChange(pages)} aria-label="Ultima pagina">⏭</button>
      {onPageSizeChange ? (
        <select
          value={pageSize}
          onChange={(event) => onPageSizeChange(Number(event.target.value))}
          aria-label="Elementi per pagina"
        >
          {pageSizeOptions.map((size) => <option key={size} value={size}>{size} per pagina</option>)}
        </select>
      ) : null}
    </div>
  );
};

export default ResponsivePagination;
