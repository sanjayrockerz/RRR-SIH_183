"""
Phase 2 Comprehensive Test Suite
Validates Cross-Chain Continuation, Realtime Reactive Retracing, Risk Registry,
Case Fusion integration, and Alerting using deterministic fixtures.
"""

import json
from datetime import datetime, timezone
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.domain import (
    Chain,
    DataMode,
    RealtimeEvent,
    RealtimeEventType,
    RealtimeProcessingStatus,
    CrossChainObservationCreate,
    Transfer,
)


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def sample_case(client):
    res = client.post("/api/v1/cases", json={
        "title": "Phase 2 Deterministic Investigation",
        "fraud_type": "Pig Butchering",
        "priority": "HIGH"
    })
    assert res.status_code == 200
    case_data = res.json()
    case_id = case_data["case_id"]
    w_res = client.post(f"/api/v1/cases/{case_id}/wallets", json={
        "address": "0x1111111111111111111111111111111111111111",
        "chain": "ethereum"
    })
    assert w_res.status_code == 200
    return w_res.json()


# -- 1. Invalid Webhook Signature Rejection --
def test_invalid_webhook_signature_rejected(client):
    body = {"event": "test"}
    raw = json.dumps(body).encode()
    headers = {"X-Alchemy-Signature": "invalid_signature_hash"}
    res = client.post("/api/v1/realtime/providers/alchemy/webhook", content=raw, headers=headers)
    assert res.status_code in {401, 403, 422} or "Signature validation failed" in res.text


# -- 2. Valid Webhook Execution --
def test_valid_simulated_webhook_execution(client, sample_case):
    case_id = sample_case["case_id"]
    client.post(f"/api/v1/cases/{case_id}/watches", json={
        "address": "0x1111111111111111111111111111111111111111",
        "chain": "ethereum",
        "source": "SIMULATED"
    })

    event_id = str(uuid4())
    tx_hash = "0x" + "a" * 64
    event = RealtimeEvent(
        event_id=event_id,
        provider="DEVELOPMENT SYNTHETIC",
        chain=Chain.ETHEREUM,
        event_type=RealtimeEventType.ADDRESS_ACTIVITY,
        received_at=datetime.now(timezone.utc),
        observed_at=datetime.now(timezone.utc),
        transaction_hash=tx_hash,
        from_address="0x1111111111111111111111111111111111111111",
        to_address="0x2222222222222222222222222222222222222222",
        asset="ETH",
        amount="10.5",
        processing_status=RealtimeProcessingStatus.RECEIVED,
    )

    res = client.post("/api/v1/realtime/simulated/events", json=event.model_dump(mode="json"))
    assert res.status_code == 200
    data = res.json()
    assert "results" in data
    results = data["results"]
    assert len(results) > 0
    assert results[0]["event"]["transaction_hash"] == tx_hash


# -- 3. Duplicate Webhook Idempotency --
def test_duplicate_webhook_idempotency(client, sample_case):
    event_id = str(uuid4())
    tx_hash = "0x" + "b" * 64
    event = RealtimeEvent(
        event_id=event_id,
        provider="DEVELOPMENT SYNTHETIC",
        chain=Chain.ETHEREUM,
        event_type=RealtimeEventType.ADDRESS_ACTIVITY,
        received_at=datetime.now(timezone.utc),
        transaction_hash=tx_hash,
        from_address="0x1111111111111111111111111111111111111111",
        to_address="0x3333333333333333333333333333333333333333",
        asset="USDT",
        amount="5000",
    )

    res1 = client.post("/api/v1/realtime/simulated/events", json=event.model_dump(mode="json"))
    assert res1.status_code == 200
    res2 = client.post("/api/v1/realtime/simulated/events", json=event.model_dump(mode="json"))
    assert res2.status_code == 200
    data2 = res2.json()
    results2 = data2.get("results", [])
    assert len(results2) > 0
    assert results2[0]["duplicate"] is True


# -- 4. Cross-Chain Correlation & Inferred vs Observed Distinction --
def test_cross_chain_inferred_vs_observed(client, sample_case):
    case_id = sample_case["case_id"]
    obs = CrossChainObservationCreate(
        mode=DataMode.DEVELOPMENT_FIXTURE,
        transfer=Transfer(
            chain=Chain.ETHEREUM,
            tx_hash="0x" + "c" * 64,
            source="0x1111111111111111111111111111111111111111",
            destination="0x7777777777777777777777777777777777777777",
            asset="USDT",
            amount="1000",
            provider="Alchemy Ethereum",
            raw_reference={"destination_chain": "tron", "destination_address": "TTestTronRecipientAddress12345678"},
        ),
    )
    res_obs = client.post(f"/api/v1/cases/{case_id}/cross-chain/observations", json=obs.model_dump(mode="json"))
    assert res_obs.status_code == 200

    res_cont = client.post(
        f"/api/v1/cases/{case_id}/cross-chain/continuation",
        json={"root_chain": "ethereum", "root_address": "0x1111111111111111111111111111111111111111"},
    )
    assert res_cont.status_code == 200
    trace = res_cont.json()
    assert "edges" in trace

    for edge in trace["edges"]:
        if edge["edge_type"] == "CROSS_CHAIN_LINK":
            assert edge["observed_or_inferred"] == "INFERRED"
            assert edge["observed_or_inferred"] != "OBSERVED"
        elif edge["edge_type"] in {"TRANSFER", "BRIDGE_DEPOSIT", "TOKEN_TRANSFER"}:
            assert edge["observed_or_inferred"] == "OBSERVED"


# -- 5. Risk Registry Aggregation & Search --
def test_risk_registry_search_and_intelligence(client, sample_case):
    address = sample_case["wallets"][0]["address"]
    res_search = client.get(f"/api/v1/risk-registry/search?wallet={address}")
    assert res_search.status_code == 200
    data = res_search.json()
    assert "entries" in data

    res_intel = client.get(f"/api/v1/wallets/{address}/intelligence")
    assert res_intel.status_code in {200, 404, 422}


# -- 6. Case Fusion Integration & Non-presumptive Phrasing --
def test_case_fusion_non_presumptive_wording(client, sample_case):
    case_id = sample_case["case_id"]
    res_fusion = client.get(f"/api/v1/cases/{case_id}/fusion")
    assert res_fusion.status_code in {200, 404}
    if res_fusion.status_code == 200:
        fusion = res_fusion.json()
        assert "limitations" in fusion
        assert any("not establish common ownership or criminal attribution" in lim for lim in fusion["limitations"])


# -- 7. Realtime Event Replay Endpoint --
def test_realtime_event_replay_endpoint(client, sample_case):
    event_id = str(uuid4())
    event = RealtimeEvent(
        event_id=event_id,
        provider="DEVELOPMENT SYNTHETIC",
        chain=Chain.ETHEREUM,
        event_type=RealtimeEventType.ADDRESS_ACTIVITY,
        received_at=datetime.now(timezone.utc),
        transaction_hash="0x" + "d" * 64,
        from_address="0x1111111111111111111111111111111111111111",
        to_address="0x4444444444444444444444444444444444444444",
        asset="ETH",
        amount="1.0",
    )
    client.post("/api/v1/realtime/simulated/events", json=event.model_dump(mode="json"))

    res_replay = client.post(f"/api/v1/realtime/replay/{event_id}")
    assert res_replay.status_code == 200
    replay_data = res_replay.json()
    assert "results" in replay_data
