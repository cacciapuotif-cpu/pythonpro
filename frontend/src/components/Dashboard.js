import React, { useCallback, useEffect, useMemo, useState } from 'react';
import apiService from '../services/apiService';
import { getAgentCommunications, getAgentSuggestions } from '../services/apiService';
import './Dashboard.css';

const formatNumber = (value) => new Intl.NumberFormat('it-IT').format(Number(value || 0));

const formatHours = (value) => `${new Intl.NumberFormat('it-IT', { maximumFractionDigits: 1 }).format(Number(value || 0))} h`;

const formatDate = (value) => {
  if (!value) {
    return 'Non impostata';
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return 'Non impostata';
  }

  return parsed.toLocaleDateString('it-IT');
};

const getDocumentAlert = (collaborator) => {
  if (!collaborator?.documento_identita_filename) {
    return {
      severity: 'critical',
      title: 'Documento identita assente',
      detail: 'Caricare il documento prima di procedere con attivita contrattuali.',
      dueLabel: 'File mancante',
    };
  }

  if (!collaborator?.documento_identita_scadenza) {
    return {
      severity: 'warning',
      title: 'Scadenza documento non impostata',
      detail: 'Il file e presente ma la data di scadenza non e censita.',
      dueLabel: 'Data mancante',
    };
  }

  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const expiryDate = new Date(collaborator.documento_identita_scadenza);
  expiryDate.setHours(0, 0, 0, 0);

  if (Number.isNaN(expiryDate.getTime())) {
    return {
      severity: 'warning',
      title: 'Scadenza documento non valida',
      detail: 'La data salvata non puo essere interpretata correttamente.',
      dueLabel: 'Dato non valido',
    };
  }

  const diffDays = Math.ceil((expiryDate - today) / (1000 * 60 * 60 * 24));

  if (diffDays < 0) {
    return {
      severity: 'critical',
      title: 'Documento scaduto',
      detail: `Il documento e scaduto il ${formatDate(expiryDate)}.`,
      dueLabel: `${Math.abs(diffDays)} giorni fa`,
    };
  }

  if (diffDays <= 30) {
    return {
      severity: 'warning',
      title: 'Documento in scadenza',
      detail: `Rinnovo richiesto entro il ${formatDate(expiryDate)}.`,
      dueLabel: `${diffDays} giorni`,
    };
  }

  return null;
};

const getAssignmentAlert = (assignment, collaboratorsMap, projectsMap) => {
  const collaboratorName = collaboratorsMap.get(assignment.collaborator_id) || `Collaboratore #${assignment.collaborator_id}`;
  const projectName = projectsMap.get(assignment.project_id) || `Progetto #${assignment.project_id}`;
  const startDate = assignment?.start_date ? new Date(assignment.start_date) : null;
  const endDate = assignment?.end_date ? new Date(assignment.end_date) : null;

  if (!assignment?.contract_type) {
    return {
      severity: 'critical',
      title: 'Assegnazione senza tipo contratto',
      detail: `${collaboratorName} su ${projectName} non ha il tipo contratto impostato.`,
      dueLabel: 'Preflight richiesto',
    };
  }

  if (!assignment?.hourly_rate || !assignment?.assigned_hours) {
    return {
      severity: 'warning',
      title: 'Assegnazione incompleta',
      detail: `${collaboratorName} su ${projectName} ha ore o tariffa mancanti.`,
      dueLabel: 'Dati economici',
    };
  }

  if (startDate && endDate && startDate > endDate) {
    return {
      severity: 'critical',
      title: 'Date assegnazione incoerenti',
      detail: `${collaboratorName} su ${projectName} ha data fine precedente alla data inizio.`,
      dueLabel: 'Correggere periodo',
    };
  }

  if (assignment?.is_active && endDate && !Number.isNaN(endDate.getTime())) {
    const now = new Date();
    now.setHours(0, 0, 0, 0);
    const threshold = Math.ceil((endDate - now) / (1000 * 60 * 60 * 24));

    if (threshold <= 14) {
      return {
        severity: threshold < 0 ? 'critical' : 'info',
        title: threshold < 0 ? 'Assegnazione oltre termine' : 'Assegnazione in chiusura',
        detail: `${collaboratorName} su ${projectName} termina il ${formatDate(endDate)}.`,
        dueLabel: threshold < 0 ? `${Math.abs(threshold)} giorni fa` : `${threshold} giorni`,
      };
    }
  }

  return null;
};

