"""Deterministic, evidence-backed investigative risk posture calculation.

Score is normalized 0–100 from weighted factor contributions.
Raw weights sum to ~156 max; dividing by 1.56 normalises to 100.
Same evidence always produces the same score (no randomness).

Risk bands:
  0–19   LOW
  20–39  GUARDED
  40–59  ELEVATED
  60–79  HIGH
  80–100 CRITICAL
"""
from datetime import datetime, timezone
from uuid import uuid4

from .domain import *

_CONFIDENCE_RANK = {
    ConfidenceLevel.UNKNOWN: 0,
    ConfidenceLevel.LOW: 1,
    ConfidenceLevel.MEDIUM: 2,
    ConfidenceLevel.HIGH: 3,
    ConfidenceLevel.CONFIRMED: 4,
}

# Maximum raw score before normalisation (sum of all max_contributions below)
_RAW_MAX = 156.0

# Fraud typology bonus map — maps fraud_type keywords to bonus points (raw)
_TYPOLOGY_BONUS: dict[str, float] = {
    "scam": 6.0,
    "fraud": 5.0,
    "extortion": 5.0,
    "ransomware": 5.0,
    "phishing": 4.0,
    "ponzi": 4.0,
    "rug": 4.0,
    "hack": 4.0,
    "theft": 3.0,
    "money launder": 5.0,
    "laundering": 5.0,
    "wash": 3.0,
}


def default_risk_config() -> RiskScoringConfig:
    definitions = [
        # ── Pattern-based factors ─────────────────────────────────────────────
        RiskFactorDefinition(
            id="pattern:rapid_hop", name="Rapid multi-hop movement",
            category="TRANSACTION_BEHAVIOR",
            default_weight=16, max_contribution=24,
            explanation_template="Observed rapid-hop behaviour across {count} persisted pattern observation(s) — funds moved through multiple hops in rapid succession.",
        ),
        RiskFactorDefinition(
            id="pattern:mixer_interaction", name="Mixer interaction",
            category="ENTITY_EXPOSURE",
            default_weight=14, max_contribution=20,
            explanation_template="Observed {count} interaction(s) with addresses attributed to cryptocurrency mixing services.",
        ),
        RiskFactorDefinition(
            id="pattern:bridge_hop", name="Cross-chain bridge movement",
            category="CROSS_CHAIN_BEHAVIOR",
            default_weight=11, max_contribution=16,
            explanation_template="Observed {count} bridge-mediated cross-chain movement(s) — funds crossed chain boundaries via a bridge protocol.",
        ),
        RiskFactorDefinition(
            id="pattern:fan_out", name="Fan-out dispersion",
            category="TRANSACTION_BEHAVIOR",
            default_weight=7, max_contribution=10,
            explanation_template="Observed fan-out dispersion across {count} observation(s) — a single source distributing to multiple destinations.",
        ),
        RiskFactorDefinition(
            id="pattern:fan_in", name="Fan-in consolidation",
            category="TRANSACTION_BEHAVIOR",
            default_weight=7, max_contribution=10,
            explanation_template="Observed fan-in consolidation across {count} observation(s) — multiple sources converging to a common destination.",
        ),
        RiskFactorDefinition(
            id="pattern:peel_chain", name="Peel-chain behaviour",
            category="FLOW_CHARACTERISTICS",
            default_weight=5, max_contribution=8,
            explanation_template="Observed peel-chain forwarding in {count} observation(s) — sequential hops with residual value left at each step.",
        ),
        RiskFactorDefinition(
            id="pattern:burst_activity", name="Burst activity",
            category="TEMPORAL_CHARACTERISTICS",
            default_weight=5, max_contribution=8,
            explanation_template="Observed high transaction density (burst) in {count} observation(s).",
        ),
        RiskFactorDefinition(
            id="pattern:consolidation", name="Value consolidation",
            category="FLOW_CHARACTERISTICS",
            default_weight=4, max_contribution=6,
            explanation_template="Observed {count} consolidation event(s) — multiple source flows merging before onward movement.",
        ),
        RiskFactorDefinition(
            id="pattern:cross_chain_hop", name="Cross-chain hop",
            category="CROSS_CHAIN_BEHAVIOR",
            default_weight=4, max_contribution=6,
            explanation_template="Observed {count} evidence-backed cross-chain hop(s).",
        ),
        RiskFactorDefinition(
            id="pattern:dormant_activation", name="Dormant-to-active transition",
            category="TEMPORAL_CHARACTERISTICS",
            default_weight=3, max_contribution=4,
            explanation_template="Observed a prolonged inactivity period followed by rapid activity — a dormant wallet reactivation signal.",
        ),
        # ── Entity-based factors ─────────────────────────────────────────────
        RiskFactorDefinition(
            id="entity:mixer", name="Direct mixer entity exposure",
            category="ENTITY_EXPOSURE",
            default_weight=4, max_contribution=6,
            explanation_template="Observed a path reaching an address attributed to a mixer entity.",
        ),
        RiskFactorDefinition(
            id="entity:vasp", name="VASP / exchange proximity",
            category="ENTITY_EXPOSURE",
            default_weight=8, max_contribution=12,
            explanation_template="Observed {count} path(s) reaching source-backed attributed VASP or exchange entity/entities.",
        ),
        RiskFactorDefinition(
            id="entity:bridge", name="Bridge entity exposure",
            category="ENTITY_EXPOSURE",
            default_weight=3, max_contribution=4,
            explanation_template="Observed interaction with an address attributed to a bridge protocol.",
        ),
        # ── Graph / structural factors ────────────────────────────────────────
        RiskFactorDefinition(
            id="graph:hop_depth", name="Deep graph traversal",
            category="GRAPH_CHARACTERISTICS",
            default_weight=5, max_contribution=8,
            explanation_template="The bounded graph reached {hops} observed hops — deep layering is a structural obfuscation indicator.",
        ),
        # ── Value / velocity factors ──────────────────────────────────────────
        RiskFactorDefinition(
            id="value:high_transfer", name="High-value transfer",
            category="VALUE_CHARACTERISTICS",
            default_weight=7, max_contribution=14,
            explanation_template="Observed high-value transfer(s): {detail}.",
        ),
        # ── Fraud typology ────────────────────────────────────────────────────
        RiskFactorDefinition(
            id="fraud:typology", name="High-risk fraud typology",
            category="CASE_CONTEXT",
            default_weight=2, max_contribution=6,
            explanation_template="Case fraud typology '{fraud_type}' is associated with elevated layering risk.",
        ),
    ]
    return RiskScoringConfig(version="phase6-weighted-v2", factors=definitions, thresholds=RiskBandThresholds())


