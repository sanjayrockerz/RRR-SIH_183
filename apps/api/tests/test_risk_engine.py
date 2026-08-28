from datetime import datetime, timedelta, timezone
import pytest

from app.domain import *
from app.risk_engine import RiskEngine, default_risk_config
from app.domain import GraphEdge, GraphNode, TransactionPath, Transfer

def edge(number, source, target, amount="10", seconds=0):
    transfer=Transfer(tx_hash="0x"+number*64,chain=Chain.ETHEREUM,source=source,destination=target,asset="ETH",amount=amount,provider="fixture",timestamp=datetime(2026,1,1,tzinfo=timezone.utc))
    transfer=transfer.model_copy(update={"timestamp":transfer.timestamp+timedelta(seconds=seconds)})
    return GraphEdge(edge_id=f"edge-{number}",source=source,target=target,transfer=transfer,transaction_hash=transfer.tx_hash,evidence_id=f"ev-{number}")

def trace(edges):
    nodes={}
    for item in edges:
        nodes.setdefault(item.source,GraphNode(id=item.source,address=item.source)); nodes.setdefault(item.target,GraphNode(id=item.target,address=item.target))
    paths=[TransactionPath(path_id="path",node_ids=[edges[0].source]+[e.target for e in edges],edges=edges)] if edges else []
    return TraceResult(case_id="case",trace_id="trace",root_address=edges[0].source if edges else "0x"+"a"*40,mode=DataMode.HISTORICAL,provider="fixture",nodes=list(nodes.values()),edges=edges,signals=[],evidence=[],paths=paths)


def test_risk_score_is_deterministic_and_evidence_backed():
    a,b,c,d=["0x"+letter*40 for letter in "abcd"]
    edges=[edge("1",a,b,seconds=0),edge("2",b,c,seconds=60),edge("3",c,d,seconds=120)]
    observed=trace(edges)
    pattern=PatternObservation(pattern_id="pattern-1",case_id="case",trace_id="trace",pattern_type=PatternType.RAPID_HOP,status=PatternStatus.OBSERVED,confidence_level=ConfidenceLevel.HIGH,severity=PatternSeverity.HIGH,description="Observed rapid hop",explanation="Observed",observed_at=edges[-1].transfer.timestamp,affected_nodes=[a,b,c,d],affected_edges=[e.edge_id for e in edges],transaction_hashes=[e.transaction_hash for e in edges],evidence_ids=["ev-1","ev-2","ev-3"],fingerprint="fp-1")
    subject=RiskSubject(subject_id=a,case_id="case",chain=Chain.ETHEREUM,address=a)
    engine=RiskEngine(); config=default_risk_config()
    first=engine.assess(observed,[pattern],[],subject,config,calculated_at=datetime(2026,1,1,1,tzinfo=timezone.utc))
    second=engine.assess(observed,[pattern],[],subject,config,calculated_at=datetime(2026,1,1,1,tzinfo=timezone.utc))
    # Raw contribution: rapid_hop (16) + high_transfer (7) = 23
    # Normalized: 23 * 100 / 156 = 14.7
    assert first.score==second.score==14.7
    assert first.band==second.band==RiskBand.LOW
    assert first.factors[0].evidence_ids==["ev-1","ev-2","ev-3"]


def test_duplicate_observations_are_capped_by_factor_maximum():
    a,b,c,d=["0x"+letter*40 for letter in "abcd"]
    observed=trace([edge("1",a,b),edge("2",b,c),edge("3",c,d)])
    # Use different fingerprints so they are unique observations, scaling up to cap at max_contribution=24
    patterns=[PatternObservation(pattern_id=f"p-{i}",case_id="case",trace_id="trace",pattern_type=PatternType.RAPID_HOP,status=PatternStatus.OBSERVED,confidence_level=ConfidenceLevel.MEDIUM,severity=PatternSeverity.HIGH,description="Observed",explanation="Observed",observed_at=observed.edges[-1].transfer.timestamp,transaction_hashes=[observed.edges[-1].transaction_hash],evidence_ids=["ev-1"],fingerprint=f"observation-{i}") for i in range(5)]
    result=RiskEngine().assess(observed,patterns,[],RiskSubject(subject_id=a,case_id="case",chain=Chain.ETHEREUM,address=a),default_risk_config())
    factor=next(item for item in result.factors if item.definition_id=="pattern:rapid_hop")
    assert factor.contribution==24


def test_risk_delta_tracks_new_removed_and_changed_factors():
    a,b,c,d=["0x"+letter*40 for letter in "abcd"]
    observed=trace([edge("1",a,b),edge("2",b,c),edge("3",c,d)])
    subject=RiskSubject(subject_id=a,case_id="case",chain=Chain.ETHEREUM,address=a)
    engine=RiskEngine(); config=default_risk_config()
    p1=PatternObservation(pattern_id="p1",case_id="case",trace_id="trace",pattern_type=PatternType.FAN_OUT,status=PatternStatus.OBSERVED,confidence_level=ConfidenceLevel.MEDIUM,severity=PatternSeverity.MEDIUM,description="Observed",explanation="Observed",observed_at=observed.edges[-1].transfer.timestamp,transaction_hashes=["tx1"],evidence_ids=["ev1"])
    p2=p1.model_copy(update={"pattern_id":"p2","pattern_type":PatternType.BURST_ACTIVITY,"transaction_hashes":["tx2"],"evidence_ids":["ev2"]})
    previous=engine.assess(observed,[p1],[],subject,config,calculated_at=datetime(2026,1,1,tzinfo=timezone.utc))
    current=engine.assess(observed,[p1,p2],[],subject,config,previous,calculated_at=datetime(2026,1,1,1,tzinfo=timezone.utc))
    assert current.delta and current.delta.delta>0
    assert "pattern:burst_activity" in current.delta.new_factors


def test_invalid_thresholds_and_missing_evidence_are_rejected_or_ignored():
    with pytest.raises(ValueError):
        RiskEngine().assess(trace([]),[],[],RiskSubject(subject_id="0x"+"a"*40,case_id="case",chain=Chain.ETHEREUM,address="0x"+"a"*40),RiskScoringConfig(thresholds=RiskBandThresholds(guarded_min=50,elevated_min=20)))
    a,b=["0x"+letter*40 for letter in "ab"]
    # Use small amount so value factor does not fire
    observed=trace([edge("1",a,b,amount="0.01")])
    no_evidence=PatternObservation(pattern_id="p",case_id="case",trace_id="trace",pattern_type=PatternType.FAN_OUT,status=PatternStatus.OBSERVED,confidence_level=ConfidenceLevel.MEDIUM,severity=PatternSeverity.MEDIUM,description="Observed",explanation="Observed",observed_at=observed.edges[0].transfer.timestamp)
    result=RiskEngine().assess(observed,[no_evidence],[],RiskSubject(subject_id=a,case_id="case",chain=Chain.ETHEREUM,address=a),default_risk_config())
    assert result.score==0 and result.factors==[]
