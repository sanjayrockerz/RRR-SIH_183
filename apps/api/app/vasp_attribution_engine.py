import uuid
from datetime import datetime
from typing import Dict, List, Optional
from .domain import (
    AddressCluster,
    AttributionEvidence,
    AttributionEvidenceType,
    AttributionResult,
    Chain,
    TraceResult,
    Transfer,
    VaspBlockchainAddress,
    VaspClassification,
    VaspEntity,
)

# Configurable Signal Weights for Attribution Confidence Calculation
DEFAULT_SIGNAL_WEIGHTS = {
    AttributionEvidenceType.KNOWN_ADDRESS: 0.95,
    AttributionEvidenceType.KNOWN_CLUSTER: 0.88,
    AttributionEvidenceType.TRANSACTION_TO_KNOWN_ENTITY: 0.82,
    AttributionEvidenceType.CONSOLIDATION_PATTERN: 0.70,
    AttributionEvidenceType.DEPOSIT_ADDRESS_PATTERN: 0.75,
    AttributionEvidenceType.SWEEP_PATTERN: 0.72,
    AttributionEvidenceType.HISTORICAL_ASSOCIATION: 0.65,
    AttributionEvidenceType.CROSS_CHAIN_ASSOCIATION: 0.60,
    AttributionEvidenceType.BEHAVIORAL_SIMILARITY: 0.55,
    AttributionEvidenceType.EXTERNAL_INTELLIGENCE: 0.80,
}

# Classification Threshold Boundaries
THRESHOLD_KNOWN = 0.90
THRESHOLD_PROBABLE = 0.70
THRESHOLD_POSSIBLE = 0.40


