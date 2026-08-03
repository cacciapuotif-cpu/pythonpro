/**
 * COMPONENTE CALENDARIO OTTIMIZZATO
 * - Fetch server-side diretto (filtri mai applicati lato client su tutto il dataset)
 * - Barra filtri persistente (URL + localStorage per utente)
 * - Performance ottimizzate con memo e callback
 * - Error handling avanzato
 * - Loading states e skeleton UI
 */

import React, { useState, useEffect, useCallback, useMemo, memo } from 'react';
import { Calendar as BigCalendar, momentLocalizer } from 'react-big-calendar';
import moment from 'moment';
import { formatPersonName } from '../utils/personName';
import 'moment/locale/it';  // Import locale italiana
import 'react-big-calendar/lib/css/react-big-calendar.css';

import { useAppContext } from '../context/AppContext';
import apiService from '../services/apiService';
import AttendanceModal from './AttendanceModal';
import LoadingSpinner from './LoadingSpinner';
import ErrorBoundary from './ErrorBoundary';
import { canPerform } from '../auth/permissions';
import useDismissibleLayerHistory from '../hooks/useDismissibleLayerHistory';
import {
  DEFAULT_CALENDAR_FILTERS,
  MAX_RENDERABLE_EVENTS,
  filtersFromURL,
  filtersToParams,
  loadPersistedFilters,
  savePersistedFilters,
} from './calendar/calendarFilters';
import CalendarFilterBar from './calendar/CalendarFilterBar';
import './Calendar.scss';

// CONFIGURAZIONE LOCALE ITALIANA
moment.locale('it');
const localizer = momentLocalizer(moment);

// Configurazioni ottimizzate per performance
const CALENDAR_CONFIG = {
  step: 30,
  timeslots: 2,
  minTime: new Date(0, 0, 0, 7, 0, 0),
  maxTime: new Date(0, 0, 0, 20, 0, 0),
  dayLayoutAlgorithm: 'no-overlap'
};

// Colori progetti/collaboratori memoizzati
const PROJECT_COLORS = [
  '#3174ad', '#e74c3c', '#2ecc71', '#f39c12',
  '#9b59b6', '#1abc9c', '#34495e', '#e67e22',
  '#95a5a6', '#f1c40f', '#e91e63', '#00bcd4'
];

const VIEW_UNIT = {
  day: 'day',
  week: 'week',
  month: 'month',
};

/**
 * MESSAGGI DEL CALENDARIO IN ITALIANO
 * react-big-calendar supporta la localizzazione, qui definiamo tutti i testi
 */
const messages = {
  allDay: 'Tutto il giorno',
  previous: '◀ Precedente',
  next: 'Successivo ▶',
  today: 'Oggi',
  month: 'Mese',
  week: 'Settimana',
  day: 'Giorno',
  agenda: 'Agenda',
  date: 'Data',
  time: 'Orario',
  event: 'Presenza',
  showMore: total => `+ Altri ${total}`,
  noEventsInRange: 'Nessuna presenza in questo periodo.',
};

const dedupeById = (entities) => {
  const byId = new Map();
  entities.forEach((entity) => byId.set(entity.id, entity));
  return Array.from(byId.values());
};

/**
 * COMPONENTE CALENDARIO OTTIMIZZATO
 */
