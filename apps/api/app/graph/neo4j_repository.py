from __future__ import annotations

import hashlib
from ..domain import TraceResult, normalize_address
from .graph_models import GraphQueryResult
from .neo4j_client import Neo4jClient


def deterministic_id(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


class Neo4jGraphRepository:
    def __init__(self, client: Neo4jClient):
        self.client = client

    async def project_trace(self, trace: TraceResult) -> int:
        if not self.client.driver:
            raise RuntimeError(self.client.detail)
        for constraint in (
            "CREATE CONSTRAINT case_id IF NOT EXISTS FOR (n:Case) REQUIRE n.case_id IS UNIQUE",
            "CREATE CONSTRAINT wallet_node_id IF NOT EXISTS FOR (n:Wallet) REQUIRE n.node_id IS UNIQUE",
            "CREATE CONSTRAINT transaction_id IF NOT EXISTS FOR (n:Transaction) REQUIRE n.transaction_id IS UNIQUE",
            "CREATE CONSTRAINT evidence_id IF NOT EXISTS FOR (n:Evidence) REQUIRE n.evidence_id IS UNIQUE",
            "CREATE CONSTRAINT chain_id IF NOT EXISTS FOR (n:Chain) REQUIRE n.chain_id IS UNIQUE",
        ):
            await self.client.run(constraint)
        await self.client.run("MERGE (c:Case {case_id:$case_id}) SET c.updated_at=$updated_at", case_id=trace.case_id, updated_at=trace.trace_id)
        for node in trace.nodes:
            chain = node.chain.value if hasattr(node.chain, "value") else str(node.chain)
            node_id = f"{chain}:{normalize_address(node.chain,node.address)}"
            await self.client.run("""
                MERGE (w:Wallet {node_id:$node_id})
                SET w.address=$address,w.chain=$chain,w.node_type=$node_type,w.transaction_count=$transaction_count,
                    w.first_seen=$first_seen,w.last_seen=$last_seen
                MERGE (c:Case {case_id:$case_id})
                MERGE (c)-[:CONTAINS]->(w)
                MERGE (ch:Chain {chain_id:$chain})
                MERGE (w)-[:ON_CHAIN]->(ch)
            """, node_id=node_id, address=normalize_address(node.chain,node.address), chain=chain, node_type=node.node_type, transaction_count=node.transaction_count, first_seen=node.first_seen.isoformat() if node.first_seen else None, last_seen=node.last_seen.isoformat() if node.last_seen else None, case_id=trace.case_id)
        projected = 0
        for edge in trace.edges:
            transfer=edge.transfer
            chain=transfer.chain.value if hasattr(transfer.chain,"value") else str(transfer.chain)
            source_id=f"{chain}:{normalize_address(transfer.chain,edge.source)}"; target_id=f"{chain}:{normalize_address(transfer.chain,edge.target)}"
            tx_id=deterministic_id("transaction",chain,transfer.tx_hash.lower())
            event_id=deterministic_id("edge",trace.case_id,chain,transfer.tx_hash.lower(),normalize_address(transfer.chain,edge.source),normalize_address(transfer.chain,edge.target),transfer.asset,transfer.amount,str(edge.hop))
            await self.client.run("""
                MERGE (s:Wallet {node_id:$source_id}) SET s.address=$source,s.chain=$chain
                MERGE (d:Wallet {node_id:$target_id}) SET d.address=$target,d.chain=$chain
                MERGE (t:Transaction {transaction_id:$tx_id})
                SET t.tx_hash=$tx_hash,t.chain=$chain,t.block_number=$block_number,t.timestamp=$timestamp,
                    t.asset=$asset,t.amount=$amount,t.provider=$provider,t.evidence_id=$evidence_id
                MERGE (c:Case {case_id:$case_id})
                MERGE (c)-[:CONTAINS]->(s)
                MERGE (c)-[:CONTAINS]->(d)
                MERGE (s)-[:PARTICIPATED_IN]->(t)
                MERGE (t)-[:TRANSFERS]->(d)
                MERGE (s)-[r:SENT {event_id:$event_id}]->(d)
                SET r.tx_hash=$tx_hash,r.chain=$chain,r.asset=$asset,r.amount=$amount,r.hop=$hop,
                    r.block_number=$block_number,r.timestamp=$timestamp,r.evidence_id=$evidence_id,
                    r.direction=$direction
            """,source_id=source_id,target_id=target_id,source=normalize_address(transfer.chain,edge.source),target=normalize_address(transfer.chain,edge.target),chain=chain,tx_id=tx_id,tx_hash=transfer.tx_hash.lower(),block_number=transfer.block_number,timestamp=transfer.timestamp.isoformat() if transfer.timestamp else None,asset=transfer.asset,amount=transfer.amount,provider=transfer.provider,evidence_id=edge.evidence_id,case_id=trace.case_id,event_id=event_id,hop=edge.hop,direction="FORWARD" if trace.direction.value=="forward" else "BACKWARD")
            if edge.evidence_id:
                await self.client.run("""
                    MERGE (e:Evidence {evidence_id:$evidence_id})
                    SET e.case_id=$case_id,e.tx_hash=$tx_hash,e.chain=$chain
                    MERGE (t:Transaction {transaction_id:$tx_id})
                    MERGE (t)-[:SUPPORTED_BY]->(e)
                """, evidence_id=edge.evidence_id,case_id=trace.case_id,tx_hash=transfer.tx_hash.lower(),chain=chain,tx_id=tx_id)
            projected += 1
        return projected

    async def neighbors(self, case_id: str, address: str, depth: int = 1) -> GraphQueryResult:
        depth=max(1,min(depth,5))
        rows=await self.client.run("""
            MATCH (c:Case {case_id:$case_id})-[:CONTAINS]->(root:Wallet {address:$address})
            MATCH p=(root)-[:SENT|RECEIVED*1..5]-(neighbor:Wallet)
            WHERE length(p) <= $depth
            RETURN collect(DISTINCT {id:neighbor.node_id,address:neighbor.address,chain:neighbor.chain,type:neighbor.node_type}) AS nodes,
              collect(DISTINCT [rel IN relationships(p) | {id:rel.event_id,tx_hash:rel.tx_hash,chain:rel.chain,asset:rel.asset,amount:rel.amount,evidence_id:rel.evidence_id}]) AS paths
        """,case_id=case_id,address=address.lower(),depth=depth)
        row=rows[0] if rows else {"nodes":[],"paths":[]}
        edges=[edge for path in row.get("paths",[]) for edge in path]
        return GraphQueryResult(case_id=case_id,nodes=row.get("nodes",[]),edges=edges,evidence_ids=list(dict.fromkeys(e.get("evidence_id") for e in edges if e.get("evidence_id"))),note="Neo4j relationship projection; PostgreSQL remains authoritative.")

    async def shortest_path(self, case_id: str, source: str, destination: str) -> GraphQueryResult:
        rows=await self.client.run("""
            MATCH (c:Case {case_id:$case_id})-[:CONTAINS]->(s:Wallet {address:$source}),
                  (c)-[:CONTAINS]->(d:Wallet {address:$destination})
            MATCH p=shortestPath((s)-[:SENT|RECEIVED*..12]-(d))
            RETURN [n IN nodes(p) | {id:n.node_id,address:n.address,chain:n.chain,type:n.node_type}] AS nodes,
              [r IN relationships(p) | {id:r.event_id,tx_hash:r.tx_hash,chain:r.chain,asset:r.asset,amount:r.amount,evidence_id:r.evidence_id}] AS edges
        """,case_id=case_id,source=source.lower(),destination=destination.lower())
        row=rows[0] if rows else {"nodes":[],"edges":[]}
        edges=row.get("edges",[])
        return GraphQueryResult(case_id=case_id,nodes=row.get("nodes",[]),edges=edges,evidence_ids=list(dict.fromkeys(e.get("evidence_id") for e in edges if e.get("evidence_id"))),note="Shortest observed relationship in the Neo4j projection; not a criminality conclusion.")
