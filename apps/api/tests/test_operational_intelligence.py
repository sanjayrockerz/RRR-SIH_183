import pytest
from fastapi import HTTPException

from types import SimpleNamespace

from app.domain import DashboardIntelligence, RiskBand, RiskDelta
from app.main import dashboard_intelligence, case_vasp_candidates, risk_registry_search, calculate_intervention_priority


@pytest.mark.asyncio
async def test_dashboard_intelligence_contract(monkeypatch):
    async def fake_read_model(limit: int):
        assert limit == 5
        return DashboardIntelligence(generated_at="2026-01-01T00:00:00Z")

    monkeypatch.setattr("app.main.repo.dashboard_intelligence", fake_read_model)
    result = await dashboard_intelligence(5)
    assert result.status == "READY"
    assert result.priority_cases == []


@pytest.mark.asyncio
async def test_dashboard_intelligence_rejects_unbounded_limit():
    with pytest.raises(HTTPException) as error:
        await dashboard_intelligence(101)
    assert error.value.status_code == 422


@pytest.mark.asyncio
async def test_vasp_candidates_are_unresolved_without_a_persisted_trace(monkeypatch):
    class CaseWithoutTrace:
        latest_trace = None

    async def fake_case(_case_id):
        return CaseWithoutTrace()

    monkeypatch.setattr("app.main.get_case", fake_case)
    result = await case_vasp_candidates("case-1")
    assert result[0].classification == "UNRESOLVED"
    assert "no persisted trace" in result[0].reasons


@pytest.mark.asyncio
async def test_registry_rejects_unknown_record_kind(monkeypatch):
    async def fake_search(_query, _kind, _limit):
        raise ValueError("kind must be ALL, WALLET, ENTITY, VASP, CASE, or TRANSACTION")

    monkeypatch.setattr("app.main.repo.risk_registry_search", fake_search)
    with pytest.raises(HTTPException) as error:
        await risk_registry_search(kind="UNKNOWN")
    assert error.value.status_code == 422


def test_intervention_priority_exposes_inputs_and_reasons():
    result = calculate_intervention_priority(
        SimpleNamespace(band=RiskBand.CRITICAL, score=89),
        RiskDelta(previous_score=72, current_score=89, delta=17),
        True,
        {"hop_distance": 4, "attribution_confidence": "HIGH", "observed_linked_amount": "3920 USDT"},
        3,
        [],
        {"status": "ANALYZED"},
    )
    assert result.level == "VERY_HIGH"
    assert result.score <= 100
    assert result.formula_version == "intervention-priority-v1"
    assert result.inputs["risk_delta"] == 17
    assert any("risk increased" in reason for reason in result.reasons)
