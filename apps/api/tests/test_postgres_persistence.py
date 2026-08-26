import os
from pathlib import Path
from uuid import uuid4
import asyncpg
import pytest
from app.domain import CaseCreate, WalletCreate, TransactionCreate, Chain, TraceResult, GraphNode, GraphEdge, Transfer, Evidence, DataMode
from app.persistence import PostgresCaseRepository

pytestmark = pytest.mark.skipif(not os.getenv("RUN_POSTGRES_TESTS"), reason="Set RUN_POSTGRES_TESTS=1 with PostgreSQL available")

@pytest.mark.asyncio
async def test_persistent_core_survives_reconnect():
    database_url=os.getenv("DATABASE_URL","postgresql://postgres:postgres@localhost:5432/crypto_fraud_intelligence")
    conn=await asyncpg.connect(database_url)
    migrations=Path(__file__).parents[2] / "infrastructure/postgres"
    await conn.execute((migrations / "001_initial.sql").read_text())
    await conn.execute((migrations / "002_blockchain_data_fabric.sql").read_text())
    await conn.execute((migrations / "003_trace_runs.sql").read_text())
    await conn.execute((migrations / "004_entity_attribution.sql").read_text())
    await conn.execute((migrations / "005_fraud_patterns.sql").read_text())
    await conn.execute((migrations / "006_risk_intelligence.sql").read_text())
    repo=PostgresCaseRepository(); repo.pool=await asyncpg.create_pool(database_url)
    try:
        first=await repo.create(CaseCreate(title="Persistence one",fraud_type="Phishing"))
        second=await repo.create(CaseCreate(title="Persistence two",fraud_type="Phishing"))
        wallet=WalletCreate(address="0x"+"a"*40,chain=Chain.ETHEREUM)
        await repo.add_wallet(first.case_id,wallet); await repo.add_wallet(first.case_id,wallet); await repo.add_wallet(second.case_id,wallet)
        tx_hash="0x"+"1"*64
        await repo.add_transaction(first.case_id,TransactionCreate(tx_hash=tx_hash,chain=Chain.ETHEREUM))
        await repo.add_transaction(second.case_id,TransactionCreate(tx_hash=tx_hash,chain=Chain.ETHEREUM))
        transfer=Transfer(tx_hash=tx_hash,chain=Chain.ETHEREUM,source="0x"+"a"*40,destination="0x"+"b"*40,asset="ETH",amount="1",value_native=1,provider="fixture")
        result=TraceResult(case_id=first.case_id,root_address=wallet.address,mode=DataMode.HISTORICAL,provider="fixture",nodes=[GraphNode(id=wallet.address,address=wallet.address,depth=0),GraphNode(id=transfer.destination,address=transfer.destination,depth=1)],edges=[GraphEdge(source=wallet.address,target=transfer.destination,transfer=transfer)],signals=[],evidence=[Evidence(evidence_id=str(uuid4()),case_id=first.case_id,type="TRANSACTION",chain=Chain.ETHEREUM,tx_hash=tx_hash,source="fixture",captured_at=transfer.timestamp or __import__("datetime").datetime.now(__import__("datetime").timezone.utc),metadata={})])
        await repo.persist_trace(result); await repo.persist_trace(result)
        await repo.close()
        reconnected=PostgresCaseRepository(); reconnected.pool=await asyncpg.create_pool(database_url)
        loaded=await reconnected.get(first.case_id)
        assert loaded and len(loaded.wallets)==1 and len(loaded.latest_trace.edges)==1 and len(loaded.latest_trace.evidence)==1
        counts=await conn.fetchrow("SELECT (SELECT count(*) FROM transactions WHERE chain='ethereum' AND tx_hash=$1) AS tx_count,(SELECT count(*) FROM case_transactions WHERE transaction_id=(SELECT transaction_id FROM transactions WHERE chain='ethereum' AND tx_hash=$1)) AS relation_count",(tx_hash,))
        assert counts["tx_count"]==1 and counts["relation_count"]==2
        await reconnected.close()
    finally:
        await conn.execute("DELETE FROM cases WHERE title IN ('Persistence one','Persistence two')")
        await conn.close()
