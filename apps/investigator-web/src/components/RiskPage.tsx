import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import type { Case, RiskAlert, RiskAssessment, RiskDelta, RiskFactor, Trace } from '../types';
import { api } from '../api';
import '../risk.css';

function PanelTitle({ eyebrow, title }: { eyebrow: string; title: string }) {
  return (
    <div className="panel-title">
      <div className="eyebrow">{eyebrow}</div>
      <h3>{title}</h3>
    </div>
  );
}

function Empty({ label, text, action }: { label: string; text: string; action?: ReactNode }) {
  return (
    <div className="empty-block">
      <span>◇</span>
      <b>{label}</b>
      <p>{text}</p>
      {action}
    </div>
  );
}

export function RiskPage({
  caseData,
  trace,
  onNavigate,
}: {
  caseData: Case;
  trace: Trace;
  onNavigate: (route: string, query?: string) => void;
}) {
  const [assessment, setAssessment] = useState<RiskAssessment | null>(null);
  const [history, setHistory] = useState<RiskAssessment[]>([]);
  const [delta, setDelta] = useState<RiskDelta | null>(null);
  const [factors, setFactors] = useState<RiskFactor[]>([]);
  const [alerts, setAlerts] = useState<RiskAlert[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [loaded, setLoaded] = useState(false);

  // Expanded factor view state for evidence details
  const [expandedFactor, setExpandedFactor] = useState<string | null>(null);

  async function load(assess: boolean) {
    setBusy(true);
    setError('');
    try {
      const current = assess
        ? await api.assessRisk(caseData.case_id, trace.trace_id)
        : await api.risk(caseData.case_id);
      setAssessment(current);

      const [nextHistory, nextAlerts] = await Promise.all([
        api.riskHistory(caseData.case_id),
        api.riskAlerts(caseData.case_id),
      ]);
      setHistory(nextHistory);
      setAlerts(nextAlerts);

      if (current) {
        const [nextDelta, nextFactors] = await Promise.all([
          api.riskDelta(caseData.case_id),
          api.riskFactors(caseData.case_id, current.assessment_id),
        ]);
        setDelta(nextDelta);
        setFactors(nextFactors);
      } else {
        setDelta(null);
        setFactors([]);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Risk assessment unavailable');
    } finally {
      setLoaded(true);
      setBusy(false);
    }
  }

  useEffect(() => {
    setLoaded(false);
    load(false);
  }, [caseData.case_id, trace.trace_id]);

  const status = error
    ? 'ASSESSMENT FAILED'
    : busy
    ? 'ASSESSMENT IN PROGRESS'
    : assessment
    ? 'RISK ASSESSED'
    : loaded
    ? 'RISK NOT YET ASSESSED'
    : 'LOADING';

  const bandClass = assessment ? `risk-band-${assessment.band.toLowerCase()}` : '';

  const short = (val: string) => (val && val.length > 16 ? `${val.slice(0, 8)}…${val.slice(-6)}` : val);

  return (
    <>
      <div className="page-header">
        <div>
          <div className="eyebrow">CASEWORK / RISK INTELLIGENCE</div>
          <h1>Investigative risk posture</h1>
          <p className="muted">
            {caseData.title} | {status} | evidence-backed and not a legal determination.
          </p>
        </div>
        <button className="primary" type="button" onClick={() => load(true)} disabled={busy}>
          {busy
            ? 'Calculating deterministic posture...'
            : assessment
            ? 'Reassess persisted evidence'
            : 'Assess persisted evidence'}
        </button>
      </div>

      {error && (
        <div className="error" role="alert">
          {error}
        </div>
      )}

      {!assessment ? (
        <div className="surface">
          <Empty
            label={status}
            text="No score is inferred from the case alone. Run an assessment after the trace, patterns, and evidence have been persisted."
            action={
              <button className="primary" type="button" onClick={() => load(true)} disabled={busy}>
                {busy ? 'Assessment in progress' : 'ASSESS RISK'}
              </button>
            }
          />
        </div>
      ) : (
        <>
          <section className={`risk-hero-container ${bandClass}`}>
            <div className="risk-score-wrapper">
              <div
                className="risk-meter-radial"
                style={{ '--risk-pct': assessment.score } as React.CSSProperties}
              >
                <div className="risk-radial-value">
                  <span className="risk-radial-score">{assessment.score}</span>
                  <span className="risk-radial-max">/ 100</span>
                </div>
              </div>

              <div className="risk-hero-info">
                <span className="risk-band-pill">{assessment.band}</span>
                <p className="risk-explanation-text">{assessment.explanation}</p>
              </div>
            </div>

            <div className="risk-score-track" style={{ marginBottom: 20 }}>
              <div className="risk-score-bar" style={{ width: `${assessment.score}%` }} />
            </div>

            <div className="risk-hero-meta">
              <span>
                INVESTIGATIVE PRIORITY<strong>{assessment.priority}</strong>
              </span>
              <span>
                WATCH STATUS<strong>{assessment.watch_status}</strong>
              </span>
              <span>
                CALCULATED<strong>{new Date(assessment.calculated_at).toLocaleString()}</strong>
              </span>
            </div>
          </section>

          <div className="risk-grid">
            <section className="surface">
              <PanelTitle
                eyebrow="EVIDENCE-DERIVED CONTRIBUTING FACTORS"
                title={factors.length ? `${factors.length} active risk factors` : 'No qualifying factors'}
              />

              {factors.length ? (
                <div className="risk-factor-list" style={{ marginTop: 15 }}>
                  {factors.map(factor => {
                    const contributionClass =
                      factor.contribution >= 15
                        ? 'critical-val'
                        : factor.contribution >= 8
                        ? 'high-val'
                        : 'medium-val';

                    const percent = Math.round((factor.contribution / factor.max_contribution) * 100);
                    const isExpanded = expandedFactor === factor.factor_id;

                    return (
                      <article
                        className="risk-factor-card"
                        key={factor.factor_id}
                        onClick={() => setExpandedFactor(isExpanded ? null : factor.factor_id)}
                      >
                        <div className="risk-factor-header">
                          <div className="risk-factor-title-area">
                            <span className={`risk-contribution-badge ${contributionClass}`}>
                              +{factor.contribution}
                            </span>
                            <div>
                              <strong className="risk-factor-name">{factor.name}</strong>
                              <div className="risk-factor-category">{factor.category.replaceAll('_', ' ')}</div>
                            </div>
                          </div>
                          <span className="badge neutral">{factor.confidence_level}</span>
                        </div>

                        <p className="risk-factor-desc">{factor.explanation}</p>

                        <div className="risk-factor-bar-wrapper">
                          <div
                            className="risk-factor-progress-bg"
                            style={{ '--factor-color': 'var(--risk-color, #3b82f6)' } as React.CSSProperties}
                          >
                            <div className="risk-factor-progress-fill" style={{ width: `${percent}%` }} />
                          </div>
                          <span className="risk-factor-weight-label">
                            contribution: {factor.contribution} / {factor.max_contribution} max
                          </span>
                        </div>

                        {/* Interactive transaction and evidence links */}
                        {isExpanded && (
                          <div className="risk-evidence-details" onClick={e => e.stopPropagation()}>
                            <div style={{ fontSize: 11, fontWeight: 'bold', color: '#64748b', marginBottom: 4 }}>
                              TRACEABLE EVIDENCE
                            </div>
                            <div className="risk-evidence-chips">
                              {factor.transaction_hashes.map(tx => (
                                <button
                                  key={tx}
                                  className="risk-chip-token tx-token"
                                  onClick={() => onNavigate('graph', `tx=${encodeURIComponent(tx)}`)}
                                  title="Click to view and highlight transaction in graph"
                                >
                                  🔗 Tx: {short(tx)}
                                </button>
                              ))}

                              {factor.evidence_ids.map(id => (
                                <button
                                  key={id}
                                  className="risk-chip-token evidence-token"
                                  onClick={() => onNavigate('evidence')}
                                  title="Click to view evidence in the custody ledger"
                                >
                                  📄 Evidence: {short(id)}
                                </button>
                              ))}

                              {!factor.transaction_hashes.length && !factor.evidence_ids.length && (
                                <span style={{ fontSize: 12, color: '#64748b', fontStyle: 'italic' }}>
                                  No transaction or evidence links recorded for this factor.
                                </span>
                              )}
                            </div>
                          </div>
                        )}
                        {!isExpanded && (
                          <div style={{ fontSize: 11, color: '#475569', textAlign: 'right' }}>
                            [ click to expand evidence detail ]
                          </div>
                        )}
                      </article>
                    );
                  })}
                </div>
              ) : (
                <Empty
                  label="INSUFFICIENT EVIDENCE"
                  text="Factors are only created when persisted observations include evidence references."
                />
              )}
            </section>

              <aside className="surface">
                <PanelTitle eyebrow="RISK POSTURE DELTA" title="Why did the posture change?" />
                {delta ? (
                  <dl className="risk-delta">
                    <dt>PREVIOUS SCORE</dt>
                    <dd>{delta.previous_score != null ? delta.previous_score : '--'}</dd>
                    <dt>CURRENT SCORE</dt>
                    <dd>{delta.current_score}</dd>
                    <dt>POSTURE DELTA</dt>
                    <dd className={delta.delta >= 0 ? 'delta-up' : 'delta-down'}>
                      {delta.delta >= 0 ? '+' : ''}
                      {delta.delta}
                    </dd>
                    <dt>NEW FACTORS ADDED</dt>
                    <dd>{delta.new_factors.length ? delta.new_factors.join(', ') : 'None'}</dd>
                    <dt>REMOVED FACTORS</dt>
                    <dd>{delta.removed_factors.length ? delta.removed_factors.join(', ') : 'None'}</dd>
                  </dl>
                ) : (
                  <Empty
                    label="First assessment"
                    text="A later assessment will expose score and factor changes against this version."
                  />
                )}
                <button className="secondary wide" type="button" onClick={() => onNavigate('graph')} style={{ marginTop: 20 }}>
                  Open evidence graph
                </button>
              </aside>
            </div>

            <section className="surface">
              <PanelTitle
                eyebrow="RISK ALERTS & HISTORY"
                title={`${history.length} assessment version(s) recorded`}
              />
              {alerts.length ? (
                alerts.map(alert => (
                  <div className="risk-alert" key={alert.candidate_id}>
                    <span className="integration-status simulated" />
                    <div>
                      <strong>{alert.trigger}</strong>
                      <p>
                        {alert.risk_delta >= 0 ? '+' : ''}
                        {alert.risk_delta} posture delta | {alert.evidence_ids.length} evidence references
                      </p>
                    </div>
                    <span className="badge neutral">{alert.status}</span>
                  </div>
                ))
              ) : (
                <Empty
                  label="No alert candidates"
                  text="Candidates are created only when a later assessment records a positive evidence-backed change."
                />
              )}
              <div className="factor-stack" style={{ marginTop: 20 }}>
                {history.map(item => (
                  <div className="factor-line" key={item.assessment_id}>
                    <span>Version {item.version}</span>
                    <b>
                      {item.band} {item.score}/100
                    </b>
                    <small>{new Date(item.calculated_at).toLocaleString()}</small>
                  </div>
                ))}
              </div>
            </section>
        </>
      )}
    </>
  );
}
