import { useCallback, useEffect, useRef } from 'react';

/**
 * Inserisce i layer applicativi nella cronologia senza perdere lo stato del
 * router. Back/gesture chiude prima il layer e solo dopo cambia pagina.
 */
const useDismissibleLayerHistory = ({ id, open, onDismiss }) => {
  const dismissRef = useRef(onDismiss);
  dismissRef.current = onDismiss;

  useEffect(() => {
    if (!open || window.history.state?.dismissibleLayer === id) return;
    window.history.pushState(
      { ...window.history.state, dismissibleLayer: id },
      '',
      `${window.location.pathname}${window.location.search}${window.location.hash}`,
    );
  }, [id, open]);

  useEffect(() => {
    const handlePopState = (event) => {
      if (open && event.state?.dismissibleLayer !== id) {
        dismissRef.current?.();
      }
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, [id, open]);

  return useCallback(() => {
    if (window.history.state?.dismissibleLayer === id) {
      window.history.back();
    } else {
      dismissRef.current?.();
    }
  }, [id]);
};

export default useDismissibleLayerHistory;