const Calendar = memo(({
  currentUser,
  initialFocus,
  mode = null,
  onConsumeFocus,
}) => {
  const {
    state,
    createEntity,
    updateEntity,
    deleteEntity,
    openModal,
    closeModal,
    addNotification
  } = useAppContext();

  // Filtri: URL ha priorità, poi localStorage per utente, poi default
  const [filters, setFilters] = useState(() => {
    const fromUrl = filtersFromURL();
    const hasUrlFilters = window.location.search.length > 0;
    if (hasUrlFilters) return fromUrl;
    return loadPersistedFilters(currentUser?.username) || DEFAULT_CALENDAR_FILTERS;
  });

  // Local state per UI
  const [selectedSlot, setSelectedSlot] = useState(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const canWriteAttendances = canPerform(currentUser, 'WRITE_ATTENDANCES');

  // Dati calendario: fetch diretto, mai dalla cache condivisa AppContext
  const [attendances, setAttendances] = useState({ items: [], total: 0 });
  const [loadingAttendances, setLoadingAttendances] = useState(true);
  const [attendancesError, setAttendancesError] = useState(null);

  const [projects, setProjects] = useState([]);
  const [collaborators, setCollaborators] = useState([]);
  const [loadingLookups, setLoadingLookups] = useState(true);
  const [lookupsError, setLookupsError] = useState(null);

  const isModalOpen = state.ui.modals.attendance?.isOpen || false;
  const selectedAttendance = state.ui.modals.attendance?.data || null;

  const loadLookups = useCallback(async () => {
    const [activeProjects, closedProjects, collaboratorsList] = await Promise.all([
      apiService.getProjects({}, { skip: 0, limit: 1000 }),
      apiService.getProjects({ isActive: false }, { skip: 0, limit: 1000 }),
      apiService.getCollaborators({}, { skip: 0, limit: 1000 }),
    ]);
    return {
      projectsList: dedupeById([...activeProjects, ...closedProjects]),
      collaboratorsList: collaboratorsList.items || collaboratorsList,
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    loadLookups()
      .then(({ projectsList, collaboratorsList }) => {
        if (cancelled) return;
        setProjects(projectsList);
        setCollaborators(collaboratorsList);
        setLookupsError(null);
      })
      .catch((error) => {
        if (cancelled) return;
        console.error('Errore caricamento progetti/collaboratori:', error);
        setLookupsError('Impossibile caricare progetti/collaboratori');
      })
      .finally(() => {
        if (!cancelled) setLoadingLookups(false);
      });
    return () => { cancelled = true; };
  }, [loadLookups]);

  // Intervallo di query: la vista corrente, allargata per includere sempre
  // "oggi" e "questa settimana" (usati dal pannello operativo) anche se
  // l'utente ha navigato altrove nel calendario. Resta un intervallo
  // delimitato: mai fetch-tutto-e-filtra-nel-browser.
  const queryRange = useMemo(() => {
    const viewUnit = VIEW_UNIT[filters.view] || 'month';
    const referenceDate = new Date(filters.date);
    const viewStart = moment(referenceDate).startOf(viewUnit).toDate();
    const viewEnd = moment(referenceDate).endOf(viewUnit).toDate();
    const now = new Date();
    const startOfWeek = moment(now).startOf('week').toDate();
    const endOfToday = moment(now).endOf('day').toDate();

    return {
      start: viewStart < startOfWeek ? viewStart : startOfWeek,
      end: viewEnd > endOfToday ? viewEnd : endOfToday,
    };
  }, [filters.view, filters.date]);

  const loadAttendances = useCallback(() => (
    apiService.getCalendarAttendances({
      startDate: queryRange.start.toISOString(),
      endDate: queryRange.end.toISOString(),
      collaboratorIds: filters.collaboratorIds,
      projectIds: filters.projectIds,
      includeClosedProjects: filters.includeClosedProjects,
      onlyMine: filters.onlyMine,
    })
  ), [queryRange, filters.collaboratorIds, filters.projectIds, filters.includeClosedProjects, filters.onlyMine]);

  useEffect(() => {
    let cancelled = false;
    setLoadingAttendances(true);
    loadAttendances()
      .then((res) => {
        if (cancelled) return;
        setAttendances(res);
        setAttendancesError(null);
        const query = filtersToParams(filters).toString();
        window.history.replaceState(
          window.history.state,
          '',
          `${window.location.pathname}${query ? `?${query}` : ''}`,
        );
        savePersistedFilters(currentUser?.username, filters);
      })
      .catch((error) => {
        if (cancelled) return;
        console.error('Errore caricamento presenze calendario:', error);
        setAttendancesError('Impossibile caricare le presenze');
      })
      .finally(() => {
        if (!cancelled) setLoadingAttendances(false);
      });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters, currentUser?.username]);

  const refreshAttendances = useCallback(() => {
    loadAttendances()
      .then(setAttendances)
      .catch((error) => console.error('Errore aggiornamento presenze calendario:', error));
  }, [loadAttendances]);

  const updateFilters = useCallback((partial) => {
    setFilters((previous) => ({ ...previous, ...partial }));
  }, []);

  const resetFilters = useCallback(() => {
    setFilters(DEFAULT_CALENDAR_FILTERS);
    window.history.replaceState({}, '', window.location.pathname);
  }, []);

  // Refresh manuale (ricarica sia le presenze del calendario che le lookup)
  const handleRefresh = useCallback(async () => {
    setIsRefreshing(true);
    try {
      const [attendancesRes, { projectsList, collaboratorsList }] = await Promise.all([
        loadAttendances(),
        loadLookups(),
      ]);
      setAttendances(attendancesRes);
      setProjects(projectsList);
      setCollaborators(collaboratorsList);
      addNotification({
        type: 'success',
        message: 'Dati aggiornati con successo'
      });
    } catch (error) {
      console.error('Refresh error:', error);
    } finally {
      setIsRefreshing(false);
    }
  }, [loadAttendances, loadLookups, addNotification]);

  const getCollaboratorName = useCallback((collaboratorId) => {
    const collaborator = collaborators.find(c => c.id === collaboratorId);
    return collaborator ? formatPersonName(collaborator) : 'Sconosciuto';
  }, [collaborators]);

  const getProjectName = useCallback((projectId) => {
    const project = projects.find(p => p.id === projectId);
    return project ? project.name : 'Progetto sconosciuto';
  }, [projects]);

  const getEntityColor = useCallback((entityId) => (
    PROJECT_COLORS[entityId % PROJECT_COLORS.length]
  ), []);

  // Legenda dinamica: colora per collaboratore quando sono selezionati più
  // collaboratori e al più un progetto, altrimenti per progetto (default).
  const colorDimension = filters.collaboratorIds.length > 1 && filters.projectIds.length <= 1
    ? 'collaborator'
    : 'project';

  const legendEntities = useMemo(() => (
    colorDimension === 'collaborator'
      ? collaborators.filter((c) => filters.collaboratorIds.length === 0 || filters.collaboratorIds.includes(c.id))
      : projects.filter((p) => (
        (filters.includeClosedProjects || p.is_active)
        && (filters.projectIds.length === 0 || filters.projectIds.includes(p.id))
      ))
  ), [
    colorDimension,
    collaborators,
    projects,
    filters.collaboratorIds,
    filters.projectIds,
    filters.includeClosedProjects,
  ]);

  // Eventi calendario memoizzati per performance
  const calendarEvents = useMemo(() => (
    attendances.items.map(attendance => {
      const collaboratorName = getCollaboratorName(attendance.collaborator_id);
      const projectName = getProjectName(attendance.project_id);
      const entityColor = getEntityColor(
        colorDimension === 'collaborator' ? attendance.collaborator_id : attendance.project_id
      );

      return {
        id: attendance.id,
        title: `${collaboratorName} - ${projectName}${attendance.delivery_sede_label ? ` · ${attendance.delivery_sede_label}` : ''}`,
        start: new Date(attendance.start_time),
        end: new Date(attendance.end_time),
        resource: attendance,
        style: {
          backgroundColor: entityColor,
          borderColor: entityColor,
          color: '#ffffff',
          border: 'none',
          borderRadius: '4px',
          fontSize: '12px',
          fontWeight: '500'
        }
      };
    })
  ), [attendances.items, getCollaboratorName, getProjectName, getEntityColor, colorDimension]);

  const operationsBoard = useMemo(() => {
    const now = new Date();
    const startOfToday = new Date(now);
    startOfToday.setHours(0, 0, 0, 0);
    const endOfToday = new Date(now);
    endOfToday.setHours(23, 59, 59, 999);

    const startOfWeek = moment(now).startOf('week').toDate();
    const endOfWeek = moment(now).endOf('week').toDate();

    const todayAttendances = attendances.items.filter((attendance) => {
      const start = new Date(attendance.start_time);
      return start >= startOfToday && start <= endOfToday;
    });

    const weekAttendances = attendances.items.filter((attendance) => {
      const start = new Date(attendance.start_time);
      return start >= startOfWeek && start <= endOfWeek;
    });

    const todayHours = todayAttendances.reduce((sum, attendance) => sum + Number(attendance.hours || 0), 0);
    const weekHours = weekAttendances.reduce((sum, attendance) => sum + Number(attendance.hours || 0), 0);

    const todayAgenda = todayAttendances
      .slice()
      .sort((left, right) => new Date(left.start_time) - new Date(right.start_time))
      .slice(0, 5);

    const collaboratorLoad = weekAttendances.reduce((accumulator, attendance) => {
      const key = attendance.collaborator_id;
      accumulator[key] = (accumulator[key] || 0) + Number(attendance.hours || 0);
      return accumulator;
    }, {});

    const heavyLoad = Object.entries(collaboratorLoad)
      .sort((left, right) => right[1] - left[1])
      .slice(0, 3)
      .map(([collaboratorId, hours]) => ({
        collaboratorId: Number(collaboratorId),
        name: getCollaboratorName(Number(collaboratorId)),
        hours,
      }));

    return {
      todayAttendances,
      weekAttendances,
      todayHours,
      weekHours,
      todayAgenda,
      heavyLoad,
    };
  }, [attendances.items, getCollaboratorName]);

  // Gestori eventi ottimizzati con useCallback
  const handleSelectSlot = useCallback((slotInfo) => {
    if (!canWriteAttendances) return;
    // Permettiamo l'inserimento di presenze anche nel passato
    // (utile per correggere dimenticanze o inserimenti retroattivi)
    setSelectedSlot({
      start: slotInfo.start,
      end: slotInfo.end,
      date: slotInfo.start
    });

    openModal('attendance', null);
  }, [canWriteAttendances, openModal]);

  const handleSelectEvent = useCallback((event) => {
    setSelectedSlot(null);
    openModal('attendance', event.resource);
  }, [openModal]);

  const dismissAttendanceModal = useCallback(() => {
    closeModal('attendance');
    setSelectedSlot(null);
  }, [closeModal]);
  const handleCloseModal = useDismissibleLayerHistory({
    id: 'attendance',
    open: isModalOpen,
    onDismiss: dismissAttendanceModal,
  });

  useEffect(() => {
    if (initialFocus !== 'new-attendance' || !canWriteAttendances) return;
    const start = new Date();
    start.setMinutes(0, 0, 0);
    const end = new Date(start);
    end.setHours(end.getHours() + 1);
    handleSelectSlot({ start, end });
    onConsumeFocus?.();
  }, [initialFocus, canWriteAttendances, handleSelectSlot, onConsumeFocus]);

  useEffect(() => () => closeModal('attendance'), [closeModal]);

  const handleNavigate = useCallback((date, view) => {
    updateFilters({ date: date.toISOString(), view });
  }, [updateFilters]);

  const handleViewChange = useCallback((view) => {
    updateFilters({ view });
  }, [updateFilters]);

  // Gestori CRUD ottimizzati
  const handleSaveAttendance = useCallback(async (attendanceData) => {
    try {
      if (selectedAttendance) {
        await updateEntity('attendances', selectedAttendance.id, attendanceData);
      } else {
        await createEntity('attendances', attendanceData);
      }
      handleCloseModal();
      refreshAttendances();
    } catch (error) {
      console.error('Save error:', error);
    }
  }, [selectedAttendance, updateEntity, createEntity, handleCloseModal, refreshAttendances]);

  const handleDeleteAttendance = useCallback(async () => {
    if (!selectedAttendance) return;

    try {
      await deleteEntity('attendances', selectedAttendance.id);
      handleCloseModal();
      refreshAttendances();
    } catch (error) {
      console.error('Delete error:', error);
    }
  }, [selectedAttendance, deleteEntity, handleCloseModal, refreshAttendances]);

  // Event prop getter per performance
  const eventPropGetter = useCallback((event) => ({
    style: event.style
  }), []);

  // Loading states
  const isLoading = loadingAttendances || loadingLookups;
  const hasError = attendancesError || lookupsError;
  const tooManyEvents = attendances.total > MAX_RENDERABLE_EVENTS;

  if (isLoading && !attendances.items.length) {
    return (
      <div className={`calendar-container ${mode === 'attendance' ? 'attendance-mode' : ''}`}>
        <LoadingSpinner message="Caricamento calendario..." />
      </div>
    );
  }

  if (hasError && !attendances.items.length) {
    return (
      <div className="calendar-container">
        <div className="error-state">
          <div className="error-icon">⚠️</div>
          <h3>Errore nel caricamento</h3>
          <p>{hasError}</p>
          <button onClick={handleRefresh} className="retry-button">
            Riprova
          </button>
        </div>
      </div>
    );
  }

  return (
    <ErrorBoundary>
      <div className="calendar-container">
        {/* HEADER MODERNO */}
        <div className="calendar-header">
          <div className="header-content">
            <div className="header-text">
              <h1>{mode === 'attendance' ? '✚ Presenze' : '📅 Calendario Presenze'}</h1>
              <p>
                {mode === 'attendance'
                  ? 'Consulta le presenze di oggi e registra una nuova attività'
                  : 'Gestisci le presenze dei collaboratori sui progetti'}
              </p>
            </div>
            <div className="header-actions">
              {mode === 'attendance' && canWriteAttendances && (
                <button
                  type="button"
                  className="attendance-primary-action"
                  onClick={() => {
                    const start = new Date();
                    const end = new Date(start);
                    end.setHours(end.getHours() + 1);
                    handleSelectSlot({ start, end });
                  }}
                >
                  ✚ Registra presenza
                </button>
              )}
              <button
                onClick={handleRefresh}
                disabled={isRefreshing}
                className="refresh-button"
                title="Aggiorna dati"
              >
                {isRefreshing ? '🔄' : '↻'} Aggiorna
              </button>
              <div className="view-selector">
                <button
                  className={filters.view === 'month' ? 'active' : ''}
                  onClick={() => handleViewChange('month')}
                >
                  Mese
                </button>
                <button
                  className={filters.view === 'week' ? 'active' : ''}
                  onClick={() => handleViewChange('week')}
                >
                  Settimana
                </button>
                <button
                  className={filters.view === 'day' ? 'active' : ''}
                  onClick={() => handleViewChange('day')}
                >
                  Giorno
                </button>
              </div>
            </div>
          </div>

          {/* STATISTICHE RAPIDE */}
          <div className="calendar-stats">
            <div className="stat-item">
              <span className="stat-number">{attendances.total}</span>
              <span className="stat-label">Presenze nel periodo</span>
            </div>
            <div className="stat-item">
              <span className="stat-number">{operationsBoard.todayAttendances.length}</span>
              <span className="stat-label">Presenze oggi</span>
            </div>
            <div className="stat-item">
              <span className="stat-number">{projects.filter(p => p.is_active).length}</span>
              <span className="stat-label">Progetti attivi</span>
            </div>
          </div>
        </div>

        <CalendarFilterBar
          filters={filters}
          projects={projects}
          collaborators={collaborators}
          eventCount={attendances.total}
          onChange={updateFilters}
          onReset={resetFilters}
        />

        <div className="calendar-ops-board">
          <div className="calendar-ops-card highlight">
            <span>Ore oggi</span>
            <strong>{operationsBoard.todayHours.toFixed(1)} h</strong>
            <small>{operationsBoard.todayAttendances.length} presenze registrate</small>
          </div>
          <div className="calendar-ops-card">
            <span>Ore settimana</span>
            <strong>{operationsBoard.weekHours.toFixed(1)} h</strong>
            <small>{operationsBoard.weekAttendances.length} presenze nel periodo</small>
          </div>
          <div className="calendar-ops-card agenda">
            <span>Agenda di oggi</span>
            {operationsBoard.todayAgenda.length > 0 ? (
              <ul className="calendar-agenda-list">
                {operationsBoard.todayAgenda.map((attendance) => (
                  <li key={attendance.id}>
                    <strong>{getCollaboratorName(attendance.collaborator_id)}</strong>
                    <small>
                      {moment(attendance.start_time).format('HH:mm')} - {getProjectName(attendance.project_id)}
                    </small>
                  </li>
                ))}
              </ul>
            ) : (
              <small>Nessuna presenza programmata oggi.</small>
            )}
          </div>
          <div className="calendar-ops-card">
            <span>Carico piu alto</span>
            {operationsBoard.heavyLoad.length > 0 ? (
              <ul className="calendar-load-list">
                {operationsBoard.heavyLoad.map((item) => (
                  <li key={item.collaboratorId}>
                    <strong>{item.name}</strong>
                    <small>{item.hours.toFixed(1)} h settimana</small>
                  </li>
                ))}
              </ul>
            ) : (
              <small>Nessun carico rilevato.</small>
            )}
          </div>
        </div>

        {/* LEGENDA DINAMICA: PROGETTI O COLLABORATORI */}
        {legendEntities.length > 0 && (
          <div className="projects-legend">
            <h3>🏷️ Legenda: {colorDimension === 'collaborator' ? 'Collaboratori' : 'Progetti'}</h3>
            <div className="legend-items">
              {legendEntities.map((entity) => (
                <div key={entity.id} className="legend-item">
                  <div
                    className="legend-color"
                    style={{ backgroundColor: getEntityColor(entity.id) }}
                  />
                  <span className="legend-name">
                    {colorDimension === 'collaborator' ? formatPersonName(entity) : entity.name}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* CALENDARIO PRINCIPALE OTTIMIZZATO */}
        <div className="calendar-wrapper">
          {isLoading && (
            <div className="calendar-loading-overlay">
              <LoadingSpinner size="small" message="Aggiornamento..." />
            </div>
          )}

          {tooManyEvents ? (
            <div className="calendar-too-many-events">
              <p>Troppi eventi da mostrare ({attendances.total}): restringi i filtri per continuare.</p>
            </div>
          ) : (
            <BigCalendar
              localizer={localizer}
              events={calendarEvents}
              messages={messages}
              startAccessor="start"
              endAccessor="end"
              style={{ height: 700 }}

              // Configurazioni ottimizzate
              selectable={true}
              longPressThreshold={0}
              onSelectSlot={handleSelectSlot}
              onSelectEvent={handleSelectEvent}
              onNavigate={handleNavigate}
              onView={handleViewChange}

              // Vista corrente
              view={filters.view}
              date={new Date(filters.date)}
              views={['month', 'week', 'day', 'agenda']}
              drilldownView="day"

              // Configurazioni orari
              {...CALENDAR_CONFIG}

              // Formatters
              formats={{
                timeGutterFormat: 'HH:mm',
                eventTimeRangeFormat: ({ start, end }) =>
                  `${moment(start).format('HH:mm')} - ${moment(end).format('HH:mm')}`,
                dayHeaderFormat: 'dddd DD/MM',
                monthHeaderFormat: 'MMMM YYYY',
                agendaDateFormat: 'DD/MM/YYYY',
                agendaTimeFormat: 'HH:mm',
                agendaTimeRangeFormat: ({ start, end }) =>
                  `${moment(start).format('HH:mm')} - ${moment(end).format('HH:mm')}`
              }}

              // Performance optimizations
              eventPropGetter={eventPropGetter}
              dayLayoutAlgorithm="no-overlap"
              showMultiDayTimes={true}
              popup={true}
              popupOffset={30}
            />
          )}
        </div>

        {/* MODAL OTTIMIZZATO */}
        {isModalOpen && (
          <AttendanceModal
            isOpen={isModalOpen}
            onClose={handleCloseModal}
            onSave={handleSaveAttendance}
            onDelete={handleDeleteAttendance}
            attendance={selectedAttendance}
            selectedSlot={selectedSlot}
            collaborators={collaborators}
            projects={projects}
            readOnly={!canWriteAttendances}
          />
        )}

        {/* OFFLINE INDICATOR */}
        {!state.system.isOnline && (
          <div className="offline-indicator">
            📵 Modalità offline - Le modifiche verranno sincronizzate alla riconnessione
          </div>
        )}
      </div>
    </ErrorBoundary>
  );
});

Calendar.displayName = 'Calendar';

export default Calendar;
