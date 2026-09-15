import { useEffect, useMemo, useState } from 'react';
import { dashboardIntelligence, dashboardSummary, listAlerts, listCases, systemProviders, systemStatus } from '../api';
import type { CaseListItem, DashboardIntelligence, DashboardSummary, ProviderOperationalStatus, RealtimeAlert, SystemStatus } from '../types';
import '../styles/operational-dashboard.css';

const statusClass = (value?: string) => {
  const state = String(value || 'UNAVAILABLE').toUpperCase();
  if (['CONNECTED', 'ONLINE', 'HEALTHY', 'READY', 'SUPPORTED'].includes(state)) return 'is-good';
  if (['DEGRADED', 'SIMULATED', 'DEVELOPMENT_FIXTURE'].includes(state)) return 'is-warn';
  return 'is-off';
};
const valueOrDash = (value: number | string | null | undefined) => value === null || value === undefined ? '—' : value;
const shortId = (value?: string | null) => value && value.length > 18 ? `${value.slice(0, 8)}…${value.slice(-5)}` : value || '—';
const timeAgo = (value?: string | null) => {
  if (!value) return '—';
  const elapsed = Math.max(0, Date.now() - new Date(value).getTime());
  const minutes = Math.floor(elapsed / 60000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
};

type Props = { onNavigate: (route: string) => void; onOpenCase: (caseId: string) => void };

export function OperationalDashboard({ onNavigate, onOpenCase }: Props) {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [intelligence, setIntelligence] = useState<DashboardIntelligence | null>(null);
  const [system, setSystem] = useState<SystemStatus | null>(null);
  const [cases, setCases] = useState<CaseListItem[]>([]);
  const [alerts, setAlerts] = useState<RealtimeAlert[]>([]);
  const [providers, setProviders] = useState<ProviderOperationalStatus[]>([]);
  const [error, setError] = useState('');
  const [refreshedAt, setRefreshedAt] = useState<Date | null>(null);

  const load = () => {
    Promise.all([dashboardSummary(), dashboardIntelligence(), systemStatus(), listCases(), listAlerts(), systemProviders().catch(() => [])])
      .then(([nextSummary, nextIntelligence, nextSystem, nextCases, nextAlerts, nextProviders]) => {
        setSummary(nextSummary); setIntelligence(nextIntelligence); setSystem(nextSystem); setCases(nextCases); setAlerts(nextAlerts); setProviders(nextProviders); setError(''); setRefreshedAt(new Date());
      }).catch((cause) => setError(cause instanceof Error ? cause.message : 'Operational intelligence unavailable'));
  };
  useEffect(() => { load(); const timer = window.setInterval(load, 10000); return () => window.clearInterval(timer); }, []);

  const priorityCases = intelligence?.priority_cases?.slice(0, 5) || [];
  const vaspRows = useMemo(() => {
    const seen = new Set<string>();
    return priorityCases.flatMap((item) => {
      const candidate = item.nearest_vasp;
      if (!candidate || seen.has(candidate.entity_id)) return [];
      seen.add(candidate.entity_id);
      return [{ ...candidate, caseId: item.case_id, caseLabel: item.external_case_reference || item.title }];
    });
  }, [priorityCases]);
  const riskMovements = intelligence?.risk_movements?.slice(0, 4) || [];
  const riskFactors = intelligence?.risk_factor_summary?.slice(0, 5) || [];
  const events = intelligence?.recent_intelligence_events?.slice(0, 7) || [];
  const apiState = system?.system || (error ? 'UNAVAILABLE' : 'LOADING');
  const metricCards = [
    { label: 'CRITICAL CASES', value: intelligence?.critical_cases, context: intelligence ? `${intelligence.critical_alerts} critical alert${intelligence.critical_alerts === 1 ? '' : 's'}` : 'Unavailable', tone: 'critical', route: 'cases', glyph: '!' },
    { label: 'ACTIVE WATCHES', value: intelligence?.active_watches, context: intelligence ? 'Persisted active targets' : 'Unavailable', tone: 'watch', route: 'monitoring', glyph: '◎' },
    { label: 'VASP LEADS', value: intelligence?.vasp_leads, context: intelligence ? `${intelligence.high_confidence_vasp_leads} high-confidence` : 'Unavailable', tone: 'vasp', route: 'entities', glyph: '▣' },
    { label: 'CROSS-CHAIN CASES', value: intelligence?.cross_chain_cases, context: intelligence ? `${intelligence.unresolved_cross_chain_cases} unresolved` : 'Unavailable', tone: 'cross', route: 'cross-chain', glyph: '↗' },
    { label: 'CASE FUSION', value: intelligence?.related_case_clusters, context: 'Exact overlap records', tone: 'fusion', route: 'cases', glyph: '◇' },
    { label: 'OPEN ALERTS', value: intelligence?.open_alerts, context: intelligence ? `${intelligence.critical_alerts} critical` : 'Unavailable', tone: 'alerts', route: 'alerts', glyph: '△' },
    { label: 'THREAT-INTEL CASES', value: intelligence?.threat_intel_match_cases, context: 'External direct matches', tone: 'alerts', route: 'cases', glyph: '!' },
    { label: 'P1 RECOMMENDATIONS', value: intelligence?.p1_recommendations, context: 'Current snapshots', tone: 'critical', route: 'cases', glyph: '!' }
  ];

  return <section className="ops-dashboard" aria-label="RRR operational intelligence command center">
    <header className="ops-command-header"><div className="ops-command-title"><span className="ops-kicker">RRR / INVESTIGATION COMMAND CENTER</span><h1>Crypto Fraud Intelligence &amp; VASP Attribution</h1></div><div className="ops-header-meta"><span className={`ops-system-badge ${statusClass(apiState)}`}><i /> {apiState}</span><span className="ops-refresh">Updated {refreshedAt ? refreshedAt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '—'}</span></div></header>
    <div className={`ops-status-strip ${statusClass(system?.dependencies?.postgresql || apiState)}`} role="status"><span className="ops-status-label"><i /> SYSTEM STATUS</span><strong>{system?.dependencies?.postgresql === 'CONNECTED' ? 'System ready' : 'Storage unavailable'}</strong><span>{system?.dependencies?.postgresql === 'CONNECTED' ? 'Core persistence and intelligence queries are available.' : system?.details?.postgresql || 'Intelligence metrics will populate when persistence is restored.'}</span></div>
    {error && <div className="ops-inline-error" role="alert">{error}</div>}

    <section className="ops-kpi-strip" aria-label="Operational metrics">{metricCards.map((card) => <button className={`ops-kpi-card ${card.tone}`} key={card.label} onClick={() => onNavigate(card.route)}><span className="ops-kpi-top"><span>{card.label}</span><b aria-hidden="true">{card.glyph}</b></span><strong>{valueOrDash(card.value)}</strong><small>{card.context}</small></button>)}</section>

    <section className="ops-main-grid">
      <div className="ops-panel ops-priority-panel"><PanelHeader eyebrow="PRIORITY INVESTIGATIONS" title="Cases requiring immediate review" action="VIEW ALL →" onAction={() => onNavigate('cases')} />
        {priorityCases.length ? <div className="ops-table-wrap"><table className="ops-table ops-priority-table"><thead><tr><th>CASE</th><th>FRAUD TYPE</th><th>RISK</th><th>Δ</th><th>WATCH</th><th>NEAREST VASP</th><th>RELATED</th><th>LAST ACTIVITY</th><th>ACTION</th></tr></thead><tbody>{priorityCases.map((item) => <tr key={item.case_id} className={item.risk_band === 'CRITICAL' ? 'is-urgent' : ''}><td><button className="ops-link-button ops-case-name" onClick={() => onOpenCase(item.case_id)}><strong>{item.external_case_reference || shortId(item.case_id)}</strong><small>{item.title}</small></button></td><td>{item.fraud_type || '—'}</td><td><span className={`ops-risk-badge ${String(item.risk_band || 'UNKNOWN').toLowerCase()}`}>{item.risk_band || '—'}<b>{item.risk_score == null ? '—' : item.risk_score}</b></span></td><td className={item.risk_delta > 0 ? 'ops-delta-up' : item.risk_delta < 0 ? 'ops-delta-down' : 'ops-muted'}>{item.risk_delta > 0 ? '+' : ''}{item.risk_delta ?? '—'}</td><td><span className={`ops-watch-badge ${item.watch_state === 'ACTIVE' ? 'active' : ''}`}><i />{item.watch_state === 'ACTIVE' ? 'LIVE' : 'INACTIVE'}</span></td><td>{item.nearest_vasp ? <button className="ops-link-button ops-vasp-cell" onClick={() => onOpenCase(item.case_id)}><strong>{item.nearest_vasp.entity_name}</strong><small>{item.nearest_vasp.confidence} · {item.nearest_vasp.hop_distance} hops</small></button> : <span className="ops-muted">Unresolved</span>}</td><td>{item.related_case_count ?? '—'}</td><td className="ops-time">{timeAgo(item.latest_activity_at)}</td><td><button className="ops-open-button" onClick={() => onOpenCase(item.case_id)}>OPEN <span>→</span></button></td></tr>)}</tbody></table></div> : <EmptyState title={intelligence ? 'No active persisted investigations' : 'Priority queue unavailable'} detail={intelligence ? 'Cases will appear here when persisted operational signals qualify for review.' : 'Restore API persistence to load the queue.'} />}
      </div>
      <div className="ops-panel ops-timeline-panel"><PanelHeader eyebrow="LIVE INVESTIGATION INTELLIGENCE" title="Real-time events, analysis and system updates" />{events.length ? <div className="ops-live-timeline">{events.map((event) => { const type = event?.event_type || ''; return <button className="ops-timeline-item" key={`${event.case_id}:${event.timestamp}:${type}`} onClick={() => onOpenCase(event.case_id)}><span className={`ops-timeline-dot ${type.includes('ALERT') ? 'alert' : type.includes('RISK') ? 'risk' : type.includes('PATTERN') ? 'pattern' : 'event'}`} /><span className="ops-time">{new Date(event.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</span><span className="ops-timeline-copy"><strong>{type.replaceAll('_', ' ') || 'INTELLIGENCE EVENT'}</strong><small>{event.summary}</small></span><span className="ops-timeline-case">↗</span></button>; })}</div> : <EmptyState title="No recent persisted intelligence events" detail={intelligence ? 'Timeline entries will appear after acquisition, reassessment, or realtime processing.' : 'Unavailable until the intelligence read model responds.'} />}</div>
    </section>

    <section className="ops-secondary-grid">
      <div className="ops-panel"><PanelHeader eyebrow="VASP ACTIONABILITY" title="Top source-backed leads" action="VIEW ALL →" onAction={() => onNavigate('entities')} />{vaspRows.length ? <div className="ops-compact-list">{vaspRows.map((item, index) => <button className="ops-compact-row" key={item.entity_id} onClick={() => onOpenCase(item.caseId)}><span className="ops-rank">#{index + 1}</span><span className="ops-compact-main"><strong>{item.entity_name}</strong><small>{item.caseLabel}</small></span><span><b className="ops-confidence">{item.confidence}</b><small>{item.hop_distance} hops</small></span><span className="ops-row-arrow">View →</span></button>)}</div> : <EmptyState title="No source-backed VASP leads" detail="Candidate ranking requires persisted attribution records and a trace." />}</div>
      <div className="ops-panel"><PanelHeader eyebrow="RISK INTELLIGENCE" title="Current posture and contributing factors" action="VIEW DETAILS →" onAction={() => onNavigate('patterns')} />{riskMovements.length ? <><div className="ops-risk-summary"><div><small>CURRENT SCORE</small><strong>{riskMovements[0].score} <em>/ 100</em></strong><span className={`ops-risk-badge ${(riskMovements[0]?.risk_band || 'UNKNOWN').toLowerCase()}`}>{riskMovements[0]?.risk_band || '—'}</span></div><div className="ops-risk-delta"><b>{(riskMovements[0].score_delta || 0) >= 0 ? '+' : ''}{riskMovements[0].score_delta || 0}</b><small>latest delta</small></div></div><div className="ops-risk-factors">{riskFactors.length ? riskFactors.map((factor) => <div className="ops-risk-factor" key={factor.name}><span>{factor.name}</span><b>+{factor.contribution}</b><i><em style={{ width: `${Math.min(100, Math.max(0, factor.contribution / Math.max(1, factor.max_contribution) * 100))}%` }} /></i><small>{factor.evidence_count} evidence</small></div>) : <p className="ops-muted">Factor detail is available in the case risk workspace.</p>}</div></> : <EmptyState title="No completed risk assessment" detail="Risk posture appears after a persisted rule-based assessment." />}</div>
      <div className="ops-panel ops-fusion-panel"><PanelHeader eyebrow="RRR CASE FUSION" title="Related investigations and shared infrastructure" action="VIEW CASES →" onAction={() => onNavigate('cases')} />{priorityCases.some((item) => item.related_case_count > 0) ? <><div className="ops-fusion-map">{priorityCases.filter((item) => item.related_case_count > 0).slice(0, 4).map((item) => <button key={item.case_id} onClick={() => onOpenCase(item.case_id)}>{item.external_case_reference || shortId(item.case_id)}</button>)}<span>CONFIRMED<br />OVERLAP</span></div><p className="ops-fusion-note">Shared infrastructure is an investigative lead and does not prove common ownership or common criminal control.</p></> : <EmptyState title="No related persisted infrastructure identified" detail="Only exact shared wallet or transaction relationships are shown." />}</div>
    </section>

    <section className="ops-panel ops-health-panel"><PanelHeader eyebrow="SYSTEM & PROVIDER HEALTH" title="Infrastructure and provider connectivity" action="VIEW DETAILS →" onAction={() => onNavigate('operations')} /><div className="ops-health-grid">{['postgresql', 'Alchemy Ethereum', 'TronGrid', 'Neo4j', 'realtime', 'SAHYOG'].map((name) => { const value = name === 'postgresql' ? system?.dependencies?.postgresql : name === 'realtime' ? system?.dependencies?.realtime : name === 'SAHYOG' ? 'SIMULATED' : providers.find((provider) => (provider?.provider || '').toLowerCase().includes(name.toLowerCase()))?.status; return <button className="ops-health-item" key={name} onClick={() => onNavigate('operations')}><i className={statusClass(value)} /><span>{name}</span><b>{value || 'NOT CONFIGURED'}</b></button>; })}</div></section>
    <div className="ops-diagnostics"><span>{cases.length ? `${cases.length} cases loaded` : 'Case registry unavailable'}</span><span>{summary?.transactions_analyzed == null ? 'Transactions —' : `${summary.transactions_analyzed} transactions observed`}</span><span>{alerts.length ? `${alerts.length} alerts loaded` : 'Alerts —'}</span><span>PostgreSQL remains authoritative</span></div>
  </section>;
}

function PanelHeader({ eyebrow, title, action, onAction }: { eyebrow: string; title: string; action?: string; onAction?: () => void }) { return <div className="ops-panel-header"><div><span className="ops-kicker">{eyebrow}</span><h2>{title}</h2></div>{action && onAction && <button className="ops-text-button" onClick={onAction}>{action}</button>}</div>; }
function EmptyState({ title, detail }: { title: string; detail: string }) { return <div className="ops-empty"><strong>{title}</strong><span>{detail}</span></div>; }
