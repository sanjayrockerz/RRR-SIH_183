import { useEffect, useState } from 'react';
import { caseFusionClusters } from '../api';
import type { CaseFusionCluster } from '../types';

export function CaseFusionPage({ onOpenCase }: { onOpenCase?: (caseId: string) => void }) {
  const [clusters, setClusters] = useState<CaseFusionCluster[]>([]);
  const [status, setStatus] = useState('LOADING');
  const [error, setError] = useState('');
  useEffect(() => { caseFusionClusters().then(result => { setClusters(result.clusters); setStatus(result.status); }).catch(e => { setError(e instanceof Error ? e.message : 'Case Fusion unavailable'); setStatus('UNAVAILABLE'); }); }, []);
  return <section className="surface">
    <div className="panel-title"><div><div className="eyebrow">RRR / CASE FUSION</div><h3>Persisted infrastructure relationships</h3><p className="muted">Explainable overlap and similarity between investigations. A relationship does not establish common ownership or criminal attribution.</p></div><span className="status-badge">{status}</span></div>
    {error && <div className="error" role="alert">{error}</div>}
    {clusters.length ? <div className="registry-grid">{clusters.map(cluster => <article className="surface" key={cluster.cluster_id}><div className="eyebrow">{cluster.relationship} · SCORE {Math.round(cluster.score * 100)}%</div><div className="case-fusion-nodes">{cluster.case_ids.map((caseId, index) => <button className="secondary" key={caseId} onClick={() => onOpenCase?.(caseId)}>CASE {caseId.slice(0, 10)}{index < cluster.case_ids.length - 1 ? ' ↔' : ''}</button>)}</div><p>{cluster.shared_infrastructure.length ? `Shared persisted infrastructure: ${cluster.shared_infrastructure.join(', ')}` : 'Similarity derived from persisted observations.'}</p><ul>{cluster.reasons.map(reason => <li key={reason}>{reason}</li>)}</ul></article>)}</div> : <div className="empty-block"><b>{status === 'UNAVAILABLE' ? 'CASE FUSION UNAVAILABLE' : 'NO RELATED PERSISTED INFRASTRUCTURE'}</b><p>Clusters appear only when persisted investigations share infrastructure or meet the deterministic similarity threshold.</p></div>}
  </section>;
}
