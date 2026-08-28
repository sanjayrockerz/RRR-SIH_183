"""Selection of the one defensible investigative fund-flow path."""

from collections import deque
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from .attribution import AttributionEngine
from .domain import AttributionRole, ConfidenceLevel, EntityType, GraphEdge, TraceResult

_RANK = {ConfidenceLevel.UNKNOWN: 0, ConfidenceLevel.LOW: 1, ConfidenceLevel.MEDIUM: 2, ConfidenceLevel.HIGH: 3, ConfidenceLevel.CONFIRMED: 4}
_TERMINAL_TYPES = {EntityType.VASP, EntityType.EXCHANGE, EntityType.CUSTODIAL_SERVICE}
_DEPOSIT_ROLES = {AttributionRole.DEPOSIT, AttributionRole.DEPOSIT_ADDRESS, AttributionRole.HOT_WALLET, AttributionRole.COLD_WALLET, AttributionRole.TREASURY}


def _key(chain, address: str) -> str:
    return f"{chain.value if hasattr(chain, 'value') else chain}:{address.lower()}"


def _paths_from_root(trace: TraceResult):
    root = _key(trace.edges[0].transfer.chain if trace.edges else "ethereum", trace.root_address)
    adjacency: dict[str, list[tuple[str, GraphEdge]]] = {}
    for edge in trace.edges:
        # A backward trace may describe inbound discovery, but its persisted
        # edge still means sender -> recipient. Never reverse on-chain facts to
        # make a visual path connect.
        source_address, target_address = edge.source, edge.target
        source = _key(edge.transfer.chain, source_address)
        target = _key(edge.transfer.chain, target_address)
        adjacency.setdefault(source, []).append((target, edge))
    for edges in adjacency.values():
        # Persisted row order must never decide the investigative path.
        edges.sort(key=lambda item: (
            item[1].transfer.timestamp or datetime.min.replace(tzinfo=timezone.utc),
            item[1].transaction_hash.lower(),
            item[0],
        ))
    queue = deque([(root, [root], [])])
    results = []
    while queue:
        current, nodes, edges = queue.popleft()
        results.append((nodes, edges))
        last_timestamp = edges[-1].transfer.timestamp if edges else None
        for target, edge in adjacency.get(current, []):
            edge_timestamp = edge.transfer.timestamp
            if last_timestamp and edge_timestamp and edge_timestamp < last_timestamp:
                continue
            if target not in nodes:
                queue.append((target, nodes + [target], edges + [edge]))
    return results


def select_primary_path(trace: TraceResult, entities, sources, records) -> dict:
    """Choose nearest reliable VASP endpoint, otherwise a leaf as unknown.

    The path is built from persisted directed transfers. Attribution only selects
    an endpoint; it never changes the underlying observed edges.
    """
    paths = _paths_from_root(trace)
    node_by_key = {_key(node.chain, node.address): node for node in trace.nodes}
    engine = AttributionEngine(entities, sources, records)
    attributed = []
    for node_key, node in node_by_key.items():
        resolved = engine.resolve(node.chain, node.address)
        if resolved.conflict or not resolved.selected_entity_id:
            continue
        candidate = next((item for item in resolved.candidates if item.entity.entity_id == resolved.selected_entity_id), None)
        if not candidate or candidate.entity.entity_type not in _TERMINAL_TYPES:
            continue
        role = candidate.attributions[0].role if candidate.attributions else AttributionRole.UNKNOWN
        source_rank = max((_RANK.get(source.reliability_level, 0) for source in candidate.supporting_sources), default=0)
        # Only paths that end at this address are candidates. A path that
        # continues beyond a confirmed endpoint is not the primary path.
        for path_nodes, path_edges in paths:
            if not path_edges or path_nodes[-1] != node_key:
                continue
            # Do not select a route that passed through another confirmed
            # terminal. Once a route reaches a defensible VASP/custodian, it
            # is complete even if later unrelated transfers are observed.
            if any(
                prior != node_key
                and (prior_node := node_by_key.get(prior)) is not None
                and (
                    (prior_resolution := engine.resolve(prior_node.chain, prior_node.address)).selected_entity_id
                    and not prior_resolution.conflict
                    and any(
                        item.entity.entity_type in _TERMINAL_TYPES
                        for item in prior_resolution.candidates
                        if item.entity.entity_id == prior_resolution.selected_entity_id
                    )
                )
                for prior in path_nodes[:-1]
            ):
                continue
            attributed.append((
                _path_risk_relevance(trace, path_edges),
                _RANK[candidate.confidence],
                1 if role in _DEPOSIT_ROLES else 0,
                source_rank,
                _path_sort_key(path_edges, node.address),
                candidate.entity.name.lower(),
                node.address.lower(),
                path_nodes,
                path_edges,
                node,
                candidate,
                role,
            ))
    if attributed:
        selected = max(attributed, key=lambda item: item[:7])
        _, _, _, _, _, _, _, path_nodes, path_edges, node, candidate, role = selected
        evidence_ids = sorted({edge.evidence_id for edge in path_edges if edge.evidence_id})
        return {
            "status": "ATTRIBUTED", "root_address": trace.root_address, "node_ids": [node_by_key[item].address for item in path_nodes if item in node_by_key],
            "transaction_hashes": [edge.transaction_hash for edge in path_edges], "hops": len(path_edges),
            "edge_ids": [edge.edge_id for edge in path_edges],
            **_path_measurements(path_edges),
            "terminal_address": node.address, "terminal_entity_id": candidate.entity.entity_id, "terminal_entity_name": candidate.entity.name,
            "terminal_entity_type": candidate.entity.entity_type, "terminal_role": role, "attribution": candidate.confidence,
            "why": "Highest-confidence attributable terminal reached by a directed, chronological, cycle-free path; asset continuity, meaningful transfer values, hop continuity, and evidence references were used to break ties. Traversal stops at this endpoint.",
            "evidence_ids": evidence_ids, "attribution_records": [item.attribution_id for item in candidate.attributions],
        }
    flow_sources = {_key(edge.transfer.chain, edge.source) for edge in trace.edges}
    leaves = [(nodes, edges) for nodes, edges in paths if edges and nodes[-1] not in flow_sources]
    if not leaves:
        leaves = [(nodes, edges) for nodes, edges in paths if edges]
    if not leaves:
        return {"status": "UNATTRIBUTED", "root_address": trace.root_address, "node_ids": [trace.root_address], "transaction_hashes": [], "edge_ids": [], "hops": 0, **_path_measurements([]), "terminal_address": None, "terminal_entity_id": None, "terminal_entity_name": "UNKNOWN / UNATTRIBUTED DESTINATION", "terminal_entity_type": "UNKNOWN", "terminal_role": "UNKNOWN", "attribution": "UNKNOWN", "why": "No reliable VASP, exchange, or custodian attribution is available in the persisted intelligence catalog.", "evidence_ids": [], "attribution_records": []}
    nodes, edges = max(leaves, key=lambda item: _path_sort_key(item[1], node_by_key[item[0][-1]].address if item[0][-1] in node_by_key else item[0][-1]))
    addresses = [node_by_key[item].address for item in nodes if item in node_by_key]
    return {"status": "UNATTRIBUTED", "root_address": trace.root_address, "node_ids": addresses, "transaction_hashes": [edge.transaction_hash for edge in edges], "edge_ids": [edge.edge_id for edge in edges], "hops": len(edges), **_path_measurements(edges), "terminal_address": addresses[-1] if addresses else None, "terminal_entity_id": None, "terminal_entity_name": "UNKNOWN / UNATTRIBUTED DESTINATION", "terminal_entity_type": "UNKNOWN", "terminal_role": "UNKNOWN", "attribution": "UNKNOWN", "why": "No reliable VASP, exchange, or custodian attribution is available; the endpoint is the terminal observed destination of this directed path.", "evidence_ids": sorted({edge.evidence_id for edge in edges if edge.evidence_id}), "attribution_records": []}


