import { useEffect, useState } from 'react';
import type { Case, Trace, InvestigationOperationalState, FundFlowSummary, VaspExposureItem, VaspProximityCandidate, TimeToVasp, FundAtRisk, AttributionResult, CaseLink, EvidenceRecord, RealtimeAlert, CaseTransaction } from '../types';
import { api, caseFundFlow, caseVaspExposure, caseNearestVasps, caseFundAtRisk, caseTimeToVasp, vaspAddressAttribution, listEvidence, relatedCases, createEvidenceManifest, createReport } from '../api';
import { TransactionLedger } from './TransactionLedger';
import { FundFlowPage } from './FundFlowPage';
import { PatternsPage } from './PatternsPage';
import { CrossChainPage } from './CrossChainPage';
import { RelatedCasesPanel } from './RelatedCasesPanel';
import { ReadableEvidencePage } from './ReadableEvidencePage';
import { EvidenceLedgerPanel } from './EvidenceLedgerPanel';
import { FraudNetworkPage } from './FraudNetworkPage';

interface Props {
  caseData: Case;
  trace: Trace | null;
  opState: InvestigationOperationalState | null;
  onNavigate: (route: string, query?: string) => void;
  onRefresh?: () => void;
}

export function InvestigateWorkspace({ caseData, trace, opState, onNavigate, onRefresh }: Props) {
  const [activeTab, setActiveTab] = useState<'overview' | 'transactions' | 'fund-flow' | 'entities' | 'patterns' | 'cross-chain' | 'fraud-network' | 'related' | 'evidence' | 'actions'>('overview');

  
  // Data states
  const [fundFlow, setFundFlow] = useState<FundFlowSummary | null>(null);
  const [vaspExposure, setVaspExposure] = useState<VaspExposureItem[]>([]);
  const [nearestVasps, setNearestVasps] = useState<VaspProximityCandidate[]>([]);
  const [fundAtRisk, setFundAtRisk] = useState<FundAtRisk | null>(null);
  const [timeToVasp, setTimeToVasp] = useState<TimeToVasp | null>(null);
  const [attribution, setAttribution] = useState<AttributionResult | null>(null);
  const [evidenceList, setEvidenceList] = useState<EvidenceRecord[]>([]);
  const [links, setLinks] = useState<CaseLink[]>([]);
  const [alerts, setAlerts] = useState<RealtimeAlert[]>([]);
  const [txList, setTxList] = useState<CaseTransaction[]>([]);
  
  // Loading & Action states
  const [loading, setLoading] = useState(true);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [selectedEvidence, setSelectedEvidence] = useState<any | null>(null);
  
  // Reported wallet info
  const reportedWallet = caseData.wallets?.[0]?.address || trace?.root_address || '0x0000000000000000000000000000000000000000';
  const chain = caseData.wallets?.[0]?.chain || 'ethereum';

  // Fund Flow Filter States
  const [hopFilter, setHopFilter] = useState<number | 'ALL'>('ALL');
  const [assetFilter, setAssetFilter] = useState<string>('ALL');
  const [zoomLevel, setZoomLevel] = useState<number>(100);

  const loadData = async () => {
    setLoading(true);
    try {
      const [ff, exp, near, far, ttv, evs, lks, alr, txs] = await Promise.all([
        caseFundFlow(caseData.case_id).catch(() => null),
        caseVaspExposure(caseData.case_id).catch(() => []),
        caseNearestVasps(caseData.case_id).catch(() => []),
        caseFundAtRisk(caseData.case_id).catch(() => null),
        caseTimeToVasp(caseData.case_id).catch(() => null),
        listEvidence(caseData.case_id).catch(() => []),
        relatedCases(caseData.case_id).catch(() => []),
        api.realtimeAlerts(caseData.case_id).catch(() => []),
        api.transactions(caseData.case_id, 100).catch(() => [])
      ]);
      setFundFlow(ff);
      setVaspExposure(exp);
      setNearestVasps(near);
      setFundAtRisk(far);
      setTimeToVasp(ttv);
      setEvidenceList(evs);
      setLinks(lks);
      setAlerts(alr);
      setTxList(txs);

      if (reportedWallet) {
        vaspAddressAttribution(chain, reportedWallet)
          .then(res => setAttribution(res))
          .catch(() => setAttribution(null));
      }
    } catch (err) {
      console.warn('[InvestigateWorkspace] Error loading intelligence:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    // Real-time update poll every 10 seconds
    const interval = setInterval(loadData, 10000);
    return () => clearInterval(interval);
  }, [caseData.case_id, reportedWallet]);

  const topVasp = nearestVasps[0] || null;
  const riskBand = opState?.risk?.band || 'NOT ASSESSED';
  const riskScore = opState?.risk?.score ?? '--';

  const triggerAction = async (actionType: string) => {
    setActionSuccess(null);
    try {
      if (actionType === 'monitor') {
        await api.createWatch(caseData.case_id, reportedWallet);
        setActionSuccess(`Real-time watcher initiated for ${reportedWallet.slice(0, 10)}...`);
      } else if (actionType === 'evidence') {
        await createEvidenceManifest(caseData.case_id, 'investigator-session');
        setActionSuccess('Cryptographic evidence package generated & manifest registered.');
      } else if (actionType === 'report') {
        await createReport(caseData.case_id, 'INVESTIGATION_SUMMARY', trace?.trace_id);
        setActionSuccess('Official investigation report generated and added to repository.');
      } else if (actionType === 'vasp') {
        await createReport(caseData.case_id, 'VASP_DISCLOSURE', trace?.trace_id);
        setActionSuccess('VASP Information Package generated for legal subpoena workflow.');
      } else if (actionType === 'related') {
        setActiveTab('related');
      }
    } catch (err) {
      setActionSuccess(`Action failed: ${err instanceof Error ? err.message : 'Unknown error'}`);
    }
  };

  return (
    <div className="investigate-workspace" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      
      {/* 1. Header Banner */}
      <header className="surface" style={{ padding: '20px', borderLeft: '4px solid #60a5fa' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '15px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <span className="eyebrow" style={{ color: '#60a5fa', fontWeight: 'bold' }}>INVESTIGATION WORKSPACE</span>
              <span className="badge" style={{ textTransform: 'uppercase', background: '#1e293b' }}>{caseData.status}</span>
              <span className="badge simulated" style={{ fontSize: '10px' }}><i className="ok-dot" /> LIVE UPDATING</span>
            </div>
            <h1 style={{ fontSize: '24px', margin: '8px 0 4px', color: '#f3f4f6', fontWeight: 600 }}>
              Reported Wallet: <code style={{ color: '#93c5fd', background: '#0f172a', padding: '4px 8px', borderRadius: '4px' }}>{reportedWallet}</code>
            </h1>
            <p style={{ fontSize: '12px', margin: 0, color: '#9ca3af' }}>
              Case Reference: <b>{caseData.external_case_reference || caseData.case_id.slice(0, 8).toUpperCase()}</b> | Title: <b>{caseData.title}</b> | Chain: <b style={{ textTransform: 'uppercase', color: '#38bdf8' }}>{chain}</b>
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <div style={{ textAlign: 'right' }}>
              <small style={{ display: 'block', color: '#9ca3af', fontSize: '10px', textTransform: 'uppercase' }}>Investigative Risk</small>
              <span className={`risk-band ${riskBand.toLowerCase()}`} style={{ padding: '3px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: 'bold', textTransform: 'uppercase', display: 'inline-block', marginTop: '3px' }}>
                {riskBand}
              </span>
            </div>
            <div style={{ background: '#0f172a', padding: '8px 16px', borderRadius: '6px', border: '1px solid #1e293b', textAlign: 'center' }}>
              <b style={{ fontSize: '28px', color: '#f8fafc', lineHeight: 1 }}>{riskScore}</b>
              <small style={{ display: 'block', color: '#64748b', fontSize: '10px' }}>/ 100</small>
            </div>
            {onRefresh && (
              <button className="secondary" onClick={onRefresh} style={{ padding: '8px 14px', fontSize: '11px' }}>
                RUN TRACE
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Action Notification Toast */}
      {actionSuccess && (
        <div style={{ background: '#064e3b', border: '1px solid #059669', color: '#a7f3d0', padding: '12px 16px', borderRadius: '6px', fontSize: '12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>✓ {actionSuccess}</span>
          <button onClick={() => setActionSuccess(null)} style={{ background: 'none', border: 'none', color: '#a7f3d0', cursor: 'pointer', fontWeight: 'bold' }}>✕</button>
        </div>
      )}

      {/* 2. Primary Tabs */}
      <nav className="case-tabs" style={{ display: 'flex', gap: '4px', borderBottom: '1px solid #1e293b', paddingBottom: '1px', flexWrap: 'wrap' }}>
        {[
          { id: 'overview', label: 'OVERVIEW' },
          { id: 'transactions', label: `TRANSACTIONS (${txList.length})` },
          { id: 'fund-flow', label: 'FUND FLOW' },
          { id: 'entities', label: `ENTITIES & VASP (${nearestVasps.length})` },
          { id: 'patterns', label: 'PATTERNS' },
          { id: 'cross-chain', label: 'CROSS-CHAIN' },
          { id: 'fraud-network', label: 'FRAUD NETWORK' },
          { id: 'related', label: `RELATED CASES (${links.length})` },
          { id: 'evidence', label: `EVIDENCE (${evidenceList.length})` },
          { id: 'actions', label: 'ACTIONS PANEL' }
        ].map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as any)}
            style={{
              padding: '10px 16px',
              fontSize: '12px',
              fontWeight: activeTab === tab.id ? 'bold' : 'medium',
              color: activeTab === tab.id ? '#38bdf8' : '#94a3b8',
              background: activeTab === tab.id ? '#0f172a' : 'transparent',
              border: 'none',
              borderBottom: activeTab === tab.id ? '2px solid #38bdf8' : '2px solid transparent',
              cursor: 'pointer',
              borderRadius: '4px 4px 0 0',
              transition: 'all 0.15s ease'
            }}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      {/* 3. Tab Contents */}

      {/* TAB 1: OVERVIEW */}
      {activeTab === 'overview' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Key Metrics Grid */}
          <div className="metric-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px' }}>
            <div className="metric-card">
              <span>TOTAL VICTIM LOSS</span>
              <b style={{ color: '#ef4444' }}>
                ${fundFlow?.total_victim_loss_usd ? fundFlow.total_victim_loss_usd.toLocaleString(undefined, { minimumFractionDigits: 2 }) : '0.00'}
              </b>
              <small>Reported victim losses</small>
            </div>
            <div className="metric-card">
              <span>TRACED AMOUNT</span>
              <b style={{ color: '#38bdf8' }}>
                ${fundFlow?.traced_amount_usd ? fundFlow.traced_amount_usd.toLocaleString(undefined, { minimumFractionDigits: 2 }) : '0.00'}
              </b>
              <small>Propagated through graph</small>
            </div>
            <div className="metric-card">
              <span>UNRESOLVED AMOUNT</span>
              <b style={{ color: '#f59e0b' }}>
                ${fundFlow?.unresolved_amount_usd ? fundFlow.unresolved_amount_usd.toLocaleString(undefined, { minimumFractionDigits: 2 }) : '0.00'}
              </b>
              <small>In intermediary balances</small>
            </div>
            <div className="metric-card">
              <span>TOP RECEIVING VASP</span>
              <b style={{ fontSize: '18px', color: '#a855f7' }}>
                {topVasp ? topVasp.entity_name : 'None Identified'}
              </b>
              <small>{topVasp ? `${(topVasp.percentage_of_victim_funds * 100).toFixed(1)}% funds (${topVasp.hop_distance} hops)` : 'No exposure observed'}</small>
            </div>
            <div className="metric-card"><span>VASP CONFIDENCE</span><b style={{ color: '#10b981' }}>{topVasp ? `${Math.round(topVasp.attribution_confidence * 100)}%` : '--'}</b><small>{topVasp?.directness || 'UNKNOWN'}</small></div>
            <div className="metric-card"><span>CONNECTED CASES</span><b style={{ color: '#60a5fa' }}>{links.length}</b><small>Persisted link count</small></div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: '16px' }}>
            {/* Top VASP Candidate Highlight */}
            <section className="surface" style={{ padding: '20px' }}>
              <div className="panel-title">
                <span className="eyebrow">PRIMARY RECEIVING ENTITY</span>
                <h3 style={{ margin: '4px 0 0', color: '#f3f4f6' }}>Top Attributed VASP Candidate</h3>
              </div>
              {topVasp ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', marginTop: '12px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#0f172a', padding: '16px', borderRadius: '6px' }}>
                    <div>
                      <h4 style={{ margin: 0, fontSize: '18px', color: '#a855f7' }}>{topVasp.entity_name}</h4>
                      <p style={{ margin: '4px 0 0', fontSize: '12px', color: '#94a3b8' }}>Directness: <b>{topVasp.directness}</b> | Time-to-VASP: <b style={{ color: '#38bdf8' }}>{topVasp.time_to_vasp_formatted}</b></p>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <span className="badge" style={{ background: '#3b0764', color: '#e9d5ff', borderColor: '#7e22ce', fontSize: '12px' }}>
                        {(topVasp.relevance_score * 100).toFixed(0)} Relevance Score
                      </span>
                    </div>
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '10px', fontSize: '11px', textAlign: 'center' }}>
                    <div style={{ background: '#1e293b', padding: '10px', borderRadius: '4px' }}>
                      <span style={{ color: '#94a3b8', display: 'block' }}>Attributed Funds</span>
                      <b style={{ fontSize: '14px', color: '#f8fafc' }}>${topVasp.normalized_value_usd.toLocaleString()}</b>
                    </div>
                    <div style={{ background: '#1e293b', padding: '10px', borderRadius: '4px' }}>
                      <span style={{ color: '#94a3b8', display: 'block' }}>Victim Share</span>
                      <b style={{ fontSize: '14px', color: '#10b981' }}>{(topVasp.percentage_of_victim_funds * 100).toFixed(1)}%</b>
                    </div>
                    <div style={{ background: '#1e293b', padding: '10px', borderRadius: '4px' }}>
                      <span style={{ color: '#94a3b8', display: 'block' }}>Graph Distance</span>
                      <b style={{ fontSize: '14px', color: '#f59e0b' }}>{topVasp.hop_distance} Hops</b>
                    </div>
                    <div style={{ background: '#1e293b', padding: '10px', borderRadius: '4px' }}>
                      <span style={{ color: '#94a3b8', display: 'block' }}>Confidence</span>
                      <b style={{ fontSize: '14px', color: '#38bdf8' }}>{(topVasp.attribution_confidence * 100).toFixed(0)}%</b>
                    </div>
                  </div>

                  {/* Supporting Evidence preview */}
                  <div style={{ borderTop: '1px solid #1e293b', paddingTop: '12px' }}>
                    <span style={{ fontSize: '11px', color: '#94a3b8', fontWeight: 'bold' }}>Supporting Transactions:</span>
                    <ul style={{ margin: '6px 0 0', paddingLeft: '18px', fontSize: '11px', color: '#cbd5e1' }}>
                      {topVasp.supporting_transaction_hashes.map((tx, i) => (
                        <li key={i} style={{ marginBottom: '4px' }}>
                          <code>{tx}</code>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              ) : (
                <div className="empty-block">
                  <span className="empty-visual">🏦</span>
                  <p>No VASP exposure identified yet for this wallet trace.</p>
                </div>
              )}
            </section>

            {/* Recent Activity & Latest Alerts */}
            <section className="surface" style={{ padding: '20px' }}>
              <div className="panel-title">
                <span className="eyebrow">LIVE INTELLIGENCE</span>
                <h3 style={{ margin: '4px 0 0', color: '#f3f4f6' }}>Recent Activity & Alerts</h3>
              </div>
              {alerts.length ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginTop: '12px' }}>
                  {alerts.slice(0, 4).map(alert => (
                    <div key={alert.alert_id} style={{ background: '#0f172a', padding: '12px', borderRadius: '6px', borderLeft: `3px solid ${alert.severity === 'CRITICAL' ? '#ef4444' : '#f59e0b'}` }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px' }}>
                        <b style={{ color: '#f8fafc' }}>{alert.title}</b>
                        <span style={{ color: '#94a3b8' }}>{new Date(alert.created_at).toLocaleTimeString()}</span>
                      </div>
                      <p style={{ margin: '4px 0 0', fontSize: '11px', color: '#cbd5e1' }}>{alert.explanation}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="empty-block">
                  <span className="empty-visual">⚡</span>
                  <p>No high-priority alerts triggered for current trace scope.</p>
                </div>
              )}
            </section>
          </div>
        </div>
      )}

      {/* TAB 2: TRANSACTIONS */}
      {activeTab === 'transactions' && (
        <TransactionLedger
          caseId={caseData.case_id}
          onOpenGraph={(txHash) => onNavigate('graph', txHash ? `tx=${encodeURIComponent(txHash)}` : '')}
        />
      )}

      {/* TAB 3: FUND FLOW */}
      {activeTab === 'fund-flow' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Controls Bar */}
          <div className="surface" style={{ padding: '14px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <span className="eyebrow">GRAPH CONTROLS</span>
              <div style={{ display: 'flex', gap: '6px' }}>
                <button className="secondary" onClick={() => setZoomLevel(prev => Math.min(prev + 15, 160))} style={{ padding: '4px 10px', fontSize: '11px' }}>Zoom +</button>
                <button className="secondary" onClick={() => setZoomLevel(prev => Math.max(prev - 15, 60))} style={{ padding: '4px 10px', fontSize: '11px' }}>Zoom -</button>
                <button className="secondary" onClick={() => setZoomLevel(100)} style={{ padding: '4px 10px', fontSize: '11px' }}>Reset ({zoomLevel}%)</button>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
              <div>
                <span style={{ fontSize: '11px', color: '#94a3b8', marginRight: '6px' }}>Hop Filter:</span>
                <select value={hopFilter} onChange={e => setHopFilter(e.target.value === 'ALL' ? 'ALL' : Number(e.target.value))} style={{ background: '#0f172a', border: '1px solid #1e293b', color: '#f8fafc', padding: '4px 8px', fontSize: '11px', borderRadius: '4px' }}>
                  <option value="ALL">All Hops</option>
                  <option value="1">Hop 1 Only</option>
                  <option value="2">Hop 2 Only</option>
                  <option value="3">Hop 3+</option>
                </select>
              </div>

              <div>
                <span style={{ fontSize: '11px', color: '#94a3b8', marginRight: '6px' }}>Asset:</span>
                <select value={assetFilter} onChange={e => setAssetFilter(e.target.value)} style={{ background: '#0f172a', border: '1px solid #1e293b', color: '#f8fafc', padding: '4px 8px', fontSize: '11px', borderRadius: '4px' }}>
                  <option value="ALL">All Assets</option>
                  <option value="ETH">ETH</option>
                  <option value="USDT">USDT</option>
                  <option value="USDC">USDC</option>
                  <option value="TRX">TRX</option>
                </select>
              </div>
            </div>
          </div>

          <div style={{ transform: `scale(${zoomLevel / 100})`, transformOrigin: 'top left', transition: 'transform 0.2s ease' }}>
            <FundFlowPage />
          </div>
        </div>
      )}

      {/* TAB 4: ENTITIES & VASP ATTRIBUTION */}
      {activeTab === 'entities' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <section className="surface" style={{ padding: '20px' }}>
            <div className="panel-title">
              <span className="eyebrow">VASP ATTRIBUTION & RELEVANCE</span>
              <h3 style={{ margin: '4px 0 0', color: '#f3f4f6' }}>Observed & Probable VASP Receiving Entities</h3>
            </div>

            {nearestVasps.length ? (
              <div className="ledger-table" style={{ marginTop: '14px' }}>
                <div className="ledger-row ledger-head">
                  <span>RANK / VASP</span>
                  <span>DIRECTNESS</span>
                  <span>RELEVANCE SCORE</span>
                  <span>CONFIDENCE</span>
                  <span>AMOUNT RECEIVED</span>
                  <span>HOP DISTANCE</span>
                  <span>TRANSACTIONS</span>
                </div>
                {nearestVasps.map((cand, idx) => (
                  <div key={cand.entity_id} className="ledger-row">
                    <span>
                      <b>#{cand.rank || idx + 1} {cand.entity_name}</b>
                      <small>ID: {cand.entity_id}</small>
                    </span>
                    <span>
                      <span className="badge" style={{ background: cand.directness === 'DIRECT' ? '#065f46' : '#1e293b', color: cand.directness === 'DIRECT' ? '#6ee7b7' : '#93c5fd' }}>
                        {cand.directness}
                      </span>
                    </span>
                    <span>
                      <b style={{ color: '#a855f7' }}>{(cand.relevance_score * 100).toFixed(0)} / 100</b>
                    </span>
                    <span>
                      <b>{(cand.attribution_confidence * 100).toFixed(0)}%</b>
                    </span>
                    <span>
                      <b>${cand.normalized_value_usd.toLocaleString()}</b>
                      <small>{(cand.percentage_of_victim_funds * 100).toFixed(1)}% of loss</small>
                    </span>
                    <span>
                      <b>{cand.hop_distance} hops</b>
                    </span>
                    <span>
                      <button className="secondary" onClick={() => setSelectedEvidence(cand)} style={{ padding: '4px 8px', fontSize: '10px' }}>
                        View Transactions ({cand.supporting_transaction_hashes.length})
                      </button>
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="empty-block">
                <span className="empty-visual">🏛️</span>
                <p>No VASP entities identified in current trace graph.</p>
              </div>
            )}
          </section>

          {/* Modal / Evidence Detail Box */}
          {selectedEvidence && (
            <div className="surface" style={{ padding: '20px', border: '1px solid #38bdf8', background: '#0f172a' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h4 style={{ margin: 0, color: '#38bdf8' }}>Supporting Transactions: {selectedEvidence.entity_name}</h4>
                <button className="secondary" onClick={() => setSelectedEvidence(null)} style={{ padding: '2px 8px' }}>Close</button>
              </div>
              <ul style={{ marginTop: '12px', paddingLeft: '20px', fontSize: '12px', color: '#cbd5e1' }}>
                {selectedEvidence.supporting_transaction_hashes.map((tx: string, idx: number) => (
                  <li key={idx} style={{ marginBottom: '8px' }}>
                    <b>TX #{idx + 1}</b>: <code>{tx}</code>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* TAB 5: PATTERNS */}
      {activeTab === 'patterns' && (
        trace ? <PatternsPage caseData={caseData} trace={trace} onNavigate={onNavigate} /> : <div className="surface" style={{ padding: 20 }}>No trace available for pattern analysis. Run pipeline trace first.</div>
      )}

      {/* TAB 6: CROSS-CHAIN */}
      {activeTab === 'cross-chain' && (
        trace ? <CrossChainPage caseData={caseData} trace={trace} /> : <div className="surface" style={{ padding: 20 }}>No trace available for cross-chain analysis. Run pipeline trace first.</div>
      )}

      {/* TAB 7: FRAUD NETWORK */}
      {activeTab === 'fraud-network' && (
        <FraudNetworkPage caseId={caseData.case_id} onNavigateCase={(cid) => onNavigate('case-investigate', `caseId=${cid}`)} />
      )}

      {/* TAB 8: RELATED CASES */}
      {activeTab === 'related' && (
        <RelatedCasesPanel caseId={caseData.case_id} />
      )}

      {/* TAB 8: EVIDENCE */}
      {activeTab === 'evidence' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <ReadableEvidencePage caseData={caseData} />
          <EvidenceLedgerPanel caseId={caseData.case_id} />
        </div>
      )}

      {/* TAB 9: ACTIONS PANEL */}
      {activeTab === 'actions' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <section className="surface" style={{ padding: '20px' }}>
            <div className="panel-title">
              <span className="eyebrow">LAW ENFORCEMENT & INVESTIGATOR ACTIONS</span>
              <h3 style={{ margin: '4px 0 0', color: '#f3f4f6' }}>Investigative Workflow Actions</h3>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px', marginTop: '16px' }}>
              <div style={{ background: '#0f172a', border: '1px solid #1e293b', padding: '16px', borderRadius: '6px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                <div>
                  <h4 style={{ margin: '0 0 6px', color: '#38bdf8' }}>1. Monitor Wallet</h4>
                  <p style={{ margin: 0, fontSize: '11px', color: '#94a3b8', lineHeight: 1.5 }}>
                    Subscribe reported wallet <code>{reportedWallet.slice(0, 10)}...</code> to continuous real-time retracing and automated alert generation.
                  </p>
                </div>
                <button className="primary" onClick={() => triggerAction('monitor')} style={{ marginTop: '14px', width: '100%' }}>
                  START REAL-TIME MONITORING
                </button>
              </div>

              <div style={{ background: '#0f172a', border: '1px solid #1e293b', padding: '16px', borderRadius: '6px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                <div>
                  <h4 style={{ margin: '0 0 6px', color: '#38bdf8' }}>2. Generate Evidence Package</h4>
                  <p style={{ margin: 0, fontSize: '11px', color: '#94a3b8', lineHeight: 1.5 }}>
                    Create cryptographically sealed evidence manifest containing graph snapshots, transaction proofs, and verification hashes.
                  </p>
                </div>
                <button className="primary" onClick={() => triggerAction('evidence')} style={{ marginTop: '14px', width: '100%' }}>
                  GENERATE EVIDENCE MANIFEST
                </button>
              </div>

              <div style={{ background: '#0f172a', border: '1px solid #1e293b', padding: '16px', borderRadius: '6px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                <div>
                  <h4 style={{ margin: '0 0 6px', color: '#38bdf8' }}>3. Generate Investigation Report</h4>
                  <p style={{ margin: 0, fontSize: '11px', color: '#94a3b8', lineHeight: 1.5 }}>
                    Compile formal executive PDF summary report detailing wallet activity, fund flow hops, and threat classifications.
                  </p>
                </div>
                <button className="primary" onClick={() => triggerAction('report')} style={{ marginTop: '14px', width: '100%' }}>
                  GENERATE SUMMARY REPORT
                </button>
              </div>

              <div style={{ background: '#0f172a', border: '1px solid #1e293b', padding: '16px', borderRadius: '6px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                <div>
                  <h4 style={{ margin: '0 0 6px', color: '#a855f7' }}>4. Generate VASP Information Package</h4>
                  <p style={{ margin: 0, fontSize: '11px', color: '#94a3b8', lineHeight: 1.5 }}>
                    Export targeted entity intelligence package detailing receiving deposit proxies and hop distances for legal subpoena workflows.
                  </p>
                </div>
                <button className="primary" onClick={() => triggerAction('vasp')} style={{ marginTop: '14px', width: '100%', background: '#7e22ce', borderColor: '#a855f7' }}>
                  GENERATE VASP DISCLOSURE
                </button>
              </div>

              <div style={{ background: '#0f172a', border: '1px solid #1e293b', padding: '16px', borderRadius: '6px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                <div>
                  <h4 style={{ margin: '0 0 6px', color: '#38bdf8' }}>5. Review Related Cases</h4>
                  <p style={{ margin: 0, fontSize: '11px', color: '#94a3b8', lineHeight: 1.5 }}>
                    Inspect shared wallet identities and transaction clusters across active multi-agency investigation cases.
                  </p>
                </div>
                <button className="secondary" onClick={() => triggerAction('related')} style={{ marginTop: '14px', width: '100%' }}>
                  REVIEW LINKED CASES ({links.length})
                </button>
              </div>
            </div>

            {/* Statutory Disclaimer */}
            <div style={{ marginTop: '20px', background: '#09141e', borderLeft: '3px solid #f59e0b', padding: '14px', fontSize: '11px', color: '#cbd5e1', lineHeight: 1.6 }}>
              <b style={{ color: '#f59e0b', display: 'block', marginBottom: '4px' }}>⚠️ LEGAL AUTHORIZATION & WORKFLOW NOTICE:</b>
              Actions requiring statutory legal authority (such as emergency freeze orders, formal subpoena disclosures, MLAT requests, or judicial seizure warrants) are investigative recommendation workflows generated by analytical intelligence. They do not constitute automated legal execution without law enforcement authorization.
            </div>
          </section>
        </div>
      )}

    </div>
  );
}