class VASPAttributionEngine:
    """
    Deterministic VASP Attribution Engine.
    Evaluates evidence-backed signals (direct address matches, cluster associations,
    multi-hop graph topology, flow metrics, and behavioral patterns) to assign
    a classification (KNOWN, PROBABLE, POSSIBLE, UNKNOWN) and explainable confidence score.
    """

    def __init__(
        self,
        entities: List[VaspEntity],
        addresses: List[VaspBlockchainAddress],
        clusters: List[AddressCluster],
        evidence_records: Optional[List[AttributionEvidence]] = None,
        weights: Optional[Dict[AttributionEvidenceType, float]] = None,
    ):
        self.entities = {e.id: e for e in entities}
        self.addresses = {(a.chain, a.address.lower()): a for a in addresses}
        self.clusters = {c.id: c for c in clusters}
        self.evidence_records = evidence_records or []
        self.weights = weights or DEFAULT_SIGNAL_WEIGHTS

    def analyze(
        self,
        chain: Chain,
        wallet: str,
        trace: Optional[TraceResult] = None,
        transfers: Optional[List[Transfer]] = None,
    ) -> AttributionResult:
        wallet_lower = wallet.lower()
        supporting: List[AttributionEvidence] = []
        contradictory: List[AttributionEvidence] = []
        candidate_entity: Optional[VaspEntity] = None
        graph_distance: Optional[int] = None
        fund_amount: float = 0.0
        first_observed: Optional[datetime] = None
        last_observed: Optional[datetime] = None

        # 1. Direct Known Address Match
        known_addr = self.addresses.get((chain, wallet_lower))
        if known_addr and known_addr.entity_id in self.entities:
            candidate_entity = self.entities[known_addr.entity_id]
            graph_distance = 0
            ev = AttributionEvidence(
                id=f"ev-{uuid.uuid4().hex[:8]}",
                address=wallet,
                entity_id=candidate_entity.id,
                evidence_type=AttributionEvidenceType.KNOWN_ADDRESS,
                evidence_description=f"Direct match in VASP registry for address {wallet} (Address Type: {known_addr.address_type})",
                source=known_addr.source,
                confidence=known_addr.confidence,
                observed_at=known_addr.first_seen or datetime.utcnow(),
            )
            supporting.append(ev)

            # Check associated cluster
            if known_addr.cluster_id and known_addr.cluster_id in self.clusters:
                cl = self.clusters[known_addr.cluster_id]
                ev_cl = AttributionEvidence(
                    id=f"ev-{uuid.uuid4().hex[:8]}",
                    address=wallet,
                    entity_id=candidate_entity.id,
                    evidence_type=AttributionEvidenceType.KNOWN_CLUSTER,
                    evidence_description=f"Associated with cluster {cl.id} ({cl.cluster_type}) provenance: {cl.provenance}",
                    source=cl.provenance,
                    confidence=cl.confidence,
                    observed_at=cl.created_at,
                )
                supporting.append(ev_cl)

        # Append existing persisted evidence records for this target address
        for er in self.evidence_records:
            if er.address.lower() == wallet_lower:
                if candidate_entity and er.entity_id != candidate_entity.id:
                    contradictory.append(er)
                else:
                    if not candidate_entity and er.entity_id in self.entities:
                        candidate_entity = self.entities[er.entity_id]
                    supporting.append(er)

        # 2. Multi-hop Trace & Graph Analysis
        if trace:
            for node in trace.nodes:
                if node.address.lower() == wallet_lower:
                    continue
                node_addr = self.addresses.get((node.chain, node.address.lower()))
                if node_addr and node_addr.entity_id in self.entities:
                    target_ent = self.entities[node_addr.entity_id]
                    if not candidate_entity:
                        candidate_entity = target_ent

                    if candidate_entity and target_ent.id == candidate_entity.id:
                        if graph_distance is None or node.depth < graph_distance:
                            graph_distance = node.depth

                        ev_tx = AttributionEvidence(
                            id=f"ev-{uuid.uuid4().hex[:8]}",
                            address=wallet,
                            entity_id=target_ent.id,
                            evidence_type=AttributionEvidenceType.TRANSACTION_TO_KNOWN_ENTITY,
                            evidence_description=f"Flow reaches known {target_ent.trading_name} address {node.address} at hop depth {node.depth}",
                            source="MultiHopTraceEngine",
                            confidence=max(0.3, 0.95 - (max(0, node.depth - 1) * 0.10)),
                            observed_at=datetime.utcnow(),
                        )
                        supporting.append(ev_tx)
                    elif candidate_entity and target_ent.id != candidate_entity.id:
                        ev_conflict = AttributionEvidence(
                            id=f"ev-{uuid.uuid4().hex[:8]}",
                            address=wallet,
                            entity_id=target_ent.id,
                            evidence_type=AttributionEvidenceType.TRANSACTION_TO_KNOWN_ENTITY,
                            evidence_description=f"Trace also reaches distinct entity {target_ent.trading_name} at hop depth {node.depth}",
                            source="MultiHopTraceEngine",
                            confidence=max(0.2, 0.80 - (node.depth * 0.15)),
                            observed_at=datetime.utcnow(),
                        )
                        contradictory.append(ev_conflict)

            # Sum total volume & timestamp bounds from edges / transfers
            if hasattr(trace, "edges") and trace.edges:
                for edge in trace.edges:
                    src = (getattr(edge, 'source', None) or getattr(edge, 'source_wallet', '')).lower()
                    dst = (getattr(edge, 'target', None) or getattr(edge, 'destination_wallet', '')).lower()
                    if src == wallet_lower or dst == wallet_lower:
                        amt = getattr(edge, 'amount', None) or (edge.transfer.amount if hasattr(edge, 'transfer') else '0')
                        try:
                            fund_amount += float(amt)
                        except (ValueError, TypeError):
                            pass

        if transfers:
            for tx in transfers:
                if tx.source.lower() == wallet_lower or tx.destination.lower() == wallet_lower:
                    try:
                        fund_amount += float(tx.amount)
                    except (ValueError, TypeError):
                        pass
                    if tx.timestamp:
                        if not first_observed or tx.timestamp < first_observed:
                            first_observed = tx.timestamp
                        if not last_observed or tx.timestamp > last_observed:
                            last_observed = tx.timestamp


        # 3. Compute Composite Confidence Score & Classification
        if not supporting:
            confidence = 0.0
            classification = VaspClassification.UNKNOWN
            explanation = "No attribution evidence or VASP association identified for this wallet."
        else:
            raw_scores = [ev.confidence * self.weights.get(ev.evidence_type, 0.70) for ev in supporting]
            max_score = max(raw_scores)
            avg_score = sum(raw_scores) / len(raw_scores)

            penalty = len(contradictory) * 0.12
            confidence = max(0.0, min(1.0, (max_score * 0.70 + avg_score * 0.30) - penalty))

            if confidence >= THRESHOLD_KNOWN:
                classification = VaspClassification.KNOWN
            elif confidence >= THRESHOLD_PROBABLE:
                classification = VaspClassification.PROBABLE
            elif confidence >= THRESHOLD_POSSIBLE:
                classification = VaspClassification.POSSIBLE
            else:
                classification = VaspClassification.UNKNOWN

            entity_name = candidate_entity.trading_name if candidate_entity else "Unknown VASP"
            conflict_msg = f" ({len(contradictory)} conflicting signal(s) noted)" if contradictory else ""
            explanation = (
                f"Assigned {classification} classification to {entity_name} with {confidence * 100:.1f}% confidence "
                f"based on {len(supporting)} evidence signal(s){conflict_msg}. "
                "Attribution reflects evidence-backed probability and not absolute legal certainty."
            )

        return AttributionResult(
            candidate_entity=candidate_entity,
            classification=classification,
            confidence=round(confidence, 4),
            supporting_evidence=supporting,
            contradictory_evidence=contradictory,
            graph_distance=graph_distance,
            fund_amount=round(fund_amount, 6),
            first_observed=first_observed,
            last_observed=last_observed,
            explanation=explanation,
        )
