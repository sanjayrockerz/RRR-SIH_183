import { useEffect, useState } from 'react';
import { createVaspActionPackage, vaspCandidates } from '../api';
import type { VaspActionPackage, VaspCandidate } from '../types';

const short = (value: string) => value.length > 18 ? `${value.slice(0, 8)}…${value.slice(-6)}` : value;

export function VaspIntelligencePage({ caseId }: { caseId?: string }) {
  const [items, setItems] = useState<VaspCandidate[]>([]);
  const [selected, setSelected] = useState<VaspCandidate | null>(null);
  const [pkg, setPkg] = useState<VaspActionPackage | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!caseId) return;
    setLoading(true);
    vaspCandidates(caseId).then(setItems).catch((e) => setError(e instanceof Error ? e.message : 'VASP intelligence unavailable')).finally(() => setLoading(false));
  }, [caseId]);

  async function generate() {
    if (!caseId) return;
    setError('');
    try {
      setPkg(await createVaspActionPackage(caseId, selected ? { entity_id: selected.entity_id, address: selected.address, created_by: 'investigator-session' } : { created_by: 'investigator-session' }));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Action package generation failed');
    }
  }

  if (!caseId) return <section className="surface"><h2>VASP intelligence</h2><p>Open a case before querying source-backed VASP candidates.</p></section>;

  return <>
    <div className="page-header"><div><div className="eyebrow">INTELLIGENCE / VASP ACTIONABILITY</div><h1>VASP intelligence</h1><p className="muted">Source-backed candidate ranking from the persisted investigation trace.</p></div><button className="primary" onClick={generate} disabled={loading}>GENERATE VASP ACTION PACKAGE</button></div>
    {error && <div className="error" role="alert">{error}</div>}
    <section className="surface">
      <div className="panel-title"><div><div className="eyebrow">RANKED CANDIDATES</div><h3>{loading ? 'Loading…' : items.length ? `${items.length} candidate${items.length === 1 ? '' : 's'}` : 'NO DATA'}</h3></div><span className="status-badge">SOURCE-BACKED ONLY</span></div>
      {items.length ? <div className="case-table"><table className="workspace-table"><thead><tr><th>RANK / VASP</th><th>CHAIN</th><th>HOPS</th><th>OBSERVED FLOW</th><th>CONFIDENCE</th><th>SOURCE</th><th>CLASSIFICATION</th></tr></thead><tbody>{items.map(item => <tr key={`${item.entity_id}:${item.address}`} onClick={() => setSelected(item)} style={{ cursor: 'pointer', background: selected?.address === item.address ? '#172033' : undefined }}><td><strong>#{item.rank} {item.entity_name}</strong><small style={{ display: 'block', color: '#9ca3af' }}>{short(item.address)} · {item.entity_type}</small></td><td>{item.chain.toUpperCase()}</td><td>{item.hop_distance}</td><td>{item.observed_linked_amount}</td><td>{item.attribution_confidence}</td><td>{item.attribution_source}</td><td><span className="status-badge">{item.classification}</span></td></tr>)}</tbody></table></div> : <div className="empty-block"><b>NO SOURCE-BACKED VASP CANDIDATES</b><p>Candidate ranking requires a persisted trace and configured attribution records. This is not a clearance determination.</p></div>}
    </section>
    {selected && <section className="surface"><div className="panel-title"><div><div className="eyebrow">CANDIDATE DETAIL</div><h3>{selected.entity_name}</h3></div><span>{selected.classification}</span></div><p>{selected.reasons.join(' ')}</p><dl><dt>ADDRESS</dt><dd className="mono">{selected.address}</dd><dt>SHORTEST OBSERVED PATH</dt><dd>{selected.evidence_path.length ? selected.evidence_path.map(short).join(' → ') : 'NO DATA'}</dd><dt>EVIDENCE REFERENCES</dt><dd>{selected.evidence_ids.length || 'NO DATA'}</dd></dl><p className="muted">Shared infrastructure is an investigative lead and does not prove common ownership or common criminal control.</p></section>}
    {pkg && <section className="surface"><div className="eyebrow">ACTION PACKAGE GENERATED</div><h3>{pkg.vasp_candidate?.entity_name || 'No candidate resolved'}</h3><p>{pkg.recommended_next_step}</p><dl><dt>GENERATED</dt><dd>{new Date(pkg.generated_at).toLocaleString()} · v{pkg.report_version}</dd><dt>PACKAGE HASH</dt><dd className="mono">{pkg.integrity_hash}</dd><dt>REPORT SNAPSHOT</dt><dd className="mono">{pkg.report_id}</dd><dt>EVIDENCE MANIFEST</dt><dd>{pkg.manifest_id ? `${pkg.manifest_id} · ${pkg.evidence_manifest_hash}` : 'NO DATA — no evidence records were available to manifest'}</dd><dt>LIMITATIONS</dt><dd>{pkg.limitations.join(' ')}</dd></dl><details><summary>VIEW PACKAGE JSON</summary><pre>{JSON.stringify(pkg, null, 2)}</pre></details></section>}
  </>;
}
