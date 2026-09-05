from datetime import datetime, timezone
import uuid
from typing import List, Dict, Optional, Set, Tuple

from .domain import (
    InvestigationCase,
    CaseRelationshipScore,
    CaseRelationshipType,
    InfrastructureImpactNode,
    FraudNetworkGraph,
    FraudNetworkNode,
    FraudNetworkEdge,
    Chain,
    TraceResult,
    GraphNode,
    GraphEdge,
)

class CaseRelationshipEngine:
    """
    Cross-Case Wallet Correlation & Fraud Network Intelligence Engine.
    Identifies shared cryptocurrency infrastructure (wallets, intermediaries, VASPs,
    bridges, mixers) across distinct investigation cases.
    """

    def __init__(self, cases: List[InvestigationCase]):
        self.cases = {c.case_id: c for c in cases if c and c.case_id}

    def compare_cases(self, case_a: InvestigationCase, case_b: InvestigationCase) -> List[CaseRelationshipScore]:
        """
        Evaluates structural, topological, and behavioral correlations between two cases.
        Returns candidate relationship scores.
        """
        if not case_a or not case_b or case_a.case_id == case_b.case_id:
            return []

        results: List[CaseRelationshipScore] = []
        now = datetime.now(timezone.utc)

        wallets_a = {w.address.lower() for w in case_a.wallets if w.address}
        wallets_b = {w.address.lower() for w in case_b.wallets if w.address}
        shared_direct = wallets_a.intersection(wallets_b)

        # 1. SHARED_WALLET (Direct reported wallet overlap)
        if shared_direct:
            shared_wallet_items = [{"address": addr, "chain": "ethereum"} for addr in shared_direct]
            results.append(
                CaseRelationshipScore(
                    link_id=f"{case_a.case_id}:{case_b.case_id}:SHARED_WALLET",
                    case_a_id=case_a.case_id,
                    case_b_id=case_b.case_id,
                    case_b_title=case_b.title,
                    relationship_score=0.95,
                    relationship_type=CaseRelationshipType.SHARED_WALLET,
                    shared_wallets=shared_wallet_items,
                    explanation=f"Direct reported wallet match across case {case_a.case_id[:8]} and {case_b.case_id[:8]} ({len(shared_direct)} shared address(es)).",
                    calculated_at=now,
                )
            )

        trace_a = case_a.latest_trace
        trace_b = case_b.latest_trace

        if not trace_a or not trace_b:
            return results

        nodes_a = {n.address.lower(): n for n in trace_a.nodes if n.address}
        nodes_b = {n.address.lower(): n for n in trace_b.nodes if n.address}
        shared_nodes = set(nodes_a.keys()).intersection(set(nodes_b.keys()))

        if not shared_nodes:
            return results

        # Categorize shared nodes
        shared_intermediaries: List[str] = []
        shared_vasps: List[str] = []
        shared_mixers: List[str] = []
        shared_bridges: List[str] = []

        for addr in shared_nodes:
            na = nodes_a[addr]
            nb = nodes_b[addr]
            node_type = (na.node_type or nb.node_type or "WALLET").upper()

            if "MIXER" in node_type or "TORNADO" in addr or "MIXER" in addr:
                shared_mixers.append(addr)
            elif "BRIDGE" in node_type or "BRIDGE" in addr:
                shared_bridges.append(addr)
            elif "VASP" in node_type or "EXCHANGE" in node_type or "CUSTODIAL" in node_type:
                shared_vasps.append(addr)
            else:
                shared_intermediaries.append(addr)

        # 2. SHARED_MIXER
        if shared_mixers:
            results.append(
                CaseRelationshipScore(
                    link_id=f"{case_a.case_id}:{case_b.case_id}:SHARED_MIXER",
                    case_a_id=case_a.case_id,
                    case_b_id=case_b.case_id,
                    case_b_title=case_b.title,
                    relationship_score=0.85,
                    relationship_type=CaseRelationshipType.SHARED_MIXER,
                    shared_infrastructure=[{"address": a, "type": "MIXER"} for a in shared_mixers],
                    explanation=f"Shared privacy mixer infrastructure observed across both cases ({len(shared_mixers)} mixer node(s)).",
                    calculated_at=now,
                )
            )

        # 3. SHARED_BRIDGE
        if shared_bridges:
            results.append(
                CaseRelationshipScore(
                    link_id=f"{case_a.case_id}:{case_b.case_id}:SHARED_BRIDGE",
                    case_a_id=case_a.case_id,
                    case_b_id=case_b.case_id,
                    case_b_title=case_b.title,
                    relationship_score=0.78,
                    relationship_type=CaseRelationshipType.SHARED_BRIDGE,
                    shared_infrastructure=[{"address": a, "type": "BRIDGE"} for a in shared_bridges],
                    explanation=f"Shared cross-chain bridge infrastructure observed across both cases ({len(shared_bridges)} bridge node(s)).",
                    calculated_at=now,
                )
            )

        # 4. SHARED_INTERMEDIARY
        if shared_intermediaries:
            results.append(
                CaseRelationshipScore(
                    link_id=f"{case_a.case_id}:{case_b.case_id}:SHARED_INTERMEDIARY",
                    case_a_id=case_a.case_id,
                    case_b_id=case_b.case_id,
                    case_b_title=case_b.title,
                    relationship_score=0.88,
                    relationship_type=CaseRelationshipType.SHARED_INTERMEDIARY,
                    shared_wallets=[{"address": a, "role": "INTERMEDIARY"} for a in shared_intermediaries],
                    explanation=f"Shared intermediary wallet(s) present in both transaction graphs ({len(shared_intermediaries)} node(s)).",
                    calculated_at=now,
                )
            )

        # 5. SHARED_VASP
        if shared_vasps:
            results.append(
                CaseRelationshipScore(
                    link_id=f"{case_a.case_id}:{case_b.case_id}:SHARED_VASP",
                    case_a_id=case_a.case_id,
                    case_b_id=case_b.case_id,
                    case_b_title=case_b.title,
                    relationship_score=0.70,
                    relationship_type=CaseRelationshipType.SHARED_VASP,
                    shared_infrastructure=[{"address": a, "type": "VASP"} for a in shared_vasps],
                    explanation=f"Both cases share common destination VASP exchange infrastructure ({len(shared_vasps)} VASP node(s)).",
                    calculated_at=now,
                )
            )

        # 6. TEMPORAL_CORRELATION (Transfers within 1-hour window)
        tx_times_a = [e.transfer.timestamp for e in trace_a.edges if e.transfer and e.transfer.timestamp]
        tx_times_b = [e.transfer.timestamp for e in trace_b.edges if e.transfer and e.transfer.timestamp]

        if tx_times_a and tx_times_b:
            min_delta_seconds = min(abs((ta - tb).total_seconds()) for ta in tx_times_a for tb in tx_times_b)
            if min_delta_seconds <= 3600:
                results.append(
                    CaseRelationshipScore(
                        link_id=f"{case_a.case_id}:{case_b.case_id}:TEMPORAL_CORRELATION",
                        case_a_id=case_a.case_id,
                        case_b_id=case_b.case_id,
                        case_b_title=case_b.title,
                        relationship_score=0.62,
                        relationship_type=CaseRelationshipType.TEMPORAL_CORRELATION,
                        explanation=f"Temporal execution proximity: Transfers in both cases occurred within {int(min_delta_seconds / 60)} minutes.",
                        calculated_at=now,
                    )
                )

        return results

    def correlate_all(self, target_case_id: str) -> List[CaseRelationshipScore]:
        """Correlates target case against all other active cases in repo."""
        target = self.cases.get(target_case_id)
        if not target:
            return []

        all_scores: List[CaseRelationshipScore] = []
        for case_id, other in self.cases.items():
            if case_id == target_case_id:
                continue
            scores = self.compare_cases(target, other)
            all_scores.extend(scores)

        all_scores.sort(key=lambda s: s.relationship_score, reverse=True)
        return all_scores

    def calculate_infrastructure_impact(self, node_id: str) -> InfrastructureImpactNode:
        """
        Calculates multi-victim aggregation metrics for a shared infrastructure node.
        """
        node_id_lower = node_id.lower()
        connected_cases: List[InvestigationCase] = []
        victim_addresses: Set[str] = set()
        total_exposure = 0.0
        first_obs: Optional[datetime] = None
        last_obs: Optional[datetime] = None
        detected_type = "INTERMEDIARY"

        for case in self.cases.values():
            if not case.latest_trace:
                continue
            trace = case.latest_trace
            node_match = next((n for n in trace.nodes if n.address.lower() == node_id_lower), None)
            if node_match:
                connected_cases.append(case)
                if node_match.node_type:
                    detected_type = node_match.node_type

                for w in case.wallets:
                    victim_addresses.add(w.address.lower())

                for edge in trace.edges:
                    if edge.source.lower() == node_id_lower or edge.target.lower() == node_id_lower:
                        try:
                            total_exposure += float(edge.transfer.amount)
                        except (ValueError, TypeError):
                            pass
                        ts = edge.transfer.timestamp
                        if ts:
                            if not first_obs or ts < first_obs:
                                first_obs = ts
                            if not last_obs or ts > last_obs:
                                last_obs = ts

        return InfrastructureImpactNode(
            node_id=node_id,
            chain=Chain.ETHEREUM,
            node_type=detected_type,
            connected_case_ids=[c.case_id for c in connected_cases],
            connected_case_titles=[c.title for c in connected_cases],
            victim_count=max(len(victim_addresses), len(connected_cases)),
            aggregate_exposure_usd=round(total_exposure * 3000.0, 2) if total_exposure < 1000 else round(total_exposure, 2), # USD conversion estimate
            first_observed=first_obs,
            last_observed=last_obs,
            provenance_description=f"Shared infrastructure node linked across {len(connected_cases)} active investigation case(s).",
        )

    def build_fraud_network_graph(self, target_case_id: Optional[str] = None) -> FraudNetworkGraph:
        """
        Constructs higher-level investigation graph distinguished into:
        - TRANSACTION_RELATIONSHIP (direct money flow)
        - INVESTIGATIVE_RELATIONSHIP (case/infrastructure correlation)
        """
        nodes: List[FraudNetworkNode] = []
        edges: List[FraudNetworkEdge] = []
        seen_nodes: Set[str] = set()
        seen_edges: Set[str] = set()

        target_cases = [self.cases[target_case_id]] if target_case_id and target_case_id in self.cases else list(self.cases.values())

        for case in target_cases:
            # Case Node
            c_node_id = f"case:{case.case_id}"
            if c_node_id not in seen_nodes:
                seen_nodes.add(c_node_id)
                nodes.append(
                    FraudNetworkNode(
                        id=c_node_id,
                        label=f"Case: {case.title}",
                        node_type="CASE",
                        chain="system",
                        metadata={"case_id": case.case_id, "priority": case.priority, "status": case.status},
                    )
                )

            # Victim Nodes
            for wallet in case.wallets:
                v_node_id = f"victim:{wallet.address.lower()}"
                if v_node_id not in seen_nodes:
                    seen_nodes.add(v_node_id)
                    nodes.append(
                        FraudNetworkNode(
                            id=v_node_id,
                            label=f"Victim: {wallet.address[:8]}...",
                            node_type="VICTIM",
                            chain=wallet.chain.value if hasattr(wallet.chain, 'value') else str(wallet.chain),
                            metadata={"address": wallet.address},
                        )
                    )
                
                # Edge: Victim -> Case (Investigative Relationship)
                e_id = f"{v_node_id}->{c_node_id}"
                if e_id not in seen_edges:
                    seen_edges.add(e_id)
                    edges.append(
                        FraudNetworkEdge(
                            edge_id=e_id,
                            source=v_node_id,
                            target=c_node_id,
                            relationship_kind="INVESTIGATIVE_RELATIONSHIP",
                            label="REPORTED_BY",
                        )
                    )

            # Trace nodes & edges
            if case.latest_trace:
                for n in case.latest_trace.nodes:
                    w_node_id = f"wallet:{n.address.lower()}"
                    ntype = (n.node_type or "WALLET").upper()

                    if w_node_id not in seen_nodes:
                        seen_nodes.add(w_node_id)
                        nodes.append(
                            FraudNetworkNode(
                                id=w_node_id,
                                label=f"{ntype}: {n.address[:8]}...",
                                node_type=ntype if ntype in {"VASP", "MIXER", "BRIDGE"} else "WALLET",
                                chain=n.chain.value if hasattr(n.chain, 'value') else str(n.chain),
                                metadata={"address": n.address, "depth": n.depth},
                            )
                        )

                    # Edge: Case -> Wallet (Investigative Link)
                    c_w_edge = f"{c_node_id}->{w_node_id}"
                    if c_w_edge not in seen_edges:
                        seen_edges.add(c_w_edge)
                        edges.append(
                            FraudNetworkEdge(
                                edge_id=c_w_edge,
                                source=c_node_id,
                                target=w_node_id,
                                relationship_kind="INVESTIGATIVE_RELATIONSHIP",
                                label="INCLUDES_INFRASTRUCTURE",
                            )
                        )

                for e in case.latest_trace.edges:
                    src_id = f"wallet:{e.source.lower()}"
                    dst_id = f"wallet:{e.target.lower()}"
                    tx_edge_id = f"tx:{e.transaction_hash}"
                    
                    if tx_edge_id not in seen_edges:
                        seen_edges.add(tx_edge_id)
                        edges.append(
                            FraudNetworkEdge(
                                edge_id=tx_edge_id,
                                source=src_id,
                                target=dst_id,
                                relationship_kind="TRANSACTION_RELATIONSHIP",
                                label=f"{e.transfer.amount} {e.transfer.asset}",
                                metadata={"tx_hash": e.transaction_hash, "hop": e.hop},
                            )
                        )

        # Cross-case correlation edges
        case_list = list(target_cases)
        for i in range(len(case_list)):
            for j in range(i + 1, len(case_list)):
                scores = self.compare_cases(case_list[i], case_list[j])
                for score in scores:
                    cc_edge_id = f"corr:{score.case_a_id}:{score.case_b_id}:{score.relationship_type}"
                    if cc_edge_id not in seen_edges:
                        seen_edges.add(cc_edge_id)
                        edges.append(
                            FraudNetworkEdge(
                                edge_id=cc_edge_id,
                                source=f"case:{score.case_a_id}",
                                target=f"case:{score.case_b_id}",
                                relationship_kind="INVESTIGATIVE_RELATIONSHIP",
                                label=f"{score.relationship_type} ({int(score.relationship_score * 100)}%)",
                                weight=score.relationship_score,
                                metadata={"type": score.relationship_type, "score": score.relationship_score},
                            )
                        )

        return FraudNetworkGraph(
            nodes=nodes,
            edges=edges,
            metrics={
                "total_cases": len(target_cases),
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "transaction_relationships": len([e for e in edges if e.relationship_kind == "TRANSACTION_RELATIONSHIP"]),
                "investigative_relationships": len([e for e in edges if e.relationship_kind == "INVESTIGATIVE_RELATIONSHIP"]),
            },
            generated_at=datetime.now(timezone.utc),
        )

    def detect_linked_clusters(self) -> List[Dict]:
        """
        Discovers associated wallet/case clusters across all investigations.
        Uses non-definitive language ("associated cluster", "linked infrastructure").
        """
        clusters: List[Dict] = []
        visited_nodes: Set[str] = set()

        for case in self.cases.values():
            if not case.latest_trace:
                continue

            node_addresses = {n.address.lower() for n in case.latest_trace.nodes if n.address}
            unvisited = node_addresses - visited_nodes
            if not unvisited:
                continue

            cluster_id = f"cluster-assoc-{uuid.uuid5(uuid.NAMESPACE_URL, ':'.join(sorted(unvisited)))[:8]}"
            connected_case_ids = []

            for other_id, other_case in self.cases.items():
                if other_case.latest_trace:
                    other_nodes = {n.address.lower() for n in other_case.latest_trace.nodes if n.address}
                    if node_addresses.intersection(other_nodes):
                        connected_case_ids.append(other_id)

            visited_nodes.update(node_addresses)

            clusters.append({
                "cluster_id": cluster_id,
                "cluster_label": f"Associated Infrastructure Cluster #{len(clusters) + 1}",
                "terminology": "associated cluster",
                "confidence": 0.85 if len(connected_case_ids) > 1 else 0.50,
                "node_count": len(node_addresses),
                "connected_cases_count": len(connected_case_ids),
                "case_ids": connected_case_ids,
                "addresses": list(node_addresses)[:10],
                "description": f"Linked infrastructure candidate observed across {len(connected_case_ids)} investigation case(s).",
            })

        return clusters
