from app.demo_fixtures import fixture_specs, build_fixture, validate_fixture
from app.domain import PatternObservation, RiskSubject
from app.risk_engine import RiskEngine
from app.domain import RiskScoringConfig


def test_demo_fixtures_have_one_explicit_path_and_one_edge_per_transaction():
    for spec in fixture_specs():
        trace, patterns, config, layout = build_fixture(spec, f"00000000-0000-0000-0000-{spec['reference'][-12:] .replace('-', '0')}")
        validate_fixture(trace)
        assert len(trace.predominant_path) == len(trace.edges) + 1
        assert len(trace.edges) == len({edge.transaction_hash for edge in trace.edges})
        assert all(edge.source in trace.predominant_path and edge.target in trace.predominant_path for edge in trace.edges)
        assert all(edge.transfer.amount == edge.amount for edge in trace.edges)
        assert all(edge.evidence_id for edge in trace.edges)
        assert len(layout["positions"]) == len(trace.nodes)


def test_small_value_transaction_is_not_filtered_from_graph():
    spec = fixture_specs()[0].copy()
    spec["amounts"] = ["12.40", "12.10", "11.95", "0.25", "11.55"]
    trace, _, _, _ = build_fixture(spec, "00000000-0000-0000-0000-000000000001")
    small = next(edge for edge in trace.edges if edge.transfer.amount == "0.25")
    assert small.source in {node.address for node in trace.nodes}
    assert small.target in {node.address for node in trace.nodes}
    assert small.amount == "0.25"
    assert small.transfer.asset == "ETH"
