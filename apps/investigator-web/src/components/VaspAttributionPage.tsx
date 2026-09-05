import { useEffect, useState } from 'react';
import { vaspAddressAttribution, vaspEntities } from '../api';
import type { AttributionResult, VaspEntity } from '../types';

export function VaspAttributionPage() {
  const [address, setAddress] = useState('0x28c6c06298d514db089934071355e5743bf21d60');
  const [chain, setChain] = useState('ethereum');
  const [result, setResult] = useState<AttributionResult | null>(null);
  const [entities, setEntities] = useState<VaspEntity[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    vaspEntities()
      .then(setEntities)
      .catch(() => {});
    runAnalysis('0x28c6c06298d514db089934071355e5743bf21d60', 'ethereum');
  }, []);

  async function runAnalysis(addrToAnalyze = address, chainToAnalyze = chain) {
    if (!addrToAnalyze.trim()) return;
    setBusy(true);
    setError('');
    try {
      const data = await vaspAddressAttribution(chainToAnalyze, addrToAnalyze.trim());
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'VASP attribution lookup failed');
      setResult(null);
    } finally {
      setBusy(false);
    }
  }

  function getBadgeClass(classification: string) {
    switch (classification) {
      case 'KNOWN':
        return 'badge-known';
      case 'PROBABLE':
        return 'badge-probable';
      case 'POSSIBLE':
        return 'badge-possible';
      default:
        return 'badge-unknown';
    }
  }

  return (
    <div className="vasp-attribution-workspace" style={{ padding: '24px', color: '#e5e7eb' }}>
      <header className="page-header" style={{ marginBottom: '24px' }}>
        <div style={{ fontSize: '11px', letterSpacing: '0.08em', color: '#6b7280', fontWeight: 600 }}>
          INTELLIGENCE / VASP ATTRIBUTION
        </div>
        <h1 style={{ fontSize: '24px', fontWeight: 700, margin: '4px 0 8px 0', color: '#f9fafb' }}>
          VASP Intelligence & Attribution Engine
        </h1>
        <p style={{ color: '#9ca3af', fontSize: '14px', margin: 0 }}>
          Evidence-backed entity classification (<span style={{ color: '#10b981' }}>KNOWN</span>,{' '}
          <span style={{ color: '#3b82f6' }}>PROBABLE</span>, <span style={{ color: '#f59e0b' }}>POSSIBLE</span>,{' '}
          <span style={{ color: '#6b7280' }}>UNKNOWN</span>) with deterministic confidence scoring and explicit provenance.
        </p>
      </header>

      {/* Address Search Bar */}
      <section
        className="surface"
        style={{
          background: '#111827',
          border: '1px solid #1f2937',
          borderRadius: '8px',
          padding: '20px',
          marginBottom: '24px',
        }}
      >
        <div style={{ fontSize: '11px', letterSpacing: '0.05em', color: '#9ca3af', marginBottom: '8px', fontWeight: 600 }}>
          RUN ADDRESS ATTRIBUTION LOOKUP
        </div>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <select
            value={chain}
            onChange={(e) => setChain(e.target.value)}
            style={{
              background: '#030712',
              border: '1px solid #374151',
              color: '#f9fafb',
              padding: '10px 14px',
              borderRadius: '6px',
              fontSize: '14px',
            }}
          >
            <option value="ethereum">Ethereum (ETH)</option>
            <option value="tron">TRON (TRX)</option>
          </select>

          <input
            type="text"
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            placeholder="Enter wallet address (0x... or T...)"
            style={{
              flex: 1,
              background: '#030712',
              border: '1px solid #374151',
              color: '#f9fafb',
              padding: '10px 14px',
              borderRadius: '6px',
              fontFamily: 'monospace',
              fontSize: '14px',
            }}
          />

          <button
            onClick={() => runAnalysis(address, chain)}
            disabled={busy || !address.trim()}
            style={{
              background: '#2563eb',
              color: '#ffffff',
              border: 'none',
              padding: '10px 20px',
              borderRadius: '6px',
              fontWeight: 600,
              cursor: busy ? 'not-allowed' : 'pointer',
            }}
          >
            {busy ? 'ANALYZING...' : 'RUN ATTRIBUTION'}
          </button>
        </div>

        {error && (
          <div style={{ marginTop: '12px', color: '#ef4444', fontSize: '13px', background: '#2d1215', padding: '8px 12px', borderRadius: '4px' }}>
            {error}
          </div>
        )}
      </section>

      {/* Attribution Result */}
      {result && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px', marginBottom: '24px' }}>
          {/* Main Card */}
          <section
            className="surface"
            style={{
              background: '#111827',
              border: '1px solid #1f2937',
              borderRadius: '8px',
              padding: '24px',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
              <div>
                <div style={{ fontSize: '11px', color: '#9ca3af', fontWeight: 600, letterSpacing: '0.05em' }}>CANDIDATE ENTITY</div>
                <h2 style={{ fontSize: '20px', fontWeight: 700, margin: '4px 0', color: '#f3f4f6' }}>
                  {result.candidate_entity ? result.candidate_entity.trading_name : 'No Match Identified'}
                </h2>
                {result.candidate_entity?.legal_name && (
                  <div style={{ fontSize: '13px', color: '#9ca3af' }}>Legal: {result.candidate_entity.legal_name}</div>
                )}
              </div>

              <div style={{ textAlign: 'right' }}>
                <span
                  style={{
                    display: 'inline-block',
                    padding: '6px 14px',
                    borderRadius: '9999px',
                    fontWeight: 700,
                    fontSize: '13px',
                    letterSpacing: '0.05em',
                    background:
                      result.classification === 'KNOWN'
                        ? '#064e3b'
                        : result.classification === 'PROBABLE'
                        ? '#1e3a8a'
                        : result.classification === 'POSSIBLE'
                        ? '#78350f'
                        : '#374151',
                    color:
                      result.classification === 'KNOWN'
                        ? '#34d399'
                        : result.classification === 'PROBABLE'
                        ? '#60a5fa'
                        : result.classification === 'POSSIBLE'
                        ? '#fbbf24'
                        : '#9ca3af',
                    border: `1px solid ${
                      result.classification === 'KNOWN'
                        ? '#059669'
                        : result.classification === 'PROBABLE'
                        ? '#2563eb'
                        : result.classification === 'POSSIBLE'
                        ? '#d97706'
                        : '#4b5563'
                    }`,
                  }}
                >
                  {result.classification}
                </span>
                <div style={{ fontSize: '22px', fontWeight: 800, marginTop: '8px', color: '#f9fafb' }}>
                  {(result.confidence * 100).toFixed(1)}%
                </div>
              </div>
            </div>

            <div
              style={{
                background: '#030712',
                border: '1px solid #1f2937',
                borderRadius: '6px',
                padding: '14px',
                fontSize: '13px',
                color: '#d1d5db',
                marginBottom: '16px',
              }}
            >
              <strong>Explanation:</strong> {result.explanation}
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px', fontSize: '12px' }}>
              <div style={{ background: '#0a0d14', padding: '10px', borderRadius: '6px' }}>
                <div style={{ color: '#6b7280', fontWeight: 600 }}>GRAPH DISTANCE</div>
                <div style={{ fontSize: '15px', fontWeight: 700, marginTop: '2px', color: '#f3f4f6' }}>
                  {result.graph_distance !== null && result.graph_distance !== undefined
                    ? `${result.graph_distance} hop(s)`
                    : 'Direct Match'}
                </div>
              </div>

              <div style={{ background: '#0a0d14', padding: '10px', borderRadius: '6px' }}>
                <div style={{ color: '#6b7280', fontWeight: 600 }}>VOLUME OBSERVED</div>
                <div style={{ fontSize: '15px', fontWeight: 700, marginTop: '2px', color: '#f3f4f6' }}>
                  {result.fund_amount} crypto
                </div>
              </div>

              <div style={{ background: '#0a0d14', padding: '10px', borderRadius: '6px' }}>
                <div style={{ color: '#6b7280', fontWeight: 600 }}>JURISDICTION</div>
                <div style={{ fontSize: '15px', fontWeight: 700, marginTop: '2px', color: '#f3f4f6' }}>
                  {result.candidate_entity?.jurisdiction || 'N/A'}
                </div>
              </div>
            </div>
          </section>

          {/* Evidence Cards */}
          <section
            className="surface"
            style={{
              background: '#111827',
              border: '1px solid #1f2937',
              borderRadius: '8px',
              padding: '24px',
            }}
          >
            <h3 style={{ fontSize: '15px', fontWeight: 700, margin: '0 0 16px 0', color: '#f3f4f6' }}>
              Supporting Evidence ({result.supporting_evidence.length})
            </h3>

            {result.supporting_evidence.length === 0 ? (
              <div style={{ fontSize: '13px', color: '#9ca3af' }}>No supporting evidence records found.</div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', maxHeight: '220px', overflowY: 'auto' }}>
                {result.supporting_evidence.map((ev) => (
                  <div
                    key={ev.id}
                    style={{
                      background: '#064e3b22',
                      borderLeft: '4px solid #10b981',
                      padding: '10px 12px',
                      borderRadius: '4px',
                      fontSize: '12px',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', color: '#10b981', fontWeight: 700 }}>
                      <span>✓ {ev.evidence_type}</span>
                      <span>Confidence: {(ev.confidence * 100).toFixed(0)}%</span>
                    </div>
                    <div style={{ color: '#e5e7eb', marginTop: '4px' }}>{ev.evidence_description}</div>
                    <div style={{ color: '#6b7280', fontSize: '11px', marginTop: '4px' }}>Source: {ev.source}</div>
                  </div>
                ))}
              </div>
            )}

            <h3 style={{ fontSize: '15px', fontWeight: 700, margin: '20px 0 12px 0', color: '#f3f4f6' }}>
              Contradictory Evidence ({result.contradictory_evidence.length})
            </h3>

            {result.contradictory_evidence.length === 0 ? (
              <div style={{ fontSize: '13px', color: '#9ca3af' }}>No contradictory or conflicting evidence signals.</div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', maxHeight: '180px', overflowY: 'auto' }}>
                {result.contradictory_evidence.map((ev) => (
                  <div
                    key={ev.id}
                    style={{
                      background: '#78350f22',
                      borderLeft: '4px solid #f59e0b',
                      padding: '10px 12px',
                      borderRadius: '4px',
                      fontSize: '12px',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', color: '#f59e0b', fontWeight: 700 }}>
                      <span>⚠ {ev.evidence_type}</span>
                      <span>Confidence: {(ev.confidence * 100).toFixed(0)}%</span>
                    </div>
                    <div style={{ color: '#e5e7eb', marginTop: '4px' }}>{ev.evidence_description}</div>
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>
      )}

      {/* VASP Registry Catalog Table */}
      <section
        className="surface"
        style={{
          background: '#111827',
          border: '1px solid #1f2937',
          borderRadius: '8px',
          padding: '24px',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <div>
            <div style={{ fontSize: '11px', color: '#9ca3af', fontWeight: 600, letterSpacing: '0.05em' }}>REGISTRY INTELLIGENCE</div>
            <h3 style={{ fontSize: '18px', fontWeight: 700, margin: '2px 0 0 0', color: '#f3f4f6' }}>
              Registered VASP Entities ({entities.length})
            </h3>
          </div>
          <span style={{ fontSize: '12px', background: '#1f2937', padding: '4px 10px', borderRadius: '4px', color: '#9ca3af' }}>
            DEMO DATASET ACTIVE
          </span>
        </div>

        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid #374151', color: '#9ca3af' }}>
              <th style={{ padding: '10px' }}>Trading Name</th>
              <th style={{ padding: '10px' }}>Legal Name</th>
              <th style={{ padding: '10px' }}>Jurisdiction</th>
              <th style={{ padding: '10px' }}>Status</th>
              <th style={{ padding: '10px' }}>Website</th>
              <th style={{ padding: '10px' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {entities.map((e) => (
              <tr key={e.id} style={{ borderBottom: '1px solid #1f2937' }}>
                <td style={{ padding: '12px 10px', fontWeight: 600, color: '#f9fafb' }}>{e.trading_name}</td>
                <td style={{ padding: '12px 10px', color: '#d1d5db' }}>{e.legal_name}</td>
                <td style={{ padding: '12px 10px', color: '#9ca3af' }}>{e.jurisdiction || 'N/A'}</td>
                <td style={{ padding: '12px 10px' }}>
                  <span
                    style={{
                      background: '#064e3b',
                      color: '#34d399',
                      padding: '2px 8px',
                      borderRadius: '4px',
                      fontSize: '11px',
                      fontWeight: 600,
                    }}
                  >
                    {e.regulatory_status}
                  </span>
                </td>
                <td style={{ padding: '12px 10px', color: '#60a5fa' }}>{e.website || 'N/A'}</td>
                <td style={{ padding: '12px 10px' }}>
                  <button
                    onClick={() => {
                      if (e.id === 'vasp-demo-binance') runAnalysis('0x28c6c06298d514db089934071355e5743bf21d60', 'ethereum');
                      else if (e.id === 'vasp-demo-kraken') runAnalysis('0x2910543af39aba0cd09bfb2650210b2d86da3536', 'ethereum');
                      else if (e.id === 'vasp-demo-coinbase') runAnalysis('0x71660c4005ba85c37ccec55d0c4493e66fe775d3', 'ethereum');
                      else if (e.id === 'vasp-demo-okx') runAnalysis('TYDzsYawMuJF93wYo9V3Biq7rB2nKfyb5j', 'tron');
                    }}
                    style={{
                      background: '#374151',
                      color: '#f3f4f6',
                      border: 'none',
                      padding: '4px 10px',
                      borderRadius: '4px',
                      fontSize: '11px',
                      cursor: 'pointer',
                    }}
                  >
                    Sample Lookup
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
