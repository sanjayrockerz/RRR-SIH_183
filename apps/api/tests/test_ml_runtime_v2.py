import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, "apps/api")

from app.ml.features import FEATURES, FeatureSchemaError, InsufficientDataError, extract_features
from app.ml.inference import WalletMLRiskService
from app.ml.model_loader import get_wallet_risk_model
from app.ml_persistence import MLPersistenceMixin
from app.ml.schemas import MLModelStatus


ADDRESS = "0x" + "d" * 40


class FakeConn:
    def __init__(self, rows): self.rows = rows
    async def fetch(self, query, *args): return self.rows
    async def __aenter__(self): return self
    async def __aexit__(self, *args): pass


class FakePool:
    def __init__(self, rows): self.rows = rows
    def acquire(self): return FakeConn(self.rows)


class FakeRepo:
    def __init__(self, rows): self.pool = FakePool(rows); self.persisted = []
    def _require_pool(self): return self.pool
    async def get(self, case_id): return None
    async def persist_ml_inference(self, record): self.persisted.append(record); return record


def rows_for(address=ADDRESS):
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [
        {"tx_hash": "0x1", "from_address": "0x" + "a" * 40, "to_address": address, "timestamp": now, "native_value": 2, "transfer_type": "native", "contract_address": None},
        {"tx_hash": "0x2", "from_address": address, "to_address": "0x" + "b" * 40, "timestamp": now + timedelta(minutes=10), "native_value": 1, "transfer_type": "token", "contract_address": "0x" + "c" * 40},
    ]


def test_frozen_model_loader_uses_approved_artifact():
    loaded = get_wallet_risk_model()
    assert len(loaded.metadata["feature_order"]) == 41
    assert loaded.metadata["feature_order"] == FEATURES


@pytest.mark.asyncio
async def test_ready_inference_persists_full_provenance():
    repo = FakeRepo(rows_for())
    result = await WalletMLRiskService(repo).assess_result("00000000-0000-0000-0000-000000000001", ADDRESS, "ethereum")
    assert result.status == MLModelStatus.READY
    assert len(result.top_features) <= 5
    assert len(result.feature_hash) == 64
    assert repo.persisted[0]["features"]
    assert repo.persisted[0]["provenance"]["model_sha256"]


@pytest.mark.asyncio
async def test_unsupported_chain_fails_closed_without_persistence():
    repo = FakeRepo(rows_for())
    result = await WalletMLRiskService(repo).assess_result("00000000-0000-0000-0000-000000000001", ADDRESS, "tron")
    assert result.status == MLModelStatus.UNSUPPORTED_CHAIN
    assert len(repo.persisted) == 1
    assert repo.persisted[0]["status"] == "UNSUPPORTED_CHAIN"


@pytest.mark.asyncio
async def test_empty_wallet_is_insufficient_data():
    repo = FakeRepo([])
    result = await WalletMLRiskService(repo).assess_result("00000000-0000-0000-0000-000000000001", ADDRESS, "ethereum")
    assert result.status == MLModelStatus.INSUFFICIENT_DATA
    assert len(repo.persisted) == 1
    assert repo.persisted[0]["status"] == "INSUFFICIENT_DATA"


class PersistConn:
    def __init__(self): self.statements = []
    async def execute(self, query, *args): self.statements.append((query, args))
    async def __aenter__(self): return self
    async def __aexit__(self, *args): pass


class PersistPool:
    def __init__(self): self.conn = PersistConn()
    def acquire(self): return self.conn


class PersistRepo(MLPersistenceMixin):
    def __init__(self): self.pool = PersistPool()
    def _require_pool(self): return self.pool


@pytest.mark.asyncio
async def test_append_only_persistence_creates_two_historical_rows():
    repo = PersistRepo()
    base = {"case_id": "00000000-0000-0000-0000-000000000001", "wallet_id": None, "chain": "ethereum", "address": ADDRESS, "model_version": "rrr_ethereum_wallet_xgb_v2", "feature_schema_version": "RRRFeatureSchemaV2", "probability": .7, "classification": "HIGH_RISK_LIKE", "threshold": .63, "feature_hash": "a" * 64, "features": {"x": 1.0}, "top_features": [], "generated_at": datetime.now(timezone.utc), "provenance": {"model_sha256": "b" * 64, "metadata_sha256": "c" * 64}}
    first = await repo.create_assessment({"inference_id": "00000000-0000-0000-0000-000000000002", **base})
    second = await repo.create_assessment({"inference_id": "00000000-0000-0000-0000-000000000003", **base, "probability": .8})
    assert len(repo.pool.conn.statements) == 2
    assert first["inference_id"] != second["inference_id"]
    assert repo.pool.conn.statements[0][1][9] == .7
    assert repo.pool.conn.statements[1][1][9] == .8
    assert "INSERT INTO ml_wallet_assessments" in repo.pool.conn.statements[0][0]
