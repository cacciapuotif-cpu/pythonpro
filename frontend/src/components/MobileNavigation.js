import React, { useEffect, useMemo, useRef, useState } from 'react';
import { normalizeRole, ROLES } from '../auth/permissions';
import { getPathForSection } from '../navigation/routes';

const ADMIN_OPERATOR_DESTINATIONS = Object.freeze([
  { id: 'home', label: 'Home', icon: '🏠', section: 'home' },
  { id: 'calendar', label: 'Calendario', icon: '📅', section: 'calendar' },
  { id: 'attendance', label: 'Presenze', icon: '✚', section: 'calendar', mode: 'attendance' },
  { id: 'proposals', label: 'Proposte', icon: '✅', section: 'agents-review', filters: { status: 'pending' } },
]);

const CONSULTATION_DESTINATIONS = Object.freeze([
  { id: 'home', label: 'Home', icon: '🏠', section: 'home' },
  { id: 'calendar', label: 'Calendario', icon: '📅', section: 'calendar' },
  { id: 'people', label: 'Persone', icon: '👥', section: 'collaborators' },
  { id: 'archive', label: 'Archivio', icon: '💬', section: 'archivio-chiedi' },
]);

const GROUP_LABELS = Object.freeze({
  Attività: 'Attività',
  Reportistica: 'Attività',
  Persone: 'Persone',
  Commerciale: 'Commerciale',
  Conoscenza: 'Conoscenza',
  Config: 'Amministrazione e strumenti',
});

export const getMobileDestinations = (role) => (
  normalizeRole(role) === ROLES.CONSULTATION
    ? CONSULTATION_DESTINATIONS
    : ADMIN_OPERATOR_DESTINATIONS
);

const groupSections = (sections) => {
  const groups = new Map();
  sections.forEach((section) => {
    const label = GROUP_LABELS[section.group] || (
      ['entities', 'utenti', 'agents-dashboard', 'agents', 'agents-review', 'templates'].includes(section.id)
        ? 'Amministrazione e strumenti'
        : 'Attività'
    );
    if (!groups.has(label)) groups.set(label, []);
    groups.get(label).push(section);
  });
  return Array.from(groups, ([label, items]) => ({ label, sections: items }));
};

const MobileNavigation = ({
  role,
  activeSection,
  activeMode,
  availableSections,
  menuOpen,
  onOpenMenu,
  onCloseMenu,
  onNavigate,
  onLogout,
}) => {
  const [query, setQuery] = useState('');
  const searchRef = useRef(null);
  const moreRef = useRef(null);
  const dialogRef = useRef(null);
  const destinations = getMobileDestinations(role);

  const primarySections = useMemo(
    () => new Set(destinations.map((destination) => destination.section)),
    [destinations],
  );
  const menuGroups = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase('it');
    return groupSections(
      availableSections.filter((section) => (
        !primarySections.has(section.id)
        && (!normalizedQuery || `${section.label} ${section.title}`
          .toLocaleLowerCase('it')
          .includes(normalizedQuery))
      )),
    );
  }, [availableSections, primarySections, query]);

  useEffect(() => {
    if (!menuOpen) {
      setQuery('');
      return undefined;
    }

    const previousOverflow = document.body.style.overflow;
    const moreTrigger = moreRef.current;
    document.body.style.overflow = 'hidden';
    window.requestAnimationFrame(() => searchRef.current?.focus());

    const trapFocus = (event) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        onCloseMenu();
        return;
      }
      if (event.key !== 'Tab' || !dialogRef.current) return;
      const focusable = Array.from(dialogRef.current.querySelectorAll(
        'button:not([disabled]), a[href], input:not([disabled])',
      ));
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
    document.addEventListener('keydown', trapFocus);

    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener('keydown', trapFocus);
      window.requestAnimationFrame(() => moreTrigger?.focus());
    };
  }, [menuOpen, onCloseMenu]);

  const selectDestination = (event, destination) => {
    event.preventDefault();
    onNavigate(destination.section, destination.filters || {}, { mode: destination.mode });
  };

  return (
    <>
      <nav className="mobile-bottom-navigation" aria-label="Navigazione mobile">
        {destinations.map((destination) => {
          const isActive = activeSection === destination.section
            && (
              destination.mode === 'attendance'
                ? activeMode === 'attendance'
                : activeMode !== 'attendance'
            );
          return (
            <a
              key={destination.id}
              href={destination.mode === 'attendance'
                ? '/presenze'
                : getPathForSection(destination.section)}
              className="mobile-nav-item"
              data-mobile-destination={destination.id}
              aria-current={isActive ? 'page' : undefined}
              onClick={(event) => selectDestination(event, destination)}
            >
              <span className="mobile-nav-icon" aria-hidden="true">{destination.icon}</span>
              <span>{destination.label}</span>
            </a>
          );
        })}
        <button
          ref={moreRef}
          type="button"
          className="mobile-nav-item"
          data-mobile-destination="more"
          aria-expanded={menuOpen}
          aria-controls="mobile-full-navigation"
          onClick={onOpenMenu}
        >
          <span className="mobile-nav-icon" aria-hidden="true">☰</span>
          <span>Altro</span>
        </button>
      </nav>

      {menuOpen && (
        <div
          ref={dialogRef}
          id="mobile-full-navigation"
          className="mobile-full-navigation"
          data-mobile-menu
          role="dialog"
          aria-modal="true"
          aria-labelledby="mobile-menu-title"
        >
          <header className="mobile-menu-header">
            <h2 id="mobile-menu-title">Tutte le funzioni</h2>
            <button type="button" className="mobile-menu-close" onClick={onCloseMenu} aria-label="Chiudi menu">
              ✕
            </button>
          </header>
          <div className="mobile-menu-search">
            <label htmlFor="mobile-menu-query">Cerca nel menu</label>
            <input
              ref={searchRef}
              id="mobile-menu-query"
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Cerca una funzione"
            />
          </div>
          <div className="mobile-menu-content">
            {menuGroups.map((group) => (
              <section key={group.label} className="mobile-menu-group" data-nav-group={group.label}>
                <h3>{group.label}</h3>
                <div className="mobile-menu-links">
                  {group.sections.map((section) => (
                    <a
                      key={section.id}
                      href={getPathForSection(section.id)}
                      data-section-id={section.id}
                      onClick={(event) => selectDestination(event, { section: section.id })}
                    >
                      <span aria-hidden="true">{section.icon}</span>
                      <span>
                        <strong>{section.label}</strong>
                        <small>{section.title}</small>
                      </span>
                    </a>
                  ))}
                </div>
              </section>
            ))}
            {menuGroups.length === 0 && (
              <p className="mobile-menu-empty" role="status">Nessuna funzione trovata.</p>
            )}
          </div>
          <footer className="mobile-menu-footer">
            <button type="button" onClick={onLogout}>Esci in sicurezza</button>
          </footer>
        </div>
      )}
    </>
  );
};

export default MobileNavigation;
