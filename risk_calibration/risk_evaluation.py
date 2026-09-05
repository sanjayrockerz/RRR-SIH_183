"""Risk Calibration Harness for RRR-Realtime.

Evaluates scenarios RISK-001 through RISK-010 against the deterministic RiskEngine,
verifying bounded scores (0 <= score <= 100), band thresholds, and 100% reproducibility.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add apps/api to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "apps" / "api"))

from app.domain import Chain, DataMode, PatternObservation, PatternStatus, PatternType, PatternSeverity, RiskBand, NearestEntityResult, Entity, EntityType, ConfidenceLevel, AttributionRole, TransactionPath, TraceResult, RiskSubject, GraphNode
from app.risk_engine import RiskEngine


def run_calibration():
    base_dir = Path(__file__).resolve().parent
    scenarios_file = base_dir / "scenarios.json"
    expected_file = base_dir / "expected_results.json"

    scenarios = json.loads(scenarios_file.read_text(encoding="utf-8"))
    expected = json.loads(expected_file.read_text(encoding="utf-8"))

    engine = RiskEngine()
    results = []
    all_passed = True

    print("=================================================================")
    print("      RRR-REALTIME RISK ENGINE CALIBRATION HARNESS               ")
    print("=================================================================")

    now = datetime.now(timezone.utc)

    for sc in scenarios:
        sc_id = sc["scenario_id"]
        exp = expected.get(sc_id, {})

        # Construct synthetic inputs for scenario
        patterns = []
        attributions = []

        if "pattern:rapid_hop" in sc["factors"]:
            patterns.append(PatternObservation(
                pattern_id=f"p-{sc_id}-1", case_id=f"case-{sc_id}", trace_id=f"trace-{sc_id}",
                pattern_type=PatternType.RAPID_HOP, status=PatternStatus.OBSERVED, confidence_score=0.85,
                severity=PatternSeverity.HIGH, description="Rapid hop movement observed",
                explanation="Observed 4 transfers within 6 minutes", evidence_ids=["ev-1"], observed_at=now, metadata={}
            ))
        if "entity:mixer_interaction" in sc["factors"]:
            patterns.append(PatternObservation(
                pattern_id=f"p-{sc_id}-2", case_id=f"case-{sc_id}", trace_id=f"trace-{sc_id}",
                pattern_type=PatternType.MIXER_INTERACTION, status=PatternStatus.OBSERVED, confidence_score=0.90,
                severity=PatternSeverity.HIGH, description="Mixer interaction observed",
                explanation="Interaction with mixer smart contract", evidence_ids=["ev-2"], observed_at=now, metadata={}
            ))
        if "pattern:bridge_hop" in sc["factors"]:
            patterns.append(PatternObservation(
                pattern_id=f"p-{sc_id}-3", case_id=f"case-{sc_id}", trace_id=f"trace-{sc_id}",
                pattern_type=PatternType.BRIDGE_INTERACTION, status=PatternStatus.OBSERVED, confidence_score=0.80,
                severity=PatternSeverity.MEDIUM, description="Bridge interaction observed",
                explanation="Cross-chain bridge interaction", evidence_ids=["ev-3"], observed_at=now, metadata={}
            ))
        if "vasp:deposit_proximity" in sc["factors"]:
            entity = Entity(entity_id="vasp-1", name="Binance", entity_type=EntityType.VASP, legal_name="Binance Ltd")
            path = TransactionPath(path_id="path-1", node_ids=["node-1"], edges=[])
            attributions.append(NearestEntityResult(
                entity=entity,
                address="0x" + "b" * 40,
                chain=Chain.ETHEREUM,
                hop_distance=1,
                path=path,
                confidence=ConfidenceLevel.HIGH,
                role=AttributionRole.DEPOSIT_ADDRESS,
                supporting_attributions=[],
                supporting_sources=[],
                evidence=[],
                explanation="VASP deposit proximity"
            ))

        trace = TraceResult(
            case_id=f"case-{sc_id}",
            trace_id=f"trace-{sc_id}",
            root_address=sc["root_address"],
            mode=DataMode.HISTORICAL,
            provider="CALIBRATION",
            nodes=[GraphNode(id="node-1", address=sc["root_address"], chain=Chain.ETHEREUM)],
            edges=[],
            signals=[],
            evidence=[]
        )
        subject = RiskSubject(subject_id=f"subj-{sc_id}", case_id=f"case-{sc_id}", address=sc["root_address"], chain=Chain.ETHEREUM, subject_type="WALLET")

        assessment = engine.assess(
            trace=trace,
            patterns=patterns,
            attributions=attributions,
            subject=subject,
            case_fraud_type="INVESTIGATION"
        )

        score = assessment.score
        band = assessment.band.value if hasattr(assessment.band, "value") else str(assessment.band)

        # Verification rules
        bounded = 0.0 <= score <= 100.0
        band_ok = band in sc.get("expected_band_in", exp.get("allowed_bands", []))
        max_ok = "max_score" not in sc or score <= sc["max_score"]
        min_ok = "min_score" not in sc or score >= sc["min_score"]

        # Reproducibility check
        reassessment = engine.assess(
            trace=trace,
            patterns=patterns,
            attributions=attributions,
            subject=subject,
            case_fraud_type="INVESTIGATION"
        )
        reproducible = (assessment.score == reassessment.score) and (assessment.band == reassessment.band)

        passed = bounded and band_ok and max_ok and min_ok and reproducible
        if not passed:
            all_passed = False

        status_str = "PASS" if passed else "FAIL"
        print(f"[{sc_id}] {sc['title']:<30} | Score: {score:>5.1f} | Band: {band:<8} | Status: {status_str}")

        results.append({
            "scenario_id": sc_id,
            "title": sc["title"],
            "score": score,
            "band": band,
            "bounded": bounded,
            "reproducible": reproducible,
            "status": status_str
        })

    print("=================================================================")
    print(f"FINAL CALIBRATION HARNESS RESULT: {'PASS' if all_passed else 'FAIL'}")
    print("=================================================================")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(run_calibration())
