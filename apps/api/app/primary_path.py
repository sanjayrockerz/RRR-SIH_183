"""Selection of the one defensible investigative fund-flow path."""

from collections import deque
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
        source_address, target_address = (edge.target, edge.source) if trace.direction.value == "backward" else (edge.source, edge.target)
        source = _key(edge.transfer.chain, source_address)
        target = _key(edge.transfer.chain, target_address)
        adjacency.setdefault(source, []).append((target, edge))
    queue = deque([(root, [root], [])])
    results = []
    while queue:
        current, nodes, edges = queue.popleft()
        results.append((nodes, edges))
        for target, edge in adjacency.get(current, []):
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
        match = next(((nodes, edges) for nodes, edges in paths if node_key in nodes), None)
        if not match or not match[1]:
            continue
        path_nodes, path_edges = match
        role = candidate.attributions[0].role if candidate.attributions else AttributionRole.UNKNOWN
        source_rank = max((_RANK.get(source.reliability_level, 0) for source in candidate.supporting_sources), default=0)
        evidence_count = len({edge.evidence_id for edge in path_edges if edge.evidence_id})
        attributed.append((len(path_edges), -_RANK[candidate.confidence], -(1 if role in _DEPOSIT_ROLES else 0), -source_rank, -evidence_count, candidate.entity.name, path_nodes, path_edges, node, candidate, role))
    if attributed:
        attributed.sort(key=lambda item: item[:6])
        hops, _, _, _, _, _, path_nodes, path_edges, node, candidate, role = attributed[0]
        evidence_ids = sorted({edge.evidence_id for edge in path_edges if edge.evidence_id})
        return {
            "status": "ATTRIBUTED", "root_address": trace.root_address, "node_ids": [node_by_key[item].address for item in path_nodes if item in node_by_key],
            "transaction_hashes": [edge.transaction_hash for edge in path_edges], "hops": hops,
            "terminal_address": node.address, "terminal_entity_id": candidate.entity.entity_id, "terminal_entity_name": candidate.entity.name,
            "terminal_entity_type": candidate.entity.entity_type, "terminal_role": role, "attribution": candidate.confidence,
            "why": "Nearest attributable VASP or exchange receiving the traced fund flow; directed edge continuity is preserved and traversal stops at this endpoint.",
            "evidence_ids": evidence_ids, "attribution_records": [item.attribution_id for item in candidate.attributions],
        }
    flow_sources = {_key(edge.transfer.chain, edge.target if trace.direction.value == "backward" else edge.source) for edge in trace.edges}
    leaves = [(len(edges), -len({edge.evidence_id for edge in edges if edge.evidence_id}), nodes, edges) for nodes, edges in paths if edges and nodes[-1] not in flow_sources]
    if not leaves:
        leaves = [(len(edges), -len({edge.evidence_id for edge in edges if edge.evidence_id}), nodes, edges) for nodes, edges in paths if edges]
    if not leaves:
        return {"status": "UNATTRIBUTED", "root_address": trace.root_address, "node_ids": [trace.root_address], "transaction_hashes": [], "hops": 0, "terminal_address": None, "terminal_entity_id": None, "terminal_entity_name": "UNKNOWN / UNATTRIBUTED DESTINATION", "terminal_entity_type": "UNKNOWN", "terminal_role": "UNKNOWN", "attribution": "UNKNOWN", "why": "No reliable VASP, exchange, or custodian attribution is available in the persisted intelligence catalog.", "evidence_ids": [], "attribution_records": []}
    _, _, nodes, edges = max(leaves, key=lambda item: (item[0], item[1]))
    addresses = [node_by_key[item].address for item in nodes if item in node_by_key]
    return {"status": "UNATTRIBUTED", "root_address": trace.root_address, "node_ids": addresses, "transaction_hashes": [edge.transaction_hash for edge in edges], "hops": len(edges), "terminal_address": addresses[-1] if addresses else None, "terminal_entity_id": None, "terminal_entity_name": "UNKNOWN / UNATTRIBUTED DESTINATION", "terminal_entity_type": "UNKNOWN", "terminal_role": "UNKNOWN", "attribution": "UNKNOWN", "why": "No reliable VASP, exchange, or custodian attribution is available; the endpoint is the terminal observed destination of this directed path.", "evidence_ids": sorted({edge.evidence_id for edge in edges if edge.evidence_id}), "attribution_records": []}
