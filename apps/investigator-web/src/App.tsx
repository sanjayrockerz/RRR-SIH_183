import { useEffect, useState } from 'react';
import { Shell } from './components/Shell';
import { GraphInspector, GraphUnavailable } from './components/GraphInspector';
import { PatternsPage } from './components/PatternsPage';
import { RiskPage } from './components/RiskPage';
import { RealtimePage } from './components/RealtimePage';
import { CrossChainPage } from './components/CrossChainPage';
import { EvidenceLedgerPanel } from './components/EvidenceLedgerPanel';
import { ReportsPage } from './components/ReportsPage';
import { RelatedCasesPanel } from './components/RelatedCasesPanel';
import { ConnectedIntake } from './components/ConnectedIntake';
import { WorkflowPanel } from './components/WorkflowPanel';
import { ReadableEvidencePage } from './components/ReadableEvidencePage';
import { SyntheticGenerator } from './components/SyntheticGenerator';
import { SyntheticRealtimeControl } from './components/SyntheticRealtimeControl';
import { LiveIntelligence } from './components/LiveIntelligence';
import { RunInvestigationDemo } from './components/RunInvestigationDemo';
import { TransactionLedger } from './components/TransactionLedger';
import { CaseCommandCenter } from './components/CaseCommandCenter';
import { OperationalDashboard } from './components/OperationalDashboard';
import { api, caseScreenings, intelligenceSources, screenCase, systemStatus } from './api';
import type { AddressScreening, Case, IntelligenceSource, Trace, InvestigationOperationalState } from './types';
import { Dashboard, GenericPage, Intake, Workspace, CasesPage, WalletsPage, EntitiesPage, EvidencePage, AlertsPage, ProviderOperationsPage } from './pages';

