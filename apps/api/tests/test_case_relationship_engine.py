from datetime import datetime, timezone
import pytest

from app.domain import (
    InvestigationCase,
    WalletCreate,
    Chain,
    TraceResult,
    GraphNode,
    GraphEdge,
    Transfer,
    TraceLimits,
    TraceMetrics,
    DataMode,
)
from app.case_relationship_engine import CaseRelationshipEngine

VICTIM_A = "0x1111111111111111111111111111111111111111"
VICTIM_B = "0x2222222222222222222222222222222222222222"
VICTIM_C = "0x3333333333333333333333333333333333333333"
VICTIM_U = "0x4444444444444444444444444444444444444444"

INTER_X = "0x8888888888888888888888888888888888888888"
INTER_Y = "0x7777777777777777777777777777777777777777"
UNRELATED_Z = "0x5555555555555555555555555555555555555555"

VASP_1 = "0x9999999999999999999999999999999999999999"
VASP_2 = "0x6666666666666666666666666666666666666666"
VASP_3 = "0x0000000000000000000000000000000000000099"


@pytest.fixture
def multi_case_infrastructure_setup():
    """
    Fixtures for multi-case infrastructure correlation test:
    Case A: Victim A -> Intermediary X -> VASP 1
    Case B: Victim B -> Intermediary X -> VASP 1
    Case C: Victim C -> Intermediary Y -> Intermediary X -> VASP 2
    Unrelated Case U: Victim U -> Wallet Z -> VASP 3 (No shared infrastructure)
    """
    now = datetime.now(timezone.utc)

    # Case A
    case_a = InvestigationCase(
        case_id="case-a-1111",
        title="Case A - Phishing Campaign",
        fraud_type="Phishing",
        priority="HIGH",
        status="OPEN",
        created_at=now,
        updated_at=now,
        wallets=[WalletCreate(address=VICTIM_A, chain=Chain.ETHEREUM)],
        latest_trace=TraceResult(
            case_id="case-a-1111",
            trace_id="trace-a-1",
            root_address=VICTIM_A,
            mode=DataMode.DEVELOPMENT_FIXTURE,
            provider="FIXTURE",
            nodes=[
                GraphNode(id=VICTIM_A, address=VICTIM_A, chain=Chain.ETHEREUM, depth=0, node_type="ROOT"),
                GraphNode(id=INTER_X, address=INTER_X, chain=Chain.ETHEREUM, depth=1, node_type="INTERMEDIARY"),
                GraphNode(id=VASP_1, address=VASP_1, chain=Chain.ETHEREUM, depth=2, node_type="VASP"),
            ],
            edges=[
                GraphEdge(
                    edge_id="e-a-1",
                    source=VICTIM_A,
                    target=INTER_X,
                    hop=1,
                    transaction_hash="0xa100000000000000000000000000000000000000000000000000000000000001",
                    transfer=Transfer(
                        tx_hash="0xa100000000000000000000000000000000000000000000000000000000000001",
                        chain=Chain.ETHEREUM,
                        timestamp=now,
                        source=VICTIM_A,
                        destination=INTER_X,
                        asset="ETH",
                        amount="5.0",
                        provider="FIXTURE",
                    ),
                ),
                GraphEdge(
                    edge_id="e-a-2",
                    source=INTER_X,
                    target=VASP_1,
                    hop=2,
                    transaction_hash="0xa200000000000000000000000000000000000000000000000000000000000002",
                    transfer=Transfer(
                        tx_hash="0xa200000000000000000000000000000000000000000000000000000000000002",
                        chain=Chain.ETHEREUM,
                        timestamp=now,
                        source=INTER_X,
                        destination=VASP_1,
                        asset="ETH",
                        amount="4.8",
                        provider="FIXTURE",
                    ),
                ),
            ],
            limits=TraceLimits(max_hops=3, max_nodes=100, max_edges=500, max_transactions=500, max_duration=60),
            metrics=TraceMetrics(node_count=3, edge_count=2, unique_wallet_count=3, maximum_hop=2, path_count=1),
            signals=[],
            evidence=[],
        ),
    )

    # Case B
    case_b = InvestigationCase(
        case_id="case-b-2222",
        title="Case B - Investment Fraud",
        fraud_type="Investment",
        priority="HIGH",
        status="OPEN",
        created_at=now,
        updated_at=now,
        wallets=[WalletCreate(address=VICTIM_B, chain=Chain.ETHEREUM)],
        latest_trace=TraceResult(
            case_id="case-b-2222",
            trace_id="trace-b-1",
            root_address=VICTIM_B,
            mode=DataMode.DEVELOPMENT_FIXTURE,
            provider="FIXTURE",
            nodes=[
                GraphNode(id=VICTIM_B, address=VICTIM_B, chain=Chain.ETHEREUM, depth=0, node_type="ROOT"),
                GraphNode(id=INTER_X, address=INTER_X, chain=Chain.ETHEREUM, depth=1, node_type="INTERMEDIARY"),
                GraphNode(id=VASP_1, address=VASP_1, chain=Chain.ETHEREUM, depth=2, node_type="VASP"),
            ],
            edges=[
                GraphEdge(
                    edge_id="e-b-1",
                    source=VICTIM_B,
                    target=INTER_X,
                    hop=1,
                    transaction_hash="0xb100000000000000000000000000000000000000000000000000000000000001",
                    transfer=Transfer(
                        tx_hash="0xb100000000000000000000000000000000000000000000000000000000000001",
                        chain=Chain.ETHEREUM,
                        timestamp=now,
                        source=VICTIM_B,
                        destination=INTER_X,
                        asset="ETH",
                        amount="10.0",
                        provider="FIXTURE",
                    ),
                ),
            ],
            limits=TraceLimits(max_hops=3, max_nodes=100, max_edges=500, max_transactions=500, max_duration=60),
            metrics=TraceMetrics(node_count=3, edge_count=1, unique_wallet_count=3, maximum_hop=2, path_count=1),
            signals=[],
            evidence=[],
        ),
    )

    # Case C: C -> Y -> X
    case_c = InvestigationCase(
        case_id="case-c-3333",
        title="Case C - Ransomware Payment",
        fraud_type="Ransomware",
        priority="HIGH",
        status="OPEN",
        created_at=now,
        updated_at=now,
        wallets=[WalletCreate(address=VICTIM_C, chain=Chain.ETHEREUM)],
        latest_trace=TraceResult(
            case_id="case-c-3333",
            trace_id="trace-c-1",
            root_address=VICTIM_C,
            mode=DataMode.DEVELOPMENT_FIXTURE,
            provider="FIXTURE",
            nodes=[
                GraphNode(id=VICTIM_C, address=VICTIM_C, chain=Chain.ETHEREUM, depth=0, node_type="ROOT"),
                GraphNode(id=INTER_Y, address=INTER_Y, chain=Chain.ETHEREUM, depth=1, node_type="INTERMEDIARY"),
                GraphNode(id=INTER_X, address=INTER_X, chain=Chain.ETHEREUM, depth=2, node_type="INTERMEDIARY"),
            ],
            edges=[
                GraphEdge(
                    edge_id="e-c-1",
                    source=VICTIM_C,
                    target=INTER_Y,
                    hop=1,
                    transaction_hash="0xc100000000000000000000000000000000000000000000000000000000000001",
                    transfer=Transfer(
                        tx_hash="0xc100000000000000000000000000000000000000000000000000000000000001",
                        chain=Chain.ETHEREUM,
                        timestamp=now,
                        source=VICTIM_C,
                        destination=INTER_Y,
                        asset="ETH",
                        amount="15.0",
                        provider="FIXTURE",
                    ),
                ),
                GraphEdge(
                    edge_id="e-c-2",
                    source=INTER_Y,
                    target=INTER_X,
                    hop=2,
                    transaction_hash="0xc200000000000000000000000000000000000000000000000000000000000002",
                    transfer=Transfer(
                        tx_hash="0xc200000000000000000000000000000000000000000000000000000000000002",
                        chain=Chain.ETHEREUM,
                        timestamp=now,
                        source=INTER_Y,
                        destination=INTER_X,
                        asset="ETH",
                        amount="14.5",
                        provider="FIXTURE",
                    ),
                ),
            ],
            limits=TraceLimits(max_hops=3, max_nodes=100, max_edges=500, max_transactions=500, max_duration=60),
            metrics=TraceMetrics(node_count=3, edge_count=2, unique_wallet_count=3, maximum_hop=2, path_count=1),
            signals=[],
            evidence=[],
        ),
    )

    # Unrelated Case U
    case_u = InvestigationCase(
        case_id="case-u-9999",
        title="Case U - Unrelated Fraud",
        fraud_type="Identity Theft",
        priority="LOW",
        status="OPEN",
        created_at=now,
        updated_at=now,
        wallets=[WalletCreate(address=VICTIM_U, chain=Chain.ETHEREUM)],
        latest_trace=TraceResult(
            case_id="case-u-9999",
            trace_id="trace-u-1",
            root_address=VICTIM_U,
            mode=DataMode.DEVELOPMENT_FIXTURE,
            provider="FIXTURE",
            nodes=[
                GraphNode(id=VICTIM_U, address=VICTIM_U, chain=Chain.ETHEREUM, depth=0, node_type="ROOT"),
                GraphNode(id=UNRELATED_Z, address=UNRELATED_Z, chain=Chain.ETHEREUM, depth=1, node_type="INTERMEDIARY"),
            ],
            edges=[],
            limits=TraceLimits(max_hops=3, max_nodes=100, max_edges=500, max_transactions=500, max_duration=60),
            metrics=TraceMetrics(node_count=2, edge_count=0, unique_wallet_count=2),
            signals=[],
            evidence=[],
        ),
    )

    return [case_a, case_b, case_c, case_u]


