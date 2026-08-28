import pytest
from app.cyber_intelligence import CuratedSanctionsProvider
from app.domain import Chain, IntelligenceConfidence, IntelligenceSourceStatus, IndicatorType, SanctionsRecord, ScreeningOutcome


ADDRESS = "0x" + "a" * 40


def record(value=ADDRESS, chain=Chain.ETHEREUM):
    return SanctionsRecord(record_id="record-1", source_id="source-1", subject_type=IndicatorType.WALLET, value=value, normalized_value=value.lower(), chain=chain, source_reference="fixture://sanctions", dataset_version="fixture-v1", confidence=IntelligenceConfidence.HIGH)


@pytest.mark.asyncio
async def test_exact_match_is_explicit_and_source_backed():
    result = await CuratedSanctionsProvider([record()]).screen_address(Chain.ETHEREUM, ADDRESS)
    assert result.outcome == ScreeningOutcome.DIRECT_MATCH
    assert result.source_status == IntelligenceSourceStatus.CONFIGURED
    assert result.matches[0].record_id == "record-1"


@pytest.mark.asyncio
async def test_chain_mismatch_is_not_a_match():
    result = await CuratedSanctionsProvider([record(chain=Chain.TRON)]).screen_address(Chain.ETHEREUM, ADDRESS)
    assert result.outcome == ScreeningOutcome.NO_MATCH


@pytest.mark.asyncio
async def test_unconfigured_source_is_not_reported_as_no_match():
    result = await CuratedSanctionsProvider([], configured=False).screen_address(Chain.ETHEREUM, ADDRESS)
    assert result.outcome == ScreeningOutcome.NOT_CONFIGURED
