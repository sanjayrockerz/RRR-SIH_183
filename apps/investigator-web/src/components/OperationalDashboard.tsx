import { useEffect, useState } from 'react';
import { dashboardSummary, listAlerts, listCases, systemStatus, systemProviders } from '../api';
import type { DashboardSummary, RealtimeAlert, CaseListItem, SystemStatus } from '../types';

const statusClass = (value: string) => {
  const v = String(value).toUpperCase();
  if (v === 'CONNECTED' || v === 'ONLINE' || v === 'HEALTHY') return 'good';
  if (v === 'DEVELOPMENT_FIXTURE' || v === 'SIMULATED') return 'simulated';
  if (v === 'DEGRADED') return 'warn';
  return 'off';
};

const formatVal = (val: number | undefined | null) => {
  if (val === undefined || val === null) return 'NO DATA';
  return val;
};

const short = (val?: string) => val && val.length > 18 ? `${val.slice(0, 8)}…${val.slice(-6)}` : (val || '—');

export function OperationalDashboard({ onNavigate, onOpenCase }: { onNavigate: (route: string) => void; onOpenCase: (caseId: string) => void }) {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [system, setSystem] = useState<SystemStatus | null>(null);
  const [cases, setCases] = useState<CaseListItem[]>([]);
  const [alerts, setAlerts] = useState<RealtimeAlert[]>([]);
  const [providers, setProviders] = useState<any[]>([]);
  const [error, setError] = useState('');

  const loadData = () => {
    Promise.all([
      dashboardSummary(),
      systemStatus(),
      listCases(),
      listAlerts(),
      systemProviders().catch(() => [])
    ]).then(([s, sy, c, a, p]) => {
      setSummary(s);
      setSystem(sy);
      setCases(c);
      setAlerts(a);
      setProviders(p);
    }).catch(e => {
      setError(e instanceof Error ? e.message : 'Operational state unavailable');
    });
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 10000);
    return () => clearInterval(interval);
  }, []);

  const getProviderStatus = (name: string) => {
    const found = providers.find(p => String(p.provider).toLowerCase().includes(name.toLowerCase()));
    return found ? found.status : 'NOT_CONFIGURED';
  };

  return (
    <section className="operational-dashboard" style={{ color: '#cbd5e1' }}>
      <header className="ops-head" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <div>
          <span className="eyebrow">RRR / OPERATIONAL COMMAND CENTER</span>
          <h1 style={{ color: '#f3f4f6', margin: '4px 0' }}>Cyber-fraud investigation operations</h1>
          <p className="muted" style={{ margin: 0 }}>Real-time backend-authoritative case, graph, and provider dependency metrics.</p>
        </div>
        <div className={`ops-system ${statusClass(system?.system || 'UNAVAILABLE')}`} style={{ padding: '8px 16px', borderRadius: '6px', background: '#111827', display: 'flex', flexDirection: 'column', alignItems: 'flex-end' }}>
          <span style={{ fontWeight: 'bold' }}>SYSTEM {system?.system || 'OFFLINE'}</span>
          <small style={{ color: '#9ca3af', fontSize: '11px' }}>Mode: {system?.mode || 'HISTORICAL'}</small>
        </div>
      </header>

      {error && <div className="error" role="alert" style={{ background: '#7f1d1d', padding: '12px', borderRadius: '6px', marginBottom: '20px' }}>{error}</div>}

      {/* Case Metrics Grid */}
      <h2 className="eyebrow" style={{ marginTop: '30px', marginBottom: '10px' }}>Case Metrics</h2>
      <div className="ops-metrics" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '15px', marginBottom: '30px' }}>
        <article className="metric-card" style={{ background: '#111827', padding: '15px', borderRadius: '6px', border: '1px solid #1f2937' }}>
          <span>ACTIVE INVESTIGATIONS</span>
          <b style={{ display: 'block', fontSize: '24px', margin: '5px 0', color: '#3b82f6' }}>{formatVal(summary?.active_cases)}</b>
          <small>Active case registry files</small>
        </article>
        <article className="metric-card" style={{ background: '#111827', padding: '15px', borderRadius: '6px', border: '1px solid #1f2937' }}>
          <span>INVESTIGATIONS TODAY</span>
          <b style={{ display: 'block', fontSize: '24px', margin: '5px 0', color: '#10b981' }}>{formatVal(summary?.investigations_today)}</b>
          <small>Cases created in the last 24h</small>
        </article>
        <article className="metric-card" style={{ background: '#111827', padding: '15px', borderRadius: '6px', border: '1px solid #1f2937' }}>
          <span>WALLETS UNDER INVESTIGATION</span>
          <b style={{ display: 'block', fontSize: '24px', margin: '5px 0', color: '#f59e0b' }}>{formatVal(summary?.wallets_under_investigation)}</b>
          <small>Reported and traced wallet targets</small>
        </article>
        <article className="metric-card" style={{ background: '#111827', padding: '15px', borderRadius: '6px', border: '1px solid #1f2937' }}>
          <span>TRANSACTIONS ANALYZED</span>
          <b style={{ display: 'block', fontSize: '24px', margin: '5px 0', color: '#a855f7' }}>{formatVal(summary?.transactions_analyzed)}</b>
          <small>Observed historical transactions</small>
        </article>
        <article className="metric-card" style={{ background: '#111827', padding: '15px', borderRadius: '6px', border: '1px solid #1f2937' }}>
          <span>GRAPH NODES</span>
          <b style={{ display: 'block', fontSize: '24px', margin: '5px 0', color: '#38bdf8' }}>{formatVal(summary?.graph_nodes)}</b>
          <small>Entity vertices projected</small>
        </article>
        <article className="metric-card" style={{ background: '#111827', padding: '15px', borderRadius: '6px', border: '1px solid #1f2937' }}>
          <span>GRAPH EDGES</span>
          <b style={{ display: 'block', fontSize: '24px', margin: '5px 0', color: '#ec4899' }}>{formatVal(summary?.graph_edges)}</b>
          <small>Flow relationships established</small>
        </article>
        <article className="metric-card" style={{ background: '#111827', padding: '15px', borderRadius: '6px', border: '1px solid #1f2937' }}>
          <span>OPEN ALERTS</span>
          <b style={{ display: 'block', fontSize: '24px', margin: '5px 0', color: '#ef4444' }}>{formatVal(summary?.open_alerts)}</b>
          <small>Awaiting investigator triage</small>
        </article>
        <article className="metric-card" style={{ background: '#111827', padding: '15px', borderRadius: '6px', border: '1px solid #1f2937' }}>
          <span>CRITICAL CASES</span>
          <b style={{ display: 'block', fontSize: '24px', margin: '5px 0', color: '#ffffff' }}>{formatVal(summary?.critical_cases)}</b>
          <small>High or Critical priority cases</small>
        </article>
      </div>

      <div className="ops-layout" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: '20px', marginBottom: '30px' }}>
        {/* Investigations Queue */}
        <section className="ops-panel case-queue" style={{ background: '#111827', padding: '20px', borderRadius: '6px', border: '1px solid #1f2937' }}>
          <div className="panel-title" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
            <div>
              <span className="eyebrow">ACTIVE INVESTIGATIONS</span>
              <h3 style={{ margin: '4px 0', color: '#f3f4f6' }}>Investigator work queue</h3>
            </div>
            <button className="secondary" onClick={() => onNavigate('cases')}>VIEW REGISTRY</button>
          </div>
          {error ? (
            <p className="ops-empty">Backend unavailable — case registry could not be loaded.</p>
          ) : cases.length ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {cases.slice(0, 5).map(item => (
                <button className="ops-case-row" key={item.case_id} onClick={() => onOpenCase(item.case_id)} style={{ width: '100%', textAlign: 'left', background: '#1f2937', border: '1px solid #374151', padding: '10px', borderRadius: '6px', cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <strong style={{ display: 'block', color: '#e5e7eb' }}>{item.title}</strong>
                    <small style={{ color: '#9ca3af' }}>{item.fraud_type} · {item.wallet_count} wallets · {item.transaction_count} txs</small>
                  </div>
                  <span className="data-badge">{item.workflow_stage || item.status}</span>
                </button>
              ))}
            </div>
          ) : (
            <p className="ops-empty">No persisted cases found.</p>
          )}
        </section>

        {/* Live Pipeline Event Log */}
        <section className="ops-panel live-pipeline" style={{ background: '#111827', padding: '20px', borderRadius: '6px', border: '1px solid #1f2937' }}>
          <div className="panel-title" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
            <div>
              <span className="eyebrow">LIVE PIPELINE</span>
              <h3 style={{ margin: '4px 0', color: '#f3f4f6' }}>Operational activity readout</h3>
            </div>
          </div>
          <div className="pipeline-readout-stack" style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div style={{ padding: '10px', background: '#0a0d14', borderRadius: '6px' }}>
              <span className="eyebrow">LATEST BLOCKCHAIN EVENT</span>
              {summary?.latest_blockchain_event ? (
                <div style={{ color: '#e5e7eb', marginTop: '4px' }}>
                  <strong>TX: {short(summary.latest_blockchain_event.tx_hash)}</strong>
                  <div>{summary.latest_blockchain_event.amount} {summary.latest_blockchain_event.asset} ({summary.latest_blockchain_event.chain})</div>
                </div>
              ) : (
                <div style={{ color: '#ef4444', marginTop: '4px', fontWeight: 'bold' }}>NO DATA</div>
              )}
            </div>

            <div style={{ padding: '10px', background: '#0a0d14', borderRadius: '6px' }}>
              <span className="eyebrow">LATEST GRAPH MUTATION</span>
              {summary?.latest_graph_mutation ? (
                <div style={{ color: '#e5e7eb', marginTop: '4px' }}>
                  <strong>Edge: {short(summary.latest_graph_mutation.edge_id)}</strong>
                  <div>{short(summary.latest_graph_mutation.source_wallet)} → {short(summary.latest_graph_mutation.destination_wallet)}</div>
                </div>
              ) : (
                <div style={{ color: '#ef4444', marginTop: '4px', fontWeight: 'bold' }}>NO DATA</div>
              )}
            </div>

            <div style={{ padding: '10px', background: '#0a0d14', borderRadius: '6px' }}>
              <span className="eyebrow">LATEST PATTERN DETECTED</span>
              {summary?.latest_pattern ? (
                <div style={{ color: '#e5e7eb', marginTop: '4px' }}>
                  <strong>{summary.latest_pattern.pattern_type} ({summary.latest_pattern.severity})</strong>
                  <div>{summary.latest_pattern.description}</div>
                </div>
              ) : (
                <div style={{ color: '#ef4444', marginTop: '4px', fontWeight: 'bold' }}>NO DATA</div>
              )}
            </div>

            <div style={{ padding: '10px', background: '#0a0d14', borderRadius: '6px' }}>
              <span className="eyebrow">LATEST RISK CHANGE</span>
              {summary?.latest_risk_change ? (
                <div style={{ color: '#e5e7eb', marginTop: '4px' }}>
                  <strong>Score: {summary.latest_risk_change.score} ({summary.latest_risk_change.band})</strong>
                  <div>Assessment calculated at {new Date(summary.latest_risk_change.calculated_at).toLocaleTimeString()}</div>
                </div>
              ) : (
                <div style={{ color: '#ef4444', marginTop: '4px', fontWeight: 'bold' }}>NO DATA</div>
              )}
            </div>

            <div style={{ padding: '10px', background: '#0a0d14', borderRadius: '6px' }}>
              <span className="eyebrow">LATEST CRITICAL ALERT</span>
              {summary?.latest_alert ? (
                <div style={{ color: '#e5e7eb', marginTop: '4px' }}>
                  <strong>{summary.latest_alert.title} ({summary.latest_alert.severity})</strong>
                  <div>Generated at {new Date(summary.latest_alert.created_at).toLocaleString()}</div>
                </div>
              ) : (
                <div style={{ color: '#ef4444', marginTop: '4px', fontWeight: 'bold' }}>NO DATA</div>
              )}
            </div>
          </div>
        </section>
      </div>

      {/* Dependency Status Board */}
      <section className="ops-panel dependency-board" style={{ background: '#111827', padding: '20px', borderRadius: '6px', border: '1px solid #1f2937', marginBottom: '20px' }}>
        <div className="panel-title" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
          <div>
            <span className="eyebrow">DEPENDENCY CONTROL CENTER</span>
            <h3 style={{ margin: '4px 0', color: '#f3f4f6' }}>Operational health checks</h3>
          </div>
          <button className="secondary" onClick={() => onNavigate('operations')}>VIEW DIAGNOSTICS</button>
        </div>
        
        <div className="dependency-grid" style={{ display: 'flex', flexWrap: 'wrap', gap: '15px' }}>
          <span className={`dependency ${statusClass(system?.dependencies?.postgresql || 'UNAVAILABLE')}`} style={{ background: '#0a0d14', padding: '8px 12px', borderRadius: '6px', display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ color: '#9ca3af' }}>PostgreSQL:</span>
            <strong>{system?.dependencies?.postgresql || 'UNAVAILABLE'}</strong>
          </span>
          <span className={`dependency ${statusClass(getProviderStatus('Neo4j') || 'UNAVAILABLE')}`} style={{ background: '#0a0d14', padding: '8px 12px', borderRadius: '6px', display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ color: '#9ca3af' }}>Neo4j Graph DB:</span>
            <strong>{getProviderStatus('Neo4j') || 'UNAVAILABLE'}</strong>
          </span>
          <span className={`dependency ${statusClass(getProviderStatus('Alchemy Ethereum') || 'UNAVAILABLE')}`} style={{ background: '#0a0d14', padding: '8px 12px', borderRadius: '6px', display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ color: '#9ca3af' }}>Alchemy Mainnet:</span>
            <strong>{getProviderStatus('Alchemy Ethereum') || 'UNAVAILABLE'}</strong>
          </span>
          <span className={`dependency ${statusClass(system?.dependencies?.ofac || 'UNAVAILABLE')}`} style={{ background: '#0a0d14', padding: '8px 12px', borderRadius: '6px', display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ color: '#9ca3af' }}>OFAC Sanctions:</span>
            <strong>{system?.dependencies?.ofac || 'UNAVAILABLE'}</strong>
          </span>
          <span className={`dependency ${statusClass(system?.dependencies?.realtime || 'UNAVAILABLE')}`} style={{ background: '#0a0d14', padding: '8px 12px', borderRadius: '6px', display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ color: '#9ca3af' }}>Realtime Webhook Engine:</span>
            <strong>{system?.dependencies?.realtime || 'UNAVAILABLE'}</strong>
          </span>
        </div>
      </section>
    </section>
  );
}
