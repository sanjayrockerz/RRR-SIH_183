from __future__ import annotations

import logging
from ..domain import CapabilityStatus, TraceResult
from ..domain import DataMode, Evidence, GraphEdge, GraphNode, normalize_address
from ..realtime import IncrementalGraphUpdater
from .graph_models import GraphProjectionStatus
from .neo4j_client import Neo4jClient
from .neo4j_repository import Neo4jGraphRepository, deterministic_id

logger = logging.getLogger("crypto_fraud_intelligence")


class GraphProjectionService:
    """Best-effort projection of authoritative observations into Neo4j.

    Projection failure never changes the PostgreSQL trace result. Operators can
    retry projection explicitly once Neo4j becomes available.
    """

    def __init__(self, client: Neo4jClient):
        self.client = client
        self.repository = Neo4jGraphRepository(client)

    def status(self) -> GraphProjectionStatus:
        return GraphProjectionStatus(status=self.client.status, detail=self.client.detail)

    async def project(self, trace: TraceResult) -> int:
        try:
            count = await self.repository.project_trace(trace)
            logger.info("graph_projection_completed", extra={"case_id": trace.case_id, "trace_id": trace.trace_id, "edge_count": count})
            return count
        except Exception as exc:
            self.client.status = CapabilityStatus.UNAVAILABLE
            self.client.detail = f"Neo4j projection failed: {type(exc).__name__}"
            logger.warning("graph_projection_unavailable", extra={"case_id": trace.case_id, "error_type": type(exc).__name__})
            return 0

    async def project_incremental(self, case_id: str, event, graph_edge_id: str | None = None, evidence_id: str | None = None) -> int:
        """Project one already-normalized realtime observation as a bounded batch.

        PostgreSQL remains authoritative; this method only updates the optional
        Neo4j projection. It deliberately accepts the event produced by the
        existing realtime normalizer instead of accepting arbitrary provider
        payloads.
        """
        transfer = IncrementalGraphUpdater().transfer(event)
        edge_id = graph_edge_id or deterministic_id("realtime-edge", case_id, event.event_id)
        nodes = [
            GraphNode(id=f"{event.chain.value}:{normalize_address(event.chain,event.from_address)}", address=normalize_address(event.chain,event.from_address), chain=event.chain),
            GraphNode(id=f"{event.chain.value}:{normalize_address(event.chain,event.to_address)}", address=normalize_address(event.chain,event.to_address), chain=event.chain),
        ]
        evidence = []
        if evidence_id:
            evidence.append(Evidence(evidence_id=evidence_id, case_id=case_id, type="REALTIME_BLOCKCHAIN_OBSERVATION", chain=event.chain, tx_hash=event.transaction_hash, source=event.provider, captured_at=event.received_at, metadata={"event_id": event.event_id, "block_number": event.block_number}))
        trace = TraceResult(case_id=case_id, trace_id=f"realtime:{event.event_id}", root_address=normalize_address(event.chain,event.from_address), mode=DataMode.WEBHOOK, provider=event.provider, nodes=nodes, edges=[GraphEdge(edge_id=edge_id, source=normalize_address(event.chain,event.from_address), target=normalize_address(event.chain,event.to_address), transfer=transfer, hop=1, transaction_hash=event.transaction_hash, evidence_id=evidence_id)], signals=[], evidence=evidence, status="COMPLETED")
        return await self.project(trace)

    async def require_repository(self) -> Neo4jGraphRepository:
        if self.client.status != CapabilityStatus.SUPPORTED or not self.client.driver:
            raise RuntimeError(self.client.detail)
        return self.repository
