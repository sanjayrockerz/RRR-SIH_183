import { useEffect, useState } from 'react';
import type { CaseFusionResponse } from '../types';
import { caseFusion } from '../api';

export function RelatedCasesPanel({ caseId }: { caseId: string }) {
  const [result, setResult] = useState<CaseFusionResponse | null>(null);
  const [error, setError] = useState('');
  useEffect(() => { caseFusion(caseId).then(setResult).catch(e => setError(e instanceof Error ? e.message : 'Case Fusion unavailable')); }, [caseId]);
  const items = result?.related_cases || [];
  return <section className="surface"><div className="panel-title"><div><div className="eyebrow">RRR CASE FUSION</div><h3>{items.length ? `${items.length} related cases` : 'No related persisted infrastructure'}</h3></div><span className="status-badge">EXPLAINABLE CORRELATION</span></div>{error && <div className="error" role="alert">{error}</div>}{items.length ? <><div className="case-table">{items.map(item => <article className="case-row" key={item.related_case_id}><strong>{item.related_case_id}</strong><span>{item.relationship} · {Math.round(item.score * 100)}%</span><span>{item.shared_wallets.length} wallets · {item.shared_vasps.length} VASPs · {item.shared_bridges.length} bridges</span><small>{item.reasons.join(' · ')}</small></article>)}</div><p className="muted">Shared infrastructure is an investigative lead and does not prove common ownership or common criminal control.</p></> : <div className="empty-block"><b>{error ? 'CASE FUSION UNAVAILABLE' : 'No persisted relationship'}</b><p>Only persisted infrastructure overlap or deterministic infrastructure similarity is shown.</p></div>}</section>;
}
