"""Persistence boundary for normalized cross-chain observations and links."""
from datetime import datetime, timezone
from uuid import UUID, uuid4
import json
import asyncpg

from .domain import *


class CrossChainPersistenceMixin:
    async def persist_cross_chain_observation(self, case_id: str, observation: CrossChainObservationCreate):
        from .persistence import DatabaseError
        transfer=observation.transfer; now=datetime.now(timezone.utc)
        try:
            async with self._require_pool().acquire() as conn:
                async with conn.transaction():
                    case_uuid=UUID(case_id)
                    if not await conn.fetchval("SELECT 1 FROM cases WHERE case_id=$1",case_uuid): return None
                    await conn.execute("INSERT INTO chain_addresses(chain,address,created_at) VALUES($1,$2,$3) ON CONFLICT DO NOTHING",transfer.chain,normalize_address(transfer.chain,transfer.source),now)
                    await conn.execute("INSERT INTO chain_addresses(chain,address,created_at) VALUES($1,$2,$3) ON CONFLICT DO NOTHING",transfer.chain,normalize_address(transfer.chain,transfer.destination),now)
                    tx_id=await conn.fetchval("SELECT transaction_id FROM transactions WHERE chain=$1 AND tx_hash=$2",transfer.chain,transfer.tx_hash.lower())
                    if not tx_id:
                        tx_id=await conn.fetchval("INSERT INTO transactions(transaction_id,chain,tx_hash,block_number,timestamp,status,from_address,to_address,native_value,raw_reference,created_at,provider,provider_retrieved_at) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13) RETURNING transaction_id",uuid4(),transfer.chain,transfer.tx_hash.lower(),transfer.block_number,transfer.timestamp,"OBSERVED",transfer.source,transfer.destination,transfer.value_native,json.dumps(transfer.raw_reference),now,transfer.provider,now)
                    await conn.execute("INSERT INTO transaction_transfers(transfer_id,transaction_id,transfer_type,asset,amount,source_address,destination_address,contract_address,token_id,decimals,raw_reference,created_at) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12) ON CONFLICT DO NOTHING",uuid4(),tx_id,transfer.transfer_type,transfer.asset,transfer.amount,transfer.source,transfer.destination,transfer.contract_address or "",transfer.token_id or "",transfer.decimals,json.dumps({**(transfer.raw_reference or {}),"cross_chain_observation":{"mode":observation.mode,"destination_chain":observation.destination_chain,"destination_address":observation.destination_address,"bridge_contract":observation.bridge_contract,"message_id":observation.message_id,"nonce":observation.nonce}}),now)
                    await conn.execute("INSERT INTO case_transactions(case_id,transaction_id,relation_type,created_at) VALUES($1,$2,'CROSS_CHAIN_OBSERVED',$3) ON CONFLICT DO NOTHING",case_uuid,tx_id,now)
            return True
        except (asyncpg.PostgresError,ValueError) as exc: raise DatabaseError("Cross-chain observation could not be persisted") from exc

    async def cross_chain_transfers(self, case_id: str):
        from .persistence import DatabaseError
        try:
            async with self._require_pool().acquire() as conn:
                rows=await conn.fetch("SELECT DISTINCT ON (t.chain,t.tx_hash,tt.source_address,tt.destination_address,tt.asset,tt.amount) t.chain,t.tx_hash,t.block_number,t.timestamp,t.from_address,t.to_address,t.native_value,t.provider,t.raw_reference,tt.transfer_type,tt.asset,tt.amount,tt.source_address,tt.destination_address,tt.contract_address,tt.token_id,tt.decimals,tt.raw_reference AS transfer_raw FROM transactions t JOIN case_transactions ct ON ct.transaction_id=t.transaction_id JOIN transaction_transfers tt ON tt.transaction_id=t.transaction_id WHERE ct.case_id=$1 ORDER BY t.chain,t.tx_hash,tt.source_address,tt.destination_address,tt.asset,tt.amount,tt.created_at",UUID(case_id))
            result=[]
            for row in rows:
                raw=row["transfer_raw"] or row["raw_reference"] or {}; raw=json.loads(raw) if isinstance(raw,str) else raw
                result.append(Transfer(tx_hash=row["tx_hash"],chain=row["chain"],block_number=row["block_number"],timestamp=row["timestamp"],source=row["source_address"] or row["from_address"],destination=row["destination_address"] or row["to_address"],asset=row["asset"],amount=row["amount"],value_native=float(row["native_value"]) if row["native_value"] is not None else None,provider=row["provider"] or "PostgreSQL",transfer_type=row["transfer_type"],contract_address=row["contract_address"] or None,token_id=row["token_id"] or None,decimals=row["decimals"],raw_reference=raw))
            return result
        except (asyncpg.PostgresError,ValueError) as exc: raise DatabaseError("Cross-chain observations could not be retrieved") from exc

    async def persist_bridge_definition(self, definition: BridgeDefinition):
        from .persistence import DatabaseError
        try:
            async with self._require_pool().acquire() as conn:
                await conn.execute("INSERT INTO bridge_definitions(bridge_id,name,supported_chains,deposit_contracts,withdrawal_contracts,router_contracts,token_mappings,event_signatures,confidence_policy,source,version,updated_at) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12) ON CONFLICT(bridge_id) DO UPDATE SET name=EXCLUDED.name,supported_chains=EXCLUDED.supported_chains,deposit_contracts=EXCLUDED.deposit_contracts,withdrawal_contracts=EXCLUDED.withdrawal_contracts,router_contracts=EXCLUDED.router_contracts,confidence_policy=EXCLUDED.confidence_policy,source=EXCLUDED.source,version=EXCLUDED.version,updated_at=EXCLUDED.updated_at",definition.bridge_id,definition.name,json.dumps([str(x) for x in definition.supported_chains]),json.dumps({str(k):v for k,v in definition.deposit_contracts.items()}),json.dumps({str(k):v for k,v in definition.withdrawal_contracts.items()}),json.dumps({str(k):v for k,v in definition.router_contracts.items()}),json.dumps([x.model_dump(mode="json") for x in definition.token_mappings]),json.dumps(definition.event_signatures),definition.confidence_policy,definition.source,definition.version,datetime.now(timezone.utc))
        except (asyncpg.PostgresError,ValueError) as exc: raise DatabaseError("Bridge definition could not be persisted") from exc

    async def persist_bridge_interaction(self, case_id: str, item: BridgeInteraction):
        from .persistence import DatabaseError
        try:
            async with self._require_pool().acquire() as conn:
                await conn.execute("INSERT INTO bridge_interactions(interaction_id,case_id,bridge_id,interaction_type,source_chain,destination_chain,transaction_hash,bridge_contract,source_address,recipient,asset,amount,timestamp,message_id,nonce,evidence_ids,confidence,source,explanation,raw_reference,created_at) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21) ON CONFLICT(case_id,bridge_id,transaction_hash,interaction_type) DO NOTHING",UUID(item.interaction_id),UUID(case_id),item.bridge_id,item.interaction_type,item.source_chain,item.destination_chain,item.transaction_hash,item.bridge_contract,item.source_address,item.recipient,item.asset,item.amount,item.timestamp,item.message_id,item.nonce,json.dumps(item.evidence_ids),item.confidence,item.source,item.explanation,json.dumps(item.raw_reference),datetime.now(timezone.utc))
        except (asyncpg.PostgresError,ValueError) as exc: raise DatabaseError("Bridge interaction could not be persisted") from exc

    async def persist_cross_chain_link(self, case_id: str, link: CrossChainLink):
        from .persistence import DatabaseError
        try:
            async with self._require_pool().acquire() as conn:
                await conn.execute("INSERT INTO cross_chain_links(link_id,case_id,source_chain,source_address,destination_chain,destination_address,source_transaction_hash,destination_transaction_hash,bridge_id,correlation_id,correlation_level,confidence_score,confidence_band,evidence_count,correlation_reasons,evidence_ids,provenance_source,explanation,observed_or_inferred,created_at) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20) ON CONFLICT(case_id,correlation_id) DO NOTHING",UUID(link.link_id),UUID(case_id),link.source.chain,link.source.address,link.destination.chain if link.destination else None,link.destination.address if link.destination else None,link.source_transaction_hash,link.destination_transaction_hash,link.bridge_id,link.correlation_id,link.correlation_level,link.confidence_score,link.confidence_band,link.evidence_count,json.dumps(link.correlation_reasons),json.dumps(link.evidence_ids),link.provenance_source,link.explanation,link.observed_or_inferred,link.created_at)
                for evidence_id in link.evidence_ids:
                    try: await conn.execute("INSERT INTO cross_chain_link_evidence(link_id,evidence_id) VALUES($1,$2) ON CONFLICT DO NOTHING",UUID(link.link_id),UUID(evidence_id))
                    except ValueError: continue
        except (asyncpg.PostgresError,ValueError) as exc: raise DatabaseError("Cross-chain link could not be persisted") from exc

    async def persist_cross_chain_trace(self, trace: CrossChainTrace):
        from .persistence import DatabaseError
        try:
            async with self._require_pool().acquire() as conn:
                async with conn.transaction():
                    await conn.execute("INSERT INTO cross_chain_trace_runs(trace_id,case_id,root_chain,root_address,chains,limits,status,cross_chain_hops,node_count,edge_count,created_at) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)",UUID(trace.trace_id),UUID(trace.case_id),trace.root.chain,trace.root.address,json.dumps([str(x) for x in trace.chains_visited]),json.dumps({"max_hops":trace.max_hops,"max_cross_chain_hops":trace.max_cross_chain_hops,"max_nodes":trace.max_nodes,"max_edges":trace.max_edges,"max_bridge_interactions":trace.max_bridge_interactions,"max_transactions":trace.max_transactions}),trace.status,trace.cross_chain_hops,len(trace.nodes),len(trace.edges),datetime.now(timezone.utc))
                    for node in trace.nodes:
                        await conn.execute("INSERT INTO cross_chain_trace_nodes(trace_id,node_id,chain,address,node_type,metadata) VALUES($1,$2,$3,$4,$5,$6) ON CONFLICT DO NOTHING",UUID(trace.trace_id),node.node_id,node.chain,node.address,node.node_type,json.dumps(node.metadata))
                    for edge in trace.edges:
                        await conn.execute("INSERT INTO cross_chain_trace_edges(trace_id,edge_id,edge_type,source_node,destination_node,chain,destination_chain,transaction_hash,destination_transaction_hash,asset,amount,timestamp,bridge_id,link_id,confidence_band,evidence_ids,observed_or_inferred,metadata) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18) ON CONFLICT DO NOTHING",UUID(trace.trace_id),UUID(edge.edge_id),edge.edge_type,edge.source_node,edge.destination_node,edge.chain,edge.destination_chain,edge.transaction_hash,edge.destination_transaction_hash,edge.asset,edge.amount,edge.timestamp,edge.bridge_id,UUID(edge.link_id) if edge.link_id else None,edge.confidence_band,json.dumps(edge.evidence_ids),edge.observed_or_inferred,json.dumps(edge.metadata))
            return trace
        except (asyncpg.PostgresError,ValueError) as exc: raise DatabaseError("Cross-chain trace could not be persisted") from exc

    async def cross_chain_links(self, case_id: str):
        from .persistence import DatabaseError
        try:
            async with self._require_pool().acquire() as conn: rows=await conn.fetch("SELECT * FROM cross_chain_links WHERE case_id=$1 ORDER BY created_at DESC",UUID(case_id))
            return [CrossChainLink(link_id=str(r["link_id"]),source=ChainAddress(chain=r["source_chain"],address=r["source_address"]),destination=ChainAddress(chain=r["destination_chain"],address=r["destination_address"]) if r["destination_address"] else None,source_transaction_hash=r["source_transaction_hash"],destination_transaction_hash=r["destination_transaction_hash"],bridge_id=r["bridge_id"],correlation_id=r["correlation_id"],correlation_level=r["correlation_level"],confidence_score=float(r["confidence_score"]),confidence_band=r["confidence_band"],evidence_count=r["evidence_count"],correlation_reasons=r["correlation_reasons"] or [],evidence_ids=r["evidence_ids"] or [],provenance_source=r["provenance_source"],explanation=r["explanation"],observed_or_inferred=r["observed_or_inferred"],created_at=r["created_at"]) for r in rows]
        except (asyncpg.PostgresError,ValueError) as exc: raise DatabaseError("Cross-chain links could not be retrieved") from exc

    async def persist_cross_chain_patterns(self, patterns: list[CrossChainPatternObservation]):
        from .persistence import DatabaseError
        try:
            async with self._require_pool().acquire() as conn:
                for item in patterns:
                    await conn.execute("INSERT INTO cross_chain_pattern_observations(pattern_id,case_id,trace_id,pattern_type,status,confidence_level,severity,description,explanation,link_ids,evidence_ids,metadata,fingerprint,observed_at,created_at) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15) ON CONFLICT(fingerprint) DO NOTHING",UUID(item.pattern_id),UUID(item.case_id),UUID(item.trace_id),item.pattern_type,item.status,item.confidence_level,item.severity,item.description,item.explanation,json.dumps(item.link_ids),json.dumps(item.evidence_ids),json.dumps(item.metadata),item.fingerprint,item.observed_at,datetime.now(timezone.utc))
            return patterns
        except (asyncpg.PostgresError,ValueError) as exc: raise DatabaseError("Cross-chain patterns could not be persisted") from exc

    async def cross_chain_patterns(self, case_id: str):
        from .persistence import DatabaseError
        try:
            async with self._require_pool().acquire() as conn: rows=await conn.fetch("SELECT * FROM cross_chain_pattern_observations WHERE case_id=$1 ORDER BY observed_at DESC",UUID(case_id))
            return [CrossChainPatternObservation(pattern_id=str(r["pattern_id"]),case_id=str(r["case_id"]),trace_id=str(r["trace_id"]),pattern_type=r["pattern_type"],status=r["status"],confidence_level=r["confidence_level"],severity=r["severity"],description=r["description"],explanation=r["explanation"],link_ids=r["link_ids"] or [],evidence_ids=r["evidence_ids"] or [],metadata=r["metadata"] or {},fingerprint=r["fingerprint"],observed_at=r["observed_at"]) for r in rows]
        except (asyncpg.PostgresError,ValueError) as exc: raise DatabaseError("Cross-chain patterns could not be retrieved") from exc
