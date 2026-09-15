import { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
    errorInfo: null
  };

  public static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('[RRR ErrorBoundary] Uncaught runtime exception:', error, errorInfo);
    this.setState({ errorInfo });
  }

  private handleReset = () => {
    location.hash = 'dashboard';
    window.location.reload();
  };

  public render() {
    if (this.state.hasError) {
      return (
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '100vh',
          backgroundColor: '#0b0f19',
          color: '#f3f4f6',
          fontFamily: 'Inter, system-ui, sans-serif',
          padding: '20px'
        }}>
          <div style={{
            maxWidth: '600px',
            width: '100%',
            backgroundColor: '#172033',
            border: '1px solid #dc2626',
            borderRadius: '12px',
            padding: '30px',
            boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.5)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px' }}>
              <span style={{ fontSize: '24px', color: '#f87171' }}>⚠️</span>
              <h2 style={{ margin: 0, fontSize: '20px', fontWeight: 600, color: '#f87171' }}>
                Application Runtime Error
              </h2>
            </div>
            
            <p style={{ color: '#9ca3af', fontSize: '14px', lineHeight: 1.5, marginBottom: '20px' }}>
              An unexpected UI exception occurred while rendering the Investigator Command Center workspace.
            </p>

            {this.state.error && (
              <div style={{
                backgroundColor: 'rgba(15, 23, 42, 0.8)',
                border: '1px solid rgba(248, 113, 113, 0.3)',
                borderRadius: '6px',
                padding: '12px 16px',
                marginBottom: '20px',
                fontFamily: 'DM Mono, monospace',
                fontSize: '13px',
                color: '#fca5a5',
                overflowX: 'auto'
              }}>
                {this.state.error.name}: {this.state.error.message}
              </div>
            )}

            {this.state.errorInfo && (
              <details style={{ marginBottom: '20px', color: '#64748b', fontSize: '12px' }}>
                <summary style={{ cursor: 'pointer', marginBottom: '8px', color: '#94a3b8' }}>Component Stack Diagnostics</summary>
                <pre style={{
                  fontFamily: 'DM Mono, monospace',
                  fontSize: '11px',
                  backgroundColor: '#0f172a',
                  padding: '10px',
                  borderRadius: '4px',
                  overflowX: 'auto',
                  maxHeight: '150px'
                }}>
                  {this.state.errorInfo.componentStack}
                </pre>
              </details>
            )}

            <div style={{ display: 'flex', gap: '12px' }}>
              <button
                onClick={this.handleReset}
                style={{
                  backgroundColor: '#2563eb',
                  color: '#ffffff',
                  border: 'none',
                  borderRadius: '6px',
                  padding: '10px 18px',
                  fontSize: '14px',
                  fontWeight: 600,
                  cursor: 'pointer'
                }}
              >
                Return to Dashboard
              </button>
              <button
                onClick={() => window.location.reload()}
                style={{
                  backgroundColor: '#334155',
                  color: '#f8fafc',
                  border: 'none',
                  borderRadius: '6px',
                  padding: '10px 18px',
                  fontSize: '14px',
                  fontWeight: 500,
                  cursor: 'pointer'
                }}
              >
                Reload Page
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
