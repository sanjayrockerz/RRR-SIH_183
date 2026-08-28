import { useMemo } from 'react';
import { api } from '../api';
import type { Case, InvestigationOperationalState, OperationalStage } from '../types';

const short = (value?: string) => value && value.length > 18 ? `${value.slice(0, 8)}...${value.slice(-6)}` : (value || 'Unavailable');
const stageLabel = (value: string) => value.replaceAll('_', ' ');

export function CaseCommandCenter({
  caseData,
  state,
  onNavigate
}: {
  caseData: Case;
  state: InvestigationOperationalState | null;
  onNavigate: (route: string) => void;
}) {
  const activeCase = state?.case || caseData;
  const trace = activeCase.latest_trace;
  const summary = state?.summary;
  const risk = state?.risk || summary?.risk || null;
  const root = activeCase.wallets[0];
  const vasp = summary?.vasp_exposure?.nearest;
  const completed = useMemo(() => state?.stages.filter(item => ['COMPLETED', 'PARTIAL', 'SIMULATED'].includes(item.status)).length || 0, [state]);

  const handleStageClick = (stageName: string) => {
    const s = stageName.toUpperCase();
    if (['INTAKE', 'CASE_CREATED', 'WALLET_REGISTERED'].includes(s)) {
      onNavigate('cases');
    } else if (['DATA_ACQUISITION', 'NORMALIZATION', 'LEDGER_BUILT'].includes(s)) {
      onNavigate('transactions');
    } else if (['GRAPH_BUILT', 'FUND_FLOW_ANALYSIS', 'GRAPH_UPDATED'].includes(s)) {
      onNavigate('graph');
    } else if (['ENTITY_ATTRIBUTION'].includes(s)) {
      onNavigate('entities');
    } else if (['PATTERN_ANALYSIS', 'PATTERN_DETECTION'].includes(s)) {
      onNavigate('patterns');
    } else if (['RISK_ASSESSMENT', 'RISK_REASSESSED'].includes(s)) {
      onNavigate('risk');
    } else if (['REALTIME_WATCH', 'ALERT_GENERATED', 'EVENT_RECEIVED', 'ALERT_CREATED'].includes(s)) {
      onNavigate('realtime');
    } else if (['EVIDENCE_REVIEW', 'INVESTIGATOR_ACTION'].includes(s)) {
      onNavigate('evidence');
    } else if (['REPORT_GENERATED'].includes(s)) {
      onNavigate('reports');
    }
  };

  return (
    <div className="case-command-overview">
      <div className="case-operation-grid" style={{ marginBottom: '20px' }}>
        <Metric label="REPORTED WALLETS" value={summary?.wallets ?? activeCase.wallets.length} detail={`${root?.chain || 'No chain'} | ${short(root?.address)}`} />
        <Metric label="TRANSACTIONS" value={summary?.transactions ?? 0} detail={`${trace?.mode || 'NO TRACE'} | ${trace?.provider || 'Provider unavailable'}`} />
        <Metric label="GRAPH" value={summary?.graph_edges ?? 0} detail={`${summary?.graph_nodes ?? 0} nodes | ${state?.graph_backend || 'PostgreSQL'}`} />
        <Metric label="VASP EXPOSURE" value={summary?.vasp_exposure?.count ?? 0} detail={vasp ? `${vasp.entity} | ${vasp.hop_distance} hops` : 'No source-backed match'} />
        <Metric label="PATTERNS" value={summary?.patterns ?? 0} detail={`${state?.patterns.filter(item => ['HIGH', 'CRITICAL'].includes(item.severity)).length || 0} high/critical`} />
        <Metric label="EVIDENCE" value={summary?.evidence ?? 0} detail={`${summary?.alerts ?? 0} alerts | ${summary?.active_watches ?? 0} watches`} />
      </div>

      <div className="case-command-layout">
        <section className="command-panel pipeline-panel">
          <div className="panel-title">
            <div>
              <span className="eyebrow">AUTHORITATIVE WORKFLOW</span>
              <h3>Investigation execution</h3>
            </div>
            <b>{completed}/{state?.stages.length || 14}</b>
          </div>
          <div className="pipeline-list">
            {(state?.stages || fallbackStages()).map(stage => (
              <StageRow key={stage.stage} stage={stage} onClick={() => handleStageClick(stage.stage)} />
            ))}
          </div>
        </section>

        <section className="command-panel command-main">
          <div className="panel-title">
            <div>
              <span className="eyebrow">CURRENT MONEY FLOW</span>
              <h3>Persisted investigation state</h3>
            </div>
            <button className="secondary" onClick={() => onNavigate('graph')}>OPEN GRAPH</button>
          </div>
          {trace ? (
            <div className="flow-readout">
              <div><span>Root</span><b className="mono">{short(trace.root_address)}</b></div>
              <div><span>Observed edges</span><b>{trace.metrics.edge_count}</b></div>
              <div><span>Transactions</span><b>{trace.metrics.unique_transaction_count}</b></div>
              <div><span>Assets</span><b>{trace.metrics.unique_asset_count}</b></div>
              <div><span>Max hop</span><b>{trace.metrics.maximum_hop}</b></div>
            </div>
          ) : (
            <p className="empty-copy">No persisted graph yet. Click RUN PIPELINE in the header to trace wallet flow.</p>
          )}
          {vasp && (
            <div className="vasp-strip">
              <span>NEAREST SOURCE-BACKED VASP</span>
              <b>{vasp.entity}</b>
              <small>{short(vasp.address)} | {vasp.confidence} | {summary?.vasp_exposure?.source}</small>
            </div>
          )}
          <div className="panel-title small-title" style={{ marginTop: '20px' }}>
            <div>
              <span className="eyebrow">RISK FACTORS</span>
              <h3>{risk ? `${risk.band} ${risk.score}/100` : 'Not assessed'}</h3>
            </div>
            <button className="secondary" onClick={() => onNavigate('risk')}>OPEN RISK</button>
          </div>
          {risk ? (
            <div className="factor-stack">
              {risk.factors.slice(0, 6).map(factor => (
                <div className="factor-line" key={factor.factor_id}>
                  <span>{factor.name}</span>
                  <b>+{factor.contribution}</b>
                  <small>{factor.evidence_ids.length} evidence</small>
                </div>
              ))}
            </div>
          ) : (
            <p className="empty-copy">Risk engine has not persisted an assessment for this case.</p>
          )}
        </section>

        <aside className="command-panel intelligence-panel">
          <div className="panel-title">
            <div>
              <span className="eyebrow">LIVE / EVIDENCE</span>
              <h3>Latest timeline</h3>
            </div>
            <button className="secondary" onClick={() => onNavigate('realtime')}>LIVE</button>
          </div>
          {(state?.workflow_events || []).slice(0, 3).map(item => (
            <div className="mini-event" key={item.event_id}>
              <b>{stageLabel(item.stage)}</b>
              <small>{item.provider || 'RRR'} | {item.result_count ?? 0} records</small>
            </div>
          ))}
          {(state?.evidence || []).slice(0, 4).map(item => (
            <div className="mini-event" key={item.evidence_id}>
              <b>{item.type}</b>
              <small>{short(item.tx_hash)} | {item.source}</small>
            </div>
          ))}
          {state && !state.evidence.length && (
            <p className="empty-copy">Evidence will appear after acquisition or realtime event processing.</p>
          )}
        </aside>
      </div>
    </div>
  );
}

