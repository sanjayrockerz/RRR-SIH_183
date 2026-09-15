from __future__ import annotations

from dataclasses import dataclass

from .schemas import HybridPriority


RULESET_VERSION = "phase3-hybrid-investigation-v1"


@dataclass(frozen=True)
class RuleDecision:
    priority: HybridPriority
    reason_codes: list[str]
    recommendation: str


def decide(s: dict) -> RuleDecision:
    risk_band = str(s.get("risk_band") or "").upper(); risk_high = risk_band in {"HIGH", "CRITICAL"}; risk_moderate = risk_band in {"ELEVATED", "HIGH", "CRITICAL"}
    ml_high = bool(s.get("ml_high")); movement = bool(s.get("movement")); direct = bool(s.get("direct_threat")); vasp = bool(s.get("vasp")); vasp_confirmed = bool(s.get("vasp_confirmed")); cross = bool(s.get("cross_chain")); fusion = bool(s.get("fusion")); registry_high = bool(s.get("registry_high")); risk_increased = bool(s.get("risk_increased")); patterns = bool(s.get("patterns")); watch = bool(s.get("watch"))
    if (risk_high and ml_high and movement) or (direct and vasp) or (risk_increased and cross and vasp) or (fusion and risk_high and registry_high):
        codes = []
        if risk_high: codes.append("HIGH_DETERMINISTIC_RISK")
        if ml_high: codes.append("ML_HIGH_RISK_LIKE")
        if movement: codes.append("REALTIME_MOVEMENT")
        if risk_increased: codes.append("RISK_INCREASED")
        if direct: codes.append("CHAINABUSE_DIRECT_MATCH")
        if vasp: codes.append("VASP_PROBABLE")
        if vasp_confirmed: codes.append("VASP_SOURCE_CONFIRMED")
        if cross: codes.append("CROSS_CHAIN_CONTINUATION")
        if fusion: codes.append("CASE_FUSION_CONFIRMED")
        if registry_high: codes.append("RISK_REGISTRY_REPEAT_WALLET")
        return RuleDecision(HybridPriority.P1, codes, "Priority review is recommended because multiple independent investigative signals align. Review the supporting evidence paths and coordinate appropriate next steps.")
    if (risk_high) or (ml_high and patterns and not movement) or (fusion and risk_moderate) or (vasp and not vasp_confirmed) or direct:
        codes = []
        if risk_high: codes.append("HIGH_DETERMINISTIC_RISK")
        if ml_high: codes.append("ML_HIGH_RISK_LIKE")
        if patterns: codes.append("SUSPICIOUS_PATTERN_CLUSTER")
        if fusion: codes.append("CASE_FUSION_CONFIRMED")
        if vasp: codes.append("VASP_PROBABLE")
        if direct: codes.append("CHAINABUSE_DIRECT_MATCH")
        if not vasp_confirmed: codes.append("INSUFFICIENT_ATTRIBUTION")
        return RuleDecision(HybridPriority.P2, codes, "Investigate the current behavioural, risk, and infrastructure signals; attribution or corroboration remains incomplete.")
    codes = ["INSUFFICIENT_ATTRIBUTION"]
    if watch: codes.append("WATCH_ACTIVE")
    if not movement: codes.append("NO_REALTIME_MOVEMENT")
    return RuleDecision(HybridPriority.P3, codes, "Current evidence is insufficient for strong attribution. Maintain the wallet watch where active and reassess on new transaction activity.")
