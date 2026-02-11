/**
 * CALENDARIO SEMPLIFICATO - Versione funzionante senza context complesso
 */

import React, { useState, useEffect } from 'react';
import { Calendar as BigCalendar, momentLocalizer } from 'react-big-calendar';
import moment from 'moment';
import 'moment/locale/it';  // Import locale italiana
import 'react-big-calendar/lib/css/react-big-calendar.css';
import ErrorBanner from './ErrorBanner';
import { getAttendances, getCollaborators, getProjects } from '../services/apiService';

// Configurazione locale italiana
moment.locale('it');
const localizer = momentLocalizer(moment);

// Messaggi in italiano
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
  time: 'Ora',
  event: 'Evento',
  noEventsInRange: 'Nessuna presenza in questo periodo',
  showMore: total => `+ Altri ${total}`
};

// Colori per i progetti
const PROJECT_COLORS = [
  '#3174ad', '#e74c3c', '#2ecc71', '#f39c12',
  '#9b59b6', '#1abc9c', '#34495e', '#e67e22'
];

const CalendarSimple = () => {
  const [attendances, setAttendances] = useState([]);
  const [collaborators, setCollaborators] = useState([]);
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Carica i dati al mount
  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);

      // Carica tutti i dati in parallelo
      const [attendancesData, collaboratorsData, projectsData] = await Promise.all([
        getAttendances(),
        getCollaborators(),
        getProjects()
      ]);

      setAttendances(attendancesData);
      setCollaborators(collaboratorsData);
      setProjects(projectsData);
    } catch (err) {
      console.error('Error loading data:', err);
      setError('Errore nel caricamento dei dati: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  // Converte le presenze in eventi per il calendario
  const calendarEvents = attendances.map(attendance => {
    const collaborator = collaborators.find(c => c.id === attendance.collaborator_id);
    const project = projects.find(p => p.id === attendance.project_id);

    return {
      id: attendance.id,
      title: `${collaborator?.first_name || 'N/A'} ${collaborator?.last_name || ''} - ${project?.name || 'Progetto N/A'}`,
      start: new Date(attendance.start_time),
      end: new Date(attendance.end_time),
      resource: {
        attendance,
        collaborator,
        project,
        color: PROJECT_COLORS[attendance.project_id % PROJECT_COLORS.length]
      }
    };
  });

  // Stile personalizzato per gli eventi
  const eventStyleGetter = (event) => {
    const backgroundColor = event.resource?.color || '#3174ad';
    return {
      style: {
        backgroundColor,
        borderRadius: '5px',
        opacity: 0.8,
        color: 'white',
        border: '0px',
        display: 'block'
      }
    };
  };

  // Gestione click su evento
  const handleSelectEvent = (event) => {
    const { attendance, collaborator, project } = event.resource;
    alert(`
Dettagli Presenza:
• Collaboratore: ${collaborator?.first_name} ${collaborator?.last_name}
• Progetto: ${project?.name}
• Data: ${moment(attendance.date).format('DD/MM/YYYY')}
• Orario: ${moment(attendance.start_time).format('HH:mm')} - ${moment(attendance.end_time).format('HH:mm')}
• Ore: ${attendance.hours}
• Note: ${attendance.notes || 'Nessuna nota'}
    `);
  };

  // Gestione click su slot vuoto
  const handleSelectSlot = (slotInfo) => {
    alert(`
Slot selezionato:
• Data: ${moment(slotInfo.start).format('DD/MM/YYYY')}
• Ora: ${moment(slotInfo.start).format('HH:mm')}

Per aggiungere una presenza, usa la sezione "Collaboratori" o "Progetti".
    `);
  };

  if (loading) {
    return (
      <div style={{ padding: '20px', textAlign: 'center' }}>
        <h2>📅 Calendario Presenze</h2>
        <p>Caricamento dati...</p>
        <div style={{
          border: '4px solid #f3f3f3',
          borderTop: '4px solid #3498db',
          borderRadius: '50%',
          width: '30px',
          height: '30px',
          animation: 'spin 1s linear infinite',
          margin: '20px auto'
        }}></div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: '20px', textAlign: 'center' }}>
        <h2>📅 Calendario Presenze</h2>
        <div style={{ color: 'red', marginBottom: '20px' }}>
          ⚠️ <ErrorBanner error={error} />
        </div>
        <button
          onClick={loadData}
          style={{
            padding: '10px 20px',
            backgroundColor: '#3498db',
            color: 'white',
            border: 'none',
            borderRadius: '5px',
            cursor: 'pointer'
          }}
        >
          🔄 Riprova
        </button>
      </div>
    );
  }

  return (
    <div style={{ padding: '20px' }}>
      <div style={{ marginBottom: '20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2>📅 Calendario Presenze</h2>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button
            onClick={loadData}
            style={{
              padding: '8px 16px',
              backgroundColor: '#2ecc71',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
          >
            🔄 Aggiorna
          </button>
          <div style={{
            padding: '8px 12px',
            backgroundColor: '#ecf0f1',
            borderRadius: '4px',
            fontSize: '14px'
          }}>
            📊 {attendances.length} presenze registrate
          </div>
        </div>
      </div>

      <div style={{ height: '600px', backgroundColor: 'white', border: '1px solid #ddd', borderRadius: '8px' }}>
        <BigCalendar
          localizer={localizer}
          events={calendarEvents}
          startAccessor="start"
          endAccessor="end"
          messages={messages}
          onSelectEvent={handleSelectEvent}
          onSelectSlot={handleSelectSlot}
          selectable
          eventPropGetter={eventStyleGetter}
          style={{ height: '100%', padding: '10px' }}
          views={['month', 'week', 'day', 'agenda']}
          defaultView="month"
          popup
          showMultiDayTimes
          step={30}
          timeslots={2}
        />
      </div>

      {/* Legenda colori progetti */}
      <div style={{ marginTop: '20px', padding: '15px', backgroundColor: '#f8f9fa', borderRadius: '8px' }}>
        <h4>🎨 Legenda Progetti:</h4>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px' }}>
          {projects.map((project, index) => (
            <div key={project.id} style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
              <div
                style={{
                  width: '16px',
                  height: '16px',
                  backgroundColor: PROJECT_COLORS[project.id % PROJECT_COLORS.length],
                  borderRadius: '3px'
                }}
              ></div>
              <span style={{ fontSize: '14px' }}>{project.name}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default CalendarSimple;