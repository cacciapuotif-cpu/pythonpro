/**
 * Componente Loading Spinner riutilizzabile con diverse varianti
 */

import React from 'react';
import './LoadingSpinner.css';

const LoadingSpinner = ({
  size = 'medium',
  message = 'Caricamento...',
  variant = 'primary',
  overlay = false,
  inline = false
}) => {
  const spinnerClass = `loading-spinner loading-spinner-${size} loading-spinner-${variant}`;
  const containerClass = `loading-container ${overlay ? 'loading-overlay' : ''} ${inline ? 'loading-inline' : ''}`;

  return (
    <div className={containerClass}>
      <div className="loading-content">
        <div className={spinnerClass}>
          <div className="spinner-ring">
            <div></div>
            <div></div>
            <div></div>
            <div></div>
          </div>
        </div>
        {message && (
          <p className="loading-message">{message}</p>
        )}
      </div>
    </div>
  );
};

export default LoadingSpinner;