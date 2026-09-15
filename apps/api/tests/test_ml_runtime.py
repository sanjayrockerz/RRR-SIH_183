import sys
from datetime import datetime, timezone, timedelta

import pytest

sys.path.insert(0, "apps/api")
from app.ml.features import FEATURES, extract_features, feature_hash


class FakeConn:
    async def fetch(self, query, chain, address):
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        return [
            {"tx_hash": "0x1", "from_address": "0x" + "a" * 40, "to_address": address, "timestamp": now, "native_value": 2, "transfer_type": "native", "contract_address": None},
            {"tx_hash": "0x2", "from_address": address, "to_address": "0x" + "b" * 40, "timestamp": now + timedelta(minutes=10), "native_value": 1, "transfer_type": "token", "contract_address": "0x" + "c" * 40},
        ]

    async def __aenter__(self): return self
    async def __aexit__(self, *args): pass


class FakePool:
    def acquire(self): return FakeConn()


class FakeRepo:
    def __init__(self): self.pool = FakePool()
    def _require_pool(self): return self.pool


@pytest.mark.asyncio
async def test_runtime_feature_order_and_hash():
    address = "0x" + "d" * 40
    features = await extract_features(FakeRepo(), "ethereum", address)
    assert list(features) == FEATURES
    assert features["incoming_tx_count"] == 1
    assert features["outgoing_tx_count"] == 1
    assert features["token_transfer_count"] == 1
    assert len(feature_hash(features)) == 64
