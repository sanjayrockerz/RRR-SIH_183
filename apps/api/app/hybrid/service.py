from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from uuid import uuid4

from .rules import RULESET_VERSION, decide
from .schemas import HybridInvestigationIntelligence, HybridPriority, HybridSnapshot, HybridStatus

logger = logging.getLogger("crypto_fraud_intelligence")


def _dump(value):
    if value is None: return None
    if hasattr(value, "model_dump"): return value.model_dump(mode="json")
    if isinstance(value, dict): return {str(k): _dump(v) for k, v in value.items()}
    if hasattr(value, "__dict__"): return {str(k): _dump(v) for k, v in vars(value).items() if not k.startswith("_")}
    return value


class HybridInvestigationIntelligenceService:
    def __init__(self, repository, vasp_resolver=None):
        self.repository = repository
        self.vasp_resolver = vasp_resolver

    async def build_case_intelligence(self, case_id: str, *, persist: bool = True) -> HybridInvestigationIntelligence:
        case = await self.repository.get(case_id)
        if not case: raise ValueError("Case not found")
        generated_at = datetime.now(timezone.utc)
        risk = await self._safe("latest_risk", case_id)
        ml_rows = await self._safe("ml_inferences", case_id=case_id, limit=1) or []
        ml = ml_rows[0] if ml_rows else None
        patterns = await self._safe("list_patterns", case_id) or []
        pattern_summary = await self._safe("pattern_summary", case_id) or {}
        threat_rows = await self._safe("threat_intel_observations", case_id=case_id) or []
        related = await self._safe("related_cases", case_id) or []
        cross_links = await self._safe("cross_chain_links", case_id) or []
        watches = await self._safe("list_watches", case_id) or []
        events = await self._safe("list_realtime_events", case_id, limit=20) or []
        registry = None
        if case.wallets:
            wallet = case.wallets[0]
            registry = await self._safe("risk_registry_wallet", wallet.chain, wallet.address)
        vasp_candidates = []
        if self.vasp_resolver and case.latest_trace:
            try:
                vasp_candidates = await self.vasp_resolver(case.latest_trace)
            except Exception:
                vasp_candidates = []

        risk_dict = _dump(risk) or {}
        ml_dict = _dump(ml) or {}
        pattern_dict = _dump(pattern_summary) or {"total_patterns": len(patterns), "pattern_ids": [getattr(p, "pattern_id", None) for p in patterns]}
        threat_dict = {"status": "DIRECT_MATCH" if any(str(getattr(x, "match_type", "")) == "DIRECT_MATCH" for x in threat_rows) else (str(getattr(threat_rows[0], "raw_status", "NO_DATA")) if threat_rows else "NO_DATA"), "observations": [_dump(x) for x in threat_rows]}
        fusion_dict = {"related_cases": [_dump(x) for x in related], "confirmed_structural_overlap": bool(related), "similarity_is_not_common_ownership": True}
        cross_dict = {"links": [_dump(x) for x in cross_links], "continuation": any(getattr(x, "destination", None) is not None for x in cross_links), "inferred": any(str(getattr(x, "observed_or_inferred", "")).upper() != "OBSERVED" for x in cross_links)}
        vasp_dict = {"candidates": [_dump(x) for x in vasp_candidates], "selected": _dump(vasp_candidates[0]) if vasp_candidates else None}
        realtime_dict = {"watch_active": any(str(getattr(w, "status", "")).upper() in {"ACTIVE", "MONITORED"} for w in watches), "new_movement_detected": bool(events), "last_event_timestamp": getattr(events[0], "observed_at", None) if events else None, "event_ids": [getattr(x, "event_id", None) for x in events]}
        vasp = vasp_candidates[0] if vasp_candidates else None
        confidence = str(getattr(vasp, "attribution_confidence", "UNKNOWN")).upper() if vasp else "UNKNOWN"
        risk_band_value = getattr(risk, "band", None) if risk else None
        if risk_band_value is None and isinstance(risk_dict, dict): risk_band_value = risk_dict.get("band", "")
        risk_band = str(risk_band_value or "").split(".")[-1].upper()
        risk_delta = float(getattr(getattr(risk, "delta", None), "delta", 0) or 0) if risk else 0
        direct = threat_dict["status"] == "DIRECT_MATCH"
        state = {"risk_band": risk_band, "risk_increased": risk_delta > 0, "ml_high": ml_dict.get("classification") in {"HIGH_RISK_LIKE", "HIGH-RISK-LIKE BEHAVIOUR"} or (ml_dict.get("probability") is not None and float(ml_dict["probability"]) >= float(ml_dict.get("threshold", .63))), "movement": realtime_dict["new_movement_detected"], "direct_threat": direct, "vasp": bool(vasp and getattr(vasp, "classification", "UNRESOLVED") != "UNRESOLVED"), "vasp_confirmed": confidence in {"HIGH", "CONFIRMED"}, "cross_chain": cross_dict["continuation"], "fusion": bool(related), "registry_high": str(getattr(registry, "highest_investigative_risk_band", "")).upper() in {"HIGH", "CRITICAL"}, "patterns": bool(patterns) or bool(pattern_dict.get("total_patterns")), "watch": realtime_dict["watch_active"]}
        decision = decide(state)
        evidence = self._evidence(risk, ml, patterns, threat_rows, registry, related, vasp, cross_links, events)
        limitations = self._limitations(ml, threat_dict, vasp, cross_dict, realtime_dict, fusion_dict)
        signal_summary = {"risk": risk_dict, "ml": ml_dict, "patterns": pattern_dict, "threat_intelligence": threat_dict, "risk_registry": _dump(registry) or {}, "case_fusion": fusion_dict, "vasp": vasp_dict, "cross_chain": cross_dict, "realtime": realtime_dict}
        state_payload = {"ruleset_version": RULESET_VERSION, "priority": decision.priority.value, "recommendation": decision.recommendation, "reason_codes": decision.reason_codes, "signals": signal_summary, "evidence": evidence, "limitations": limitations}
        state_hash = hashlib.sha256(json.dumps(state_payload, sort_keys=True, default=str, separators=(",", ":")).encode()).hexdigest()
        previous = await self._safe("get_latest_hybrid_snapshot", case_id)
        previous_priority = getattr(previous, "priority", None) if previous else (previous or {}).get("priority") if isinstance(previous, dict) else None
        previous_priority = HybridPriority(str(previous_priority)) if previous_priority and str(previous_priority) in {x.value for x in HybridPriority} else None
        intelligence = HybridInvestigationIntelligence(case_id=case_id, generated_at=generated_at, ruleset_version=RULESET_VERSION, status=HybridStatus.READY, deterministic_risk=risk_dict, ml_behavioural_intelligence=ml_dict, pattern_summary=pattern_dict, threat_intelligence=threat_dict, risk_registry_summary=_dump(registry) or {}, case_fusion_summary=fusion_dict, vasp_actionability=vasp_dict, realtime_state=realtime_dict, cross_chain=cross_dict, priority=decision.priority, recommendation=decision.recommendation, reason_codes=decision.reason_codes, evidence_refs=evidence, limitations=limitations, previous_priority=previous_priority, priority_changed=previous_priority is not None and previous_priority != decision.priority, state_hash=state_hash)
        if persist and hasattr(self.repository, "persist_hybrid_snapshot"):
            await self.repository.persist_hybrid_snapshot(intelligence)
        logger.info("hybrid_intelligence_built", extra={"case_id": case_id, "priority": decision.priority.value, "reason_codes": decision.reason_codes})
        return intelligence

    async def latest_case_intelligence(self, case_id: str):
        row = await self._safe("get_latest_hybrid_snapshot", case_id)
        if not row: return None
        payload = row.get("signal_summary_json") if isinstance(row, dict) else getattr(row, "signal_summary_json", None)
        if isinstance(payload, dict) and payload.get("case_id"):
            return HybridInvestigationIntelligence(**payload)
        return None

    async def history(self, case_id: str):
        rows = await self._safe("list_hybrid_snapshots", case_id) or []
        result = []
        for row in rows:
            if isinstance(row, dict):
                result.append(HybridSnapshot(id=row["id"], case_id=row["case_id"], ruleset_version=row["ruleset_version"], priority=row["priority"], recommendation_text=row["recommendation_text"], reason_codes=row.get("reason_codes_json", []), signal_summary=row.get("signal_summary_json", {}), evidence_refs=row.get("evidence_refs_json", []), limitations=row.get("limitations_json", []), previous_priority=row.get("previous_priority"), priority_changed=row.get("priority_changed", False), state_hash=row["state_hash"], generated_at=row["generated_at"], created_at=row["created_at"]))
        return result

    async def _safe(self, method, *args, **kwargs):
        fn = getattr(self.repository, method, None)
        if not fn: return None
        try: return await fn(*args, **kwargs)
        except Exception as exc:
            logger.warning("hybrid_signal_unavailable", extra={"signal": method, "error_type": type(exc).__name__})
            return None

    def _evidence(self, risk, ml, patterns, threat, registry, related, vasp, cross, events):
        refs = []
        def add(kind, values):
            for value in values:
                if value: refs.append({"type": kind, "id": str(value)})
        add("RISK_ASSESSMENT", [getattr(risk, "assessment_id", None)]); add("ML_ASSESSMENT", [ml.get("inference_id") if isinstance(ml, dict) else None]); add("PATTERN_OBSERVATION", [getattr(x, "pattern_id", None) for x in patterns]); add("THREAT_INTEL_OBSERVATION", [getattr(x, "observation_id", None) for x in threat]); add("RISK_REGISTRY", [getattr(registry, "record_id", None)]); add("CASE_FUSION", [getattr(x, "link_id", None) for x in related]); add("VASP_ATTRIBUTION", [getattr(vasp, "entity_id", None) if vasp else None]); add("CROSS_CHAIN_LINK", [getattr(x, "link_id", None) for x in cross]); add("REALTIME_EVENT", [getattr(x, "event_id", None) for x in events]); return refs

    def _limitations(self, ml, threat, vasp, cross, realtime, fusion):
        result = []
        if not ml: result.append("ML assessment is unavailable; deterministic signals remain usable.")
        if threat["status"] in {"NOT_CONFIGURED", "NO_DATA"}: result.append("No Chainabuse direct match is available from the current persisted provider state.")
        if vasp and str(getattr(vasp, "attribution_confidence", "UNKNOWN")).upper() not in {"HIGH", "CONFIRMED"}: result.append("VASP attribution is probable, not source-confirmed.")
        if not vasp: result.append("VASP attribution is unresolved.")
        if cross.get("inferred"): result.append("Cross-chain continuation includes inferred correlation and requires investigator review.")
        if fusion.get("confirmed_structural_overlap"): result.append("Case Fusion similarity is structural and does not prove common ownership or coordinated control.")
        if not realtime["watch_active"]: result.append("No realtime watch is active.")
        return result
