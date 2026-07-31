import React, { useEffect, useRef, useState } from 'react';
import useDismissibleLayerHistory from '../../hooks/useDismissibleLayerHistory';
import useMobileLayout from '../../hooks/useMobileLayout';
import './ResponsiveFilters.scss';

const ResponsiveFilters = ({
  children,
  activeCount = 0,
  onReset,
  title = 'Filtri',
  className = '',
  layerId = 'responsive-filters',
}) => {
  const isMobile = useMobileLayout();
  const [open, setOpen] = useState(false);
  const triggerRef = useRef(null);
  const closeButtonRef = useRef(null);
  const sheetRef = useRef(null);
  const wasOpenRef = useRef(false);
  const dismiss = useDismissibleLayerHistory({
    id: layerId,
    open,
    onDismiss: () => setOpen(false),
  });

  useEffect(() => {
    if (open) {
      closeButtonRef.current?.focus();
    } else if (wasOpenRef.current) {
      triggerRef.current?.focus();
    }
    wasOpenRef.current = open;
  }, [open]);

  useEffect(() => {
    if (!open) return undefined;
    const handleKeyDown = (event) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        dismiss();
        return;
      }
      if (event.key !== 'Tab') return;
      const focusable = Array.from(sheetRef.current?.querySelectorAll(
        'button:not([disabled]), input:not([disabled]), select:not([disabled]), [href], [tabindex]:not([tabindex="-1"])',
      ) || []);
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [dismiss, open]);

  useEffect(() => {
    if (!isMobile && open) dismiss();
  }, [dismiss, isMobile, open]);

  if (!isMobile) return <div className={className}>{children}</div>;

  return (
    <div className="responsive-filters">
      <button
        ref={triggerRef}
        type="button"
        className="responsive-filters-trigger"
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={() => setOpen(true)}
      >
        Filtri{activeCount ? ` (${activeCount})` : ''}
      </button>
      {open ? (
        <div className="responsive-filters-overlay" role="presentation" onMouseDown={(event) => {
          if (event.target === event.currentTarget) dismiss();
        }}>
          <section ref={sheetRef} className="responsive-filters-sheet" role="dialog" aria-modal="true" aria-label={title}>
            <header>
              <div><strong>{title}</strong><span>{activeCount} attivi</span></div>
              <button ref={closeButtonRef} type="button" aria-label="Chiudi filtri" onClick={dismiss}>×</button>
            </header>
            <div className={`responsive-filters-content ${className}`.trim()}>{children}</div>
            <footer>
              <button type="button" className="btn-secondary" onClick={onReset} disabled={!activeCount}>Azzera</button>
              <button type="button" className="btn-primary" onClick={dismiss}>Mostra risultati</button>
            </footer>
          </section>
        </div>
      ) : null}
    </div>
  );
};

export default ResponsiveFilters;
