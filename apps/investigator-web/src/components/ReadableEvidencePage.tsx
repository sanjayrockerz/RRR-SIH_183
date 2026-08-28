import { useEffect, useState } from 'react';
import { listEvidence } from '../api';
import type { Case, EvidenceRecord } from '../types';

const labels: Record<string, string> = {
  TRANSACTION: 'Blockchain transaction',
  REALTIME_BLOCKCHAIN_OBSERVATION: 'Realtime blockchain observation',
  REALTIME_TRANSACTION: 'Realtime transaction',
  TRACE_OBSERVATION: 'Trace observation'
};

const short = (value?: string) => value ? `${value.slice(0, 10)}…${value.slice(-8)}` : '—';
const pretty = (value: string) => value.replaceAll('_', ' ').toLowerCase().replace(/(^| )\S/g, c => c.toUpperCase());

export function ReadableEvidencePage({ caseData }: { caseData: Case | null }) {
  const [items, setItems] = useState<EvidenceRecord[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    setError('');
    if (!caseData) {
      setItems([]);
      setLoading(false);
      return;
    }
    listEvidence(caseData.case_id)
      .then(setItems)
      .catch((e) => setError(e instanceof Error ? e.message : 'Evidence service unavailable'))
      .finally(() => setLoading(false));
  };

  useEffect(load, [caseData?.case_id]);

  const copyId = (id: string) => {
    navigator.clipboard?.writeText(id);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 1500);
  };

  const openInGraph = () => {
    window.location.hash = 'graph';
  };

  return (
    <section className="readable-evidence">
      <div className="page-header">
        <div>
          <div className="eyebrow">FORENSIC LEDGER / {caseData ? short(caseData.case_id) : 'NO CASE SELECTED'}</div>
          <h1>Forensic Evidence Ledger</h1>
          <p className="muted">Verify cryptographic hashes, original source adapters, and blockchain transaction provenance.</p>
        </div>
        <div className="evidence-summary">
          <span>{items.length}</span>
          <small>persisted records</small>
        </div>
      </div>

      {!caseData && (
        <div className="surface" style={{ padding: '40px', textAlign: 'center' }}>
          <div className="empty-state">
            <strong>Select an active investigation</strong>
            <p>Open a case context from the Case command center before exploring captured evidence.</p>
          </div>
        </div>
      )}

      {loading && <div className="empty-state">Verifying evidence integrity status…</div>}
      {error && (
        <div className="error-state">
          <strong>Evidence could not be loaded</strong>
          <span>{error}</span>
          <button onClick={load}>RETRY</button>
        </div>
      )}

      {!loading && !error && caseData && !items.length && (
        <div className="empty-state">
          <strong>No evidence logs persisted</strong>
          <p>Evidence records are generated automatically during provider traces and real-time webhook ingestion.</p>
        </div>
      )}

      <div className="evidence-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))', gap: '20px', marginTop: '20px' }}>
        {items.map(item => {
          const meta = (item.metadata || {}) as Record<string, string>;
          const isETH = String(item.chain).toLowerCase() === 'ethereum';
          const explorerTxUrl = isETH 
            ? `https://etherscan.io/tx/${item.tx_hash}` 
            : `https://tronscan.org/#/transaction/${item.tx_hash}`;
          const explorerAddrUrl = isETH
            ? `https://etherscan.io/address/${meta.from || meta.to || ''}`
            : `https://tronscan.org/#/address/${meta.from || meta.to || ''}`;

          return (
            <article className="evidence-card" key={item.evidence_id} style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between', border: '1px stroke #374151' }}>
              <div>
                <div className="evidence-card-top" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                  <span className="data-badge" style={{ textTransform: 'uppercase' }}>{labels[item.type] || pretty(item.type)}</span>
                  <span className={`integrity ${item.integrity_status === 'VALID' ? 'valid' : ''}`}>
                    {item.integrity_status || 'SECURED'}
                  </span>
                </div>
                
                <h3 title={item.evidence_id} style={{ fontSize: '15px', color: '#e5e7eb', marginBottom: '10px' }}>
                  ID: {short(item.evidence_id)}
                </h3>

                <div className="evidence-meta" style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', fontSize: '12px', color: '#9ca3af', marginBottom: '12px' }}>
                  <span><b>Source</b> {item.source}</span>
                  <span><b>Captured</b> {new Date(item.captured_at).toLocaleString()}</span>
                  <span><b>Chain</b> {String(item.chain).toUpperCase()}</span>
                </div>

                <div className="evidence-facts" style={{ background: '#0a0d14', padding: '12px', borderRadius: '6px', fontSize: '13px', color: '#cbd5e1', marginBottom: '12px' }}>
                  {item.tx_hash && (
                    <div style={{ marginBottom: '6px' }}>
                      <b>TX Hash:</b> <a href={explorerTxUrl} target="_blank" rel="noopener noreferrer" className="mono" style={{ color: '#3b82f6' }}>{short(item.tx_hash)} ↗</a>
                    </div>
                  )}
                  {meta.from && (
                    <div style={{ marginBottom: '6px' }}>
                      <b>From:</b> <code style={{ fontSize: '11px' }}>{String(meta.from)}</code>
                    </div>
                  )}
                  {meta.to && (
                    <div style={{ marginBottom: '6px' }}>
                      <b>To:</b> <code style={{ fontSize: '11px' }}>{String(meta.to)}</code>
                    </div>
                  )}
                  {meta.amount && (
                    <div style={{ marginBottom: '6px' }}>
                      <b>Amount:</b> {String(meta.amount)} {String(meta.asset || 'ETH')}
                    </div>
                  )}
                  {meta.block_number && (
                    <div style={{ marginBottom: '6px' }}>
                      <b>Block:</b> {String(meta.block_number)}
                    </div>
                  )}
                  {meta.provider && (
                    <div style={{ marginBottom: '6px' }}>
                      <b>Provider:</b> {String(meta.provider)}
                    </div>
                  )}
                  {meta.risk_factors && (
                    <div style={{ marginTop: '8px' }}>
                      <b>Risk factors:</b> <span className="factor-chip risk-high" style={{ fontSize: '11px', padding: '2px 6px' }}>{String(meta.risk_factors)}</span>
                    </div>
                  )}
                  {meta.patterns && (
                    <div style={{ marginTop: '8px' }}>
                      <b>Pattern indicators:</b> <span className="factor-chip" style={{ fontSize: '11px', padding: '2px 6px' }}>{String(meta.patterns)}</span>
                    </div>
                  )}
                </div>
              </div>

              <div className="evidence-card-actions" style={{ display: 'flex', gap: '10px', marginTop: 'auto' }}>
                <button className="secondary btn-xs" onClick={() => copyId(item.evidence_id)}>
                  {copiedId === item.evidence_id ? 'Copied ✓' : 'Copy ID'}
                </button>
                <button className="secondary btn-xs" onClick={openInGraph}>
                  View in Graph
                </button>
                <a className="button secondary btn-xs" href={explorerTxUrl} target="_blank" rel="noopener noreferrer" style={{ display: 'inline-flex', alignItems: 'center' }}>
                  Verify block ↗
                </a>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
