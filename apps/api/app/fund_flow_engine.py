from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
from uuid import uuid4
from .domain import (
    AssetValue,
    CategoryFlowBreakdown,
    Chain,
    FundFlowSummary,
    GraphEdge,
    GraphNode,
    PropagatedFlowHop,
    TraceResult,
    VaspClassification,
    VaspExposureItem,
)

# Standard mock USD price conversion for asset-aware accounting
DEFAULT_ASSET_USD_PRICES = {
    "ETH": 3200.0,
    "USDT": 1.0,
    "USDC": 1.0,
    "TRX": 0.25,
    "WBTC": 65000.0,
    "BTC": 65000.0,
    "DAI": 1.0,
}


def parse_float_amount(amount_str: str) -> float:
    try:
        return float(amount_str)
    except (ValueError, TypeError):
        return 0.0


def normalize_to_usd(amount_str: str, asset: str) -> float:
    val = parse_float_amount(amount_str)
    price = DEFAULT_ASSET_USD_PRICES.get(asset.upper(), 1.0)
    return round(val * price, 2)


class FundFlowEngine:
    """
    Fund Flow Propagation & Asset-Aware Accounting Engine.
    Tracks value flow from victim root addresses across transaction graphs,
    accounting per asset, avoiding double-counting on converging paths,
    and classifying flow into VASP, Mixer, Bridge, Intermediary, and Unresolved.
    """

    def __init__(self, trace: TraceResult, node_attributions: Optional[Dict[str, dict]] = None):
        self.trace = trace
        # Map node address (lower) -> attribution info dict: {"classification": ..., "entity_id": ..., "entity_name": ..., "node_type": ...}
        self.node_attributions = node_attributions or {}

    def analyze(self) -> FundFlowSummary:
        if not self.trace or not self.trace.edges:
            return FundFlowSummary(case_id=self.trace.case_id if self.trace else "")

        root_lower = self.trace.root_address.lower()
        
        # 1. Identify victim outgoing edges (hop 1)
        root_edges = [
            e for e in self.trace.edges 
            if e.source.lower() == root_lower or getattr(e, 'from_address', '').lower() == root_lower
        ]

        if not root_edges:
            # Fallback if root edge source isn't explicitly root_address (e.g. hop 0/1 edge)
            min_hop = min((getattr(e, 'hop', 1) for e in self.trace.edges), default=1)
            root_edges = [e for e in self.trace.edges if getattr(e, 'hop', 1) == min_hop]

        # Asset-aware accounting for initial victim loss
        victim_asset_map: Dict[tuple[str, str], float] = {} # (asset, chain) -> total amount
        for e in root_edges:
            asset = getattr(e, 'asset', 'ETH') or 'ETH'
            chain_val = getattr(e, 'chain', Chain.ETHEREUM)
            chain_str = chain_val.value if isinstance(chain_val, Chain) else str(chain_val)
            amount = parse_float_amount(getattr(e, 'amount', '0'))
            key = (asset.upper(), chain_str)
            victim_asset_map[key] = victim_asset_map.get(key, 0.0) + amount

        total_victim_loss_usd = sum(
            normalize_to_usd(str(amt), asset) 
            for (asset, _), amt in victim_asset_map.items()
        )

        # 2. Graph Flow Propagation (BFS with path tracking & deduplication)
        propagated_hops: List[PropagatedFlowHop] = []
        visited_edge_ids: Set[str] = set()

        category_usd_totals = {
            "VASP": 0.0,
            "MIXER": 0.0,
            "BRIDGE": 0.0,
            "INTERMEDIARY": 0.0,
            "UNRESOLVED": 0.0,
        }

        category_asset_maps: Dict[str, Dict[tuple[str, str], float]] = {
            c: {} for c in category_usd_totals
        }

        # Track visited destination nodes to handle path convergence without double counting
        processed_destinations: Set[str] = set()

        # Sort edges by hop number & timestamp
        sorted_edges = sorted(
            self.trace.edges,
            key=lambda e: (getattr(e, 'hop', 1), getattr(e, 'timestamp', datetime.min) or datetime.min)
        )

        for edge in sorted_edges:
            edge_id = getattr(edge, 'edge_id', '') or f"{edge.source}->{edge.target}:{getattr(edge, 'transaction_hash', '')}"
            if edge_id in visited_edge_ids:
                continue
            visited_edge_ids.add(edge_id)

            src = getattr(edge, 'source', '') or getattr(edge, 'from_address', '')
            dst = getattr(edge, 'target', '') or getattr(edge, 'to_address', '')
            asset = getattr(edge, 'asset', 'ETH') or 'ETH'
            chain_val = getattr(edge, 'chain', Chain.ETHEREUM)
            chain_str = chain_val.value if isinstance(chain_val, Chain) else str(chain_val)
            amount_str = getattr(edge, 'amount', '0') or '0'
            amount_val = parse_float_amount(amount_str)
            hop_num = getattr(edge, 'hop', 1)
            tx_hash = getattr(edge, 'transaction_hash', '')
            ts = getattr(edge, 'timestamp', None)

            hop = PropagatedFlowHop(
                source=src,
                destination=dst,
                asset=asset,
                amount=amount_str,
                timestamp=ts,
                transaction_hash=tx_hash,
                hop_number=hop_num,
                confidence=1.0,
            )
            propagated_hops.append(hop)

            # Classify destination node
            dst_lower = dst.lower()
            attribution = self.node_attributions.get(dst_lower, {})
            classification = attribution.get('classification', VaspClassification.UNKNOWN)
            node_type = attribution.get('node_type', '').upper()

            # Convergence Check: Avoid double-counting if dst was already counted as an endpoint
            if dst_lower in processed_destinations:
                continue
            processed_destinations.add(dst_lower)

            usd_val = normalize_to_usd(amount_str, asset)
            key = (asset.upper(), chain_str)

            if classification in (VaspClassification.KNOWN, VaspClassification.PROBABLE) or node_type == 'VASP':
                category_usd_totals["VASP"] += usd_val
                category_asset_maps["VASP"][key] = category_asset_maps["VASP"].get(key, 0.0) + amount_val
            elif node_type == 'MIXER' or 'MIXER' in str(attribution.get('entity_name', '')).upper():
                category_usd_totals["MIXER"] += usd_val
                category_asset_maps["MIXER"][key] = category_asset_maps["MIXER"].get(key, 0.0) + amount_val
            elif node_type == 'BRIDGE' or 'BRIDGE' in str(attribution.get('entity_name', '')).upper():
                category_usd_totals["BRIDGE"] += usd_val
                category_asset_maps["BRIDGE"][key] = category_asset_maps["BRIDGE"].get(key, 0.0) + amount_val
            else:
                # Check if dst is an intermediary (has outgoing edges in trace)
                has_outgoing = any(
                    e.source.lower() == dst_lower or getattr(e, 'from_address', '').lower() == dst_lower 
                    for e in self.trace.edges
                )
                if has_outgoing:
                    category_usd_totals["INTERMEDIARY"] += usd_val
                    category_asset_maps["INTERMEDIARY"][key] = category_asset_maps["INTERMEDIARY"].get(key, 0.0) + amount_val
                else:
                    category_usd_totals["UNRESOLVED"] += usd_val
                    category_asset_maps["UNRESOLVED"][key] = category_asset_maps["UNRESOLVED"].get(key, 0.0) + amount_val

        traced_amount_usd = (
            category_usd_totals["VASP"]
            + category_usd_totals["MIXER"]
            + category_usd_totals["BRIDGE"]
            + category_usd_totals["INTERMEDIARY"]
        )

        unresolved_amount_usd = max(0.0, total_victim_loss_usd - traced_amount_usd) + category_usd_totals["UNRESOLVED"]

        # Build asset breakdown list
        asset_breakdowns: List[AssetValue] = [
            AssetValue(
                asset=asset,
                chain=Chain(chain_str) if chain_str in Chain._value2member_map_ else Chain.ETHEREUM,
                amount=str(round(amt, 6)),
                normalized_usd=normalize_to_usd(str(amt), asset),
                valuation_timestamp=datetime.now(timezone.utc),
                valuation_source="ESTIMATED_MARKET_FIXTURE",
            )
            for (asset, chain_str), amt in victim_asset_map.items()
        ]

        # Build category breakdowns
        category_flows: List[CategoryFlowBreakdown] = []
        for cat_name, usd_tot in category_usd_totals.items():
            pct = round((usd_tot / total_victim_loss_usd * 100.0), 2) if total_victim_loss_usd > 0 else 0.0
            cat_asset_vals = [
                AssetValue(
                    asset=asset,
                    chain=Chain(chain_str) if chain_str in Chain._value2member_map_ else Chain.ETHEREUM,
                    amount=str(round(amt, 6)),
                    normalized_usd=normalize_to_usd(str(amt), asset),
                    valuation_timestamp=datetime.now(timezone.utc),
                )
                for (asset, chain_str), amt in category_asset_maps[cat_name].items()
            ]
            category_flows.append(
                CategoryFlowBreakdown(
                    category=cat_name,
                    amount=str(round(usd_tot, 2)),
                    percentage=pct,
                    asset_values=cat_asset_vals,
                )
            )

        return FundFlowSummary(
            case_id=self.trace.case_id,
            total_victim_loss_usd=round(total_victim_loss_usd, 2),
            traced_amount_usd=round(traced_amount_usd, 2),
            unresolved_amount_usd=round(unresolved_amount_usd, 2),
            vasp_linked_amount_usd=round(category_usd_totals["VASP"], 2),
            mixer_linked_amount_usd=round(category_usd_totals["MIXER"], 2),
            bridge_linked_amount_usd=round(category_usd_totals["BRIDGE"], 2),
            intermediary_held_amount_usd=round(category_usd_totals["INTERMEDIARY"], 2),
            asset_breakdowns=asset_breakdowns,
            category_flows=category_flows,
            propagated_hops=propagated_hops,
            calculated_at=datetime.now(timezone.utc),
        )
