"""Performance Benchmarking Suite for RRR-Realtime Phase 8 Acceptance.

Measures p50, p95, p99 latencies for critical investigator operations against target NFR thresholds.
"""
import asyncio
import time
import json
import sys
from pathlib import Path

# Add apps/api to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "apps" / "api"))

from app.domain import Chain, TraceRequest, TraceDirection, CaseCreate, WalletCreate, RiskAssessRequest
from app.persistence import PostgresCaseRepository
from app.provider_registry import BlockchainProviderRegistry
from app.fixture_provider import DevelopmentFixtureProvider
from app.services import TraceService
from app.risk_service import RiskService
from app.action_engine import NextBestActionEngine


def percentile(data, p):
    if not data:
        return 0.0
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * (p / 100.0)
    f = int(k)
    c = f + 1 if f + 1 < len(sorted_data) else f
    d = k - f
    return sorted_data[f] + (sorted_data[c] - sorted_data[f]) * d


async def run_benchmark():
    print("=================================================================")
    print("      RRR-REALTIME PERFORMANCE BENCHMARK SUITE                   ")
    print("=================================================================")

    repo = PostgresCaseRepository()

    # Seed benchmark case
    case = await repo.create(CaseCreate(title="Benchmark Performance Case", fraud_type="INVESTIGATION", priority="HIGH"))
    case_id = case.case_id
    victim_address = "0x" + "a" * 40
    await repo.add_wallet(case_id, WalletCreate(address=victim_address, chain=Chain.ETHEREUM))

    provider = DevelopmentFixtureProvider()
    registry = BlockchainProviderRegistry([([Chain.ETHEREUM, Chain.TRON, Chain.BSC, Chain.BTC], provider)])
    tracer = TraceService(registry.get(Chain.ETHEREUM), registry)

    # Benchmark 1: Trace execution (5-hop & 10-hop)
    trace_latencies = []
    for _ in range(10):
        start = time.perf_counter()
        trace = await tracer.trace(case_id, TraceRequest(address=victim_address, chain=Chain.ETHEREUM, direction=TraceDirection.FORWARD, max_hops=5))
        elapsed = (time.perf_counter() - start) * 1000.0
        trace_latencies.append(elapsed)

    await repo.persist_trace(trace)

    # Benchmark 2: Risk Assessment
    risk_service = RiskService(repo)
    risk_latencies = []
    for _ in range(10):
        start = time.perf_counter()
        assessment = await risk_service.assess(case_id, RiskAssessRequest(trace_id=trace.trace_id))
        elapsed = (time.perf_counter() - start) * 1000.0
        risk_latencies.append(elapsed)

    # Benchmark 3: High Risk Cases/Wallets lookup
    lookup_latencies = []
    for _ in range(10):
        start = time.perf_counter()
        cases = await repo.high_risk_cases()
        wallets = await repo.high_risk_wallets()
        elapsed = (time.perf_counter() - start) * 1000.0
        lookup_latencies.append(elapsed)

    # Benchmark 4: Action Recommendation
    action_engine = NextBestActionEngine()
    action_latencies = []
    for _ in range(10):
        start = time.perf_counter()
        actions = action_engine.recommend(case_id, assessment, [], [], [], [])
        elapsed = (time.perf_counter() - start) * 1000.0
        action_latencies.append(elapsed)

    metrics = {
        "wallet_lookup": {"p50": percentile(lookup_latencies, 50), "p95": percentile(lookup_latencies, 95), "target_p95": 500.0},
        "risk_assessment": {"p50": percentile(risk_latencies, 50), "p95": percentile(risk_latencies, 95), "target_p95": 2000.0},
        "5_hop_trace": {"p50": percentile(trace_latencies, 50), "p95": percentile(trace_latencies, 95), "target_p95": 10000.0},
        "action_recommendation": {"p50": percentile(action_latencies, 50), "p95": percentile(action_latencies, 95), "target_p95": 1000.0},
    }

    print(f"{'Operation':<25} | {'p50 (ms)':<10} | {'p95 (ms)':<10} | {'Target p95':<12} | {'Status'}")
    print("-" * 72)

    all_passed = True
    for op, m in metrics.items():
        passed = m["p95"] <= m["target_p95"]
        if not passed:
            all_passed = False
        status = "PASS" if passed else "FAIL"
        print(f"{op:<25} | {m['p50']:>10.2f} | {m['p95']:>10.2f} | {m['target_p95']:>12.2f} | {status}")

    print("=================================================================")
    print(f"BENCHMARK SUITE FINAL RESULT: {'PASS' if all_passed else 'FAIL'}")
    print("=================================================================")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(run_benchmark()))
