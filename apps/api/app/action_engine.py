"""
NextBestActionEngine
Provides prioritized recommendations for investigators without performing automatic legal determinations or asset freezing.
"""
from uuid import uuid4, uuid5, NAMESPACE_URL
from datetime import datetime, timezone

from .domain import (
    NextBestAction,
    NextBestActionType,
    RiskBand,
    VaspClassification,
)


class NextBestActionEngine:
    def recommend(
        self,
        case_id: str,
        risk_assessment=None,
        vasp_proximity_candidates: list = None,
        cross_chain_links: list = None,
        related_cases: list = None,
        evidence_records: list = None,
    ) -> list[NextBestAction]:
        actions = []
        vasp_candidates = vasp_proximity_candidates or []
        links = cross_chain_links or []
        rel_cases = related_cases or []
        ev_records = evidence_records or []

        # 1. Action: Review VASP Exposure
        if vasp_candidates:
            top_vasp = vasp_candidates[0]
            evidence_ids = list(dict.fromkeys(
                e for c in vasp_candidates for e in getattr(c, "supporting_transaction_hashes", [])
            ))
            actions.append(NextBestAction(
                action_id=str(uuid5(NAMESPACE_URL, f"rrr:action:vasp:{case_id}")),
                case_id=case_id,
                action_type=NextBestActionType.REVIEW_VASP_EXPOSURE,
                title=f"Review Probable VASP Exposure: {top_vasp.entity_name}",
                reason=f"Receiving VASP candidate {top_vasp.entity_name} identified at hop distance {top_vasp.hop_distance} with confidence {top_vasp.attribution_confidence:.2f}.",
                priority="CRITICAL" if top_vasp.attribution_confidence >= 0.8 else "HIGH",
                supporting_evidence_ids=evidence_ids[:10],
            ))

            # 2. Action: Prepare VASP Information Package
            actions.append(NextBestAction(
                action_id=str(uuid5(NAMESPACE_URL, f"rrr:action:package:{case_id}")),
                case_id=case_id,
                action_type=NextBestActionType.PREPARE_VASP_INFORMATION_PACKAGE,
                title=f"Prepare VASP Information Package for {top_vasp.entity_name}",
                reason=f"Compile evidence manifest and transaction hashes for formal compliance inquiry to {top_vasp.entity_name}.",
                priority="HIGH",
                supporting_evidence_ids=evidence_ids[:10],
            ))

        # 3. Action: Review Cross-Chain Movement
        if links:
            chain_transitions = list(dict.fromkeys(
                f"{link.source.chain.value}->{link.destination.chain.value}" for link in links if hasattr(link, "source") and hasattr(link, "destination")
            ))
            actions.append(NextBestAction(
                action_id=str(uuid5(NAMESPACE_URL, f"rrr:action:cross_chain:{case_id}")),
                case_id=case_id,
                action_type=NextBestActionType.REVIEW_CROSS_CHAIN_MOVEMENT,
                title=f"Review Cross-Chain Transitions ({', '.join(chain_transitions)})",
                reason=f"Detected {len(links)} cross-chain link(s) across bridge infrastructure.",
                priority="HIGH" if len(links) > 1 else "MEDIUM",
                supporting_evidence_ids=[link.link_id for link in links[:5]],
            ))

        # 4. Action: Review Related Cases Correlation
        if rel_cases:
            top_rel = rel_cases[0]
            actions.append(NextBestAction(
                action_id=str(uuid5(NAMESPACE_URL, f"rrr:action:related:{case_id}")),
                case_id=case_id,
                action_type=NextBestActionType.REVIEW_RELATED_CASES,
                title=f"Investigate Correlation with Case {getattr(top_rel, 'case_b_id', 'Related')}",
                reason=f"Shared infrastructure correlation detected (Score: {getattr(top_rel, 'relationship_score', 0.0):.2f}, Type: {getattr(top_rel, 'relationship_type', 'SHARED')}).",
                priority="HIGH" if getattr(top_rel, "relationship_score", 0.0) >= 0.75 else "MEDIUM",
                supporting_evidence_ids=[],
            ))

        # 5. Action: Review High-Risk Movement
        if risk_assessment and getattr(risk_assessment, "band", None) in (RiskBand.CRITICAL, RiskBand.HIGH):
            actions.append(NextBestAction(
                action_id=str(uuid5(NAMESPACE_URL, f"rrr:action:risk:{case_id}")),
                case_id=case_id,
                action_type=NextBestActionType.REVIEW_HIGH_RISK_MOVEMENT,
                title=f"Evaluate Escalated Risk ({risk_assessment.band.value} - {risk_assessment.score:.1f}/100)",
                reason=risk_assessment.explanation or "Multiple elevated risk factors observed.",
                priority="CRITICAL" if risk_assessment.band == RiskBand.CRITICAL else "HIGH",
                supporting_evidence_ids=risk_assessment.evidence_ids[:10],
            ))

        # 6. Action: Generate Standardized Investigation Report
        actions.append(NextBestAction(
            action_id=str(uuid5(NAMESPACE_URL, f"rrr:action:report:{case_id}")),
            case_id=case_id,
            action_type=NextBestActionType.GENERATE_INVESTIGATION_REPORT,
            title="Generate Standardized Investigation Report",
            reason="Compile complete case snapshot, evidence manifest, VASP attribution, and risk audit trail.",
            priority="MEDIUM",
            supporting_evidence_ids=[e.evidence_id for e in ev_records[:10]] if ev_records else [],
        ))

        # 7. Action: Monitor Wallet
        actions.append(NextBestAction(
            action_id=str(uuid5(NAMESPACE_URL, f"rrr:action:monitor:{case_id}")),
            case_id=case_id,
            action_type=NextBestActionType.MONITOR_WALLET,
            title="Enable Continuous Real-time Monitoring",
            reason="Receive immediate alerts upon subsequent transaction activity on case wallets.",
            priority="MEDIUM",
            supporting_evidence_ids=[],
        ))

        return actions
