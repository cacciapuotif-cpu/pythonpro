/**
 * COMPONENTE DASHBOARD PER STATISTICHE E REPORT
 * Placeholder semplificato per ora - da espandere in futuro
 */

import React from 'react';

const Dashboard = () => {
  return (
    <div style={{ padding: '20px', textAlign: 'center' }}>
      <h2>📊 Dashboard e Report</h2>
      <p>Questa sezione mostrerà:</p>
      <ul style={{ textAlign: 'left', maxWidth: '500px', margin: '20px auto' }}>
        <li>Statistiche ore lavorate per collaboratore</li>
        <li>Report ore per progetto</li>
        <li>Grafici di produttività</li>
        <li>Esportazione dati in Excel/PDF</li>
        <li>Riepiloghi mensili e annuali</li>
      </ul>
      <p style={{ color: '#666', fontStyle: 'italic' }}>
        🚧 Sezione in sviluppo - per ora usa il calendario per gestire le presenze
      </p>
    </div>
  );
};

export default Dashboard;