/**
 * COMPONENTE CALENDARIO OTTIMIZZATO
 * - Performance ottimizzate con memo e callback
 * - State management centralizzato con context
 * - Error handling avanzato
 * - Caching intelligente
 * - Loading states e skeleton UI
 */

import React, { useState, useEffect, useCallback, useMemo, memo } from 'react';
import { Calendar as BigCalendar, momentLocalizer } from 'react-big-calendar';
import moment from 'moment';
import 'moment/locale/it';  // Import locale italiana
import 'react-big-calendar/lib/css/react-big-calendar.css';

import { useAppContext } from '../context/AppContext';
import AttendanceModal from './AttendanceModal';
import LoadingSpinner from './LoadingSpinner';
import ErrorBoundary from './ErrorBoundary';
import './Calendar.css';

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

// Colori progetti memoizzati
const PROJECT_COLORS = [
  '#3174ad', '#e74c3c', '#2ecc71', '#f39c12',
  '#9b59b6', '#1abc9c', '#34495e', '#e67e22',
  '#95a5a6', '#f1c40f', '#e91e63', '#00bcd4'
];

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

/**
 * COMPONENTE CALENDARIO OTTIMIZZATO
 */
const Calendar = memo(() => {
  const {
    state,
    fetchEntity,
    createEntity,
    updateEntity,
    deleteEntity,
    openModal,
    closeModal,
    addNotification
  } = useAppContext();

  // Local state per UI
  const [selectedSlot, setSelectedSlot] = useState(null);
  const [currentView, setCurrentView] = useState('month');
  const [currentDate, setCurrentDate] = useState(new Date());
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Destructure da state
  const {
    attendances,
    collaborators,
    projects
  } = state;

  const isModalOpen = state.ui.modals.attendance?.isOpen || false;
  const selectedAttendance = state.ui.modals.attendance?.data || null;

  // Caricamento dati con cache intelligente
  useEffect(() => {
    const loadData = async () => {
      try {
        await Promise.all([
          fetchEntity('attendances'),
          fetchEntity('collaborators'),
          fetchEntity('projects')
        ]);
      } catch (error) {
        console.error('Error loading calendar data:', error);
      }
    };

    loadData();
  }, [fetchEntity]);

  // Auto-refresh quando cambia la vista o la data
  useEffect(() => {
    const shouldRefresh = () => {
      const now = Date.now();
      const lastFetch = attendances.lastFetch;
      const fiveMinutes = 5 * 60 * 1000;
      return !lastFetch || (now - lastFetch) > fiveMinutes;
    };

    if (shouldRefresh()) {
      fetchEntity('attendances', true);
    }
  }, [currentView, currentDate, fetchEntity, attendances.lastFetch]);

  // Refresh manuale
  const handleRefresh = useCallback(async () => {
    setIsRefreshing(true);
    try {
      await Promise.all([
        fetchEntity('attendances', true),
        fetchEntity('collaborators', true),
        fetchEntity('projects', true)
      ]);
      addNotification({
        type: 'success',
        message: 'Dati aggiornati con successo'
      });
    } catch (error) {
      console.error('Refresh error:', error);
    } finally {
      setIsRefreshing(false);
    }
  }, [fetchEntity, addNotification]);

  // Funzioni di utilità memoizzate per performance
  const getProjectColor = useCallback((projectId) => {
    return PROJECT_COLORS[projectId % PROJECT_COLORS.length];
  }, []);

  const getCollaboratorName = useCallback((collaboratorId) => {
    const collaborator = collaborators.data.find(c => c.id === collaboratorId);
    return collaborator ? `${collaborator.first_name} ${collaborator.last_name}` : 'Sconosciuto';
  }, [collaborators.data]);

  const getProjectName = useCallback((projectId) => {
    const project = projects.data.find(p => p.id === projectId);
    return project ? project.name : 'Progetto sconosciuto';
  }, [projects.data]);

  // Eventi calendario memoizzati per performance
  const calendarEvents = useMemo(() => {
    if (!attendances.data || !collaborators.data || !projects.data) {
      return [];
    }

    return attendances.data.map(attendance => {
      const collaboratorName = getCollaboratorName(attendance.collaborator_id);
      const projectName = getProjectName(attendance.project_id);
      const projectColor = getProjectColor(attendance.project_id);

      return {
        id: attendance.id,
        title: `${collaboratorName} - ${projectName}`,
        start: new Date(attendance.start_time),
        end: new Date(attendance.end_time),
        resource: attendance,
        style: {
          backgroundColor: projectColor,
          borderColor: projectColor,
          color: '#ffffff',
          border: 'none',
          borderRadius: '4px',
          fontSize: '12px',
          fontWeight: '500'
        }
      };
    });
  }, [attendances.data, collaborators.data, projects.data, getCollaboratorName, getProjectName, getProjectColor]);

  // Legenda progetti memoizzata
  const projectsLegend = useMemo(() => {
    return projects.data.map(project => ({
      id: project.id,
      name: project.name,
      color: getProjectColor(project.id),
      attendanceCount: attendances.data.filter(a => a.project_id === project.id).length
    }));
  }, [projects.data, attendances.data, getProjectColor]);

  // Gestori eventi ottimizzati con useCallback
  const handleSelectSlot = useCallback((slotInfo) => {
    // Permettiamo l'inserimento di presenze anche nel passato
    // (utile per correggere dimenticanze o inserimenti retroattivi)

    // Nota: se si vuole ripristinare il controllo, decommentare questo blocco:
    // const now = new Date();
    // now.setHours(0, 0, 0, 0);
    // const slotDate = new Date(slotInfo.start);
    // slotDate.setHours(0, 0, 0, 0);
    // if (slotDate < now) {
    //   addNotification({
    //     type: 'warning',
    //     title: 'Data non valida',
    //     message: 'Non puoi aggiungere presenze nel passato'
    //   });
    //   return;
    // }

    setSelectedSlot({
      start: slotInfo.start,
      end: slotInfo.end,
      date: slotInfo.start
    });

    openModal('attendance', null);
  }, [openModal, addNotification]);

  const handleSelectEvent = useCallback((event) => {
    setSelectedSlot(null);
    openModal('attendance', event.resource);
  }, [openModal]);

  const handleCloseModal = useCallback(() => {
    closeModal('attendance');
    setSelectedSlot(null);
  }, [closeModal]);

  const handleNavigate = useCallback((date, view) => {
    setCurrentDate(date);
    setCurrentView(view);
  }, []);

  const handleViewChange = useCallback((view) => {
    setCurrentView(view);
  }, []);

  // Gestori CRUD ottimizzati
  const handleSaveAttendance = useCallback(async (attendanceData) => {
    try {
      if (selectedAttendance) {
        await updateEntity('attendances', selectedAttendance.id, attendanceData);
      } else {
        await createEntity('attendances', attendanceData);
      }
      handleCloseModal();
    } catch (error) {
      console.error('Save error:', error);
    }
  }, [selectedAttendance, updateEntity, createEntity, handleCloseModal]);

  const handleDeleteAttendance = useCallback(async () => {
    if (!selectedAttendance) return;

    try {
      await deleteEntity('attendances', selectedAttendance.id);
      handleCloseModal();
    } catch (error) {
      console.error('Delete error:', error);
    }
  }, [selectedAttendance, deleteEntity, handleCloseModal]);

  // Event prop getter per performance
  const eventPropGetter = useCallback((event) => ({
    style: event.style
  }), []);

  // Loading states
  const isLoading = attendances.loading || collaborators.loading || projects.loading;
  const hasError = attendances.error || collaborators.error || projects.error;

  if (isLoading && !attendances.data.length) {
    return (
      <div className="calendar-container">
        <LoadingSpinner message="Caricamento calendario..." />
      </div>
    );
  }

  if (hasError && !attendances.data.length) {
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
              <h1>📅 Calendario Presenze</h1>
              <p>Gestisci le presenze dei collaboratori sui progetti</p>
            </div>
            <div className="header-actions">
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
                  className={currentView === 'month' ? 'active' : ''}
                  onClick={() => handleViewChange('month')}
                >
                  Mese
                </button>
                <button
                  className={currentView === 'week' ? 'active' : ''}
                  onClick={() => handleViewChange('week')}
                >
                  Settimana
                </button>
                <button
                  className={currentView === 'day' ? 'active' : ''}
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
              <span className="stat-number">{attendances.data.length}</span>
              <span className="stat-label">Presenze totali</span>
            </div>
            <div className="stat-item">
              <span className="stat-number">{collaborators.data.filter(c => c.is_active).length}</span>
              <span className="stat-label">Collaboratori attivi</span>
            </div>
            <div className="stat-item">
              <span className="stat-number">{projects.data.filter(p => p.is_active).length}</span>
              <span className="stat-label">Progetti attivi</span>
            </div>
          </div>
        </div>

        {/* LEGENDA PROGETTI OTTIMIZZATA */}
        {projectsLegend.length > 0 && (
          <div className="projects-legend">
            <h3>🏷️ Progetti ({projectsLegend.length})</h3>
            <div className="legend-items">
              {projectsLegend.map(project => (
                <div key={project.id} className="legend-item">
                  <div
                    className="legend-color"
                    style={{ backgroundColor: project.color }}
                  />
                  <span className="legend-name">{project.name}</span>
                  <span className="legend-count">({project.attendanceCount})</span>
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
            view={currentView}
            date={currentDate}
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
            collaborators={collaborators.data}
            projects={projects.data}
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