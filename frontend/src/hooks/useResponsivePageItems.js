import { useEffect, useState } from 'react';

const getDefaultItemKey = (item) => item.id;

export const mergeUniqueItems = (current, next, getItemKey = getDefaultItemKey) => {
  const merged = new Map(current.map((item) => [getItemKey(item), item]));
  next.forEach((item) => merged.set(getItemKey(item), item));
  return Array.from(merged.values());
};

/**
 * Mantiene la paginazione numerica sul desktop e accumula le pagine su mobile.
 * Il chiamante continua a possedere fetch, filtri e autorizzazioni.
 */
const useResponsivePageItems = ({
  pageItems,
  page,
  isMobile,
  resetKey,
  getItemKey = getDefaultItemKey,
}) => {
  const [mobileItems, setMobileItems] = useState(pageItems);

  useEffect(() => {
    setMobileItems((current) => (
      page === 1
        ? pageItems
        : mergeUniqueItems(current, pageItems, getItemKey)
    ));
  }, [pageItems, page, resetKey, getItemKey]);

  if (!isMobile) return pageItems;
  return page === 1 ? pageItems : mobileItems;
};

export default useResponsivePageItems;