def test_cross_case_correlation_ab_and_c(multi_case_infrastructure_setup):
    """
    Test requirement:
    A -> X
    B -> X
    C -> Y -> X
    Expected: A, B, C become connected through infrastructure X.
    """
    cases = multi_case_infrastructure_setup
    engine = CaseRelationshipEngine(cases)

    # 1. Compare A and B
    scores_ab = engine.compare_cases(cases[0], cases[1])
    assert len(scores_ab) > 0
    intermediary_match_ab = next((s for s in scores_ab if s.relationship_type == "SHARED_INTERMEDIARY"), None)
    assert intermediary_match_ab is not None
    assert intermediary_match_ab.relationship_score >= 0.80
    assert any(w["address"] == INTER_X.lower() for w in intermediary_match_ab.shared_wallets)

    # 2. Compare C and A (C -> Y -> X vs A -> X)
    scores_ca = engine.compare_cases(cases[2], cases[0])
    assert len(scores_ca) > 0
    intermediary_match_ca = next((s for s in scores_ca if s.relationship_type == "SHARED_INTERMEDIARY"), None)
    assert intermediary_match_ca is not None
    assert any(w["address"] == INTER_X.lower() for w in intermediary_match_ca.shared_wallets)


def test_unrelated_case_no_false_positives(multi_case_infrastructure_setup):
    """
    Verify that unrelated case U has 0 relationship score / no matches with Case A.
    """
    cases = multi_case_infrastructure_setup
    engine = CaseRelationshipEngine(cases)

    scores_au = engine.compare_cases(cases[0], cases[3])
    assert len(scores_au) == 0


