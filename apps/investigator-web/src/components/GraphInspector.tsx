import React, { useEffect, useMemo, useState, useRef } from 'react';
import type { Edge, Node, PrimaryPath, RiskAssessment, Trace } from '../types';
import { api } from '../api';

const short = (value: string) => value && value.length > 18 ? `${value.slice(0, 8)}…${value.slice(-6)}` : value;
const nodeKey = (node: Node) => node.id || node.address;
const chainKey = (chain: string | undefined) => chain || 'ethereum';
const identity = (chain: string | undefined, address: string) => `${chainKey(chain)}:${chainKey(chain) === 'ethereum' ? address.toLowerCase() : address}`;

type Point = { x: number; y: number };

function layout(nodes: Node[], edges: Edge[], root: string) {
  const rootKey = identity(nodes.find(node => node.address.toLowerCase() === root.toLowerCase())?.chain, root);
  const adjacency = new Map<string, string[]>();
  for (const edge of edges) {
    const source = identity(edge.transfer.chain, edge.source);
    const target = identity(edge.transfer.chain, edge.target);
    adjacency.set(source, [...(adjacency.get(source) || []), target]);
  }
  const depth = new Map<string, number>([[rootKey, 0]]);
  const queue = [rootKey];
  while (queue.length) {
    const current = queue.shift()!;
    for (const next of adjacency.get(current) || []) {
      if (!depth.has(next)) {
        depth.set(next, (depth.get(current) || 0) + 1);
        queue.push(next);
      }
    }
  }
  const groups = new Map<number, Node[]>();
  for (const node of nodes) {
    const level = depth.get(identity(node.chain, node.address)) ?? 0;
    const group = groups.get(level) || [];
    group.push(node);
    groups.set(level, group);
  }
  const positions = new Map<string, Point>();
  const maxLevel = Math.max(...Array.from(groups.keys()), 0);
  const height = Math.max(560, Math.max(...Array.from(groups.values()).map(group => group.length), 1) * 120);
  for (const [level, group] of groups) {
    const x = 120 + (level / Math.max(maxLevel, 1)) * 760;
    group.forEach((node, index) => {
      positions.set(identity(node.chain, node.address), {
        x,
        y: 72 + (index + 1) * (height - 120) / (group.length + 1),
      });
    });
  }
  return positions;
}

