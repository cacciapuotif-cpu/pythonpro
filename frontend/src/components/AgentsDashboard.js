import React, { useState, useEffect, useCallback } from 'react';
import { getAgentsCatalog, getAgentRuns, runAgentByType } from '../services/apiService';

const AgentsDashboard = () => {
  const [agents, setAgents] = useState([]);
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [runningAgent, setRunningAgent] = useState(null);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const [agentsData, runsData] = await Promise.all([
        getAgentsCatalog(),
        getAgentRuns({ limit: 10 }),
      ]);
      setAgents(Array.isArray(agentsData) ? agentsData : []);
      setRuns(Array.isArray(runsData) ? runsData : []);
    } catch (err) {
      console.error('Errore caricamento agenti:', err);
      setError('Impossibile caricare i dati degli agenti');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const runAgent = async (agentType) => {
    try {
      setRunningAgent(agentType);
      await runAgentByType(agentType);
      await loadData();
    } catch (err) {
      alert(`Errore avvio agente: ${err.response?.data?.detail || err.message}`);
    } finally {
      setRunningAgent(null);
    }
  };

  const statusBadge = (status) => {
    const colors = {
      completed: 'bg-green-100 text-green-800',
      failed: 'bg-red-100 text-red-800',
      running: 'bg-yellow-100 text-yellow-800',
    };
    return (
      <span className={`px-2 py-0.5 rounded text-xs font-medium ${colors[status] || 'bg-gray-100 text-gray-700'}`}>
        {status}
      </span>
    );
  };

  if (loading) {
    return <div className="p-6 text-gray-500">Caricamento...</div>;
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="bg-red-50 border border-red-200 rounded p-4 text-red-700">{error}</div>
        <button onClick={loadData} className="mt-3 px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600">
          Riprova
        </button>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Dashboard Agenti AI</h1>
        <button onClick={loadData} className="px-3 py-1.5 text-sm bg-gray-100 hover:bg-gray-200 rounded">
          Aggiorna
        </button>
      </div>

      {/* Agenti disponibili */}
      <div className="mb-8">
        <h2 className="text-lg font-semibold text-gray-800 mb-3">Agenti Disponibili</h2>
        {agents.length === 0 ? (
          <p className="text-gray-500 text-sm">Nessun agente registrato</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {agents.map((agent) => (
              <div key={agent.name || agent.agent_type} className="border rounded-lg p-4 bg-white shadow-sm">
                <div className="flex items-start justify-between mb-2">
                  <h3 className="font-semibold text-gray-900">{agent.label || agent.name || agent.agent_type}</h3>
                  <span className="text-xs text-gray-400">v{agent.version || '1.0'}</span>
                </div>
                <p className="text-sm text-gray-600 mb-3">{agent.description}</p>
                <button
                  onClick={() => runAgent(agent.name || agent.agent_type)}
                  disabled={runningAgent === (agent.name || agent.agent_type)}
                  className="w-full px-3 py-1.5 bg-blue-500 text-white text-sm rounded hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {runningAgent === (agent.name || agent.agent_type) ? 'In esecuzione...' : 'Esegui'}
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Ultimi run */}
      <div>
        <h2 className="text-lg font-semibold text-gray-800 mb-3">Ultimi Run</h2>
        {runs.length === 0 ? (
          <p className="text-gray-500 text-sm">Nessun run recente</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="bg-gray-50">
                  <th className="border border-gray-200 px-3 py-2 text-left font-medium text-gray-700">Agente</th>
                  <th className="border border-gray-200 px-3 py-2 text-left font-medium text-gray-700">Stato</th>
                  <th className="border border-gray-200 px-3 py-2 text-right font-medium text-gray-700">Items</th>
                  <th className="border border-gray-200 px-3 py-2 text-right font-medium text-gray-700">Suggerimenti</th>
                  <th className="border border-gray-200 px-3 py-2 text-left font-medium text-gray-700">Avviato</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => (
                  <tr key={run.id} className="hover:bg-gray-50">
                    <td className="border border-gray-200 px-3 py-2 font-mono text-xs">
                      {run.agent_name || run.agent_type || '—'}
                    </td>
                    <td className="border border-gray-200 px-3 py-2">
                      {statusBadge(run.status)}
                    </td>
                    <td className="border border-gray-200 px-3 py-2 text-right text-gray-700">
                      {run.items_processed ?? '—'}
                    </td>
                    <td className="border border-gray-200 px-3 py-2 text-right text-gray-700">
                      {run.suggestions_count ?? run.suggestions_created ?? '—'}
                    </td>
                    <td className="border border-gray-200 px-3 py-2 text-gray-500 text-xs">
                      {run.started_at ? new Date(run.started_at).toLocaleString('it-IT') : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default AgentsDashboard;