def test_multi_victim_infrastructure_aggregation(multi_case_infrastructure_setup):
    """
    Verify multi-victim aggregation on common intermediary X:
    Connected cases: Case A, Case B, Case C (3 cases)
    Victims: 3 distinct victims
    Aggregate exposure: > 0
    """
    cases = multi_case_infrastructure_setup
    engine = CaseRelationshipEngine(cases)

    impact = engine.calculate_infrastructure_impact(INTER_X)
    assert impact.node_id == INTER_X.lower()
    assert len(impact.connected_case_ids) == 3
    assert impact.victim_count >= 3
    assert impact.aggregate_exposure_usd > 0.0


def test_fraud_network_graph_node_edge_distinction(multi_case_infrastructure_setup):
    """
    Verify that build_fraud_network_graph constructs a graph with explicit distinction
    between TRANSACTION_RELATIONSHIP and INVESTIGATIVE_RELATIONSHIP.
    """
    cases = multi_case_infrastructure_setup
    engine = CaseRelationshipEngine(cases)

    graph = engine.build_fraud_network_graph()
    assert len(graph.nodes) > 0
    assert len(graph.edges) > 0

    tx_edges = [e for e in graph.edges if e.relationship_kind == "TRANSACTION_RELATIONSHIP"]
    inv_edges = [e for e in graph.edges if e.relationship_kind == "INVESTIGATIVE_RELATIONSHIP"]

    assert len(tx_edges) > 0
    assert len(inv_edges) > 0