class RiskEngine:
    """Pure calculation boundary — no persistence, no external I/O.

    Score derivation:
      raw_score = sum of factor contributions (capped at each factor's max_contribution)
      final_score = min(100, round(raw_score / (_RAW_MAX / 100), 1))

    This guarantees natural variation: cases with only 1–2 signals score LOW/GUARDED,
    while cases combining mixer + bridge + rapid-hop + high-value reach CRITICAL.
    """

    def assess(
        self,
        trace: TraceResult,
        patterns: list[PatternObservation],
        attributions: list[NearestEntityResult],
        subject: RiskSubject,
        config: RiskScoringConfig | None = None,
        previous: RiskAssessment | None = None,
        calculated_at: datetime | None = None,
        case_fraud_type: str = "",
    ) -> RiskAssessment:
        config = config or default_risk_config()
        if not config.factors:
            config = default_risk_config().model_copy(update={"version": config.version, "thresholds": config.thresholds})
        self._validate_config(config)
        now = calculated_at or datetime.now(timezone.utc)

        unique_patterns = self._unique_patterns(patterns)
        unique_attributions = self._unique_attributions(attributions)

        factors: list[RiskFactor] = []

        for definition in config.factors:
            if not definition.enabled:
                continue

            factor: RiskFactor | None = None

            if definition.id.startswith("pattern:"):
                pattern_type = definition.id.split(":", 1)[1].upper()
                # Match both exact type and semantic aliases
                matches = [
                    p for p in unique_patterns
                    if self._pattern_matches(p.pattern_type, pattern_type) and (p.evidence_ids or p.transaction_hashes)
                ]
                if matches:
                    factor = self._pattern_factor(definition, matches)

            elif definition.id.startswith("entity:"):
                entity_type = definition.id.split(":", 1)[1].upper()
                matches = [
                    a for a in unique_attributions
                    if a.entity.entity_type == entity_type and self._entity_evidence(a)
                ]
                if matches:
                    factor = self._entity_factor(definition, matches)

            elif definition.id == "graph:hop_depth":
                if trace.metrics.maximum_hop >= 3:
                    evidence = list(dict.fromkeys(e.evidence_id for e in trace.edges if e.evidence_id))
                    tx_hashes = list(dict.fromkeys(e.transaction_hash for e in trace.edges if e.transaction_hash))
                    if tx_hashes:
                        # Scale by hop depth: 3 hops = base, 5+ = max
                        hop_contribution = min(
                            definition.max_contribution,
                            definition.default_weight * (trace.metrics.maximum_hop - 2) / 3.0
                        )
                        hop_contribution = max(definition.default_weight * 0.5, hop_contribution)
                        factor = RiskFactor(
                            factor_id=str(uuid4()),
                            definition_id=definition.id,
                            name=definition.name,
                            category=definition.category,
                            contribution=round(min(definition.max_contribution, hop_contribution), 2),
                            max_contribution=definition.max_contribution,
                            explanation=definition.explanation_template.format(hops=trace.metrics.maximum_hop),
                            confidence_level=ConfidenceLevel.MEDIUM,
                            transaction_hashes=tx_hashes[:20],
                            evidence_ids=evidence[:20],
                            metadata={"maximum_hop": trace.metrics.maximum_hop},
                        )

            elif definition.id == "value:high_transfer":
                factor = self._value_factor(definition, trace)

            elif definition.id == "fraud:typology":
                factor = self._typology_factor(definition, case_fraud_type, trace)

            if factor is not None:
                factors.append(factor)

        # Normalise to 0–100
        raw_score = sum(f.contribution for f in factors)
        score = round(min(100.0, max(0.0, raw_score * 100.0 / _RAW_MAX)), 1)

        band = self._band(score, config.thresholds)
        priority, reason = self._priority(band, trace, now)
        delta = self._delta(previous, score, factors) if previous else RiskDelta(
            current_score=score,
            delta=score,
            new_factors=[f.definition_id for f in factors],
        )

        evidence_ids = list(dict.fromkeys(e for f in factors for e in f.evidence_ids))
        pattern_ids = list(dict.fromkeys(p for f in factors for p in f.pattern_ids))
        entity_ids = list(dict.fromkeys(e for f in factors for e in f.entity_ids))

        return RiskAssessment(
            assessment_id=str(uuid4()),
            case_id=trace.case_id,
            trace_id=trace.trace_id,
            subject=subject,
            version=(previous.version + 1 if previous else 1),
            score=score,
            band=band,
            priority=priority,
            priority_reason=reason,
            factors=sorted(factors, key=lambda f: f.contribution, reverse=True),
            delta=delta,
            calculation_version=config.version,
            calculated_at=now,
            evidence_ids=evidence_ids,
            pattern_ids=pattern_ids,
            entity_ids=entity_ids,
            explanation="Investigative risk posture derived from source-backed observations and persisted blockchain evidence; it is not a legal or criminality determination.",
            previous_assessment_id=previous.assessment_id if previous else None,
        )

    # ─── Factor builders ────────────────────────────────────────────────────

    def _pattern_factor(self, definition: RiskFactorDefinition, matches: list[PatternObservation]) -> RiskFactor:
        evidence = list(dict.fromkeys(e for item in matches for e in item.evidence_ids))
        txs = list(dict.fromkeys(t for item in matches for t in item.transaction_hashes))
        pattern_ids = [p.pattern_id for p in matches]
        nodes = list(dict.fromkeys(n for item in matches for n in item.affected_nodes))
        confidence = max(
            (p.confidence_level for p in matches),
            key=lambda x: _CONFIDENCE_RANK[x],
            default=ConfidenceLevel.UNKNOWN,
        )
        # Scale by observation count but cap at max_contribution
        count = len(matches)
        contribution = round(min(
            definition.max_contribution,
            definition.default_weight + (count - 1) * definition.default_weight * 0.4,
        ), 2)
        return RiskFactor(
            factor_id=str(uuid4()),
            definition_id=definition.id,
            name=definition.name,
            category=definition.category,
            contribution=contribution,
            max_contribution=definition.max_contribution,
            explanation=definition.explanation_template.format(count=count),
            confidence_level=confidence,
            pattern_ids=pattern_ids,
            transaction_hashes=txs[:50],
            evidence_ids=evidence[:50],
            metadata={"affected_nodes": nodes, "observation_count": count},
        )

    def _entity_factor(self, definition: RiskFactorDefinition, matches: list[NearestEntityResult]) -> RiskFactor:
        evidence = list(dict.fromkeys(e for item in matches for e in self._entity_evidence(item)))
        entities = list(dict.fromkeys(item.entity.entity_id for item in matches))
        txs = list(dict.fromkeys(
            edge.transfer.tx_hash
            for item in matches
            for edge in item.path.edges
            if edge.transfer.tx_hash
        ))
        count = len(matches)
        contribution = round(min(
            definition.max_contribution,
            definition.default_weight + (count - 1) * definition.default_weight * 0.3,
        ), 2)
        confidence = max(
            (item.confidence for item in matches),
            key=lambda x: _CONFIDENCE_RANK[x],
            default=ConfidenceLevel.UNKNOWN,
        )
        entity_names = [item.entity.name for item in matches]
        hop_distances = [item.hop_distance for item in matches]
        return RiskFactor(
            factor_id=str(uuid4()),
            definition_id=definition.id,
            name=definition.name,
            category=definition.category,
            contribution=contribution,
            max_contribution=definition.max_contribution,
            explanation=definition.explanation_template.format(count=count),
            confidence_level=confidence,
            entity_ids=entities,
            transaction_hashes=txs[:30],
            evidence_ids=evidence[:30],
            metadata={"entity_names": entity_names, "hop_distances": hop_distances},
        )

    def _value_factor(self, definition: RiskFactorDefinition, trace: TraceResult) -> RiskFactor | None:
        """Scale contribution by the maximum observed transfer value in the trace."""
        if not trace.edges:
            return None
        amounts = []
        for edge in trace.edges:
            try:
                val = float(edge.transfer.amount or "0")
                amounts.append((val, edge))
            except (ValueError, AttributeError):
                pass
        if not amounts:
            return None
        amounts.sort(key=lambda x: x[0], reverse=True)
        max_val, max_edge = amounts[0]
        total_val = sum(v for v, _ in amounts)

        # Tier the contribution: treat anything >50 as token-scale (USDC etc)
        # Native ETH: >10=HIGH, >1=MEDIUM, >0.1=LOW-MED
        # Token: >10000=HIGH, >1000=MEDIUM
        if max_val >= 10000:
            # Likely token (USDC, USDT) in large quantity
            tier = 1.0
            detail = f"{max_val:,.0f} {max_edge.transfer.asset} (total: {total_val:,.0f})"
        elif max_val >= 1000:
            tier = 0.75
            detail = f"{max_val:,.0f} {max_edge.transfer.asset}"
        elif max_val >= 10:
            tier = 0.5
            detail = f"{max_val:.2f} {max_edge.transfer.asset}"
        elif max_val >= 1:
            tier = 0.3
            detail = f"{max_val:.4f} {max_edge.transfer.asset}"
        else:
            # Very small amounts — no value factor
            return None

        contribution = round(min(definition.max_contribution, definition.default_weight * tier * 2), 2)
        if contribution < 1.0:
            return None

        top_txs = [e.transaction_hash for _, e in amounts[:10] if e.transaction_hash]
        top_evidence = [e.evidence_id for _, e in amounts[:10] if e.evidence_id]

        return RiskFactor(
            factor_id=str(uuid4()),
            definition_id=definition.id,
            name=definition.name,
            category=definition.category,
            contribution=contribution,
            max_contribution=definition.max_contribution,
            explanation=definition.explanation_template.format(detail=detail),
            confidence_level=ConfidenceLevel.HIGH,
            transaction_hashes=top_txs,
            evidence_ids=top_evidence,
            metadata={"max_value": max_val, "total_value": total_val, "asset": max_edge.transfer.asset, "tier": tier},
        )

    def _typology_factor(self, definition: RiskFactorDefinition, fraud_type: str, trace: TraceResult) -> RiskFactor | None:
        """Award a small bonus when the case fraud typology is high-risk."""
        if not fraud_type:
            return None
        ft_lower = fraud_type.lower()
        bonus = 0.0
        matched_keyword = ""
        for keyword, points in _TYPOLOGY_BONUS.items():
            if keyword in ft_lower:
                if points > bonus:
                    bonus = points
                    matched_keyword = keyword
        if bonus < 1.0:
            return None
        contribution = round(min(definition.max_contribution, bonus), 2)
        # Grab a few evidence IDs from trace for traceability
        evidence = list(dict.fromkeys(e.evidence_id for e in trace.edges if e.evidence_id))[:5]
        txs = list(dict.fromkeys(e.transaction_hash for e in trace.edges if e.transaction_hash))[:5]
        return RiskFactor(
            factor_id=str(uuid4()),
            definition_id=definition.id,
            name=definition.name,
            category=definition.category,
            contribution=contribution,
            max_contribution=definition.max_contribution,
            explanation=definition.explanation_template.format(fraud_type=fraud_type),
            confidence_level=ConfidenceLevel.MEDIUM,
            transaction_hashes=txs,
            evidence_ids=evidence,
            metadata={"fraud_type": fraud_type, "matched_keyword": matched_keyword, "raw_bonus": bonus},
        )

    # ─── Helpers ─────────────────────────────────────────────────────────────

    @staticmethod
    def _pattern_matches(pattern_type: str, target: str) -> bool:
        """Allow semantic aliases so risk factors match related pattern types."""
        aliases: dict[str, set[str]] = {
            "MIXER_INTERACTION": {"MIXER_INTERACTION", "ENTITY_EXPOSURE"},
            "BRIDGE_HOP": {"BRIDGE_HOP", "BRIDGE_INTERACTION", "BRIDGE_TO_ENTITY_EXPOSURE"},
            "CROSS_CHAIN_HOP": {"CROSS_CHAIN_HOP", "RAPID_CROSS_CHAIN_MOVEMENT", "CROSS_CHAIN_FRAGMENTATION", "MULTI_CHAIN_PEEL_CHAIN"},
            "FAN_OUT": {"FAN_OUT"},
            "FAN_IN": {"FAN_IN", "CROSS_CHAIN_CONSOLIDATION"},
            "RAPID_HOP": {"RAPID_HOP", "RAPID_CROSS_CHAIN_MOVEMENT"},
            "PEEL_CHAIN": {"PEEL_CHAIN", "MULTI_CHAIN_PEEL_CHAIN"},
            "CONSOLIDATION": {"CONSOLIDATION", "CROSS_CHAIN_CONSOLIDATION"},
        }
        allowed = aliases.get(target, {target})
        return pattern_type in allowed

    @staticmethod
    def _entity_evidence(item: NearestEntityResult) -> list[str]:
        return list(dict.fromkeys(
            [e.evidence_id for e in item.evidence if e.evidence_id]
            + [edge.evidence_id for edge in item.path.edges if edge.evidence_id]
        ))

    @staticmethod
    def _unique_patterns(patterns: list[PatternObservation]) -> list[PatternObservation]:
        unique: dict[str, PatternObservation] = {}
        for item in patterns:
            key = item.fingerprint or f"{item.pattern_type}:{','.join(sorted(item.transaction_hashes))}:{','.join(sorted(item.evidence_ids))}"
            unique[key] = item
        return list(unique.values())

    @staticmethod
    def _unique_attributions(attributions: list[NearestEntityResult]) -> list[NearestEntityResult]:
        unique: dict[str, NearestEntityResult] = {}
        for item in attributions:
            unique[f"{item.entity.entity_id}:{item.address.lower()}"] = item
        return list(unique.values())

    @staticmethod
    def _validate_config(config: RiskScoringConfig) -> None:
        t = config.thresholds
        if not t.guarded_min <= t.elevated_min <= t.high_min <= t.critical_min:
            raise ValueError("Risk band thresholds must be monotonic")
        if any(f.max_contribution < f.default_weight for f in config.factors if f.enabled):
            raise ValueError("Risk factor max_contribution must be >= default_weight")

    @staticmethod
    def _band(score: float, thresholds: RiskBandThresholds) -> RiskBand:
        if score >= thresholds.critical_min:
            return RiskBand.CRITICAL
        if score >= thresholds.high_min:
            return RiskBand.HIGH
        if score >= thresholds.elevated_min:
            return RiskBand.ELEVATED
        if score >= thresholds.guarded_min:
            return RiskBand.GUARDED
        return RiskBand.LOW

    @staticmethod
    def _priority(band: RiskBand, trace: TraceResult, now: datetime) -> tuple[InvestigativePriority, str]:
        latest = max(
            (e.transfer.timestamp for e in trace.edges if e.transfer.timestamp),
            default=None,
        )
        recent = latest is not None and 0 <= (now - latest).total_seconds() <= 3600
        if recent and band in {RiskBand.HIGH, RiskBand.CRITICAL}:
            return InvestigativePriority.URGENT, "Recent observed activity falls within the one-hour freshness window."
        mapping = {
            RiskBand.CRITICAL: InvestigativePriority.URGENT,
            RiskBand.HIGH: InvestigativePriority.PRIORITY,
            RiskBand.ELEVATED: InvestigativePriority.REVIEW,
            RiskBand.GUARDED: InvestigativePriority.REVIEW,
            RiskBand.LOW: InvestigativePriority.INFORMATIONAL,
        }
        return mapping[band], "Priority reflects the calculated investigative risk posture; live monitoring is not inferred."

    def _delta(self, previous: RiskAssessment, score: float, factors: list[RiskFactor]) -> RiskDelta:
        before = {f.definition_id: f for f in previous.factors}
        after = {f.definition_id: f for f in factors}
        new = [k for k in after if k not in before]
        removed = [k for k in before if k not in after]
        changed = [k for k in after if k in before and after[k].contribution != before[k].contribution]
        return RiskDelta(
            previous_score=previous.score,
            current_score=score,
            delta=round(score - previous.score, 2),
            new_factors=new,
            removed_factors=removed,
            changed_factors=changed,
        )
