import React, { useEffect, useState } from 'react';
import type {
  FraudNetworkGraph,
  InfrastructureImpactNode,
  CaseRelationshipScore,
  FraudNetworkNode,
  FraudNetworkEdge
} from '../types';
import { caseNetwork, caseSharedInfrastructure, correlateCases } from '../api';

interface Props {
  caseId: string;
  onNavigateCase?: (caseId: string) => void;
}

export function FraudNetworkPage({ caseId, onNavigateCase }: Props) {
  const [graph, setGraph] = useState<FraudNetworkGraph | null>(null);
  const [sharedNodes, setSharedNodes] = useState<InfrastructureImpactNode[]>([]);
  const [selectedNode, setSelectedNode] = useState<FraudNetworkNode | null>(null);
  const [compareCaseId, setCompareCaseId] = useState<string>('');
  const [correlationResults, setCorrelationResults] = useState<CaseRelationshipScore[] | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [correlating, setCorrelating] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    setLoading(true);
    setError(null);

    Promise.all([
      caseNetwork(caseId).catch((err) => {
        console.warn('Network graph fetch error:', err);
        return null;
      }),
      caseSharedInfrastructure(caseId).catch((err) => {
        console.warn('Shared infrastructure fetch error:', err);
        return [];
      })
    ]).then(([netData, infraData]) => {
      if (!isMounted) return;
      setGraph(netData);
      setSharedNodes(infraData);
      if (netData && netData.nodes.length > 0) {
        setSelectedNode(netData.nodes[0]);
      }
      setLoading(false);
    });

    return () => {
      isMounted = false;
    };
  }, [caseId]);

  const handleCorrelate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!compareCaseId.trim()) return;
    setCorrelating(true);
    try {
      const res = await correlateCases(caseId, compareCaseId.trim());
      setCorrelationResults(res);
    } catch (err: any) {
      setError(err?.message || 'Failed to calculate cross-case correlation.');
    } finally {
      setCorrelating(false);
    }
  };

  if (loading) {
    return (
      <div className="p-6 text-center text-gray-400">
        <div className="animate-spin inline-block w-6 h-6 border-2 border-cyan-500 border-t-transparent rounded-full mr-2" />
        Loading Cross-Case Fraud Network & Common Infrastructure...
      </div>
    );
  }

  const nodes = graph?.nodes || [];
  const edges = graph?.edges || [];
  const clusters = graph?.associated_clusters || [];

  return (
    <div className="space-y-6">
      {/* Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-slate-900/80 border border-slate-800 rounded-lg p-4">
          <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Connected Cases</div>
          <div className="text-2xl font-bold text-cyan-400 mt-1">{graph?.connected_case_count ?? 1}</div>
          <div className="text-xs text-slate-500 mt-1">Cross-case investigative ties</div>
        </div>
        <div className="bg-slate-900/80 border border-slate-800 rounded-lg p-4">
          <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Total Victims</div>
          <div className="text-2xl font-bold text-emerald-400 mt-1">{graph?.total_victim_count ?? 0}</div>
          <div className="text-xs text-slate-500 mt-1">Impacted victims across linked cases</div>
        </div>
        <div className="bg-slate-900/80 border border-slate-800 rounded-lg p-4">
          <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Aggregate Exposure</div>
          <div className="text-2xl font-bold text-amber-400 mt-1">
            ${(graph?.aggregate_exposure_usd ?? 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}
          </div>
          <div className="text-xs text-slate-500 mt-1">
            (₹{((graph?.aggregate_exposure_usd ?? 0) * 0.0083).toFixed(1)} Lakh approx)
          </div>
        </div>
        <div className="bg-slate-900/80 border border-slate-800 rounded-lg p-4">
          <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Associated Clusters</div>
          <div className="text-2xl font-bold text-purple-400 mt-1">{clusters.length}</div>
          <div className="text-xs text-slate-500 mt-1">Linked infrastructure candidates</div>
        </div>
      </div>

      {/* Main Grid: Network Graph & Node Inspector */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Network Graph Visualizer */}
        <div className="lg:col-span-2 bg-slate-900/80 border border-slate-800 rounded-lg p-5">
          <div className="flex justify-between items-center mb-4">
            <div>
              <h3 className="text-base font-semibold text-slate-100 flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-cyan-500 inline-block" />
                Fraud Network Graph
              </h3>
              <p className="text-xs text-slate-400">
                Visualizing transaction flows & investigative correlations across cases
              </p>
            </div>
            <div className="flex items-center gap-4 text-xs">
              <span className="flex items-center gap-1.5 text-cyan-300">
                <span className="w-3 h-0.5 bg-cyan-400 inline-block" /> Transaction Flow
              </span>
              <span className="flex items-center gap-1.5 text-amber-300">
                <span className="w-3 h-0.5 border-b border-dashed border-amber-400 inline-block" /> Investigative Link
              </span>
            </div>
          </div>

          {/* Graphical Map Representation */}
          <div className="relative min-h-[360px] bg-slate-950/60 border border-slate-800/80 rounded-lg p-4 flex flex-col justify-between">
            {nodes.length === 0 ? (
              <div className="text-center my-auto text-slate-500 py-12">
                No cross-case infrastructure network observed for this case.
              </div>
            ) : (
              <div className="space-y-4">
                {/* Visual Legend & Nodes Grid */}
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
                  {nodes.map((node) => {
                    const isSelected = selectedNode?.id === node.id;
                    let typeBadgeClass = 'bg-slate-800 text-slate-300 border-slate-700';
                    if (node.node_type === 'VICTIM') typeBadgeClass = 'bg-emerald-950/60 text-emerald-300 border-emerald-800/80';
                    if (node.node_type === 'CASE') typeBadgeClass = 'bg-cyan-950/60 text-cyan-300 border-cyan-800/80';
                    if (node.node_type === 'WALLET') typeBadgeClass = 'bg-blue-950/60 text-blue-300 border-blue-800/80';
                    if (node.node_type === 'VASP') typeBadgeClass = 'bg-purple-950/60 text-purple-300 border-purple-800/80';
                    if (node.node_type === 'BRIDGE') typeBadgeClass = 'bg-amber-950/60 text-amber-300 border-amber-800/80';
                    if (node.node_type === 'MIXER') typeBadgeClass = 'bg-rose-950/60 text-rose-300 border-rose-800/80';

                    return (
                      <button
                        key={node.id}
                        onClick={() => setSelectedNode(node)}
                        className={`text-left p-3 rounded-lg border transition-all ${
                          isSelected
                            ? 'ring-2 ring-cyan-400 bg-slate-800/90 border-cyan-500 shadow-lg'
                            : `${typeBadgeClass} hover:bg-slate-800/50`
                        }`}
                      >
                        <div className="flex justify-between items-start">
                          <span className="text-[10px] uppercase font-bold tracking-wider px-1.5 py-0.5 rounded bg-slate-900/60">
                            {node.node_type}
                          </span>
                          {node.case_ids.length > 1 && (
                            <span className="text-[10px] bg-amber-500/20 text-amber-300 px-1.5 py-0.5 rounded font-mono">
                              {node.case_ids.length} cases
                            </span>
                          )}
                        </div>
                        <div className="font-mono text-xs truncate mt-2 font-medium text-slate-200" title={node.label}>
                          {node.label}
                        </div>
                        {node.exposure_usd > 0 && (
                          <div className="text-[11px] font-semibold text-slate-400 mt-1">
                            ${node.exposure_usd.toLocaleString()}
                          </div>
                        )}
                      </button>
                    );
                  })}
                </div>

                {/* Relationships Edge List */}
                <div className="mt-6 border-t border-slate-800/80 pt-4">
                  <div className="text-xs font-semibold text-slate-400 mb-2 uppercase tracking-wider">
                    Discovered Graph Relationships ({edges.length})
                  </div>
                  <div className="max-h-48 overflow-y-auto space-y-2 pr-1">
                    {edges.map((edge) => {
                      const isTx = edge.relationship_kind === 'TRANSACTION_RELATIONSHIP';
                      return (
                        <div
                          key={edge.edge_id}
                          className="flex items-center justify-between bg-slate-900/50 p-2.5 rounded border border-slate-800/60 text-xs"
                        >
                          <div className="flex items-center gap-2 font-mono text-slate-300 truncate max-w-[60%]">
                            <span className="truncate">{edge.source.slice(0, 14)}...</span>
                            <span className={isTx ? 'text-cyan-400' : 'text-amber-400 font-bold'}>
                              {isTx ? '──►' : '┄┄►'}
                            </span>
                            <span className="truncate">{edge.target.slice(0, 14)}...</span>
                          </div>
                          <div className="flex items-center gap-3">
                            <span
                              className={`text-[10px] font-semibold px-2 py-0.5 rounded ${
                                isTx
                                  ? 'bg-cyan-950/60 text-cyan-300 border border-cyan-800/60'
                                  : 'bg-amber-950/60 text-amber-300 border border-amber-800/60'
                              }`}
                            >
                              {edge.relationship_type}
                            </span>
                            <span className="text-[11px] text-slate-400 font-mono">
                              {(edge.confidence * 100).toFixed(0)}% conf
                            </span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Selected Node Details */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-lg p-5 flex flex-col justify-between">
          <div>
            <h3 className="text-base font-semibold text-slate-100 mb-1">Infrastructure Node Details</h3>
            <p className="text-xs text-slate-400 mb-4">Investigative metrics & cluster associations</p>

            {selectedNode ? (
              <div className="space-y-4 text-xs">
                <div className="bg-slate-950/80 p-3 rounded border border-slate-800">
                  <div className="text-[10px] font-semibold text-slate-400 uppercase">Node Identifier</div>
                  <div className="font-mono text-cyan-300 font-medium break-all mt-0.5">{selectedNode.id}</div>
                  <div className="mt-2 flex items-center justify-between text-slate-400">
                    <span>Type: <strong className="text-slate-200">{selectedNode.node_type}</strong></span>
                    {selectedNode.chain && <span>Chain: <strong className="text-slate-200 uppercase">{selectedNode.chain}</strong></span>}
                  </div>
                </div>

                <div className="bg-slate-950/80 p-3 rounded border border-slate-800 space-y-2">
                  <div className="flex justify-between">
                    <span className="text-slate-400">Connected Cases:</span>
                    <span className="font-bold text-cyan-400">{selectedNode.case_ids.length}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Aggregate Exposure:</span>
                    <span className="font-bold text-emerald-400">${selectedNode.exposure_usd.toLocaleString()}</span>
                  </div>
                  {selectedNode.cluster_association && (
                    <div className="flex justify-between">
                      <span className="text-slate-400">Associated Cluster:</span>
                      <span className="font-mono text-purple-300">{selectedNode.cluster_association}</span>
                    </div>
                  )}
                </div>

                <div>
                  <div className="text-[11px] font-semibold text-slate-400 mb-1.5">Linked Cases ({selectedNode.case_ids.length})</div>
                  <div className="space-y-1 max-h-32 overflow-y-auto">
                    {selectedNode.case_ids.map((cid) => (
                      <div
                        key={cid}
                        className="flex justify-between items-center p-2 rounded bg-slate-950/40 border border-slate-800/40 hover:border-slate-700 cursor-pointer"
                        onClick={() => onNavigateCase?.(cid)}
                      >
                        <span className="font-mono text-cyan-400 font-medium">{cid}</span>
                        {cid === caseId && (
                          <span className="text-[9px] bg-cyan-900/60 text-cyan-300 px-1.5 py-0.5 rounded">Current</span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-slate-500 text-center py-12">Select a node from the network graph to inspect.</div>
            )}
          </div>

          <div className="mt-6 pt-4 border-t border-slate-800">
            <div className="text-[10px] text-slate-400 italic">
              * Note: Cluster detection uses graph heuristics. Terminology strictly identifies relationship candidates and linked infrastructure candidates.
            </div>
          </div>
        </div>
      </div>

      {/* Common Infrastructure & Multi-victim Aggregation Section */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-lg p-5">
        <h3 className="text-base font-semibold text-slate-100 mb-1">Multi-Victim Infrastructure Exposure</h3>
        <p className="text-xs text-slate-400 mb-4">
          Shared wallet addresses, intermediaries, VASP destinations, mixers, and bridges with aggregated victim losses
        </p>

        {sharedNodes.length === 0 ? (
          <div className="text-center py-8 text-slate-500 bg-slate-950/40 border border-slate-800/60 rounded-lg text-xs">
            No multi-case common infrastructure nodes detected for this investigation.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-slate-800 bg-slate-950/60 text-slate-400 uppercase text-[10px] tracking-wider">
                  <th className="p-3">Infrastructure Node</th>
                  <th className="p-3">Type</th>
                  <th className="p-3">Connected Cases</th>
                  <th className="p-3">Victims</th>
                  <th className="p-3">Aggregate Funds</th>
                  <th className="p-3">First Observed</th>
                  <th className="p-3">Last Observed</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-mono text-slate-300">
                {sharedNodes.map((node) => (
                  <tr key={node.node_id} className="hover:bg-slate-800/40">
                    <td className="p-3 font-semibold text-cyan-300 break-all">{node.node_id}</td>
                    <td className="p-3">
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-slate-300 border border-slate-700 uppercase">
                        {node.node_type}
                      </span>
                    </td>
                    <td className="p-3 text-cyan-400 font-bold">{node.connected_case_ids.length} cases</td>
                    <td className="p-3 text-emerald-400 font-bold">{node.victim_count} victims</td>
                    <td className="p-3 text-amber-400 font-bold">
                      ${node.aggregate_exposure_usd.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                    </td>
                    <td className="p-3 text-slate-400">
                      {node.first_observed ? new Date(node.first_observed).toLocaleDateString() : 'N/A'}
                    </td>
                    <td className="p-3 text-slate-400">
                      {node.last_observed ? new Date(node.last_observed).toLocaleDateString() : 'N/A'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Case Relationship Evaluator */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-lg p-5">
        <h3 className="text-base font-semibold text-slate-100 mb-1">Case Relationship Evaluator</h3>
        <p className="text-xs text-slate-400 mb-4">
          Directly correlate Case {caseId} with another investigation case to calculate relationship type & evidence
        </p>

        <form onSubmit={handleCorrelate} className="flex flex-col sm:flex-row gap-3 mb-4">
          <input
            type="text"
            placeholder="Enter target Case ID (e.g. case-b-2222)"
            value={compareCaseId}
            onChange={(e) => setCompareCaseId(e.target.value)}
            className="flex-1 bg-slate-950 border border-slate-800 rounded px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-cyan-500 font-mono"
          />
          <button
            type="submit"
            disabled={correlating || !compareCaseId.trim()}
            className="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-white rounded text-xs font-semibold disabled:opacity-50 transition-colors"
          >
            {correlating ? 'Correlating...' : 'Evaluate Relationship'}
          </button>
        </form>

        {error && <div className="p-3 bg-rose-950/60 border border-rose-800 text-rose-300 rounded text-xs mb-4">{error}</div>}

        {correlationResults && (
          <div className="space-y-3">
            <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
              Correlation Results ({correlationResults.length} matches)
            </h4>
            {correlationResults.length === 0 ? (
              <div className="p-3 bg-slate-950/50 rounded border border-slate-800 text-slate-400 text-xs">
                No shared infrastructure, temporal correlation, or flow pattern overlap found between these two cases.
              </div>
            ) : (
              <div className="space-y-2">
                {correlationResults.map((score, idx) => (
                  <div key={idx} className="p-3 bg-slate-950/80 rounded border border-slate-800 text-xs space-y-2">
                    <div className="flex justify-between items-center">
                      <span className="font-bold text-cyan-400 uppercase tracking-wider">{score.relationship_type}</span>
                      <span className="px-2 py-0.5 rounded bg-emerald-950 text-emerald-300 font-mono font-bold">
                        Score: {(score.relationship_score * 100).toFixed(0)}/100
                      </span>
                    </div>
                    <div className="text-slate-300">
                      <strong>Supporting Evidence:</strong>
                      <ul className="list-disc list-inside text-slate-400 mt-1 space-y-0.5">
                        {score.supporting_evidence.map((ev, i) => (
                          <li key={i}>{ev}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
