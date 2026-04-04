import React, { useEffect, useMemo, useState } from 'react';
import { getProjects } from '../services/apiService';
import PianiFinanziariManager from './PianiFinanziariManager';
import PianiFondimpresaManager from './PianiFondimpresaManager';
import './PianiFinanziariManager.css';

const isFondimpresa = (ente) =>
  String(ente || '').trim().toUpperCase().includes('FONDIMPRESA');

export default function PianiFinanziariHub() {
  const [projects, setProjects] = useState([]);
  const [selectedProjectId, setSelectedProjectId] = useState('');
  const [filterEnte, setFilterEnte] = useState('');
  const [filterAvviso, setFilterAvviso] = useState('');
  const [loadingProjects, setLoadingProjects] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let mounted = true;
    const loadProjects = async () => {
      setLoadingProjects(true);
      setError('');
      try {
        const data = await getProjects(0, 300);
        if (!mounted) return;
        setProjects(Array.isArray(data) ? data : []);
      } catch (loadError) {
        if (!mounted) return;
        setError(loadError?.response?.data?.detail || 'Errore nel caricamento dei progetti.');
      } finally {
        if (mounted) setLoadingProjects(false);
      }
    };
    loadProjects();
    return () => { mounted = false; };
  }, []);

  // Step 1: enti unici estratti dai progetti
  const entiDisponibili = useMemo(() => {
    const seen = new Set();
    projects.forEach((p) => {
      const e = (p.ente_erogatore || '').trim();
      if (e) seen.add(e);
    });
    return Array.from(seen).sort();
  }, [projects]);

  // Step 2: avvisi unici per l'ente selezionato
  const avvisiDisponibili = useMemo(() => {
    if (!filterEnte) return [];
    const seen = new Set();
    projects
      .filter((p) => (p.ente_erogatore || '').trim() === filterEnte)
      .forEach((p) => {
        const a = (p.avviso || '').trim();
        if (a) seen.add(a);
      });
    return Array.from(seen).sort();
  }, [projects, filterEnte]);

  // Step 3: progetti filtrati per ente + avviso
  const progettiDisponibili = useMemo(() => {
    if (!filterEnte) return [];
    return projects.filter((p) => {
      const enteOk = (p.ente_erogatore || '').trim() === filterEnte;
      const avvisoOk = !filterAvviso || (p.avviso || '').trim() === filterAvviso;
      return enteOk && avvisoOk;
    });
  }, [projects, filterEnte, filterAvviso]);

  const selectedProject = useMemo(
    () => projects.find((p) => String(p.id) === String(selectedProjectId)),
    [projects, selectedProjectId],
  );

  const handleEnteChange = (e) => {
    setFilterEnte(e.target.value);
    setFilterAvviso('');
    setSelectedProjectId('');
  };

  const handleAvvisoChange = (e) => {
    setFilterAvviso(e.target.value);
    setSelectedProjectId('');
  };

  const handleProgettoChange = (e) => {
    setSelectedProjectId(e.target.value);
  };

  return (
    <div className="piani-finanziari-page">
      <div className="page-header">
        <div>
          <span className="page-eyebrow">Selezione guidata</span>
          <h2>Piani Finanziari</h2>
          <p>Seleziona prima l'ente erogatore e l'avviso, poi il progetto corrispondente.</p>
        </div>
      </div>

      {error ? <div className="banner error">{error}</div> : null}

      <div className="toolbar-card">
        <div className="toolbar-grid">

          {/* Step 1 — Ente Erogatore */}
          <label>
            <span>1. Ente Erogatore</span>
            <select value={filterEnte} onChange={handleEnteChange} disabled={loadingProjects}>
              <option value="">Seleziona ente erogatore</option>
              {entiDisponibili.map((ente) => (
                <option key={ente} value={ente}>{ente}</option>
              ))}
            </select>
          </label>

          {/* Step 2 — Avviso (cascade da ente) */}
          <label>
            <span>2. Avviso</span>
            <select value={filterAvviso} onChange={handleAvvisoChange} disabled={!filterEnte}>
              <option value="">Tutti gli avvisi</option>
              {avvisiDisponibili.map((avviso) => (
                <option key={avviso} value={avviso}>{avviso}</option>
              ))}
            </select>
          </label>

          {/* Step 3 — Progetto (cascade da ente + avviso) */}
          <label>
            <span>3. Progetto</span>
            <select value={selectedProjectId} onChange={handleProgettoChange} disabled={!filterEnte}>
              <option value="">Seleziona progetto</option>
              {progettiDisponibili.map((project) => (
                <option key={project.id} value={project.id}>{project.name}</option>
              ))}
            </select>
          </label>

          <div className="toolbar-create">
            <strong>{selectedProject ? selectedProject.name : 'Nessun progetto selezionato'}</strong>
            <small>
              {selectedProject
                ? `${selectedProject.ente_erogatore || ''}${selectedProject.avviso ? ` · Avviso ${selectedProject.avviso}` : ''}${isFondimpresa(selectedProject.ente_erogatore) ? ' — layout Fondimpresa' : ' — layout standard'}`
                : loadingProjects
                  ? 'Caricamento progetti in corso...'
                  : 'Seleziona ente erogatore, avviso e progetto per aprire il piano.'}
            </small>
          </div>
        </div>
      </div>

      {!selectedProjectId ? (
        <div className="empty-state">
          <div>💼</div>
          <h3>Nessun progetto selezionato</h3>
          <p>Usa i filtri sopra per trovare il progetto: ente erogatore → avviso → progetto.</p>
        </div>
      ) : isFondimpresa(selectedProject?.ente_erogatore) ? (
        <PianiFondimpresaManager forcedProjectId={selectedProjectId} embedded />
      ) : (
        <PianiFinanziariManager
          forcedProjectId={selectedProjectId}
          forcedEnte={selectedProject?.ente_erogatore || ''}
          embedded
        />
      )}
    </div>
  );
}
