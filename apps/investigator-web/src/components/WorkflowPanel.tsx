import React, { useEffect, useState } from 'react';
import type {
  InvestigationWorkflowState,
  InvestigatorRecommendationItem,
  VaspActionabilityCandidate,
  VaspActionPackageInfo,
  WorkflowStageDetail,
} from '../types';
import { getCaseWorkflow, retryWorkflowStage, runCaseInvestigation } from '../api';

interface WorkflowPanelProps {
  caseId: string;
  onRefreshCase?: () => void;
}

export function WorkflowPanel({ caseId, onRefreshCase }: WorkflowPanelProps) {
  const [workflow, setWorkflow] = useState<InvestigationWorkflowState | null>(null);
  const [selectedStage, setSelectedStage] = useState<WorkflowStageDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [retryingStage, setRetryingStage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchWorkflow = async () => {
    try {
      const data = await getCaseWorkflow(caseId);
      setWorkflow(data);
      if (data.stages && data.stages.length > 0) {
        // Select active/failed/last stage by default
        const active = data.stages.find((s: WorkflowStageDetail) => s.status === 'IN_PROGRESS' || s.status === 'FAILED') || data.stages[0];
        setSelectedStage(active);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch workflow state');
    }
  };

  useEffect(() => {
    fetchWorkflow();
  }, [caseId]);

  const handleRunInvestigation = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await runCaseInvestigation(caseId);
      setWorkflow(res.workflow);
      if (res.workflow.stages.length > 0) {
        setSelectedStage(res.workflow.stages[0]);
      }
      if (onRefreshCase) onRefreshCase();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Investigation pipeline execution failed');
    } finally {
      setLoading(false);
    }
  };

  const handleRetryStage = async (stageName: string) => {
    setRetryingStage(stageName);
    try {
      const updatedWf = await retryWorkflowStage(caseId, stageName);
      setWorkflow(updatedWf);
      const detail = updatedWf.stages.find((s: WorkflowStageDetail) => s.stage === stageName);
      if (detail) setSelectedStage(detail);

      if (onRefreshCase) onRefreshCase();
    } catch (err) {
      setError(err instanceof Error ? err.message : `Retry failed for stage ${stageName}`);
    } finally {
      setRetryingStage(null);
    }
  };

  const getStatusBadgeClass = (status: string) => {
    switch (status) {
      case 'COMPLETED':
        return 'status-badge status-completed';
      case 'IN_PROGRESS':
        return 'status-badge status-progress';
      case 'FAILED':
        return 'status-badge status-failed';
      case 'SKIPPED':
        return 'status-badge status-skipped';
      default:
        return 'status-badge status-pending';
    }
  };

  const getPriorityBadgeClass = (priority: string) => {
    switch (priority.toUpperCase()) {
      case 'CRITICAL':
        return 'badge badge-critical';
      case 'HIGH':
        return 'badge badge-high';
      case 'MEDIUM':
        return 'badge badge-medium';
      default:
        return 'badge badge-low';
    }
  };

  const getProvenanceBadgeClass = (provenance?: string) => {
    switch (provenance?.toUpperCase()) {
      case 'OBSERVED':
        return 'provenance-badge provenance-observed';
      case 'INFERRED':
        return 'provenance-badge provenance-inferred';
      default:
        return 'provenance-badge provenance-attributed';
    }
  };

  return (
    <section className="surface workflow-panel-container">
      <div className="panel-header-flex" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <div>
          <div className="eyebrow" style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--color-primary, #3b82f6)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            AUTONOMOUS INVESTIGATION PIPELINE
          </div>
          <h3 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 700 }}>
            Investigation Workflow Workspace
          </h3>
        </div>
        <button
          className="btn-primary"
          onClick={handleRunInvestigation}
          disabled={loading}
          style={{
            padding: '0.5rem 1.25rem',
            background: 'linear-gradient(135deg, #2563eb, #1d4ed8)',
            color: '#fff',
            border: 'none',
            borderRadius: '6px',
            fontWeight: 600,
            cursor: loading ? 'not-allowed' : 'pointer',
          }}
        >
          {loading ? 'Running 9-Stage Pipeline...' : 'Run Pipeline Investigation'}
        </button>
      </div>

      {error && (
        <div className="error-alert" role="alert" style={{ background: '#fef2f2', border: '1px solid #fca5a5', color: '#991b1b', padding: '0.75rem 1rem', borderRadius: '6px', marginBottom: '1rem' }}>
          {error}
        </div>
      )}

      {/* Stepper Pipeline Stage Progress */}
      {workflow && (
        <div className="stepper-wrapper" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(110px, 1fr))', gap: '0.5rem', marginBottom: '1.5rem' }}>
          {workflow.stages.map((st, idx) => {
            const isSelected = selectedStage?.stage === st.stage;
            return (
              <div
                key={st.stage}
                onClick={() => setSelectedStage(st)}
                style={{
                  border: isSelected ? '2px solid #3b82f6' : '1px solid var(--border-color, #e5e7eb)',
                  borderRadius: '8px',
                  padding: '0.6rem 0.5rem',
                  textAlign: 'center',
                  background: isSelected ? 'rgba(59, 130, 246, 0.05)' : 'var(--bg-surface-secondary, #f9fafb)',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                }}
              >
                <div style={{ fontSize: '0.7rem', color: '#6b7280', fontWeight: 600 }}>
                  STAGE {idx + 1}
                </div>
                <div style={{ fontSize: '0.75rem', fontWeight: 700, margin: '0.25rem 0', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {st.stage.replace('_', ' ')}
                </div>
                <span className={getStatusBadgeClass(st.status)} style={{ fontSize: '0.65rem', padding: '0.15rem 0.4rem', borderRadius: '4px', textTransform: 'uppercase', fontWeight: 700 }}>
                  {st.status}
                </span>
              </div>
            );
          })}
        </div>
      )}

      {/* Selected Stage Detail Panel */}
      {selectedStage && (
        <div className="stage-detail-card" style={{ border: '1px solid var(--border-color, #e5e7eb)', borderRadius: '8px', padding: '1rem', marginBottom: '1.5rem', background: '#fff' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
            <h4 style={{ margin: 0, fontSize: '1rem', fontWeight: 700 }}>
              Stage: {selectedStage.stage.replace('_', ' ')}
            </h4>
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              <span className={getStatusBadgeClass(selectedStage.status)}>
                {selectedStage.status}
              </span>
              {(selectedStage.status === 'FAILED' || selectedStage.status === 'PENDING') && (
                <button
                  onClick={() => handleRetryStage(selectedStage.stage)}
                  disabled={retryingStage === selectedStage.stage}
                  style={{ padding: '0.25rem 0.75rem', fontSize: '0.75rem', background: '#dc2626', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
                >
                  {retryingStage === selectedStage.stage ? 'Retrying...' : 'Retry Stage'}
                </button>
              )}
            </div>
          </div>

          {selectedStage.error && (
            <div style={{ background: '#fef2f2', color: '#991b1b', padding: '0.5rem', borderRadius: '4px', fontSize: '0.8rem', fontFamily: 'monospace', marginBottom: '0.5rem' }}>
              <strong>Error:</strong> {selectedStage.error}
            </div>
          )}

          {selectedStage.output_summary && Object.keys(selectedStage.output_summary).length > 0 && (
            <div style={{ background: '#f8fafc', padding: '0.75rem', borderRadius: '6px', fontSize: '0.8rem' }}>
              <strong>Stage Output Summary:</strong>
              <pre style={{ margin: '0.5rem 0 0 0', overflowX: 'auto', fontSize: '0.75rem' }}>
                {JSON.stringify(selectedStage.output_summary, null, 2)}
              </pre>
            </div>
          )}

          {selectedStage.evidence_references && selectedStage.evidence_references.length > 0 && (
            <div style={{ marginTop: '0.75rem', fontSize: '0.8rem' }}>
              <strong>Linked Evidence References:</strong>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', marginTop: '0.25rem' }}>
                {selectedStage.evidence_references.map((ref) => (
                  <span key={ref} style={{ background: '#e0f2fe', color: '#0369a1', padding: '0.15rem 0.5rem', borderRadius: '4px', fontSize: '0.7rem', fontFamily: 'monospace' }}>
                    {ref}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* VASP Actionability Engine & Action Package Section */}
      {workflow?.vasp_action_package && (
        <div className="vasp-action-package-card" style={{ border: '1px solid #cbd5e1', borderRadius: '8px', padding: '1.25rem', marginBottom: '1.5rem', background: 'linear-gradient(to right, #f8fafc, #f1f5f9)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <h4 style={{ margin: 0, fontSize: '1.1rem', color: '#0f172a' }}>
                Actionable VASP Action Package
              </h4>
              <span className={getProvenanceBadgeClass(workflow.vasp_action_package.provenance)} style={{ fontSize: '0.7rem', padding: '0.2rem 0.5rem', borderRadius: '4px', fontWeight: 700, background: '#dbeafe', color: '#1e40af' }}>
                {workflow.vasp_action_package.provenance || 'ATTRIBUTED'}
              </span>
            </div>
            <span style={{ fontSize: '0.8rem', fontWeight: 600, color: '#059669' }}>
              Confidence: {workflow.vasp_action_package.confidence}
            </span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginBottom: '0.75rem', fontSize: '0.85rem' }}>
            <div>
              <span style={{ color: '#64748b' }}>Target VASP:</span>
              <div style={{ fontWeight: 700, color: '#1e293b' }}>{workflow.vasp_action_package.probable_vasp}</div>
            </div>
            <div>
              <span style={{ color: '#64748b' }}>Source Wallet:</span>
              <div style={{ fontFamily: 'monospace', fontSize: '0.8rem', color: '#334155' }}>{workflow.vasp_action_package.source_wallet}</div>
            </div>
            <div>
              <span style={{ color: '#64748b' }}>Victim Linked Value:</span>
              <div style={{ fontWeight: 700, color: '#059669' }}>${workflow.vasp_action_package.linked_value.toLocaleString()} USD</div>
            </div>
          </div>

          {workflow.vasp_action_package.recommended_investigator_action && (
            <div style={{ background: '#fff', borderLeft: '4px solid #2563eb', padding: '0.75rem 1rem', borderRadius: '4px', marginTop: '0.5rem' }}>
              <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#2563eb', textTransform: 'uppercase' }}>
                RECOMMENDED LEGAL & COMPLIANCE ACTION
              </div>
              <div style={{ fontSize: '0.85rem', color: '#1e293b', marginTop: '0.25rem' }}>
                {workflow.vasp_action_package.recommended_investigator_action}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Investigator Recommendation Engine Items */}
      {workflow?.recommendations && workflow.recommendations.length > 0 && (
        <div className="investigator-recommendations-section">
          <h4 style={{ fontSize: '1rem', fontWeight: 700, marginBottom: '0.75rem' }}>
            Prioritised Investigator Actions ({workflow.recommendations.length})
          </h4>
          <div style={{ display: 'grid', gap: '0.75rem' }}>
            {workflow.recommendations.map((rec) => (
              <div
                key={rec.recommendation_id}
                style={{
                  border: '1px solid var(--border-color, #e2e8f0)',
                  borderRadius: '6px',
                  padding: '0.85rem 1rem',
                  background: '#fff',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'flex-start',
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
                    <span
                      style={{
                        padding: '0.15rem 0.4rem',
                        borderRadius: '4px',
                        fontSize: '0.65rem',
                        fontWeight: 700,
                        background: rec.priority === 'CRITICAL' ? '#fef2f2' : '#f0fdf4',
                        color: rec.priority === 'CRITICAL' ? '#dc2626' : '#16a34a',
                        border: rec.priority === 'CRITICAL' ? '1px solid #fca5a5' : '1px solid #86efac',
                      }}
                    >
                      {rec.priority}
                    </span>
                    <strong style={{ fontSize: '0.9rem', color: '#0f172a' }}>
                      {rec.recommendation || rec.action_item}
                    </strong>
                  </div>
                  <p style={{ margin: '0.25rem 0 0.5rem 0', fontSize: '0.8rem', color: '#475569' }}>
                    {rec.reason || rec.rationale}
                  </p>
                  {rec.evidence_references && rec.evidence_references.length > 0 && (
                    <div style={{ display: 'flex', gap: '0.25rem', alignItems: 'center', fontSize: '0.7rem', color: '#64748b' }}>
                      <span>Evidence:</span>
                      {rec.evidence_references.map((id) => (
                        <span key={id} style={{ background: '#f1f5f9', padding: '0.1rem 0.35rem', borderRadius: '3px', fontFamily: 'monospace' }}>
                          {id}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