const caseRouteAliases: Record<string, string> = {
  overview: 'case',
  case: 'case',
  transactions: 'transactions',
  ledger: 'transactions',
  graph: 'graph',
  'transaction-graph': 'graph',
  'fund-flow': 'fund-flow',
  patterns: 'patterns',
  risk: 'risk',
  realtime: 'monitoring',
  monitoring: 'monitoring',
  entities: 'entities',
  vasp: 'entities',
  'cross-chain': 'cross-chain',
  'threat-intelligence': 'threat-intelligence',
  sanctions: 'sanctions',
  evidence: 'evidence',
  timeline: 'timeline',
  reports: 'reports',
  report: 'reports'
};
const caseRouteLabels: Record<string, string> = {
  case: 'overview',
  transactions: 'transactions',
  graph: 'graph',
  'fund-flow': 'fund-flow',
  patterns: 'patterns',
  risk: 'risk',
  monitoring: 'realtime',
  entities: 'entities',
  'cross-chain': 'cross-chain',
  'threat-intelligence': 'threat-intelligence',
  sanctions: 'sanctions',
  evidence: 'evidence',
  timeline: 'timeline',
  reports: 'reports'
};
const caseRouteSet = new Set(Object.values(caseRouteAliases));
const routeFromHash = () => decodeURIComponent(location.hash.slice(1) || 'dashboard');
function parseRoute(value: string) {
  const clean = value.replace(/^#?\/?/, '');
  const [path, query = ''] = clean.split('?');
  const parts = path.split('/').filter(Boolean);
  if (parts[0] === 'cases' && parts[1]) {
    const rawModule = parts[2] || 'overview';
    return { raw: value, caseId: parts[1], module: caseRouteAliases[rawModule] || rawModule, query: new URLSearchParams(query) };
  }
  return { raw: value, caseId: '', module: caseRouteAliases[path] || path || 'dashboard', query: new URLSearchParams(query) };
}

export default function App() {
  const [route, setRoute] = useState(routeFromHash());
  const [caseData, setCaseData] = useState<Case | null>(null);
  const [trace, setTrace] = useState<Trace | null>(null);
  const [opState, setOpState] = useState<InvestigationOperationalState | null>(null);
  const [apiState, setApiState] = useState('UNKNOWN');
  
  const [busy, setBusy] = useState(false);
  const [runError, setRunError] = useState('');

  useEffect(() => {
    const onClick = (event: Event) => {
      const target = event.target as HTMLElement;
      const tab = target.closest('.case-tabs span');
      if (tab) {
        // Case workspace tabs own their route. Do not let the legacy global
        // navigation mapping below overwrite graph/transaction/etc. routes.
        return;
      }
      const integration = target.closest('.integration-link');
      if (integration && integration.textContent?.includes('VASP')) {
        location.hash = 'entities';
        return;
      }
      const metric = target.closest('.metric-card');
      const label = metric?.querySelector('span')?.textContent || '';
      const metricRoutes: { [key: string]: string } = {
        "ACTIVE CASES": 'cases',
        "WALLETS UNDER REVIEW": 'wallets',
        "HIGH-PRIORITY ALERTS": 'alerts',
        "ATTRIBUTED ENTITIES": 'entities',
        "OBSERVED TRANSACTIONS": 'transactions',
        "ACTIVE WATCHES": 'monitoring'
      };
      if (metric && metricRoutes[label]) location.hash = metricRoutes[label];
    };
    document.addEventListener('click', onClick);
    return () => document.removeEventListener('click', onClick);
  }, []);

  useEffect(() => {
    const onHash = () => setRoute(routeFromHash());
    addEventListener('hashchange', onHash);
    systemStatus()
      .then(result => setApiState(result.system === 'CONNECTED' ? 'ONLINE' : result.system))
      .catch(() => setApiState('UNAVAILABLE'));
    return () => removeEventListener('hashchange', onHash);
  }, []);

  const routeInfo = parseRoute(route);
  const activeRoute = routeInfo.module;

  function caseHash(caseId: string, module: string, query = '') {
    return `/cases/${caseId}/${caseRouteLabels[module] || module}${query ? `?${query}` : ''}`;
  }

  function navigate(next: string, query = '') {
    const module = caseRouteAliases[next] || next;
    const target = caseData && caseRouteSet.has(module) ? caseHash(caseData.case_id, module, query) : module;
    location.hash = target;
    setRoute(target);
  }

  async function completed(caseResult: Case, traceResult: Trace) {
    setCaseData(caseResult);
    setTrace(traceResult);
    try {
      const stateData = await api.operationalState(caseResult.case_id);
      setOpState(stateData);
    } catch {}
    const target = caseHash(caseResult.case_id, 'case');
    location.hash = target;
    setRoute(target);
  }

  async function openCase(caseId: string, targetModule = 'case') {
    const log = (msg: string) => console.info(`[RRR] ${msg}`);
    log(`CASE OPEN case_id=${caseId}`);
    try {
      // Summary is the authoritative persisted snapshot for the workspace.
      // Load it before rendering any case section so counts never default to 0.
      const summaryData = await api.summary(caseId);
      const loaded = await api.getCase(caseId);
      setCaseData(loaded);
      const loadedGraph = loaded.latest_trace ? await api.graph(caseId) : null;
      setTrace(loadedGraph || loaded.latest_trace || null);
      localStorage.setItem('rrr_active_case_id', caseId);
      log(`CASE LOADED title="${loaded.title}" has_trace=${!!loaded.latest_trace}`);
      try {
        const stateData = await api.operationalState(caseId);
        setOpState({ ...stateData, summary: summaryData });
        log(`CASE OPERATIONAL STATE loaded stages=${stateData.stages?.length ?? 0}`);
      } catch (err) {
        console.warn('[RRR] CASE OPERATIONAL STATE failed (non-fatal):', err instanceof Error ? err.message : err);
      }
      // Keep the investigator in one continuous case workspace.
      const module = caseRouteAliases[targetModule] || 'case';
      const target = caseHash(caseId, module);
      location.hash = target;
      setRoute(target);
    } catch (err) {
      console.error('[RRR] CASE OPEN FAILED:', err instanceof Error ? err.message : err);
      setCaseData(null);
      setTrace(null);
      setOpState(null);
      navigate('cases');
    }
  }

  // Restore case context after page refresh or direct hash navigation.
  useEffect(() => {
    if (caseRouteSet.has(activeRoute)) {
      const savedId = routeInfo.caseId || localStorage.getItem('rrr_active_case_id');
      if (savedId && (!caseData || caseData.case_id !== savedId)) {
        console.info(`[RRR] CASE RESTORE route=${activeRoute} case_id=${savedId}`);
        openCase(savedId, activeRoute);
      }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [route, activeRoute, routeInfo.caseId]);


  async function runInvestigation() {
    if (!caseData) return;
    const root = caseData.wallets[0];
    const wallet = root?.address;
    if (!wallet) {
      setRunError('Add a reported wallet before running investigation.');
      return;
    }
    setBusy(true);
    setRunError('');
    try {
      const next = await api.investigate(caseData.case_id, {
        address: wallet,
        chain: root.chain,
        start_watch: true,
        create_report: false
      });
      setOpState(next);
      if (next.case) {
        setCaseData(next.case);
        if (next.case.latest_trace) setTrace(next.case.latest_trace);
      }
    } catch (err) {
      setRunError(err instanceof Error ? err.message : 'Investigation failed');
    } finally {
      setBusy(false);
    }
  }

  let page;
  const isCaseScoped = caseRouteSet.has(activeRoute) && caseData;

  if (isCaseScoped && caseData) {
    let subContent;
    if (activeRoute === 'case') {
      if (trace) {
        subContent = (
          <>
            <CaseCommandCenter caseData={caseData} state={opState} onNavigate={navigate} />
            <WorkflowPanel caseId={caseData.case_id} />
            <RelatedCasesPanel caseId={caseData.case_id} />
          </>
        );
      } else {
        subContent = <CaseTraceUnavailable caseData={caseData} onNavigate={navigate} />;
      }
    } else if (activeRoute === 'transactions') {
      subContent = <TransactionLedger caseId={caseData.case_id} onOpenGraph={(txHash) => navigate('graph', txHash ? `tx=${encodeURIComponent(txHash)}` : '')} />;
    } else if (activeRoute === 'graph') {
      if (trace) {
        subContent = <GraphInspector trace={trace} selectedTx={routeInfo.query.get('tx') || undefined} />;
      } else {
        subContent = <GraphUnavailable onNavigate={navigate} />;
      }
    } else if (activeRoute === 'fund-flow') {
      subContent = trace ? <FundFlowWorkspace trace={trace} onOpenTransaction={(txHash) => navigate('graph', `tx=${encodeURIComponent(txHash)}`)} /> : <GraphUnavailable onNavigate={navigate} />;
    } else if (activeRoute === 'patterns') {
      if (trace) {
        subContent = <PatternsPage caseData={caseData} trace={trace} onNavigate={navigate} />;
      } else {
        subContent = <div className="surface" style={{ padding: 20 }}>No trace available for pattern analysis. Run pipeline trace first.</div>;
      }
    } else if (activeRoute === 'risk') {
      if (trace) {
        subContent = <RiskPage caseData={caseData} trace={trace} onNavigate={navigate} />;
      } else {
        subContent = <div className="surface" style={{ padding: 20 }}>No trace available for risk assessment. Run pipeline trace first.</div>;
      }
    } else if (activeRoute === 'entities') {
      subContent = <CaseEntitiesWorkspace state={opState} />;
    } else if (activeRoute === 'threat-intelligence') {
      subContent = <ThreatWorkspace caseData={caseData} />;
    } else if (activeRoute === 'sanctions') {
      subContent = <SanctionsWorkspace caseData={caseData} />;
    } else if (activeRoute === 'evidence') {
      subContent = (
        <>
          <ReadableEvidencePage caseData={caseData} />
          <EvidenceLedgerPanel caseId={caseData.case_id} />
        </>
      );
    } else if (activeRoute === 'timeline') {
      subContent = <TimelineWorkspace state={opState} />;
    } else if (activeRoute === 'reports') {
      subContent = <ReportsPage caseData={caseData} trace={trace || undefined} />;
    } else if (activeRoute === 'monitoring') {
      if (trace) {
        subContent = <RealtimePage caseData={caseData} trace={trace} />;
      } else {
        subContent = <div className="surface" style={{ padding: 20 }}>No trace available for real-time monitoring. Run pipeline trace first.</div>;
      }
    } else if (activeRoute === 'cross-chain') {
      if (trace) {
        subContent = <CrossChainPage caseData={caseData} trace={trace} />;
      } else {
        subContent = <div className="surface" style={{ padding: 20 }}>No trace available for cross-chain analysis. Run pipeline trace first.</div>;
      }
    }

    const activeCase = opState?.case || caseData;
    const risk = opState?.risk || opState?.summary?.risk || null;

    page = (
      <div className="case-workspace-layout" style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
        <header className="case-command-head" style={{ borderBottom: '1px solid #1f2937', paddingBottom: '15px', marginBottom: '5px' }}>
          <div>
            <span className="eyebrow" style={{ color: '#60a5fa', textTransform: 'uppercase', fontSize: '11px', fontWeight: 'bold' }}>
              INVESTIGATIONS / CASES / {activeCase.case_id.slice(0, 8).toUpperCase()}
            </span>
            <h1 style={{ fontSize: '26px', margin: '4px 0', color: '#f3f4f6', fontWeight: 600 }}>{activeCase.title}</h1>
            <p style={{ fontSize: '13px', margin: 0, color: '#9ca3af' }}>
              {activeCase.fraud_type} | {activeCase.external_case_reference || 'No external reference'} | Updated {new Date(activeCase.updated_at).toLocaleString()}
            </p>
            {runError && <div className="error" style={{ marginTop: '8px' }}>{runError}</div>}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <button className="primary" onClick={runInvestigation} disabled={busy} style={{ minWidth: '150px' }}>
              {busy ? 'Running Traces...' : 'RUN PIPELINE'}
            </button>
            <button className="secondary" onClick={() => navigate('cases')}>BACK TO CASES</button>
            <div className="case-posture" style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end' }}>
                <span className={`risk-band ${(risk?.band || 'unknown').toLowerCase()}`} style={{ padding: '3px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: 'bold', textTransform: 'uppercase' }}>
                  {risk?.band || 'NOT ASSESSED'}
                </span>
                <small style={{ fontSize: '10px', color: '#9ca3af', marginTop: '4px' }}>
                  {risk?.priority || activeCase.priority} PRIORITY
                </small>
              </div>
              <b style={{ fontSize: '32px', color: '#f3f4f6', lineHeight: 1 }}>
                {risk ? `${risk.score}` : '--'}<span style={{ fontSize: '16px', color: '#9ca3af', fontWeight: 'normal' }}>/100</span>
              </b>
            </div>
          </div>
        </header>

        <nav className="case-tabs" style={{ display: 'flex', gap: '4px', borderBottom: '1px solid #1f2937', paddingBottom: '1px', marginBottom: '15px', flexWrap: 'wrap' }}>
          {[
            { id: 'case', label: 'OVERVIEW' },
            { id: 'transactions', label: 'TRANSACTION LEDGER' },
            { id: 'fund-flow', label: 'FUND FLOW' },
            { id: 'graph', label: 'GRAPH' },
            { id: 'patterns', label: 'PATTERNS' },
            { id: 'risk', label: 'RISK INTELLIGENCE' },
            { id: 'monitoring', label: 'REAL-TIME RETRACING' },
            { id: 'entities', label: 'ENTITIES / VASP' },
            { id: 'cross-chain', label: 'CROSS-CHAIN' },
            { id: 'threat-intelligence', label: 'THREAT INTEL' },
            { id: 'sanctions', label: 'SANCTIONS' },
            { id: 'evidence', label: 'EVIDENCE' },
            { id: 'timeline', label: 'TIMELINE' },
            { id: 'reports', label: 'REPORT' }
          ].map(tab => {
            const active = activeRoute === tab.id;
            return (
              <span 
                key={tab.id}
                className={active ? 'active' : ''}
                onClick={() => navigate(tab.id)}
                style={{
                  padding: '10px 14px',
                  fontSize: '12px',
                  fontWeight: 'bold',
                  cursor: 'pointer',
                  color: active ? '#60a5fa' : '#9ca3af',
                  borderBottom: active ? '2px solid #60a5fa' : '2px solid transparent',
                  transition: 'all 0.15s ease',
                  whiteSpace: 'nowrap'
                }}
              >
                {tab.label}
              </span>
            );
          })}
        </nav>

        {subContent}
      </div>
    );
  } else {
    if (activeRoute === 'dashboard') page = <><OperationalDashboard onNavigate={navigate} onOpenCase={openCase} /><RunInvestigationDemo onOpen={() => navigate('realtime')} /><SyntheticGenerator onOpen={openCase} /></>;
    else if (activeRoute === 'dev/realtime') page = <><SyntheticRealtimeControl /><LiveIntelligence /></>;
    else if (activeRoute === 'investigate' || activeRoute === 'intake') page = <ConnectedIntake onComplete={completed} />;
    else if (activeRoute === 'realtime') page = <><SyntheticRealtimeControl /><LiveIntelligence /></>;
    else if (activeRoute === 'cases') page = <CasesPage onNavigate={navigate} onOpenCase={openCase} />;
    else if (activeRoute === 'wallets') page = <WalletsPage />;
    else if (activeRoute === 'entities') page = <EntitiesPage />;
    else if (activeRoute === 'alerts') page = <AlertsPage />;
    else if (activeRoute === 'operations') page = <ProviderOperationsPage />;
    else page = <OperationalDashboard onNavigate={navigate} onOpenCase={openCase} />;
  }

  return (
    <Shell route={activeRoute} onNavigate={navigate} apiState={apiState} caseData={caseData}>
      <div className="api-notice">
        <span className={apiState === 'ONLINE' ? 'ok-dot' : 'warn-dot'} /> API {apiState} · Historical blockchain data only
      </div>
      {page}
    </Shell>
  );
}

function PageTitle({ eyebrow, title }: { eyebrow: string; title: string }) {
  return (
    <div className="page-header">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
      </div>
    </div>
  );
}

const shortValue = (value?: string) => value && value.length > 18 ? `${value.slice(0, 10)}...${value.slice(-6)}` : (value || 'Unavailable');

function FundFlowWorkspace({ trace, onOpenTransaction }: { trace: Trace; onOpenTransaction: (txHash: string) => void }) {
  const sortedEdges = [...trace.edges].sort((a, b) => a.hop - b.hop || String(a.transfer.timestamp || '').localeCompare(String(b.transfer.timestamp || '')));
  const largest = [...sortedEdges].sort((a, b) => Number(b.transfer.amount) - Number(a.transfer.amount))[0];
  const vaspLike = sortedEdges.find(edge => /exchange|vasp|custodial|deposit/i.test(`${edge.target} ${edge.transfer.provider}`));
  return (
    <section className="ledger-workspace">
      <header className="ledger-header">
        <div>
          <span className="eyebrow">CASE / FUND FLOW</span>
          <h1>Hop-by-hop money movement</h1>
          <p>Fund Flow is reconstructed from persisted graph edges, transaction rows, and evidence references.</p>
        </div>
        <div className="ledger-count"><b>{sortedEdges.length}</b><small>PERSISTED HOPS</small></div>
      </header>
      <div className="pattern-summary-grid">
        <div className="metric-card"><span>ROOT WALLET</span><b className="mono">{shortValue(trace.root_address)}</b><small>{trace.mode} | {trace.provider}</small></div>
        <div className="metric-card"><span>LARGEST VALUE FLOW</span><b>{largest ? `${largest.transfer.amount} ${largest.transfer.asset}` : '--'}</b><small>{largest ? shortValue(largest.transaction_hash) : 'No edge'}</small></div>
        <div className="metric-card"><span>VASP PATH</span><b>{vaspLike ? 'CANDIDATE' : 'NOT OBSERVED'}</b><small>Only source-backed attribution is asserted elsewhere</small></div>
        <div className="metric-card"><span>SHORTEST PATHS</span><b>{trace.metrics.path_count}</b><small>Persisted graph path count</small></div>
      </div>
      <section className="surface">
        <div className="panel-title"><div className="eyebrow">FORWARD / BACKWARD / SUSPICIOUS PATH READOUT</div><h3>{sortedEdges.length ? 'Observed transfer sequence' : 'No persisted fund flow'}</h3></div>
        {sortedEdges.length ? (
          <div className="ledger-table">
            <div className="ledger-row ledger-head"><span>HOP</span><span>WALLET</span><span>COUNTERPARTY</span><span>TRANSFER</span><span>TX</span><span>PROVIDER</span></div>
            {sortedEdges.map((edge, index) => (
              <button className="ledger-row" key={edge.edge_id || `${edge.transaction_hash}-${index}`} onClick={() => onOpenTransaction(edge.transaction_hash)}>
                <span><b>#{edge.hop ?? index + 1}</b><small>{edge.transfer.chain || 'ethereum'}</small></span>
                <span className="mono">{shortValue(edge.source)}</span>
                <span className="mono">{shortValue(edge.target)}</span>
                <span><b>{edge.transfer.amount} {edge.transfer.asset}</b><small>{edge.transfer.timestamp ? new Date(edge.transfer.timestamp).toLocaleString() : 'Timestamp unavailable'}</small></span>
                <span className="mono">{shortValue(edge.transaction_hash)}</span>
                <span>{edge.transfer.provider}</span>
              </button>
            ))}
          </div>
        ) : (
          <div className="empty-block"><b>EMPTY INVESTIGATION</b><p>Case exists, but no persisted graph edges are available for fund-flow reconstruction.</p></div>
        )}
      </section>
    </section>
  );
}

function CaseEntitiesWorkspace({ state }: { state: InvestigationOperationalState | null }) {
  const attributions = (state?.attributions || []) as any[];
  return (
    <section className="surface">
      <div className="panel-title"><div className="eyebrow">CASE / ENTITIES AND VASP</div><h3>{attributions.length ? `${attributions.length} source-backed attribution path(s)` : 'No case attribution exposure'}</h3></div>
      {attributions.length ? (
        <div className="ledger-table">
          <div className="ledger-row ledger-head"><span>ENTITY</span><span>TYPE</span><span>ADDRESS</span><span>CONFIDENCE</span><span>DISTANCE</span><span>EVIDENCE</span></div>
          {attributions.map((item, index) => (
            <div className="ledger-row" key={`${item.entity?.entity_id || index}-${item.address}`}>
              <span><b>{item.entity?.name || 'Unknown entity'}</b><small>{item.role || 'Role unavailable'}</small></span>
              <span>{item.entity?.entity_type || 'UNKNOWN'}</span>
              <span className="mono">{shortValue(item.address)}</span>
              <span>{item.confidence || 'UNKNOWN'}</span>
              <span>{item.hop_distance ?? 'Unknown'} hop(s)</span>
              <span>{item.evidence?.length || 0} linked item(s)</span>
            </div>
          ))}
        </div>
      ) : (
        <div className="empty-block"><b>UNKNOWN</b><p>No source-backed VASP/entity attribution is linked to this case graph. No VASP exposure is asserted.</p></div>
      )}
    </section>
  );
}

function ThreatWorkspace({ caseData }: { caseData: Case }) {
  const [sources, setSources] = useState<IntelligenceSource[]>([]);
  const [error, setError] = useState('');
  useEffect(() => { intelligenceSources().then(setSources).catch(e => setError(e instanceof Error ? e.message : 'Threat intelligence sources unavailable')) }, []);
  return (
    <section className="surface">
      <div className="panel-title"><div className="eyebrow">CASE / THREAT INTELLIGENCE</div><h3>{sources.length ? `${sources.length} configured source(s)` : 'Provider status unknown'}</h3></div>
      {error && <div className="error" role="alert">{error}</div>}
      <div className="ledger-table">
        <div className="ledger-row ledger-head"><span>WALLET</span><span>THREAT OBSERVATION</span><span>SOURCE STATUS</span><span>EVIDENCE</span></div>
        {caseData.wallets.map(wallet => (
          <div className="ledger-row" key={`${wallet.chain}-${wallet.address}`}>
            <span className="mono">{shortValue(wallet.address)}</span>
            <span>UNKNOWN</span>
            <span>{sources.length ? sources.map(source => source.status).join(', ') : 'NOT CONFIGURED'}</span>
            <span>No source-backed threat observation persisted</span>
          </div>
        ))}
      </div>
    </section>
  );
}

function SanctionsWorkspace({ caseData }: { caseData: Case }) {
  const [items, setItems] = useState<AddressScreening[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const refresh = () => caseScreenings(caseData.case_id).then(setItems).catch(e => setError(e instanceof Error ? e.message : 'Sanctions screening unavailable'));
  useEffect(() => { refresh() }, [caseData.case_id]);
  async function run() { setBusy(true); setError(''); try { await screenCase(caseData.case_id); await refresh() } catch (e) { setError(e instanceof Error ? e.message : 'Sanctions screening failed') } finally { setBusy(false) } }
  return (
    <section className="surface">
      <div className="panel-title"><div className="eyebrow">CASE / SANCTIONS SCREENING</div><h3>{items.length ? `${items.length} screening result(s)` : 'No screening run persisted'}</h3><button className="secondary" onClick={run} disabled={busy}>{busy ? 'SCREENING...' : 'SCREEN CASE WALLETS'}</button></div>
      {error && <div className="error" role="alert">{error}</div>}
      {items.length ? (
        <div className="ledger-table">
          <div className="ledger-row ledger-head"><span>WALLET</span><span>CHAIN</span><span>STATUS</span><span>SOURCE</span><span>CHECKED</span><span>REASON</span></div>
          {items.map(item => (
            <div className="ledger-row" key={`${item.chain}-${item.address}-${item.screened_at}`}>
              <span className="mono">{shortValue(item.address)}</span><span>{item.chain}</span><span>{item.outcome}</span><span>{item.source_status}</span><span>{new Date(item.screened_at).toLocaleString()}</span><span>{item.explanation}</span>
            </div>
          ))}
        </div>
      ) : (
        <div className="empty-block"><b>UNKNOWN</b><p>No sanctions conclusion has been drawn. Run screening to record MATCH, NO MATCH, UNKNOWN, or NOT CONFIGURED from the backend provider boundary.</p></div>
      )}
    </section>
  );
}

function TimelineWorkspace({ state }: { state: InvestigationOperationalState | null }) {
  const events = state?.workflow_events || [];
  return (
    <section className="surface">
      <div className="panel-title"><div className="eyebrow">CASE / TIMELINE</div><h3>{events.length ? `${events.length} workflow event(s)` : 'No workflow events loaded'}</h3></div>
      {events.length ? events.map(event => <div className="timeline-row" key={event.event_id}><time>{new Date(event.completed_at || event.started_at).toLocaleString()}</time><div><strong>{event.stage.replaceAll('_',' ')}</strong><p>{event.provider || 'RRR'} | {event.result_count ?? 0} record(s)</p>{event.error && <small>{event.error}</small>}</div></div>) : <div className="empty-block"><b>No persisted workflow events</b><p>Timeline entries appear after case creation, acquisition, risk assessment, realtime processing, and report generation.</p></div>}
    </section>
  );
}

function CaseTraceUnavailable({ caseData, onNavigate }: { caseData: Case; onNavigate: (route: string) => void }) {
  return (
    <section className="case-unavailable">
      <div className="eyebrow">CASE / {caseData.case_id}</div>
      <h1>{caseData.title}</h1>
      <div className="surface">
        <span className="data-badge warning">NO PERSISTED TRACE</span>
        <h2>Case context loaded</h2>
        <p>This case was reopened from PostgreSQL, but no completed trace is available yet. Start a bounded historical trace from the investigation intake before opening the graph workspace.</p>
        <button className="primary" onClick={() => onNavigate('investigate')}>START TRACE</button>
      </div>
    </section>
  );
}