function Metric({ label, value, detail }: { label: string; value: number | string; detail: string }) {
  return (
    <article>
      <span>{label}</span>
      <b>{value}</b>
      <small>{detail}</small>
    </article>
  );
}

function StageRow({ stage, onClick }: { stage: OperationalStage; onClick: () => void }) {
  return (
    <div className={`pipeline-row ${stage.status.toLowerCase()}`} style={{ cursor: 'pointer' }} onClick={onClick}>
      <i />
      <div>
        <b>{stageLabel(stage.stage)}</b>
        <small>{stage.provider || stage.mode || 'RRR'} | {stage.records_produced} records{stage.duration_ms ? ` | ${stage.duration_ms}ms` : ''}</small>
        {stage.error && <em>{stage.error}</em>}
      </div>
      <span>{stage.status}</span>
    </div>
  );
}

function fallbackStages(): OperationalStage[] {
  return ['INTAKE', 'CASE_CREATED', 'WALLET_REGISTERED', 'DATA_ACQUISITION', 'NORMALIZATION', 'LEDGER_BUILT', 'GRAPH_BUILT', 'ENTITY_ATTRIBUTION', 'PATTERN_ANALYSIS', 'RISK_ASSESSMENT', 'REALTIME_WATCH', 'ALERT_GENERATED', 'EVIDENCE_REVIEW', 'REPORT_GENERATED'].map(stage => ({
    stage,
    status: 'PENDING',
    records_produced: 0,
    evidence_ids: []
  }));
}
