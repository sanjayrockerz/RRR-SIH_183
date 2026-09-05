from datetime import datetime, timezone
from typing import Dict, List, Optional
from .domain import (
    AttributionResult,
    Chain,
    FundAtRisk,
    GraphEdge,
    TimeToVasp,
    TraceResult,
    VaspClassification,
    VaspExposureItem,
    VaspProximityCandidate,
)
from .fund_flow_engine import FundFlowEngine, normalize_to_usd, parse_float_amount


def format_duration_seconds(seconds: Optional[float]) -> str:
    if seconds is None or seconds < 0:
        return "N/A"
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        mins = int(seconds / 60)
        return f"{mins}m {int(seconds % 60)}s"
    elif seconds < 86400:
        hours = int(seconds / 3600)
        mins = int((seconds % 3600) / 60)
        return f"{hours}h {mins}m"
    else:
        days = int(seconds / 86400)
        hours = int((seconds % 86400) / 3600)
        return f"{days}d {hours}h"


class VASPProximityEngine:
    """
    Nearest VASP Intelligence & Relevance Engine.
    Evaluates multi-factor relevance scores for candidate VASPs interacting with traced funds:
    - Hop distance (graph distance penalty)
    - Volume & percentage of victim funds
    - Temporal proximity (time between victim outflow and VASP ingress)
    - Attribution confidence
    - Directness (direct transfer vs multi-hop vs cross-chain)
    - Recency
    """

    def __init__(
        self,
        trace: TraceResult,
        attributions: Optional[Dict[str, AttributionResult]] = None,
        hop_weight: float = 0.25,
        volume_weight: float = 0.35,
        confidence_weight: float = 0.25,
        temporal_weight: float = 0.15,
    ):
        self.trace = trace
        self.attributions = {k.lower(): v for k, v in (attributions or {}).items()}
        self.hop_weight = hop_weight
        self.volume_weight = volume_weight
        self.confidence_weight = confidence_weight
        self.temporal_weight = temporal_weight

    def evaluate_proximity(self) -> List[VaspProximityCandidate]:
        if not self.trace or not self.trace.edges:
            return []

        # Find victim outflow baseline timestamp
        victim_outflows = [
            e for e in self.trace.edges 
            if getattr(e, 'timestamp', None) is not None
        ]
        first_victim_ts = min((e.timestamp for e in victim_outflows), default=None) if victim_outflows else None

        # Aggregate transfers to VASP nodes
        vasp_transfers: Dict[str, dict] = {} # entity_id -> aggregator dict

        for edge in self.trace.edges:
            dst = getattr(edge, 'target', '') or getattr(edge, 'to_address', '')
            dst_lower = dst.lower()

            attr = self.attributions.get(dst_lower)
            if not attr or not attr.candidate_entity:
                continue

            entity = attr.candidate_entity
            entity_id = getattr(entity, 'id', '') or getattr(entity, 'entity_id', '')
            entity_name = getattr(entity, 'legal_name', None) or getattr(entity, 'trading_name', None) or getattr(entity, 'name', 'Unknown VASP')

            classification = getattr(attr, 'classification', VaspClassification.UNKNOWN)
            if classification not in (VaspClassification.KNOWN, VaspClassification.PROBABLE, VaspClassification.POSSIBLE):
                continue

            amt_str = getattr(edge, 'amount', '0')
            asset = getattr(edge, 'asset', 'ETH') or 'ETH'
            usd_val = normalize_to_usd(amt_str, asset)
            hop = getattr(edge, 'hop', 1)
            tx_hash = getattr(edge, 'transaction_hash', '')
            edge_ts = getattr(edge, 'timestamp', None)

            if entity_id not in vasp_transfers:
                vasp_transfers[entity_id] = {
                    "entity_id": entity_id,
                    "entity_name": entity_name,
                    "total_usd": 0.0,
                    "min_hop": hop,
                    "attribution_confidence": attr.confidence,
                    "classification": classification,
                    "first_seen": edge_ts,
                    "last_seen": edge_ts,
                    "tx_hashes": set(),
                    "asset": asset,
                    "has_cross_chain": False,
                }

            rec = vasp_transfers[entity_id]
            rec["total_usd"] += usd_val
            rec["min_hop"] = min(rec["min_hop"], hop)
            rec["attribution_confidence"] = max(rec["attribution_confidence"], attr.confidence)
            if tx_hash:
                rec["tx_hashes"].add(tx_hash)

            if edge_ts:
                if rec["first_seen"] is None or edge_ts < rec["first_seen"]:
                    rec["first_seen"] = edge_ts
                if rec["last_seen"] is None or edge_ts > rec["last_seen"]:
                    rec["last_seen"] = edge_ts

            if getattr(edge, 'destination_chain', None) is not None:
                rec["has_cross_chain"] = True

        if not vasp_transfers:
            return []

        # Total victim fund estimate for percentage calculation
        flow_engine = FundFlowEngine(self.trace)
        flow_summary = flow_engine.analyze()
        total_victim_usd = flow_summary.total_victim_loss_usd or max(1.0, sum(r["total_usd"] for r in vasp_transfers.values()))

        candidates: List[VaspProximityCandidate] = []

        for entity_id, rec in vasp_transfers.items():
            usd_val = rec["total_usd"]
            pct = round((usd_val / total_victim_usd) * 100.0, 2)
            hop_dist = rec["min_hop"]
            conf = rec["attribution_confidence"]

            # Time to VASP
            time_to_vasp_sec = None
            if first_victim_ts and rec["first_seen"]:
                time_to_vasp_sec = max(0.0, (rec["first_seen"] - first_victim_ts).total_seconds())

            # Factor Scores (0.0 to 1.0)
            # Hop score: 1 hop -> 1.0, 2 hops -> 0.8, 3 hops -> 0.6, 4+ hops -> 0.4
            hop_score = max(0.2, 1.0 - (hop_dist - 1) * 0.2)

            # Volume score: proportion of victim funds (capped at 1.0)
            vol_score = min(1.0, usd_val / total_victim_usd) if total_victim_usd > 0 else 0.5

            # Temporal score: faster arrival gives higher score
            temp_score = 1.0
            if time_to_vasp_sec is not None:
                if time_to_vasp_sec <= 3600:
                    temp_score = 1.0
                elif time_to_vasp_sec <= 86400:
                    temp_score = 0.85
                elif time_to_vasp_sec <= 604800:
                    temp_score = 0.70
                else:
                    temp_score = 0.50

            # Directness
            directness = "DIRECT" if hop_dist == 1 else ("CROSS_CHAIN" if rec["has_cross_chain"] else "MULTI_HOP")

            # Final Relevance Score (Weighted composite)
            relevance = (
                self.hop_weight * hop_score
                + self.volume_weight * vol_score
                + self.confidence_weight * conf
                + self.temporal_weight * temp_score
            )
            relevance = round(min(1.0, max(0.0, relevance)), 4)

            candidate = VaspProximityCandidate(
                entity_id=entity_id,
                entity_name=rec["entity_name"],
                relevance_score=relevance,
                attribution_confidence=round(conf, 2),
                amount=f"${usd_val:,.2f}",
                asset=rec["asset"],
                normalized_value_usd=round(usd_val, 2),
                percentage_of_victim_funds=pct,
                hop_distance=hop_dist,
                time_to_vasp_seconds=time_to_vasp_sec,
                time_to_vasp_formatted=format_duration_seconds(time_to_vasp_sec),
                supporting_transaction_hashes=list(rec["tx_hashes"]),
                directness=directness,
            )
            candidates.append(candidate)

        # Rank by relevance score descending
        candidates.sort(key=lambda c: (c.relevance_score, c.percentage_of_victim_funds), reverse=True)
        for idx, cand in enumerate(candidates, start=1):
            cand.rank = idx

        return candidates

    def calculate_vasp_exposures(self) -> List[VaspExposureItem]:
        candidates = self.evaluate_proximity()
        exposures: List[VaspExposureItem] = []
        for cand in candidates:
            attr = next(
                (a for a in self.attributions.values() if getattr(a.candidate_entity, 'id', '') == cand.entity_id or getattr(a.candidate_entity, 'entity_id', '') == cand.entity_id),
                None
            )
            classification = getattr(attr, 'classification', VaspClassification.PROBABLE) if attr else VaspClassification.PROBABLE

            item = VaspExposureItem(
                entity_id=cand.entity_id,
                entity_name=cand.entity_name,
                amount=cand.amount,
                asset=cand.asset,
                normalized_value_usd=cand.normalized_value_usd,
                percentage_of_victim_funds=cand.percentage_of_victim_funds,
                hop_distance=cand.hop_distance,
                attribution_confidence=cand.attribution_confidence,
                classification=classification,
            )
            exposures.append(item)
        return exposures

    def calculate_time_to_vasp(self) -> TimeToVasp:
        candidates = self.evaluate_proximity()
        if not candidates:
            return TimeToVasp(case_id=self.trace.case_id if self.trace else "")

        top_cand = candidates[0]
        victim_outflows = [e for e in self.trace.edges if getattr(e, 'timestamp', None) is not None]
        first_victim_ts = min((e.timestamp for e in victim_outflows), default=None) if victim_outflows else None

        return TimeToVasp(
            case_id=self.trace.case_id,
            time_to_vasp_seconds=top_cand.time_to_vasp_seconds,
            time_to_vasp_formatted=top_cand.time_to_vasp_formatted,
            first_victim_tx_timestamp=first_victim_ts,
            first_vasp_tx_timestamp=first_victim_ts, # updated below if available
            target_vasp_id=top_cand.entity_id,
            target_vasp_name=top_cand.entity_name,
            supporting_transactions=top_cand.supporting_transaction_hashes,
        )

    def calculate_fund_at_risk(self) -> FundAtRisk:
        flow_engine = FundFlowEngine(self.trace)
        flow_summary = flow_engine.analyze()
        candidates = self.evaluate_proximity()

        actionable_vasp_usd = sum(c.normalized_value_usd for c in candidates)

        return FundAtRisk(
            case_id=self.trace.case_id,
            total_victim_loss_usd=flow_summary.total_victim_loss_usd,
            traced_amount_usd=flow_summary.traced_amount_usd,
            currently_actionable_vasp_exposure_usd=round(actionable_vasp_usd, 2),
            unresolved_amount_usd=flow_summary.unresolved_amount_usd,
            disclaimer="Investigative intelligence: Actionable VASP exposure indicates receiving entities identified in the trace flow. It does not guarantee that funds remain unspent or freezeable.",
        )
