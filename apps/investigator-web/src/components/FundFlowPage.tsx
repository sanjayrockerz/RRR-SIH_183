import React, { useEffect, useState } from 'react';
import {
  caseFundFlow,
  caseFundAtRisk,
  caseNearestVasps,
  caseTimeToVasp,
  listCases,
} from '../api';
import {
  CaseListItem,
  FundAtRisk,
  FundFlowSummary,
  TimeToVasp,
  VaspProximityCandidate,
} from '../types';

export const FundFlowPage: React.FC = () => {
  const [cases, setCases] = useState<CaseListItem[]>([]);
  const [selectedCaseId, setSelectedCaseId] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const [fundFlow, setFundFlow] = useState<FundFlowSummary | null>(null);
  const [candidates, setCandidates] = useState<VaspProximityCandidate[]>([]);
  const [fundAtRisk, setFundAtRisk] = useState<FundAtRisk | null>(null);
  const [timeToVasp, setTimeToVasp] = useState<TimeToVasp | null>(null);

  useEffect(() => {
    listCases()
      .then((data) => {
        setCases(data);
        if (data.length > 0) {
          setSelectedCaseId(data[0].case_id);
        }
      })
      .catch((err) => {
        setError(err.message || 'Failed to load case registry');
      });
  }, []);

  useEffect(() => {
    if (!selectedCaseId) return;
    setLoading(true);
    setError(null);

    Promise.all([
      caseFundFlow(selectedCaseId),
      caseNearestVasps(selectedCaseId),
      caseFundAtRisk(selectedCaseId),
      caseTimeToVasp(selectedCaseId),
    ])
      .then(([flowData, candidateData, riskData, ttvData]) => {
        setFundFlow(flowData);
        setCandidates(candidateData);
        setFundAtRisk(riskData);
        setTimeToVasp(ttvData);
      })
      .catch((err) => {
        setError(err.message || 'Failed to fetch fund flow metrics');
      })
      .finally(() => {
        setLoading(false);
      });
  }, [selectedCaseId]);

  return (
    <div style={{ padding: '24px', color: '#f8fafc', background: '#0f172a', minHeight: '100vh', fontFamily: 'Inter, system-ui, sans-serif' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <div>
          <h1 style={{ fontSize: '24px', fontWeight: '700', margin: '0 0 8px 0', background: 'linear-gradient(135deg, #38bdf8, #818cf8)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
            Victim Fund Flow & Nearest VASP Proximity
          </h1>
          <p style={{ margin: 0, color: '#94a3b8', fontSize: '14px' }}>
            Asset-aware value propagation, path flow accounting, and multi-factor VASP candidate ranking
          </p>
        </div>

        {/* Case selector */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <label style={{ fontSize: '14px', color: '#cbd5e1' }}>Select Case:</label>
          <select
            value={selectedCaseId}
            onChange={(e) => setSelectedCaseId(e.target.value)}
            style={{
              background: '#1e293b',
              color: '#f8fafc',
              border: '1px solid #334155',
              borderRadius: '8px',
              padding: '8px 16px',
              fontSize: '14px',
              outline: 'none',
              cursor: 'pointer',
            }}
          >
            {cases.map((c) => (
              <option key={c.case_id} value={c.case_id}>
                {c.title} ({c.case_id.slice(0, 8)})
              </option>
            ))}
          </select>
        </div>
      </div>

      {error && (
        <div style={{ background: '#450a0a', border: '1px solid #dc2626', color: '#fca5a5', padding: '12px 16px', borderRadius: '8px', marginBottom: '24px', fontSize: '14px' }}>
          ⚠️ {error}
        </div>
      )}

      {loading && (
        <div style={{ textAlign: 'center', padding: '40px', color: '#94a3b8' }}>
          Analyzing fund flow graph and evaluating VASP proximity...
        </div>
      )}

      {!loading && fundFlow && (
        <>
          {/* Investigative Disclaimer Banner */}
          {fundAtRisk && (
            <div style={{ background: 'rgba(30, 41, 59, 0.7)', backdropFilter: 'blur(8px)', border: '1px solid #3b82f6', borderRadius: '12px', padding: '16px', marginBottom: '24px', display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
              <div style={{ fontSize: '20px' }}>🛡️</div>
              <div>
                <div style={{ fontSize: '14px', fontWeight: '600', color: '#60a5fa', marginBottom: '4px' }}>
                  Investigative Intelligence Disclaimer
                </div>
                <div style={{ fontSize: '13px', color: '#cbd5e1', lineHeight: '1.5' }}>
                  {fundAtRisk.disclaimer}
                </div>
              </div>
            </div>
          )}

          {/* Key KPI Metric Cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '16px', marginBottom: '24px' }}>
            <div style={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '12px', padding: '16px' }}>
              <div style={{ color: '#94a3b8', fontSize: '12px', fontWeight: '600', marginBottom: '4px' }}>VICTIM LOSS</div>
              <div style={{ fontSize: '22px', fontWeight: '700', color: '#f43f5e' }}>
                ${fundFlow.total_victim_loss_usd.toLocaleString('en-US', { minimumFractionDigits: 2 })}
              </div>
            </div>

            <div style={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '12px', padding: '16px' }}>
              <div style={{ color: '#94a3b8', fontSize: '12px', fontWeight: '600', marginBottom: '4px' }}>TRACED VALUE</div>
              <div style={{ fontSize: '22px', fontWeight: '700', color: '#38bdf8' }}>
                ${fundFlow.traced_amount_usd.toLocaleString('en-US', { minimumFractionDigits: 2 })}
              </div>
            </div>

            <div style={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '12px', padding: '16px' }}>
              <div style={{ color: '#94a3b8', fontSize: '12px', fontWeight: '600', marginBottom: '4px' }}>UNRESOLVED VALUE</div>
              <div style={{ fontSize: '22px', fontWeight: '700', color: '#fbbf24' }}>
                ${fundFlow.unresolved_amount_usd.toLocaleString('en-US', { minimumFractionDigits: 2 })}
              </div>
            </div>

            <div style={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '12px', padding: '16px' }}>
              <div style={{ color: '#94a3b8', fontSize: '12px', fontWeight: '600', marginBottom: '4px' }}>VASP EXPOSURE</div>
              <div style={{ fontSize: '22px', fontWeight: '700', color: '#4ade80' }}>
                ${fundFlow.vasp_linked_amount_usd.toLocaleString('en-US', { minimumFractionDigits: 2 })}
              </div>
            </div>

            <div style={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '12px', padding: '16px' }}>
              <div style={{ color: '#94a3b8', fontSize: '12px', fontWeight: '600', marginBottom: '4px' }}>MIXER EXPOSURE</div>
              <div style={{ fontSize: '22px', fontWeight: '700', color: '#c084fc' }}>
                ${fundFlow.mixer_linked_amount_usd.toLocaleString('en-US', { minimumFractionDigits: 2 })}
              </div>
            </div>

            <div style={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '12px', padding: '16px' }}>
              <div style={{ color: '#94a3b8', fontSize: '12px', fontWeight: '600', marginBottom: '4px' }}>BRIDGE EXPOSURE</div>
              <div style={{ fontSize: '22px', fontWeight: '700', color: '#818cf8' }}>
                ${fundFlow.bridge_linked_amount_usd.toLocaleString('en-US', { minimumFractionDigits: 2 })}
              </div>
            </div>
          </div>

          {/* Time to VASP Banner */}
          {timeToVasp && timeToVasp.target_vasp_name && (
            <div style={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '12px', padding: '16px', marginBottom: '24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <span style={{ fontSize: '13px', color: '#94a3b8' }}>First Qualifying VASP Interaction: </span>
                <span style={{ fontSize: '14px', fontWeight: '700', color: '#4ade80', marginLeft: '6px' }}>{timeToVasp.target_vasp_name}</span>
              </div>
              <div style={{ background: '#0f172a', border: '1px solid #3b82f6', padding: '6px 16px', borderRadius: '20px', fontSize: '13px', fontWeight: '600', color: '#60a5fa' }}>
                Time-to-VASP: {timeToVasp.time_to_vasp_formatted}
              </div>
            </div>
          )}

          {/* Ranked VASP Candidates Table */}
          <div style={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '12px', padding: '20px', marginBottom: '24px' }}>
            <h2 style={{ fontSize: '18px', fontWeight: '700', margin: '0 0 16px 0', color: '#f8fafc' }}>
              TOP VASP CANDIDATES (Ranked by Multi-Factor Proximity Relevance)
            </h2>

            {candidates.length === 0 ? (
              <div style={{ color: '#94a3b8', fontSize: '14px', textAlign: 'center', padding: '20px' }}>
                No receiving VASP candidate entities identified in the trace flow.
              </div>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '14px', textAlign: 'left' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid #334155', color: '#94a3b8', fontSize: '12px' }}>
                      <th style={{ padding: '12px' }}>RANK</th>
                      <th style={{ padding: '12px' }}>VASP ENTITY</th>
                      <th style={{ padding: '12px' }}>RELEVANCE SCORE</th>
                      <th style={{ padding: '12px' }}>ATTRIBUTION CONFIDENCE</th>
                      <th style={{ padding: '12px' }}>AMOUNT</th>
                      <th style={{ padding: '12px' }}>VICTIM FUND %</th>
                      <th style={{ padding: '12px' }}>HOP DISTANCE</th>
                      <th style={{ padding: '12px' }}>TIME-TO-VASP</th>
                      <th style={{ padding: '12px' }}>DIRECTNESS</th>
                    </tr>
                  </thead>
                  <tbody>
                    {candidates.map((cand) => (
                      <tr key={cand.entity_id} style={{ borderBottom: '1px solid #1e293b' }}>
                        <td style={{ padding: '12px', fontWeight: '700', color: '#38bdf8' }}>#{cand.rank}</td>
                        <td style={{ padding: '12px', fontWeight: '600', color: '#f8fafc' }}>{cand.entity_name}</td>
                        <td style={{ padding: '12px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <div style={{ flex: 1, background: '#0f172a', height: '8px', borderRadius: '4px', overflow: 'hidden' }}>
                              <div style={{ width: `${cand.relevance_score * 100}%`, background: 'linear-gradient(90deg, #38bdf8, #818cf8)', height: '100%' }} />
                            </div>
                            <span style={{ fontWeight: '600', fontSize: '12px' }}>{(cand.relevance_score * 100).toFixed(1)}%</span>
                          </div>
                        </td>
                        <td style={{ padding: '12px' }}>
                          <span style={{ background: cand.attribution_confidence >= 0.85 ? 'rgba(34,197,94,0.15)' : 'rgba(234,179,8,0.15)', color: cand.attribution_confidence >= 0.85 ? '#4ade80' : '#facc15', padding: '4px 8px', borderRadius: '6px', fontSize: '12px', fontWeight: '600' }}>
                            {(cand.attribution_confidence * 100).toFixed(0)}%
                          </span>
                        </td>
                        <td style={{ padding: '12px', fontWeight: '600', color: '#4ade80' }}>{cand.amount}</td>
                        <td style={{ padding: '12px', color: '#cbd5e1' }}>{cand.percentage_of_victim_funds}%</td>
                        <td style={{ padding: '12px', color: '#cbd5e1' }}>{cand.hop_distance} {cand.hop_distance === 1 ? 'hop' : 'hops'}</td>
                        <td style={{ padding: '12px', color: '#94a3b8' }}>{cand.time_to_vasp_formatted}</td>
                        <td style={{ padding: '12px' }}>
                          <span style={{ background: '#0f172a', border: '1px solid #334155', color: '#cbd5e1', padding: '2px 8px', borderRadius: '4px', fontSize: '11px' }}>
                            {cand.directness}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Flow Hops Propagation Ledger */}
          <div style={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '12px', padding: '20px' }}>
            <h2 style={{ fontSize: '18px', fontWeight: '700', margin: '0 0 16px 0', color: '#f8fafc' }}>
              PROPAGATED FUND FLOW HOPS
            </h2>

            {fundFlow.propagated_hops.length === 0 ? (
              <div style={{ color: '#94a3b8', fontSize: '14px', textAlign: 'center', padding: '20px' }}>
                No flow hops recorded for this investigation trace.
              </div>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px', textAlign: 'left' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid #334155', color: '#94a3b8', fontSize: '12px' }}>
                      <th style={{ padding: '10px' }}>HOP</th>
                      <th style={{ padding: '10px' }}>SOURCE ADDRESS</th>
                      <th style={{ padding: '10px' }}>DESTINATION ADDRESS</th>
                      <th style={{ padding: '10px' }}>ASSET</th>
                      <th style={{ padding: '10px' }}>AMOUNT</th>
                      <th style={{ padding: '10px' }}>TRANSACTION HASH</th>
                      <th style={{ padding: '10px' }}>TIMESTAMP</th>
                    </tr>
                  </thead>
                  <tbody>
                    {fundFlow.propagated_hops.map((hop, idx) => (
                      <tr key={idx} style={{ borderBottom: '1px solid #0f172a' }}>
                        <td style={{ padding: '10px', color: '#38bdf8', fontWeight: '600' }}>#{hop.hop_number}</td>
                        <td style={{ padding: '10px', fontFamily: 'monospace', color: '#cbd5e1' }}>{hop.source.slice(0, 10)}...{hop.source.slice(-8)}</td>
                        <td style={{ padding: '10px', fontFamily: 'monospace', color: '#cbd5e1' }}>{hop.destination.slice(0, 10)}...{hop.destination.slice(-8)}</td>
                        <td style={{ padding: '10px', fontWeight: '600', color: '#818cf8' }}>{hop.asset}</td>
                        <td style={{ padding: '10px', fontWeight: '600', color: '#f8fafc' }}>{hop.amount}</td>
                        <td style={{ padding: '10px', fontFamily: 'monospace', color: '#64748b' }}>{hop.transaction_hash ? `${hop.transaction_hash.slice(0, 12)}...` : 'N/A'}</td>
                        <td style={{ padding: '10px', color: '#94a3b8' }}>{hop.timestamp ? new Date(hop.timestamp).toLocaleString() : 'N/A'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
};