export function GraphInspector({ trace, selectedTx }: { trace: Trace; selectedTx?: string }) {
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<Edge | null>(null);
  const [scale, setScale] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [asset, setAsset] = useState('ALL');
  const [risk, setRisk] = useState<RiskAssessment | null>(null);
  const [primaryPath, setPrimaryPath] = useState<PrimaryPath | null>(null);
  
  // Custom coordinates for draggable nodes
  const [customPositions, setCustomPositions] = useState<Record<string, Point>>({});
  const [draggingNode, setDraggingNode] = useState<{ id: string; startX: number; startY: number } | null>(null);
  const [isPanning, setIsPanning] = useState(false);
  const panStart = useRef({ x: 0, y: 0 });
  
  // Collapse/expand sub-graphs state
  const [collapsedNodes, setCollapsedNodes] = useState<Set<string>>(new Set());

  useEffect(() => {
    api.risk(trace.case_id).then(setRisk).catch(() => setRisk(null));
    api.primaryPath(trace.case_id).then(setPrimaryPath).catch(() => setPrimaryPath(null));
    // Load persisted layout if available
    api.graphLayout(trace.case_id).then(layoutData => {
      if (layoutData && layoutData.node_positions) {
        const positions: Record<string, Point> = {};
        Object.entries(layoutData.node_positions).forEach(([key, val]) => {
          if (val && typeof val.x === 'number' && typeof val.y === 'number') {
            positions[key] = { x: val.x, y: val.y };
          }
        });
        setCustomPositions(positions);
        if (layoutData.viewport) {
          if (typeof layoutData.viewport.scale === 'number') setScale(layoutData.viewport.scale);
          if (typeof layoutData.viewport.panX === 'number' && typeof layoutData.viewport.panY === 'number') {
            setPan({ x: layoutData.viewport.panX, y: layoutData.viewport.panY });
          }
        }
      }
    }).catch(() => {});
  }, [trace.case_id, trace.trace_id]);

  useEffect(() => {
    if (!selectedTx) return;
    const match = trace.edges.find(edge => edge.transaction_hash.toLowerCase() === selectedTx.toLowerCase());
    if (match) {
      setSelectedEdge(match);
      setSelectedNode(null);
    }
  }, [selectedTx, trace.edges]);

  const assets = useMemo(() => {
    return Array.from(new Set(trace.edges.map(item => item.transfer.asset).filter(Boolean))).sort();
  }, [trace.edges]);

  // Compute visibility based on collapse status
  const visibleFlow = useMemo(() => {
    const normalizedCollapsed = new Set(Array.from(collapsedNodes).map(addr => addr.toLowerCase()));
    const visited = new Set<string>([trace.root_address.toLowerCase()]);
    const queue = [trace.root_address.toLowerCase()];
    const outgoing = new Map<string, Edge[]>();
    
    trace.edges.forEach(edge => {
      const src = edge.source.toLowerCase();
      outgoing.set(src, [...(outgoing.get(src) || []), edge]);
    });

    while (queue.length) {
      const current = queue.shift()!;
      if (normalizedCollapsed.has(current)) continue;
      for (const edge of outgoing.get(current) || []) {
        const targetLower = edge.target.toLowerCase();
        if (!visited.has(targetLower)) {
          visited.add(targetLower);
          queue.push(targetLower);
        }
      }
    }

    const filteredNodes = trace.nodes.filter(n => visited.has(n.address.toLowerCase()));
    const filteredEdges = trace.edges.filter(e => visited.has(e.source.toLowerCase()) && visited.has(e.target.toLowerCase()));
    return { nodes: filteredNodes, edges: filteredEdges };
  }, [trace.nodes, trace.edges, trace.root_address, collapsedNodes]);

  const visibleEdges = useMemo(() => {
    return asset === 'ALL' ? visibleFlow.edges : visibleFlow.edges.filter(item => item.transfer.asset === asset);
  }, [asset, visibleFlow.edges]);

  const visibleAddresses = new Set(visibleEdges.flatMap(item => [identity(item.transfer.chain, item.source), identity(item.transfer.chain, item.target)]));
  const visibleNodes = visibleFlow.nodes.filter(item => visibleAddresses.has(identity(item.chain, item.address)) || item.address.toLowerCase() === trace.root_address.toLowerCase());

  const defaultPositions = useMemo(() => {
    return layout(visibleNodes, visibleEdges, trace.root_address);
  }, [visibleNodes, visibleEdges, trace.root_address]);

  const point = (address: string, chain?: string) => {
    const key = identity(chain, address);
    return customPositions[key] || defaultPositions.get(key) || { x: 0, y: 0 };
  };

  const riskTransactions = new Set(risk?.factors.flatMap(item => item.transaction_hashes) || []);
  const primaryTransactions = new Set(primaryPath?.transaction_hashes || []);
  const primaryNodes = new Set((primaryPath?.node_ids || []).map(address => address.toLowerCase()));
  const edgeFactors = (item: Edge) => risk?.factors.filter(factor => factor.transaction_hashes.includes(item.transaction_hash)) || [];
  const nodeFactors = (item: Node) => risk?.factors.filter(factor => factor.transaction_hashes.some(tx => trace.edges.some(itemEdge => itemEdge.transaction_hash === tx && (itemEdge.source === item.address || itemEdge.target === item.address)))) || [];

  const handleMouseDownSvg = (e: React.MouseEvent<SVGSVGElement>) => {
    if ((e.target as SVGElement).tagName === 'svg' || (e.target as SVGElement).className === 'graph-grid-lines') {
      setIsPanning(true);
      panStart.current = { x: e.clientX - pan.x, y: e.clientY - pan.y };
    }
  };

  const handleMouseMoveSvg = (e: React.MouseEvent<SVGSVGElement>) => {
    if (isPanning) {
      setPan({
        x: e.clientX - panStart.current.x,
        y: e.clientY - panStart.current.y,
      });
    } else if (draggingNode) {
      const svg = e.currentTarget;
      const rect = svg.getBoundingClientRect();
      // Translate mouse coordinates to SVG coordinate system
      const x = ((e.clientX - rect.left) - pan.x) / scale;
      const y = ((e.clientY - rect.top) - pan.y) / scale;
      setCustomPositions(prev => ({
        ...prev,
        [draggingNode.id]: { x, y }
      }));
    }
  };

  const handleMouseUpSvg = () => {
    setIsPanning(false);
    setDraggingNode(null);
  };

  const saveLayout = async () => {
    try {
      const positionsToSend: Record<string, { x: number; y: number }> = {};
      Object.entries(customPositions).forEach(([key, pt]) => {
        positionsToSend[key] = { x: pt.x, y: pt.y };
      });
      await api.saveGraphLayout(trace.case_id, {
        node_positions: positionsToSend,
        viewport: { scale, panX: pan.x, panY: pan.y }
      });
      alert('Graph layout saved successfully.');
    } catch (err) {
      alert('Failed to save layout: ' + (err instanceof Error ? err.message : String(err)));
    }
  };

  const resetLayout = () => {
    setCustomPositions({});
    setScale(1);
    setPan({ x: 0, y: 0 });
    setCollapsedNodes(new Set());
  };

  const centerOnRoot = () => {
    const rootPos = point(trace.root_address);
    setPan({
      x: 500 - rootPos.x * scale,
      y: 250 - rootPos.y * scale
    });
  };

  const fitToGraph = () => {
    if (visibleNodes.length === 0) return;
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    visibleNodes.forEach(node => {
      const p = point(node.address, node.chain);
      if (p.x < minX) minX = p.x;
      if (p.x > maxX) maxX = p.x;
      if (p.y < minY) minY = p.y;
      if (p.y > maxY) maxY = p.y;
    });
    const padding = 80;
    const graphW = Math.max(maxX - minX, 100);
    const graphH = Math.max(maxY - minY, 100);
    const scaleX = (1000 - padding * 2) / graphW;
    const scaleY = (500 - padding * 2) / graphH;
    const newScale = Math.max(0.3, Math.min(scaleX, scaleY, 1.5));
    const centerX = (minX + maxX) / 2;
    const centerY = (minY + maxY) / 2;
    setPan({
      x: 500 - centerX * newScale,
      y: 250 - centerY * newScale
    });
    setScale(newScale);
  };

  const initialFitRef = useRef<string | null>(null);
  useEffect(() => {
    if (visibleNodes.length > 0 && initialFitRef.current !== trace.trace_id) {
      initialFitRef.current = trace.trace_id;
      setTimeout(fitToGraph, 100);
    }
  }, [trace.trace_id, visibleNodes.length]);

  const toggleCollapse = (address: string) => {
    setCollapsedNodes(prev => {
      const next = new Set(prev);
      if (next.has(address)) {
        next.delete(address);
      } else {
        next.add(address);
      }
      return next;
    });
  };

  return (
    <div className="graph-workspace">
      <div className="graph-commandbar">
        <div className="graph-command-title">
          <span className="eyebrow">TRANSACTION GRAPH / OBSERVED FLOW</span>
          <strong>{trace.direction === 'backward' ? 'Inbound funding trace' : 'Outbound fund-flow trace'}</strong>
          <span className="graph-source">{trace.provider} · {trace.mode} · {trace.status}</span>
        </div>
        <div className="graph-command-actions">
          <button className="secondary" onClick={centerOnRoot}>CENTER ON ROOT</button>
          <button className="secondary" onClick={saveLayout}>SAVE LAYOUT</button>
          <button className="secondary" onClick={resetLayout}>RESET LAYOUT</button>
          <span className={`data-badge ${trace.status === 'PARTIAL' ? 'warning' : ''}`}>{trace.status === 'PARTIAL' ? 'PARTIAL TRACE' : 'OBSERVED DATA'}</span>
          <button className="icon-action" aria-label="Zoom out" onClick={() => setScale(Math.max(0.3, scale - 0.1))}>−</button>
          <button className="fit-action" onClick={fitToGraph}>FIT TO SCREEN</button>
          <button className="icon-action" aria-label="Zoom in" onClick={() => setScale(Math.min(3.0, scale + 0.1))}>+</button>
        </div>
      </div>
      
      <div className="graph-filterbar">
        <label>
          ASSET
          <select value={asset} onChange={event => setAsset(event.target.value)}>
            <option value="ALL">ALL ASSETS</option>
            {assets.map(item => <option key={item} value={item}>{item}</option>)}
          </select>
        </label>
        <span className="filter-readout">{visibleNodes.length} nodes · {visibleEdges.length} edges · {trace.metrics.unique_transaction_count} transactions</span>
        <span className="filter-readout">MAX HOP <b>{trace.metrics.maximum_hop}</b></span>
        <button className="secondary" onClick={() => { setAsset('ALL'); setScale(1); setPan({ x: 0, y: 0 }); setSelectedNode(null); setSelectedEdge(null); }}>RESET VIEW</button>
      </div>

      <div className="graph-main-grid">
        <section className="graph-surface" aria-label="Observed blockchain transaction graph">
          <div className="graph-surface-header">
            <div>
              <b>OBSERVED BLOCKCHAIN FLOW</b>
              <small>Drag nodes to organize. Double-click node to collapse/expand its branch.</small>
            </div>
            <span className="graph-legend-inline">
              <i className="legend-root" />ROOT 
              <i className="legend-wallet" />WALLET 
              <i className="legend-risk" />RISK-LINKED
              <i className="legend-collapsed" style={{ background: '#7c3aed', borderRadius: '50%', width: 8, height: 8, display: 'inline-block', marginLeft: 8, marginRight: 4 }} />COLLAPSED
            </span>
          </div>

          {visibleEdges.length === 0 ? (
            <div className="graph-empty">
              <span>⌁</span>
              <b>No graph observations match this filter</b>
              <p>Change the asset filter or run a bounded trace with persisted blockchain observations.</p>
            </div>
          ) : (
            <div className="graph-viewport" style={{ overflow: 'hidden', position: 'relative', background: '#0a0d14' }}>
              <svg 
                viewBox="0 0 1000 500" 
                role="img" 
                aria-label="Directed graph of observed blockchain transfers" 
                onMouseDown={handleMouseDownSvg}
                onMouseMove={handleMouseMoveSvg}
                onMouseUp={handleMouseUpSvg}
                onMouseLeave={handleMouseUpSvg}
                style={{ cursor: isPanning ? 'grabbing' : 'grab', width: '100%', height: '100%' }}
              >
                <defs>
                  <marker id="graph-arrow" markerWidth="7" markerHeight="7" refX="24" refY="3.5" orient="auto">
                    <path d="M0,0 L7,3.5 L0,7 Z" fill="#4b5563" />
                  </marker>
                </defs>
                
                <g className="graph-grid-lines" stroke="#1f2937" strokeWidth="0.5">
                  {Array.from({ length: 6 }, (_, index) => <line key={`h-${index}`} x1="0" y1={index * 100} x2="1000" y2={index * 100} />)}
                  {Array.from({ length: 11 }, (_, index) => <line key={`v-${index}`} x1={index * 100} y1="0" x2={index * 100} y2="500" />)}
                </g>

                <g transform={`translate(${pan.x}, ${pan.y}) scale(${scale})`}>
                  {/* Render Edges */}
                  {visibleEdges.map(item => {
                    const source = point(item.source, item.transfer.chain);
                    const target = point(item.target, item.transfer.chain);
                    const bearing = riskTransactions.has(item.transaction_hash);
                    const isPrimary = primaryTransactions.has(item.transaction_hash);
                    const selected = selectedEdge?.edge_id === item.edge_id;
                    const token = item.transfer.transfer_type !== 'native';
                    return (
                      <g 
                        key={item.edge_id} 
                        className={`graph-edge ${bearing ? 'risk-bearing' : ''} ${token ? 'token-edge' : ''} ${selected ? 'selected' : ''} ${isPrimary ? 'primary-path-edge' : ''}`}
                        role="button" 
                        tabIndex={0} 
                        aria-label={`Inspect transfer ${short(item.transaction_hash)}`} 
                        onClick={() => { setSelectedEdge(item); setSelectedNode(null); }}
                      >
                        <line x1={source.x} y1={source.y} x2={target.x} y2={target.y} markerEnd="url(#graph-arrow)" stroke={isPrimary ? '#4de1c1' : selected ? '#3b82f6' : bearing ? '#ef4444' : '#4b5563'} strokeWidth={isPrimary ? 5 : selected ? 3 : 1.5} opacity={isPrimary ? 1 : 0.45} />
                        <rect x={(source.x + target.x) / 2 - 40} y={(source.y + target.y) / 2 - 10} width="80" height="20" rx="3" fill="#111827" stroke="#374151" strokeWidth="1" />
                        <text x={(source.x + target.x) / 2} y={(source.y + target.y) / 2 + 4} textAnchor="middle" fill={isPrimary ? '#b8fff0' : '#9ca3af'} fontSize="10">{isPrimary ? `H${item.hop} ` : ''}{short(item.transfer.amount)} {item.transfer.asset}</text>
                      </g>
                    );
                  })}

                  {/* Render Nodes */}
                  {visibleNodes.map(item => {
                    const position = point(item.address, item.chain);
                    const isRoot = item.address.toLowerCase() === trace.root_address.toLowerCase();
                    const isContract = item.node_type === 'CONTRACT';
                    const isPrimaryNode = primaryNodes.has(item.address.toLowerCase());
                    const isTerminal = primaryPath?.status === 'ATTRIBUTED' && primaryPath.terminal_address?.toLowerCase() === item.address.toLowerCase();
                    const nodeRisk = nodeFactors(item).length > 0;
                    const selected = selectedNode ? identity(selectedNode.chain, selectedNode.address) === identity(item.chain, item.address) : false;
                    const isCollapsed = collapsedNodes.has(item.address);
                    
                    return (
                      <g 
                        key={nodeKey(item)} 
                        className={`graph-node ${isRoot ? 'root' : ''} ${isContract ? 'contract' : ''} ${nodeRisk ? 'risk-node' : ''} ${selected ? 'selected' : ''} ${isPrimaryNode ? 'primary-path-node' : ''} ${isTerminal ? 'primary-terminal-node' : ''}`}
                        role="button" 
                        tabIndex={0} 
                        transform={`translate(${position.x} ${position.y})`}
                        style={{ cursor: 'move' }}
                        onMouseDown={(e) => {
                          e.stopPropagation();
                          setDraggingNode({ id: identity(item.chain, item.address), startX: e.clientX, startY: e.clientY });
                        }}
                        onDoubleClick={(e) => {
                          e.stopPropagation();
                          toggleCollapse(item.address);
                        }}
                        onClick={() => { setSelectedNode(item); setSelectedEdge(null); }}
                      >
                        <circle r={isRoot ? 32 : 26} fill={isRoot ? '#1e3a8a' : isCollapsed ? '#5b21b6' : isContract ? '#065f46' : '#1f2937'} stroke={selected ? '#3b82f6' : nodeRisk ? '#ef4444' : '#4b5563'} strokeWidth="2" />
                        <circle className="node-core" r={isRoot ? 24 : 18} fill="#0f172a" />
                        <text className="node-type" textAnchor="middle" y="4" fill="#e5e7eb" fontSize="8" fontWeight="bold">{isRoot ? 'ROOT' : isTerminal ? primaryPath?.terminal_entity_type : isContract ? 'CONTRACT' : 'WALLET'}</text>
                        <text className="node-label" textAnchor="middle" y="44" fill="#f3f4f6" fontSize="10" fontWeight="500">{isTerminal ? primaryPath?.terminal_entity_name : short(item.address)}</text>
                      </g>
                    );
                  })}
                </g>
              </svg>
            </div>
          )}
          <div className="graph-surface-footer">
            <span><i className="legend-root" />Root</span>
            <span><i className="legend-wallet" />Wallet</span>
            <span><i className="legend-contract" />Contract</span>
            <span><i className="legend-risk" />Risk linked</span>
            <span className="footer-note">Double-click a node to toggle branch visibility. Drag to move.</span>
          </div>
        </section>
        
        <aside className="graph-inspector-panel" aria-live="polite">
          {selectedNode ? (
            <NodeIntelligencePanel node={selectedNode} trace={trace} factors={nodeFactors(selectedNode)} onCollapse={toggleCollapse} isCollapsed={collapsedNodes.has(selectedNode.address)} />
          ) : selectedEdge ? (
            <TransactionIntelligencePanel edge={selectedEdge} factors={edgeFactors(selectedEdge)} />
          ) : (
            <EmptyInspector trace={trace} risk={risk} />
          )}
        </aside>
      </div>
      
      <div className="graph-metrics">
        <Metric label="NODES" value={trace.metrics.node_count} />
        <Metric label="EDGES" value={trace.metrics.edge_count} />
        <Metric label="TRANSACTIONS" value={trace.metrics.unique_transaction_count} />
        <Metric label="ASSETS" value={trace.metrics.unique_asset_count || 1} />
        <Metric label="PATHS" value={trace.metrics.path_count} />
        <Metric label="MAX HOP" value={trace.metrics.maximum_hop} />
      </div>
      <GraphAnalysisRail trace={trace} edges={visibleEdges} primaryPath={primaryPath} />
    </div>
  );
}

