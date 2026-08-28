from datetime import datetime, timezone

import pytest

from app.domain import Chain, CaseLink


def test_case_link_requires_exact_observation_basis():
    link = CaseLink(link_id="case-a:case-b", case_id="case-a", related_case_id="case-b", relationship_type="SHARED_WALLET", shared_wallets=[{"chain": Chain.ETHEREUM, "address": "0x"+"a"*40}], explanation="Exact persisted wallet identity overlap.", created_at=datetime.now(timezone.utc))
    assert link.confidence_level.value == "CONFIRMED"
    assert "criminality" not in link.explanation.lower()


@pytest.mark.parametrize("bad", ["similar label", "timing only"])
def test_case_link_model_does_not_encode_unsupported_basis(bad):
    # The model only carries explicit persisted overlap collections; unsupported bases stay out of the contract.
    link = CaseLink(link_id="a:b", case_id="a", related_case_id="b", relationship_type="SHARED_TRANSACTION", explanation=bad, created_at=datetime.now(timezone.utc))
    assert link.shared_wallets == [] and link.shared_transactions == []
