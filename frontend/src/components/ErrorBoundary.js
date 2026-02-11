/**
 * Error Boundary per gestire errori React in modo elegante
 */

import React from 'react';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      retryCount: 0
    };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    this.setState({
      error,
      errorInfo,
      hasError: true
    });

    // Log error to console in development
    if (process.env.NODE_ENV === 'development') {
      console.error('ErrorBoundary caught an error:', error, errorInfo);
    }

    // In production, potresti inviare l'errore a un servizio di monitoring
    if (process.env.NODE_ENV === 'production') {
      // sendErrorToService(error, errorInfo);
    }
  }

  handleRetry = () => {
    this.setState(prevState => ({
      hasError: false,
      error: null,
      errorInfo: null,
      retryCount: prevState.retryCount + 1
    }));
  };

  handleReload = () => {
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      const { fallback: Fallback, onError } = this.props;

      // Se è fornito un componente fallback personalizzato
      if (Fallback) {
        return (
          <Fallback
            error={this.state.error}
            errorInfo={this.state.errorInfo}
            onRetry={this.handleRetry}
            onReload={this.handleReload}
          />
        );
      }

      // Callback per gestire l'errore nel componente parent
      if (onError) {
        onError(this.state.error, this.state.errorInfo);
      }

      // Fallback UI di default
      return (
        <div className="error-boundary">
          <div className="error-boundary-content">
            <div className="error-icon">⚠️</div>
            <h2>Oops! Qualcosa è andato storto</h2>
            <p>
              Si è verificato un errore imprevisto. Puoi provare a ricaricare la pagina
              o contattare l'assistenza se il problema persiste.
            </p>

            {process.env.NODE_ENV === 'development' && (
              <details className="error-details">
                <summary>Dettagli tecnici (solo sviluppo)</summary>
                <pre className="error-stack">
                  {this.state.error && this.state.error.toString()}
                  <br />
                  {this.state.errorInfo.componentStack}
                </pre>
              </details>
            )}

            <div className="error-actions">
              <button
                onClick={this.handleRetry}
                className="error-button error-button-primary"
              >
                Riprova
              </button>
              <button
                onClick={this.handleReload}
                className="error-button error-button-secondary"
              >
                Ricarica Pagina
              </button>
            </div>

            {this.state.retryCount > 2 && (
              <p className="error-hint">
                💡 Se il problema persiste, prova a svuotare la cache del browser
                o contatta l'assistenza tecnica.
              </p>
            )}
          </div>

          <style jsx>{`
            .error-boundary {
              display: flex;
              align-items: center;
              justify-content: center;
              min-height: 400px;
              padding: 40px 20px;
              background: #f9fafb;
              border-radius: 12px;
              margin: 20px;
            }

            .error-boundary-content {
              text-align: center;
              max-width: 500px;
            }

            .error-icon {
              font-size: 48px;
              margin-bottom: 16px;
            }

            .error-boundary h2 {
              color: #111827;
              font-size: 24px;
              font-weight: 600;
              margin-bottom: 12px;
            }

            .error-boundary p {
              color: #6b7280;
              font-size: 16px;
              line-height: 1.5;
              margin-bottom: 24px;
            }

            .error-details {
              background: #f3f4f6;
              border: 1px solid #d1d5db;
              border-radius: 8px;
              padding: 16px;
              margin: 20px 0;
              text-align: left;
            }

            .error-details summary {
              cursor: pointer;
              font-weight: 500;
              color: #374151;
              margin-bottom: 8px;
            }

            .error-stack {
              background: #fff;
              border: 1px solid #e5e7eb;
              border-radius: 4px;
              padding: 12px;
              font-size: 12px;
              color: #dc2626;
              overflow-x: auto;
              white-space: pre-wrap;
            }

            .error-actions {
              display: flex;
              gap: 12px;
              justify-content: center;
              flex-wrap: wrap;
            }

            .error-button {
              padding: 10px 20px;
              border-radius: 8px;
              font-size: 14px;
              font-weight: 500;
              cursor: pointer;
              transition: all 0.2s;
              border: none;
            }

            .error-button-primary {
              background: #3b82f6;
              color: white;
            }

            .error-button-primary:hover {
              background: #2563eb;
            }

            .error-button-secondary {
              background: #f3f4f6;
              color: #374151;
              border: 1px solid #d1d5db;
            }

            .error-button-secondary:hover {
              background: #e5e7eb;
            }

            .error-hint {
              margin-top: 20px;
              font-size: 14px;
              color: #6b7280;
              font-style: italic;
            }

            @media (max-width: 640px) {
              .error-boundary {
                margin: 10px;
                padding: 20px 10px;
                min-height: 300px;
              }

              .error-boundary h2 {
                font-size: 20px;
              }

              .error-actions {
                flex-direction: column;
                align-items: center;
              }

              .error-button {
                width: 100%;
                max-width: 200px;
              }
            }
          `}</style>
        </div>
      );
    }

    return this.props.children;
  }
}

// Hook per catturare errori asincroni
export const useErrorHandler = () => {
  return (error, errorInfo = {}) => {
    console.error('Async error caught:', error, errorInfo);

    // In produzione, invia a servizio di monitoring
    if (process.env.NODE_ENV === 'production') {
      // sendErrorToService(error, errorInfo);
    }
  };
};

export default ErrorBoundary;