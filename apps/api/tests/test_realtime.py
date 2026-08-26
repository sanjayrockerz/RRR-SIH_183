import hashlib
import hmac
from datetime import datetime, timezone

import pytest

from app.config import settings
from app.domain import Chain, ConfirmationState, RealtimeProcessingStatus
from app.realtime import AlchemyRealtimeAdapter, AlchemyWebhookNormalizer, event_identity


def payload(removed=False):
    return {"id": "wh_1", "event": {"network": "ETH_MAINNET", "activity": [{
        "hash": "0x" + "a" * 64, "blockNum": "0x10", "fromAddress": "0x" + "1" * 40,
        "toAddress": "0x" + "2" * 40, "asset": "ETH", "value": 2.5,
        "logIndex": "0x2", "removed": removed,
    }]}}


def test_alchemy_webhook_normalization_is_canonical_and_idempotent():
    normalizer = AlchemyWebhookNormalizer()
    first = normalizer.normalize(payload(), datetime(2026, 1, 1, tzinfo=timezone.utc))[0]
    second = normalizer.normalize(payload(), datetime(2026, 1, 2, tzinfo=timezone.utc))[0]
    assert first.event_id == second.event_id
    assert first.transfer_index == 2
    assert first.processing_status == RealtimeProcessingStatus.NORMALIZED
    assert first.confirmation_state == ConfirmationState.OBSERVED
    assert first.from_address == "0x" + "1" * 40


def test_removed_activity_is_reorg_observation():
    event = AlchemyWebhookNormalizer().normalize(payload(True))[0]
    assert event.removed is True
    assert event.event_type.value == "REORG"
    assert event.confirmation_state == ConfirmationState.REORGED


def test_signature_verification_uses_raw_body(monkeypatch):
    key = "test-signing-key"
    monkeypatch.setattr(settings, "alchemy_webhook_signing_key", key)
    adapter = AlchemyRealtimeAdapter()
    body = b'{"event":{}}'
    signature = hmac.new(key.encode(), body, hashlib.sha256).hexdigest()
    assert adapter.verify_signature(body, "sha256=" + signature)
    assert not adapter.verify_signature(body + b"x", signature)


def test_realtime_capability_is_not_configured_without_webhook_settings(monkeypatch):
    for name in ("alchemy_api_key", "alchemy_webhook_id", "alchemy_webhook_signing_key"):
        monkeypatch.setattr(settings, name, None)
    adapter = AlchemyRealtimeAdapter()
    assert adapter.capabilities()[0].status.value == "NOT_CONFIGURED"


def test_event_identity_changes_for_reorg_state():
    kwargs = (Chain.ETHEREUM, "0x" + "a" * 64, 1, "ADDRESS_ACTIVITY", "0x" + "1" * 40, "0x" + "2" * 40, "ETH")
    assert event_identity(*kwargs) != event_identity(*kwargs[:3], "REORG", *kwargs[4:])