def _path_risk_relevance(trace: TraceResult, edges: list[GraphEdge]) -> tuple:
    """Return a stable risk-evidence key for candidate path ranking.

    This only rewards risk signals that actually reference a selected edge or
    one of its endpoints. It never treats the existence of a case-wide signal
    as evidence for an unrelated candidate route.
    """
    txs = {edge.transaction_hash.lower() for edge in edges if edge.transaction_hash}
    addresses = {value.lower() for edge in edges for value in (edge.source, edge.target) if value}
    severity = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
    matched = [
        signal for signal in trace.signals
        if txs.intersection(value.lower() for value in signal.supporting_transaction_hashes)
        or addresses.intersection(value.lower() for value in signal.supporting_addresses)
    ]
    score = sum(severity.get(str(signal.severity).upper(), 0) * max(0.0, float(signal.confidence)) for signal in matched)
    return (round(score, 6), len(matched))


def _path_sort_key(edges: list[GraphEdge], terminal: str = ""):
    """Stable quality key for an observed path; larger values are stronger."""
    amounts = []
    for edge in edges:
        try:
            value = Decimal(edge.transfer.amount)
            if value > 0:
                amounts.append(value)
        except (InvalidOperation, ValueError):
            continue
    assets = [edge.transfer.asset for edge in edges]
    continuity = sum(1 for before, after in zip(assets, assets[1:]) if before == after)
    timestamps = [edge.transfer.timestamp for edge in edges if edge.transfer.timestamp]
    chronological = int(all(before <= after for before, after in zip(timestamps, timestamps[1:])))
    evidence = len({edge.evidence_id for edge in edges if edge.evidence_id})
    # Max() uses this tuple. Negative hop count makes shorter equally-good
    # paths win, while the final transaction tuple makes ties deterministic.
    return (chronological, continuity, len(amounts), sum(amounts, Decimal("0")), evidence, -len(edges), tuple(edge.transaction_hash.lower() for edge in edges), terminal.lower())


def _path_measurements(edges: list[GraphEdge]) -> dict:
    totals: dict[str, Decimal] = {}
    timestamps = [edge.transfer.timestamp for edge in edges if edge.transfer.timestamp]
    for edge in edges:
        try:
            totals[edge.transfer.asset] = totals.get(edge.transfer.asset, Decimal("0")) + Decimal(edge.transfer.amount)
        except (InvalidOperation, ValueError):
            totals.setdefault(edge.transfer.asset, Decimal("0"))
    total_value = " + ".join(
        f"{amount.normalize():f} {asset}" for asset, amount in sorted(totals.items())
    ) or "UNKNOWN"
    duration = (max(timestamps) - min(timestamps)).total_seconds() if len(timestamps) > 1 else None
    return {
        "transaction_count": len(edges),
        "total_transferred_value": total_value,
        "path_duration_seconds": duration,
    }