const getProjectAlert = (project) => {
  if (!project?.end_date || project?.status !== 'active') {
    return null;
  }

  const endDate = new Date(project.end_date);
  if (Number.isNaN(endDate.getTime())) {
    return null;
  }

  const now = new Date();
  now.setHours(0, 0, 0, 0);
  endDate.setHours(0, 0, 0, 0);

  if (endDate < now) {
    return {
      severity: 'warning',
      title: 'Progetto attivo oltre scadenza',
      detail: `${project.name} risulta ancora attivo ma e terminato il ${formatDate(endDate)}.`,
      dueLabel: 'Verificare stato',
    };
  }

  return null;
};

const ROLE_COCKPITS = {
  admin: {
    label: 'Amministratore',
    title: 'Vista di governo del sistema',
    intro: 'Presidia dati, configurazioni e blocchi che possono fermare il ciclo operativo.',
  },
  manager: {
    label: 'Operatore',
    title: 'Vista operativa del team',
    intro: 'Concentrati sulle attivita da sbloccare oggi: documenti, presenze e contratti.',
  },
  user: {
    label: 'Operatore',
    title: 'Vista operativa del team',
    intro: 'Concentrati sulle attivita da sbloccare oggi: documenti, presenze e contratti.',
  },
};

const Dashboard = ({ currentUser }) => {
  const [state, setState] = useState({
    loading: true,
    refreshing: false,
    error: '',
    data: null,
  });

  const loadDashboard = useCallback(async ({ silent = false } = {}) => {
    setState((previous) => ({
      ...previous,
      loading: silent ? previous.loading : true,
      refreshing: silent,
      error: '',
    }));

    const requests = await Promise.allSettled([
      apiService.getSummaryReport(),
      apiService.getTimesheetReport(),
      apiService.getCollaborators({}, { limit: 1000 }),
      apiService.getProjects({}, { limit: 1000 }),
      apiService.getAssignments({ limit: 1000 }),
      apiService.getContractTemplates({ limit: 200 }),
      currentUser?.role === 'admin' ? apiService.getSystemMetrics() : Promise.resolve(null),
      getAgentSuggestions({ agent_name: 'data_quality', entity_type: 'collaborator', limit: 200 }),
      getAgentCommunications({ agent_name: 'data_quality', recipient_type: 'collaborator', limit: 200 }),
    ]);

    const [
      summaryResult,
      timesheetResult,
      collaboratorsResult,
      projectsResult,
      assignmentsResult,
      templatesResult,
      metricsResult,
      agentSuggestionsResult,
      agentCommunicationsResult,
    ] = requests;

    const summary = summaryResult.status === 'fulfilled' ? summaryResult.value : null;
    const timesheet = timesheetResult.status === 'fulfilled' ? timesheetResult.value : null;
    const collaborators = collaboratorsResult.status === 'fulfilled' ? collaboratorsResult.value : [];
    const projects = projectsResult.status === 'fulfilled' ? projectsResult.value : [];
    const assignments = assignmentsResult.status === 'fulfilled' ? assignmentsResult.value : [];
    const contractTemplates = templatesResult.status === 'fulfilled' ? templatesResult.value : [];
    const metrics = metricsResult.status === 'fulfilled' ? metricsResult.value : null;
    const agentSuggestions = agentSuggestionsResult.status === 'fulfilled' ? agentSuggestionsResult.value : [];
    const agentCommunications = agentCommunicationsResult.status === 'fulfilled' ? agentCommunicationsResult.value : [];

    if (!summary && !timesheet && collaborators.length === 0 && projects.length === 0 && assignments.length === 0) {
      setState({
        loading: false,
        refreshing: false,
        error: 'Impossibile recuperare i dati del cockpit operativo.',
        data: null,
      });
      return;
    }

    setState({
      loading: false,
      refreshing: false,
      error: '',
      data: {
        summary,
        timesheet,
        collaborators,
        projects,
        assignments,
        contractTemplates,
        metrics,
        agentSuggestions,
        agentCommunications,
        lastUpdatedAt: new Date().toISOString(),
      },
    });
  }, [currentUser?.role]);

  useEffect(() => {
    loadDashboard();
  }, [loadDashboard]);

  const computed = useMemo(() => {
    if (!state.data) {
      return null;
    }

    const {
      summary,
      timesheet,
      collaborators,
      projects,
      assignments,
      contractTemplates,
      metrics,
      agentSuggestions,
      agentCommunications,
      lastUpdatedAt,
    } = state.data;

    const collaboratorsMap = new Map(
      collaborators.map((collaborator) => [collaborator.id, `${collaborator.first_name} ${collaborator.last_name}`])
    );
    const projectsMap = new Map(projects.map((project) => [project.id, project.name]));

    const documentAlerts = collaborators
      .map((collaborator) => {
        const alert = getDocumentAlert(collaborator);
        if (!alert) {
          return null;
        }

        return {
          id: `document-${collaborator.id}`,
          area: 'Documenti',
          owner: `${collaborator.first_name} ${collaborator.last_name}`,
          ...alert,
        };
      })
      .filter(Boolean);

    const assignmentAlerts = assignments
      .map((assignment) => {
        const alert = getAssignmentAlert(assignment, collaboratorsMap, projectsMap);
        if (!alert) {
          return null;
        }

        return {
          id: `assignment-${assignment.id}`,
          area: 'Contratti e assegnazioni',
          owner: collaboratorsMap.get(assignment.collaborator_id) || `Collaboratore #${assignment.collaborator_id}`,
          ...alert,
        };
      })
      .filter(Boolean);

    const projectAlerts = projects
      .map((project) => {
        const alert = getProjectAlert(project);
        if (!alert) {
          return null;
        }

        return {
          id: `project-${project.id}`,
          area: 'Progetti',
          owner: project.name,
          ...alert,
        };
      })
      .filter(Boolean);

    const activeDefaultTemplates = new Set(
      contractTemplates
        .filter((template) => template?.is_active && template?.is_default && template?.tipo_contratto)
        .map((template) => template.tipo_contratto)
    );
    const requiredContractTypes = Array.from(
      new Set(
        assignments
          .map((assignment) => assignment?.contract_type)
          .filter(Boolean)
      )
    );
    const missingTemplateAlerts = requiredContractTypes
      .filter((contractType) => !activeDefaultTemplates.has(contractType))
      .map((contractType) => ({
        id: `contract-template-${contractType}`,
        area: 'Template contratti',
        owner: contractType,
        severity: 'critical',
        title: 'Template default mancante',
        detail: `Manca un template attivo di default per il tipo contratto "${contractType}".`,
        dueLabel: 'Generazione a rischio',
      }));

    const communicationsBySuggestionId = agentCommunications.reduce((accumulator, item) => {
      if (!item.suggestion_id) {
        return accumulator;
      }
      accumulator[item.suggestion_id] = accumulator[item.suggestion_id] || [];
      accumulator[item.suggestion_id].push(item);
      return accumulator;
    }, {});

    const agentWorkflowAlerts = agentSuggestions
      .filter((item) => item.entity_type === 'collaborator' && ['pending', 'waiting', 'approved', 'sent', 'followup_due'].includes(item.status))
      .map((item) => {
        const collaboratorName = collaboratorsMap.get(item.entity_id) || `Collaboratore #${item.entity_id}`;
        const linkedCommunications = communicationsBySuggestionId[item.id] || [];
        const channels = linkedCommunications.map((entry) => entry.channel).filter(Boolean).join(', ');
        const triggerLabel = item.status === 'followup_due'
          ? 'Sollecito operatore richiesto'
          : item.status === 'sent'
            ? 'In attesa risposta'
            : 'Valutazione operatore';

        return {
          id: `agent-${item.id}`,
          area: 'Agenti automatici',
          owner: collaboratorName,
          severity: item.status === 'followup_due'
            ? 'warning'
            : item.severity === 'high'
              ? 'critical'
              : item.severity === 'medium'
                ? 'warning'
                : 'info',
          title: item.title,
          detail: `${item.description}${channels ? ` Canali pronti: ${channels}.` : ''}`,
          dueLabel: triggerLabel,
        };
      });

    const alerts = [...agentWorkflowAlerts, ...documentAlerts, ...assignmentAlerts, ...projectAlerts, ...missingTemplateAlerts]
      .sort((left, right) => {
        const priority = { critical: 0, warning: 1, info: 2 };
        return priority[left.severity] - priority[right.severity];
      });

    const kpiFromSummary = summary?.kpi_generali || {};
    const activeProjects = projects.filter((project) => project.status === 'active').length;
    const activeAssignments = assignments.filter((assignment) => assignment.is_active).length;
    const totalAttendances = Number(kpiFromSummary.totale_presenze ?? timesheet?.totali?.numero_presenze ?? 0);
    const totalHours = Number(kpiFromSummary.totale_ore_lavorate ?? timesheet?.totali?.ore_totali ?? 0);
    const topProjects = summary?.top_5_progetti || [];
    const topCollaborators = summary?.top_5_collaboratori || [];
    const contractDistribution = summary?.distribuzione_contratti || [];
    const dashboardMetrics = metrics?.dashboard_metrics || {};
    const roleConfig = ROLE_COCKPITS[currentUser?.role] || ROLE_COCKPITS.user;
    const operatorTasks = [
      {
        label: 'Documenti da completare',
        value: formatNumber(documentAlerts.length),
        detail: documentAlerts.length > 0 ? 'Sollecitare anagrafica o rinnovi.' : 'Perimetro documentale sotto controllo.',
      },
      {
        label: 'Pratiche agenti',
        value: formatNumber(agentWorkflowAlerts.length),
        detail: agentWorkflowAlerts.length > 0 ? 'Inbox operatore con richieste e follow-up.' : 'Nessuna pratica automatica aperta.',
      },
      {
        label: 'Preflight contratti',
        value: formatNumber(assignmentAlerts.length),
        detail: assignmentAlerts.length > 0 ? 'Assegnazioni da completare prima del PDF.' : 'Nessun blocco contrattuale urgente.',
      },
      {
        label: 'Template mancanti',
        value: formatNumber(missingTemplateAlerts.length),
        detail: missingTemplateAlerts.length > 0 ? 'Serve attivare i default per i tipi in uso.' : 'Tutti i tipi in uso hanno un default attivo.',
      },
      {
        label: 'Progetti da verificare',
        value: formatNumber(projectAlerts.length),
        detail: projectAlerts.length > 0 ? 'Controllare stato e date di chiusura.' : 'Nessun progetto attivo oltre termine.',
      },
    ];
    const adminTasks = [
      {
        label: 'Blocchi critici',
        value: formatNumber(alerts.filter((item) => item.severity === 'critical').length),
        detail: 'Priorita da risolvere per non fermare l’operativita.',
      },
      {
        label: 'Workflow agenti',
        value: formatNumber(agentWorkflowAlerts.length),
        detail: agentWorkflowAlerts.length > 0 ? 'Pratiche automatiche aperte su collaboratori.' : 'Nessuna pratica automatica aperta.',
      },
      {
        label: 'Metriche backend',
        value: formatNumber(Object.keys(dashboardMetrics).length),
        detail: metrics ? 'Metriche esposte dal backend disponibili.' : 'Metriche non disponibili nel dataset corrente.',
      },
      {
        label: 'Distribuzione contratti',
        value: formatNumber(contractDistribution.length),
        detail: contractDistribution.length > 0 ? 'Tipologie contrattuali gia monitorate.' : 'Nessun dato contrattuale aggregato disponibile.',
      },
      {
        label: 'Default contratti',
        value: formatNumber(activeDefaultTemplates.size),
        detail: missingTemplateAlerts.length > 0 ? 'Mancano ancora alcuni template di default richiesti.' : 'Copertura default coerente coi tipi attivi.',
      },
    ];

    return {
      roleConfig,
      heroStatus: alerts.some((item) => item.severity === 'critical')
        ? 'Ci sono priorita bloccanti da gestire oggi.'
        : alerts.length > 0
          ? 'Il sistema e sotto controllo, ma ci sono task operativi aperti.'
          : 'Nessuna anomalia rilevata nel perimetro monitorato.',
      lastUpdatedAt,
      kpis: [
        {
          label: 'Collaboratori',
          value: formatNumber(kpiFromSummary.totale_collaboratori ?? collaborators.length),
          note: `${documentAlerts.length} alert documentali / ${agentWorkflowAlerts.length} pratiche agenti`,
        },
        {
          label: 'Progetti attivi',
          value: formatNumber(activeProjects || kpiFromSummary.totale_progetti || projects.length),
          note: `${projects.length} progetti totali censiti`,
        },
        {
          label: 'Assegnazioni attive',
          value: formatNumber(activeAssignments),
          note: `${assignmentAlerts.length} criticita di preflight`,
        },
        {
          label: 'Ore registrate',
          value: formatHours(totalHours),
          note: `${formatNumber(totalAttendances)} presenze nel perimetro report`,
        },
        {
          label: 'Enti attuatori',
          value: formatNumber(kpiFromSummary.totale_enti_attuatori ?? 0),
          note: 'Dato da summary report',
        },
        {
          label: 'Alert aperti',
          value: formatNumber(alerts.length),
          note: alerts.length > 0 ? 'Centro compliance attivo' : 'Nessuna azione urgente',
        },
      ],
      alerts,
      alertCounters: {
        critical: alerts.filter((item) => item.severity === 'critical').length,
        warning: alerts.filter((item) => item.severity === 'warning').length,
        info: alerts.filter((item) => item.severity === 'info').length,
        success: alerts.length === 0 ? 1 : 0,
      },
      topProjects,
      topCollaborators,
      contractDistribution,
      systemMetrics: dashboardMetrics,
      summaryWindow: summary?.periodo,
      roleTasks: currentUser?.role === 'admin' ? adminTasks : operatorTasks,
    };
  }, [currentUser?.role, state.data]);

  if (state.loading) {
    return (
      <div className="dashboard-loading" aria-live="polite">
        <div className="dashboard-skeleton">
          <div className="dashboard-skeleton-block" />
          <div className="dashboard-skeleton-block" />
          <div className="dashboard-skeleton-block" />
        </div>
      </div>
    );
  }

  if (state.error) {
    return (
      <div className="dashboard-error" role="alert">
        <h2>Dashboard operativa non disponibile</h2>
        <p>{state.error}</p>
        <button type="button" className="retry-button" onClick={() => loadDashboard()}>
          Riprova caricamento
        </button>
      </div>
    );
  }

  if (!computed) {
    return (
      <div className="dashboard-empty">
        <h2>Dashboard operativa vuota</h2>
        <p>Non ci sono ancora dati sufficienti per popolare il cockpit operativo.</p>
      </div>
    );
  }

  return (
    <div className="dashboard-shell">
      <section className="dashboard-hero">
        <div>
          <span className="dashboard-eyebrow">Cockpit operativo</span>
          <h2>Dashboard e compliance center</h2>
          <p>{computed.heroStatus}</p>
          <div className="dashboard-hero-meta">
            <span className="hero-chip">
              Ultimo aggiornamento: {formatDate(computed.lastUpdatedAt)}
            </span>
            <span className="hero-chip">
              Profilo attivo: {computed.roleConfig.label}
            </span>
            <span className="hero-chip">
              Finestra report: {computed.summaryWindow?.from ? `${formatDate(computed.summaryWindow.from)} - ${formatDate(computed.summaryWindow.to)}` : 'intero dataset disponibile'}
            </span>
          </div>
        </div>
        <button
          type="button"
          className="dashboard-refresh"
          onClick={() => loadDashboard({ silent: true })}
          disabled={state.refreshing}
        >
          {state.refreshing ? 'Aggiornamento...' : 'Aggiorna cockpit'}
        </button>
      </section>

      <section className="dashboard-grid-kpi" aria-label="Indicatori principali">
        {computed.kpis.map((item) => (
          <article key={item.label} className="dashboard-kpi-card">
            <span>{item.label}</span>
            <strong>{item.value}</strong>
            <small>{item.note}</small>
          </article>
        ))}
      </section>

      <section className="dashboard-grid-main">
        <article className="dashboard-panel">
          <div className="dashboard-panel-header">
            <div>
              <h3>Alert e compliance</h3>
              <p>Priorita operative su documenti, assegnazioni e stato progetti.</p>
            </div>
            <span className="dashboard-pill">{computed.alerts.length} elementi monitorati</span>
          </div>

          <div className="dashboard-alert-overview">
            <div className="dashboard-mini-panel critical">
              <span>Critici</span>
              <strong>{computed.alertCounters.critical}</strong>
            </div>
            <div className="dashboard-mini-panel warning">
              <span>Warning</span>
              <strong>{computed.alertCounters.warning}</strong>
            </div>
            <div className="dashboard-mini-panel info">
              <span>Info</span>
              <strong>{computed.alertCounters.info}</strong>
            </div>
            <div className="dashboard-mini-panel success">
              <span>Sotto controllo</span>
              <strong>{computed.alertCounters.success}</strong>
            </div>
          </div>

          {computed.alerts.length > 0 ? (
            <ul className="dashboard-alert-list">
              {computed.alerts.slice(0, 8).map((alert) => (
                <li key={alert.id} className={`dashboard-alert-item ${alert.severity}`}>
                  <div className="dashboard-alert-header">
                    <strong>{alert.title}</strong>
                    <span className={`dashboard-alert-badge ${alert.severity}`}>{alert.area}</span>
                  </div>
                  <p>{alert.detail}</p>
                  <div className="dashboard-alert-meta">
                    <span>Owner: {alert.owner}</span>
                    <span>Trigger: {alert.dueLabel}</span>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="dashboard-footnote">Nessuna criticita rilevata nel perimetro monitorato.</p>
          )}
        </article>

        <div className="dashboard-section-stack">
          <article className="dashboard-panel">
            <div className="dashboard-panel-header">
              <div>
                <h3>{computed.roleConfig.title}</h3>
                <p>{computed.roleConfig.intro}</p>
              </div>
              <span className="dashboard-pill">{computed.roleTasks.length} focus attivi</span>
            </div>

            <ul className="dashboard-role-task-list">
              {computed.roleTasks.map((task) => (
                <li key={task.label} className="dashboard-role-task-item">
                  <div className="dashboard-role-task-copy">
                    <strong>{task.label}</strong>
                    <p>{task.detail}</p>
                  </div>
                  <span className="dashboard-role-task-value">{task.value}</span>
                </li>
              ))}
            </ul>
          </article>

          <article className="dashboard-panel">
            <div className="dashboard-panel-header">
              <div>
                <h3>Top volumi</h3>
                <p>Priorita basate sulle ore registrate nel reporting.</p>
              </div>
            </div>

            <ul className="dashboard-ranking-list">
              {(computed.topProjects.length > 0 ? computed.topProjects : [{ id: 'empty-projects', nome: 'Nessun progetto disponibile', ore_totali: 0 }]).map((project) => (
                <li key={`project-${project.id}`} className="dashboard-ranking-item">
                  <div className="dashboard-ranking-label">
                    <strong>{project.nome}</strong>
                    <span>Progetto</span>
                  </div>
                  <span className="dashboard-ranking-value">{formatHours(project.ore_totali)}</span>
                </li>
              ))}
            </ul>

            <ul className="dashboard-ranking-list">
              {(computed.topCollaborators.length > 0 ? computed.topCollaborators : [{ id: 'empty-collaborators', nome: 'Nessun collaboratore disponibile', ore_totali: 0 }]).map((collaborator) => (
                <li key={`collaborator-${collaborator.id}`} className="dashboard-ranking-item">
                  <div className="dashboard-ranking-label">
                    <strong>{collaborator.nome}</strong>
                    <span>Collaboratore</span>
                  </div>
                  <span className="dashboard-ranking-value">{formatHours(collaborator.ore_totali)}</span>
                </li>
              ))}
            </ul>
          </article>

          <article className="dashboard-panel">
            <div className="dashboard-panel-header">
              <div>
                <h3>{currentUser?.role === 'admin' ? 'Contratti e sistema' : 'Contratti monitorati'}</h3>
                <p>{currentUser?.role === 'admin' ? 'Distribuzione contratti e metriche esposte dal backend.' : 'Distribuzione contratti utile al presidio operativo.'}</p>
              </div>
            </div>

            <ul className="dashboard-distribution-list">
              {(computed.contractDistribution.length > 0 ? computed.contractDistribution : [{ tipo: 'Non disponibile', numero: 0 }]).map((item) => (
                <li key={item.tipo} className="dashboard-distribution-item">
                  <div className="dashboard-distribution-label">
                    <strong>{item.tipo}</strong>
                    <span>Tipo contratto</span>
                  </div>
                  <span className="dashboard-distribution-value">{formatNumber(item.numero)}</span>
                </li>
              ))}
            </ul>

            <div className="dashboard-footnote">
              {Object.keys(computed.systemMetrics).length > 0
                ? `Metriche admin disponibili: ${Object.keys(computed.systemMetrics).length} indicatori esposti.`
                : 'Metriche admin non disponibili o non accessibili con il profilo corrente.'}
            </div>
          </article>
        </div>
      </section>
    </div>
  );
};

export default Dashboard;
