import { useEffect, useState } from 'react';
import { highRiskCases, highRiskWallets, ncrpStatus, sahyogStatus } from '../api';

export function HighRiskPage({ onSelectCase }: { onSelectCase?: (caseId: string) => void }) {
  const [cases, setCases] = useState<any[]>([]);
  const [wallets, setWallets] = useState<any[]>([]);
  const [ncrp, setNcrp] = useState<any>(null);
  const [sahyog, setSahyog] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [filterBand, setFilterBand] = useState<string>('ALL');
  const [filterChain, setFilterChain] = useState<string>('ALL');

  useEffect(() => {
    setLoading(true);
    Promise.all([highRiskCases(), highRiskWallets(), ncrpStatus(), sahyogStatus()])
      .then(([c, w, n, s]) => {
        setCases(c);
        setWallets(w);
        setNcrp(n);
        setSahyog(s);
      })
      .catch((err) => setError((err as Error).message))
      .finally(() => setLoading(false));
  }, []);

  const filteredCases = cases.filter((c) => {
    if (filterBand !== 'ALL' && c.risk_band !== filterBand) return false;
    if (filterChain !== 'ALL' && c.chain !== filterChain) return false;
    return true;
  });

  const getBandBadge = (band: string) => {
    switch (band) {
      case 'CRITICAL':
        return <span className="bg-red-900/60 text-red-300 text-xs px-2.5 py-0.5 rounded font-bold border border-red-500/40">CRITICAL</span>;
      case 'HIGH':
        return <span className="bg-amber-900/60 text-amber-300 text-xs px-2.5 py-0.5 rounded font-bold border border-amber-500/40">HIGH</span>;
      case 'MEDIUM':
        return <span className="bg-yellow-900/60 text-yellow-300 text-xs px-2.5 py-0.5 rounded font-semibold border border-yellow-500/30">MEDIUM</span>;
      default:
        return <span className="bg-gray-800 text-gray-300 text-xs px-2.5 py-0.5 rounded">LOW</span>;
    }
  };

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto text-gray-100 font-sans">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-gray-800 pb-4">
        <div>
          <h1 className="text-2xl font-bold text-red-400 tracking-wide flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-red-500 animate-pulse"></span>
            HIGH-RISK INTELLIGENCE
          </h1>
          <p className="text-sm text-gray-400 mt-1">
            Prioritized operational surveillance for critical cyber-fraud infrastructure and escalated risk vectors.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {ncrp && (
            <div className="bg-gray-900 border border-gray-800 px-3 py-1.5 rounded text-xs">
              <span className="text-gray-400">NCRP: </span>
              <span className="text-emerald-400 font-semibold">{ncrp.status}</span>
            </div>
          )}
          {sahyog && (
            <div className="bg-gray-900 border border-gray-800 px-3 py-1.5 rounded text-xs">
              <span className="text-gray-400">Sahyog: </span>
              <span className="text-emerald-400 font-semibold">{sahyog.status}</span>
            </div>
          )}
        </div>
      </div>

      {error && (
        <div className="bg-red-950/60 border border-red-800 text-red-300 p-3 rounded text-sm">
          {error}
        </div>
      )}

      {/* Metrics Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-gray-900/80 border border-gray-800 rounded-lg p-4">
          <div className="text-xs text-gray-400 font-medium uppercase">Critical Risk Cases</div>
          <div className="text-2xl font-bold text-red-400 mt-1">
            {cases.filter((c) => c.risk_band === 'CRITICAL' || c.risk_score >= 80).length}
          </div>
          <div className="text-[11px] text-gray-500 mt-1">Immediate action recommended</div>
        </div>
        <div className="bg-gray-900/80 border border-gray-800 rounded-lg p-4">
          <div className="text-xs text-gray-400 font-medium uppercase">High-Risk Wallets</div>
          <div className="text-2xl font-bold text-amber-400 mt-1">{wallets.length}</div>
          <div className="text-[11px] text-gray-500 mt-1">Monitored infrastructure</div>
        </div>
        <div className="bg-gray-900/80 border border-gray-800 rounded-lg p-4">
          <div className="text-xs text-gray-400 font-medium uppercase">Actionable VASP Exposure</div>
          <div className="text-2xl font-bold text-cyan-400 mt-1">
            ${cases.reduce((sum, c) => sum + (c.vasp_exposure_usd || 0), 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </div>
          <div className="text-[11px] text-gray-500 mt-1">Actionable receiving funds</div>
        </div>
        <div className="bg-gray-900/80 border border-gray-800 rounded-lg p-4">
          <div className="text-xs text-gray-400 font-medium uppercase">Active Alerts</div>
          <div className="text-2xl font-bold text-purple-400 mt-1">
            {cases.reduce((sum, c) => sum + (c.alert_count || 0), 0)}
          </div>
          <div className="text-[11px] text-gray-500 mt-1">Evaluated real-time triggers</div>
        </div>
      </div>

      {/* Filters Bar */}
      <div className="flex flex-wrap items-center gap-4 bg-gray-900/50 p-3 rounded-lg border border-gray-800 text-xs">
        <span className="text-gray-400 font-semibold uppercase">Filters:</span>
        <div className="flex items-center gap-2">
          <span className="text-gray-500">Risk Band:</span>
          <select
            value={filterBand}
            onChange={(e) => setFilterBand(e.target.value)}
            className="bg-gray-800 border border-gray-700 text-gray-200 rounded px-2 py-1 focus:outline-none focus:border-cyan-500"
          >
            <option value="ALL">All Bands</option>
            <option value="CRITICAL">Critical</option>
            <option value="HIGH">High</option>
            <option value="MEDIUM">Medium</option>
          </select>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-gray-500">Chain:</span>
          <select
            value={filterChain}
            onChange={(e) => setFilterChain(e.target.value)}
            className="bg-gray-800 border border-gray-700 text-gray-200 rounded px-2 py-1 focus:outline-none focus:border-cyan-500"
          >
            <option value="ALL">All Chains</option>
            <option value="ethereum">Ethereum</option>
            <option value="tron">TRON</option>
            <option value="bsc">BSC</option>
            <option value="bitcoin">Bitcoin</option>
          </select>
        </div>
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: High-Risk Cases List (2 cols) */}
        <div className="lg:col-span-2 space-y-4">
          <h2 className="text-lg font-bold text-gray-200 flex items-center gap-2">
            <span>High-Risk Cases</span>
            <span className="text-xs font-normal text-gray-400 bg-gray-800 px-2 py-0.5 rounded">
              {filteredCases.length} Cases
            </span>
          </h2>

          {loading ? (
            <div className="p-8 text-center text-gray-400 bg-gray-900/40 rounded-lg border border-gray-800">
              Loading high-risk intelligence cases...
            </div>
          ) : filteredCases.length === 0 ? (
            <div className="p-8 text-center text-gray-500 bg-gray-900/40 rounded-lg border border-gray-800">
              No cases matching current filter parameters.
            </div>
          ) : (
            <div className="space-y-4">
              {filteredCases.map((c) => (
                <div
                  key={c.case_id}
                  className="bg-gray-900/80 border border-gray-800 rounded-lg p-5 hover:border-gray-700 transition space-y-4"
                >
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                    <div>
                      <div className="flex items-center gap-3">
                        <span className="font-mono text-sm font-bold text-cyan-400">{c.case_id}</span>
                        {getBandBadge(c.risk_band)}
                        <span className="text-xs font-mono bg-gray-800 text-gray-300 px-2 py-0.5 rounded uppercase">
                          {c.chain}
                        </span>
                      </div>
                      <h3 className="text-base font-semibold text-gray-200 mt-1">{c.title}</h3>
                    </div>
                    <div className="text-right">
                      <div className="text-2xl font-extrabold text-red-400">
                        {c.risk_score.toFixed(1)}
                        <span className="text-xs text-gray-500 font-normal"> / 100</span>
                      </div>
                      <div className="text-[11px] text-gray-400">Priority: {c.investigative_priority}</div>
                    </div>
                  </div>

                  {/* Wallet & VASP Details */}
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 bg-gray-950/60 p-3 rounded text-xs border border-gray-850">
                    <div>
                      <span className="text-gray-500 block">Reported Wallet:</span>
                      <span className="font-mono text-gray-300 text-[11px] break-all">{c.reported_wallet}</span>
                    </div>
                    <div>
                      <span className="text-gray-500 block">Top Receiving VASP:</span>
                      <span className="font-medium text-amber-300">{c.top_vasp_name || 'NOT YET DETERMINED'}</span>
                    </div>
                    <div>
                      <span className="text-gray-500 block">Actionable VASP Exposure:</span>
                      <span className="font-semibold text-emerald-400">
                        ${c.vasp_exposure_usd?.toLocaleString() || '0'} USD
                      </span>
                    </div>
                  </div>

                  {/* Contributing Signals Breakdown (Part C3 requirement) */}
                  <div>
                    <div className="text-xs text-gray-400 font-semibold mb-2">Contributing Risk Factors (Engine Breakdown):</div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      {c.contributing_signals?.map((sig: any, idx: number) => (
                        <div key={idx} className="flex items-start gap-2 bg-gray-950/40 p-2 rounded border border-gray-800 text-xs">
                          <span className="font-bold text-amber-400 text-xs">+{sig.score_points?.toFixed(0)}</span>
                          <div>
                            <div className="font-medium text-gray-200">{sig.label}</div>
                            <div className="text-[11px] text-gray-400 mt-0.5">{sig.description}</div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Risk Score Delta (Part C4 requirement) */}
                  {c.latest_score_change && (
                    <div className="flex items-center justify-between text-xs bg-red-950/20 border border-red-900/40 text-red-300 p-2.5 rounded">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold">Risk Escalation:</span>
                        <span className="font-mono">{c.latest_score_change.previous_score?.toFixed(0)} → {c.latest_score_change.current_score?.toFixed(0)}</span>
                        <span className="bg-red-900/60 text-red-200 px-1.5 py-0.5 rounded text-[10px] font-bold">
                          +{c.latest_score_change.change?.toFixed(0)} pts
                        </span>
                      </div>
                      <div className="text-gray-400 text-[11px] italic">{c.latest_score_change.reason}</div>
                    </div>
                  )}

                  {/* Actions */}
                  <div className="flex items-center justify-between pt-2 border-t border-gray-800 text-xs">
                    <div className="text-gray-500">
                      Connected Wallets: <span className="text-gray-300 font-medium">{c.connected_cases_count}</span> | Alerts: <span className="text-gray-300 font-medium">{c.alert_count}</span>
                    </div>
                    {onSelectCase && (
                      <button
                        onClick={() => onSelectCase(c.case_id)}
                        className="bg-cyan-600 hover:bg-cyan-500 text-white font-medium px-3 py-1.5 rounded transition shadow-sm"
                      >
                        Investigate Case →
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right Column: High-Risk Wallets & Integration Status (1 col) */}
        <div className="space-y-6">
          {/* High Risk Wallets */}
          <div className="bg-gray-900/80 border border-gray-800 rounded-lg p-5 space-y-4">
            <h3 className="text-base font-bold text-gray-200 flex items-center justify-between">
              <span>High-Risk Wallets</span>
              <span className="text-xs text-gray-400">{wallets.length} Active</span>
            </h3>

            <div className="space-y-3 max-h-[500px] overflow-y-auto pr-1">
              {wallets.map((w) => (
                <div key={w.wallet_id} className="p-3 bg-gray-950/60 border border-gray-850 rounded text-xs space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-cyan-300 text-[11px] font-semibold">{w.address.slice(0, 10)}...{w.address.slice(-8)}</span>
                    <span className="font-bold text-amber-400">{w.risk_score.toFixed(0)} Pts</span>
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {w.exposure_categories?.map((cat: string) => (
                      <span key={cat} className="bg-gray-800 text-gray-300 text-[10px] px-1.5 py-0.5 rounded font-mono">
                        {cat}
                      </span>
                    ))}
                  </div>
                  <div className="text-gray-400 text-[11px] flex justify-between pt-1 border-t border-gray-850">
                    <span>Connected Cases: {w.connected_cases_count}</span>
                    <span>Exposure: ${w.exposure_usd?.toLocaleString() || '0'}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Integration Status Card */}
          <div className="bg-gray-900/80 border border-gray-800 rounded-lg p-5 space-y-3 text-xs">
            <h3 className="text-sm font-bold text-gray-200 uppercase tracking-wider">Integration Boundaries</h3>
            
            {ncrp && (
              <div className="p-3 bg-gray-950/60 border border-gray-800 rounded space-y-1">
                <div className="flex items-center justify-between font-semibold">
                  <span className="text-gray-300">NCRP Portal</span>
                  <span className="text-emerald-400 text-[11px] font-mono">{ncrp.mode}</span>
                </div>
                <p className="text-gray-400 text-[11px]">{ncrp.disclaimer}</p>
              </div>
            )}

            {sahyog && (
              <div className="p-3 bg-gray-950/60 border border-gray-800 rounded space-y-1">
                <div className="flex items-center justify-between font-semibold">
                  <span className="text-gray-300">Sahyog Portal</span>
                  <span className="text-emerald-400 text-[11px] font-mono">{sahyog.mode}</span>
                </div>
                <p className="text-gray-400 text-[11px]">{sahyog.disclaimer}</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
