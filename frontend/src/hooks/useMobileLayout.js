import { useEffect, useState } from 'react';

const getMobileQuery = () => {
  const token = window.getComputedStyle(document.documentElement)
    .getPropertyValue('--breakpoint-mobile-max')
    .trim();
  return token ? `(max-width: ${token})` : null;
};

const readMobileLayout = () => {
  const query = getMobileQuery();
  const media = query && window.matchMedia?.(query);
  return Boolean(media?.matches);
};

/**
 * Bridge JS verso il token Sass esportato come custom property globale.
 * Nessuna soglia responsive viene duplicata nei componenti.
 */
const useMobileLayout = () => {
  const [isMobile, setIsMobile] = useState(readMobileLayout);

  useEffect(() => {
    const query = getMobileQuery();
    if (!query || !window.matchMedia) return undefined;
    const media = window.matchMedia(query);
    if (!media) return undefined;
    const update = (event) => setIsMobile(event.matches);
    setIsMobile(media.matches);
    media.addEventListener?.('change', update);
    return () => media.removeEventListener?.('change', update);
  }, []);

  return isMobile;
};

export default useMobileLayout;
