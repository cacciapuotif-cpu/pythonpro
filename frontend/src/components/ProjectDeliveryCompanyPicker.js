import React, { useEffect, useMemo, useState } from 'react';
import {
  getProjectDeliveryCompanies,
  getProjectDeliveryCompanyStudents,
} from '../services/apiService';
import { formatPersonName } from '../utils/personName';

import './ProjectDeliveryCompanyPicker.css';

const mergeById = (current, incoming) => {
  const merged = new Map((current || []).map((item) => [Number(item.id), item]));
  (incoming || []).forEach((item) => merged.set(Number(item.id), item));
  return Array.from(merged.values());
};

const ProjectDeliveryCompanyPicker = ({
  projectId,
  aziendeSelezionate = [],
  allieviSelezionati = [],
  onChange,
  onCompaniesLoaded,
  onStudentsLoaded,
  onError,
}) => {
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [companies, setCompanies] = useState([]);
  const [total, setTotal] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState({});
  const [studentsByCompany, setStudentsByCompany] = useState({});
  const [studentsLoading, setStudentsLoading] = useState({});

  const selectedCompanyIds = useMemo(
    () => (aziendeSelezionate || []).map(Number),
    [aziendeSelezionate],
  );
  const selectedStudentIds = useMemo(
    () => (allieviSelezionati || []).map(Number),
    [allieviSelezionati],
  );

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedSearch(search.trim()), 300);
    return () => window.clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    if (!projectId) return undefined;
    let cancelled = false;

    const load = async () => {
      setLoading(true);
      try {
        const page = await getProjectDeliveryCompanies(projectId, {
          q: debouncedSearch,
          limit: 20,
          offset: 0,
        });
        if (cancelled) return;
        const items = page.items || [];
        setCompanies(items);
        setTotal(page.total || 0);
        setHasMore(Boolean(page.has_more));
        onCompaniesLoaded?.(items);
      } catch (error) {
        if (!cancelled) onError?.(error?.response?.data?.detail || error?.message || 'Impossibile caricare le aziende');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    load();
    return () => { cancelled = true; };
  }, [projectId, debouncedSearch, onCompaniesLoaded, onError]);

  const loadMore = async () => {
    setLoading(true);
    try {
      const page = await getProjectDeliveryCompanies(projectId, {
        q: debouncedSearch,
        limit: 20,
        offset: companies.length,
      });
      const next = mergeById(companies, page.items || []);
      setCompanies(next);
      setTotal(page.total || 0);
      setHasMore(Boolean(page.has_more));
      onCompaniesLoaded?.(page.items || []);
    } catch (error) {
      onError?.(error?.response?.data?.detail || error?.message || 'Impossibile caricare altre aziende');
    } finally {
      setLoading(false);
    }
  };

  const toggleCompany = (companyId) => {
    const id = Number(companyId);
    if (selectedCompanyIds.includes(id)) {
      const companyStudentIds = (studentsByCompany[id] || []).map((student) => Number(student.id));
      onChange({
        azienda_ids: selectedCompanyIds.filter((item) => item !== id),
        allievo_ids: selectedStudentIds.filter((item) => !companyStudentIds.includes(item)),
      });
      return;
    }
    onChange({
      azienda_ids: [...selectedCompanyIds, id],
      allievo_ids: selectedStudentIds,
    });
  };

  const toggleStudent = (companyId, studentId) => {
    const normalizedCompanyId = Number(companyId);
    const normalizedStudentId = Number(studentId);
    const hasStudent = selectedStudentIds.includes(normalizedStudentId);
    onChange({
      azienda_ids: selectedCompanyIds.includes(normalizedCompanyId)
        ? selectedCompanyIds
        : [...selectedCompanyIds, normalizedCompanyId],
      allievo_ids: hasStudent
        ? selectedStudentIds.filter((item) => item !== normalizedStudentId)
        : [...selectedStudentIds, normalizedStudentId],
    });
  };

  const toggleExpanded = async (companyId) => {
    const id = Number(companyId);
    const willExpand = !expanded[id];
    setExpanded((current) => ({ ...current, [id]: willExpand }));
    if (!willExpand || studentsByCompany[id]) return;

    setStudentsLoading((current) => ({ ...current, [id]: true }));
    try {
      const page = await getProjectDeliveryCompanyStudents(projectId, id, {
        limit: 100,
        offset: 0,
      });
      const students = page.items || [];
      setStudentsByCompany((current) => ({ ...current, [id]: students }));
      onStudentsLoaded?.(students);
    } catch (error) {
      onError?.(error?.response?.data?.detail || error?.message || 'Impossibile caricare gli allievi');
    } finally {
      setStudentsLoading((current) => ({ ...current, [id]: false }));
    }
  };

  return (
    <div className="delivery-picker">
      <label className="delivery-picker-search">
        Cerca nel perimetro del progetto
        <input
          type="search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Ragione sociale o Partita IVA"
          autoComplete="off"
        />
      </label>

      <p className="delivery-picker-result" role="status">
        {loading && companies.length === 0 ? 'Ricerca in corso…' : `${total} aziende nel perimetro`}
      </p>

      {!loading && companies.length === 0 ? (
        <p className="delivery-picker-empty">Nessuna azienda trovata nel perimetro del progetto.</p>
      ) : (
        <div className="delivery-picker-companies">
          {companies.map((company) => {
            const id = Number(company.id);
            const students = studentsByCompany[id];
            return (
              <section className="delivery-picker-company" key={id}>
                <div className="delivery-picker-company-row">
                  <label>
                    <input
                      type="checkbox"
                      checked={selectedCompanyIds.includes(id)}
                      onChange={() => toggleCompany(id)}
                    />
                    <span>
                      <strong>{company.ragione_sociale}</strong>
                      <small>{company.partita_iva ? `P.IVA ${company.partita_iva}` : 'P.IVA non indicata'}</small>
                    </span>
                  </label>
                  <button
                    type="button"
                    className="delivery-picker-expand"
                    aria-expanded={Boolean(expanded[id])}
                    onClick={() => toggleExpanded(id)}
                  >
                    {expanded[id] ? 'Nascondi allievi' : 'Mostra allievi'}
                  </button>
                </div>

                {expanded[id] && (
                  <div className="delivery-picker-students">
                    {studentsLoading[id] ? (
                      <p>Caricamento allievi…</p>
                    ) : students?.length ? (
                      students.map((student) => (
                        <label key={student.id}>
                          <input
                            type="checkbox"
                            checked={selectedStudentIds.includes(Number(student.id))}
                            onChange={() => toggleStudent(id, student.id)}
                          />
                          <span>{formatPersonName(student)}</span>
                        </label>
                      ))
                    ) : (
                      <p>Nessun allievo registrato per questa azienda.</p>
                    )}
                  </div>
                )}
              </section>
            );
          })}
        </div>
      )}

      {hasMore && (
        <button type="button" className="delivery-picker-more" onClick={loadMore} disabled={loading}>
          {loading ? 'Caricamento…' : 'Carica altre aziende'}
        </button>
      )}
    </div>
  );
};

export default ProjectDeliveryCompanyPicker;