function NodeIntelligencePanel({ node, trace, factors, onCollapse, isCollapsed }: { node: Node; trace: Trace; factors: RiskAssessment['factors']; onCollapse: (addr: string) => void; isCollapsed: boolean }) {
  const [copied, setCopied] = useState(false);
  const [attributions, setAttributions] = useState<any>(null);

  useEffect(() => {
    api.attribution(node.chain || 'ethereum', node.address)
      .then(setAttributions)
      .catch(() => setAttributions(null));
  }, [node.address, node.chain]);

  const copyAddress = () => {
    navigator.clipboard?.writeText(node.address);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const volumeStats = useMemo(() => {
    const inboundEdges = trace.edges.filter(e => e.target.toLowerCase() === node.address.toLowerCase());
    const outboundEdges = trace.edges.filter(e => e.source.toLowerCase() === node.address.toLowerCase());
    const inboundVol = inboundEdges.reduce((sum, e) => sum + parseFloat(e.transfer.amount || '0'), 0);
    const outboundVol = outboundEdges.reduce((sum, e) => sum + parseFloat(e.transfer.amount || '0'), 0);
    return {
      inboundCount: inboundEdges.length,
      outboundCount: outboundEdges.length,
      inboundVol,
      outboundVol,
      inboundCounterparties: new Set(inboundEdges.map(e => e.source.toLowerCase())).size,
      outboundCounterparties: new Set(outboundEdges.map(e => e.target.toLowerCase())).size
    };
  }, [trace.edges, node.address]);

  const explorerUrl = node.chain === 'tron' 
    ? `https://tronscan.org/#/address/${node.address}` 
    : `https://etherscan.io/address/${node.address}`;

  return (
    <div className="intelligence-panel">
      <InspectorHeading eyebrow="NODE INTELLIGENCE" title={short(node.address)} badge={node.node_type || 'WALLET'} />
      
      <div className="panel-address-copy">
        <code className="address-display">{node.address}</code>
        <div className="panel-copy-actions">
          <button className="secondary btn-xs" onClick={copyAddress}>{copied ? 'Copied ✓' : 'Copy'}</button>
          <a className="button secondary btn-xs" href={explorerUrl} target="_blank" rel="noopener noreferrer">Explorer ↗</a>
        </div>
      </div>

      <dl className="inspector-list">
        <dt>NETWORK/CHAIN</dt>
        <dd>{(node.chain || 'ethereum').toUpperCase()}</dd>
        
        <dt>TYPE</dt>
        <dd>{node.node_type || 'WALLET'}</dd>

        <dt>VOLUME & FLOW</dt>
        <dd className="stats-box">
          <div>Inbound: {volumeStats.inboundVol.toFixed(4)} ({volumeStats.inboundCount} txs, {volumeStats.inboundCounterparties} counterp.)</div>
          <div>Outbound: {volumeStats.outboundVol.toFixed(4)} ({volumeStats.outboundCount} txs, {volumeStats.outboundCounterparties} counterp.)</div>
        </dd>

        <dt>RISK CONTRIBUTION</dt>
        <dd>
          {factors.length > 0 ? (
            factors.map(item => (
              <span className="factor-chip risk-high" key={item.factor_id}>
                {item.name} (+{item.contribution})
              </span>
            ))
          ) : (
            <span className="factor-chip risk-low">No direct risk factors</span>
          )}
        </dd>

        <dt>ATTRIBUTION / VASP</dt>
        <dd>
          {attributions && attributions.candidates && attributions.candidates.length > 0 ? (
            attributions.candidates.map((cand: any, idx: number) => (
              <div key={idx} className="attribution-row">
                <strong>{cand.entity?.name}</strong>
                <span>{cand.entity?.entity_type} ({cand.confidence} confidence)</span>
              </div>
            ))
          ) : (
            <span className="attribution-none">No matched entities</span>
          )}
        </dd>
      </dl>

      <div className="panel-actions" style={{ marginTop: 15 }}>
        <button className="primary wide-action" onClick={() => onCollapse(node.address)}>
          {isCollapsed ? 'Expand downstream branch' : 'Collapse downstream branch'}
        </button>
      </div>
    </div>
  );
}

function TransactionIntelligencePanel({ edge, factors }: { edge: Edge; factors: RiskAssessment['factors'] }) {
  const [copied, setCopied] = useState(false);
  
  const copyTxHash = () => {
    navigator.clipboard?.writeText(edge.transaction_hash);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const explorerUrl = edge.transfer.chain === 'tron'
    ? `https://tronscan.org/#/transaction/${edge.transaction_hash}`
    : `https://etherscan.io/tx/${edge.transaction_hash}`;

  return (
    <div className="intelligence-panel">
      <InspectorHeading eyebrow="TRANSACTION INTELLIGENCE" title={`${edge.transfer.amount} ${edge.transfer.asset}`} badge="FLOW EDGE" />
      
      <div className="panel-address-copy">
        <code className="address-display">{edge.transaction_hash}</code>
        <div className="panel-copy-actions">
          <button className="secondary btn-xs" onClick={copyTxHash}>{copied ? 'Copied ✓' : 'Copy'}</button>
          <a className="button secondary btn-xs" href={explorerUrl} target="_blank" rel="noopener noreferrer">Explorer ↗</a>
        </div>
      </div>

      <dl className="inspector-list">
        <dt>SOURCE ADDRESS</dt>
        <dd className="mono-text">{edge.source}</dd>
        
        <dt>DESTINATION ADDRESS</dt>
        <dd className="mono-text">{edge.target}</dd>

        <dt>BLOCK</dt>
        <dd>{edge.transfer.block_number ?? 'Unavailable'}</dd>

        <dt>TIMESTAMP</dt>
        <dd>{edge.transfer.timestamp ? new Date(edge.transfer.timestamp).toLocaleString() : 'Unavailable'}</dd>

        <dt>FEE / GAS USED</dt>
        <dd>{(edge.transfer as any).fee || '0'} ETH</dd>

        <dt>STATUS</dt>
        <dd className="status-mark">✓ OBSERVED ON-CHAIN</dd>

        <dt>EVIDENCE REFERENCE</dt>
        <dd className="verified-text">{edge.evidence_id || 'Evidence reference unlinked'}</dd>

        <dt>RISK OVERLAYS</dt>
        <dd>
          {factors.length > 0 ? (
            factors.map(item => (
              <span className="factor-chip risk-high" key={item.factor_id}>{item.name} (+{item.contribution})</span>
            ))
          ) : (
            <span className="attribution-none">No active overlays</span>
          )}
        </dd>
      </dl>
    </div>
  );
}

export function GraphUnavailable({ onNavigate }: { onNavigate: (route: string) => void }) {
  return (
    <section className="graph-unavailable" aria-labelledby="graph-unavailable-title">
      <div className="eyebrow">INVESTIGATION / GRAPH</div>
      <h1 id="graph-unavailable-title">Transaction graph</h1>
      <div className="graph-unavailable-card">
        <div className="empty-orbit" aria-hidden="true">+</div>
        <div>
          <span className="data-badge warning">NO ACTIVE TRACE</span>
          <h2>Load an evidence-backed trace to inspect the graph</h2>
          <p>The graph workspace renders persisted blockchain observations only. Start a bounded investigation to see nodes, transaction edges, hop distance, and evidence references here.</p>
          <div className="graph-unavailable-actions">
            <button className="primary" onClick={() => onNavigate('investigate')}>START INVESTIGATION</button>
            <button className="secondary" onClick={() => onNavigate('cases')}>VIEW CASES</button>
          </div>
        </div>
      </div>
    </section>
  );
}

function GraphAnalysisRail({ trace, edges, primaryPath }: { trace: Trace; edges: Edge[]; primaryPath: PrimaryPath | null }) {
  const recent = [...edges].filter(item => item.transfer.timestamp).sort((a, b) => String(b.transfer.timestamp).localeCompare(String(a.transfer.timestamp))).slice(0, 4);
  return (
    <section className="graph-analysis-rail" aria-label="Observed flow analysis">
      <div className="primary-path-panel">
        <div className="eyebrow">PRIMARY INVESTIGATIVE PATH</div>
        <div className="primary-path-chain">{primaryPath?.node_ids?.length ? primaryPath.node_ids.map((address, index) => <React.Fragment key={`${address}-${index}`}><span>{primaryPath.status === 'ATTRIBUTED' && index === primaryPath.node_ids.length - 1 ? primaryPath.terminal_entity_name : index === 0 ? 'ROOT WALLET' : `HOP ${index}`}</span>{index < primaryPath.node_ids.length - 1 && <b>→</b>}</React.Fragment>) : <span>Path unavailable</span>}</div>
        <div className="primary-path-facts"><div><small>FINAL DESTINATION</small><b>{primaryPath?.terminal_entity_name || 'UNKNOWN / UNATTRIBUTED DESTINATION'}</b></div><div><small>TYPE</small><b>{primaryPath?.terminal_entity_type || 'UNKNOWN'}</b></div><div><small>HOPS</small><b>{primaryPath?.hops ?? 0}</b></div><div><small>ATTRIBUTION</small><b>{primaryPath?.attribution || 'UNKNOWN'}</b></div></div>
        <div className="primary-path-why"><small>WHY THIS ENDPOINT</small><span>{primaryPath?.why || 'Primary path calculation unavailable.'}</span></div>
        <div className="primary-path-why"><small>EVIDENCE</small><span>{primaryPath?.transaction_hashes?.length ? primaryPath.transaction_hashes.map(short).join(' | ') : 'No linked transaction evidence'}</span></div>
      </div>
      <div className="analysis-heading">
        <div>
          <div className="eyebrow">FLOW ANALYSIS / OBSERVED FACTS</div>
          <h2>Investigation trace readout</h2>
        </div>
        <span className="data-badge">EVIDENCE-BACKED</span>
      </div>
      <div className="analysis-grid">
        <div className="analysis-card">
          <span className="analysis-label">PATHS RECONSTRUCTED</span>
          <b>{trace.metrics.path_count}</b>
          <small>Persisted paths available for inspection</small>
        </div>
        <div className="analysis-card">
          <span className="analysis-label">OBSERVATION WINDOW</span>
          <b>{recent.length ? `${recent.length} recent` : 'Unavailable'}</b>
          <small>Latest timestamped transfers in the selected view</small>
        </div>
        <div className="analysis-card analysis-activity">
          <span className="analysis-label">LATEST OBSERVED ACTIVITY</span>
          {recent.length ? recent.map(item => (
            <div className="activity-row" key={item.edge_id}>
              <span className="mono">{short(item.transaction_hash)}</span>
              <span>{item.transfer.asset} {item.transfer.amount}</span>
              <time>{new Date(item.transfer.timestamp!).toLocaleString()}</time>
            </div>
          )) : <small>No timestamped observations available in this trace.</small>}
        </div>
      </div>
      {trace.limitations.length > 0 && (
        <div className="analysis-limitations">
          <b>TRACE LIMITATIONS</b>
          <span>{trace.limitations.join(' / ')}</span>
        </div>
      )}
    </section>
  );
}

function EmptyInspector({ trace, risk }: { trace: Trace; risk: RiskAssessment | null }) {
  return (
    <div className="inspector-empty">
      <span>⌁</span>
      <div className="eyebrow">INSPECTOR READY</div>
      <h3>Select a node or edge</h3>
      <p>Review the exact address, transaction, asset, block, provider, and evidence reference behind each observed relationship.</p>
      <div className="inspector-facts">
        <b>{trace.evidence.length}<small>EVIDENCE ITEMS</small></b>
        <b>{risk ? risk.band : '—'}<small>RISK OVERLAY</small></b>
      </div>
      <small className="muted">Risk overlay is available only when a persisted assessment exists. It does not alter observed graph facts.</small>
    </div>
  );
}

function InspectorHeading({ eyebrow, title, badge }: { eyebrow: string; title: string; badge: string }) {
  return (
    <div className="inspector-heading">
      <div className="eyebrow">{eyebrow}</div>
      <h2>{title}</h2>
      <span className="data-badge">{badge}</span>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="graph-metric">
      <span>{label}</span>
      <b>{value}</b>
    </div>
  );
}
