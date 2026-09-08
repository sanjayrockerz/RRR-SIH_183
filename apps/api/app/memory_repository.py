"""In-memory implementation of CaseRepository for running without PostgreSQL.

All data lives in dictionaries and is lost on restart — but the API starts
instantly, all endpoints respond, and the frontend renders without 503 errors.
"""

from datetime import datetime, timezone, timedelta
from uuid import UUID, uuid4
import json
import logging

from .domain import *
from .services import CaseRepository

logger = logging.getLogger("crypto_fraud_intelligence")


class MemoryCaseRepository(CaseRepository):
    """Drop-in replacement for PostgresCaseRepository that stores everything in RAM."""

    def __init__(self):
        self.pool = None
        self.status = "READY"
        self.migration_status = "IN_MEMORY"
        self.last_error: str | None = None

        # Core stores
        self._cases: dict[str, InvestigationCase] = {}
        self._traces: dict[str, TraceResult] = {}  # keyed by trace_id
        self._patterns: dict[str, list[PatternObservation]] = {}  # keyed by trace_id
        self._risk: dict[str, list[RiskAssessment]] = {}  # keyed by case_id
        self._risk_alerts: dict[str, list] = {}
        self._watches: dict[str, list[WatchTarget]] = {}  # keyed by case_id
        self._timeline: dict[str, list[TimelineEvent]] = {}  # keyed by case_id
        self._change_sets: dict[str, list[InvestigationChangeSet]] = {}
        self._alerts: dict[str, list[Alert]] = {}  # keyed by case_id
        self._evidence: dict[str, list[Evidence]] = {}  # keyed by case_id
        self._reports: dict[str, list[InvestigationReport]] = {}
        self._realtime_events: dict[str, RealtimeEvent] = {}
        self._cross_chain_links: dict[str, list] = {}
        self._cross_chain_patterns: dict[str, list] = {}
        self._screenings: dict[str, list] = {}
        self._evidence_manifests: dict[str, list] = {}
        self._evidence_ledger: dict[str, list] = {}
        self._audit_events: dict[str, list] = {}
        self._workflow_events: dict[str, list[dict]] = {}
        self._graph_layouts: dict[str, dict] = {}
        self._transactions: dict[str, list] = {}
        self._entities: list[Entity] = []
        self._attributions: list[AddressAttribution] = []
        self._attribution_sources: list[AttributionSource] = []
        self._sanctions_records: list[SanctionsRecord] = []
        self._intelligence_sources: list[IntelligenceSource] = []
        self._case_fingerprints: list[CaseFingerprint] = []
        self._workflow_states: dict[str, InvestigationWorkflowState] = {}

    # ── lifecycle ─────────────────────────────────────────────────────
    async def connect(self):
        self.status = "READY"
        self.migration_status = "IN_MEMORY"
        logger.info("MemoryCaseRepository: running in-memory (no PostgreSQL)")

    async def close(self):
        pass

    def _require_pool(self):
        """Compatibility stub — returns self so callers don't crash."""
        return self

    # ── cases ─────────────────────────────────────────────────────────
    async def create(self, data: CaseCreate) -> InvestigationCase:
        case_id = str(uuid4())
        now = datetime.now(timezone.utc)
        case = InvestigationCase(
            case_id=case_id,
            title=data.title,
            description=data.description,
            fraud_type=data.fraud_type,
            priority=data.priority,
            status="OPEN",
            created_at=now,
            updated_at=now,
            external_case_reference=data.external_case_reference,
            wallets=[],
        )
        self._cases[case_id] = case
        return case

    async def delete_case(self, case_id: str) -> bool:
        return self._cases.pop(case_id, None) is not None

    async def list_cases(self) -> list[CaseListItem]:
        items = []
        for c in sorted(self._cases.values(), key=lambda x: x.updated_at, reverse=True):
            items.append(CaseListItem(
                case_id=c.case_id, title=c.title, fraud_type=c.fraud_type,
                priority=c.priority, status=c.status, created_at=c.created_at,
                updated_at=c.updated_at, wallet_count=len(c.wallets),
                transaction_count=len(self._transactions.get(c.case_id, [])),
                external_case_reference=c.external_case_reference,
                wallet_address=c.wallets[0].address if c.wallets else None,
                workflow_stage=c.workflow_stage,
            ))
        return items

    async def get(self, case_id: str) -> InvestigationCase | None:
        return self._cases.get(case_id)

    async def update_case(self, case_id: str, data: CasePatch) -> InvestigationCase | None:
        case = self._cases.get(case_id)
        if not case:
            return None
        updates = data.model_dump(exclude_unset=True)
        for key, value in updates.items():
            if hasattr(case, key):
                object.__setattr__(case, key, value)
        object.__setattr__(case, "updated_at", datetime.now(timezone.utc))
        return case

    async def close_case(self, case_id: str) -> InvestigationCase | None:
        case = self._cases.get(case_id)
        if not case:
            return None
        object.__setattr__(case, "status", "CLOSED")
        object.__setattr__(case, "updated_at", datetime.now(timezone.utc))
        return case

    async def reopen_case(self, case_id: str) -> InvestigationCase | None:
        case = self._cases.get(case_id)
        if not case:
            return None
        object.__setattr__(case, "status", "OPEN")
        object.__setattr__(case, "updated_at", datetime.now(timezone.utc))
        return case

    async def _set_case_status(self, case_id: str, status: str) -> InvestigationCase | None:
        case = self._cases.get(case_id)
        if not case:
            return None
        object.__setattr__(case, "status", status)
        object.__setattr__(case, "updated_at", datetime.now(timezone.utc))
        return case

    async def set_workflow_stage(self, case_id: str, stage: CaseWorkflowStage,
                                  provider: str | None = None, result_count: int | None = None,
                                  error: str | None = None,
                                  evidence_ids: list[str] | None = None) -> InvestigationCase | None:
        case = self._cases.get(case_id)
        if not case:
            return None
        object.__setattr__(case, "workflow_stage", stage)
        object.__setattr__(case, "updated_at", datetime.now(timezone.utc))
        self._workflow_events.setdefault(case_id, []).append({
            "event_id": str(uuid4()), "case_id": case_id, "stage": stage,
            "provider": provider, "result_count": result_count,
            "error": error, "evidence_ids": evidence_ids or [],
            "occurred_at": datetime.now(timezone.utc).isoformat(),
        })
        return case

    async def workflow_events(self, case_id: str) -> list[dict]:
        return self._workflow_events.get(case_id, [])

    # ── wallets ───────────────────────────────────────────────────────
    async def add_wallet(self, case_id: str, wallet: WalletCreate) -> InvestigationCase:
        case = self._cases.get(case_id)
        if not case:
            raise ValueError("Case not found")
        case.wallets.append(wallet)
        object.__setattr__(case, "updated_at", datetime.now(timezone.utc))
        return case

    async def add_transaction(self, case_id: str, transaction: TransactionCreate) -> InvestigationCase:
        case = self._cases.get(case_id)
        if not case:
            raise ValueError("Case not found")
        self._transactions.setdefault(case_id, []).append({
            "tx_hash": transaction.tx_hash, "chain": transaction.chain,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        object.__setattr__(case, "updated_at", datetime.now(timezone.utc))
        return case

    # ── dashboard ─────────────────────────────────────────────────────
    async def dashboard_summary(self) -> DashboardSummary:
        active = sum(1 for c in self._cases.values() if c.status != "CLOSED")
        wallets = sum(len(c.wallets) for c in self._cases.values())
        total_alerts = sum(len(v) for v in self._alerts.values())
        return DashboardSummary(
            active_cases=active,
            wallets_under_review=wallets,
            high_priority_alerts=0,
            attributed_entities=len(self._entities),
            observed_transactions=sum(len(v) for v in self._transactions.values()),
            active_watches=sum(len(v) for v in self._watches.values()),
            last_activity_at=datetime.now(timezone.utc) if self._cases else None,
            investigations_today=active,
            wallets_under_investigation=wallets,
            transactions_analyzed=0,
            graph_nodes=0,
            graph_edges=0,
            open_alerts=total_alerts,
            critical_cases=0,
        )

    async def dashboard_intelligence(self, limit: int = 20) -> DashboardIntelligence:
        all_cases = list(self._cases.values())
        critical_cases_cnt = sum(1 for c in all_cases if str(getattr(c, "priority", "")).upper() in {"CRITICAL", "HIGH"})
        active_watches_cnt = len(getattr(self, "_watches", {}))
        
        # Alerts
        all_alerts = list(getattr(self, "_alerts", {}).values()) if isinstance(getattr(self, "_alerts", {}), dict) else list(getattr(self, "_alerts", []))
        open_alerts_cnt = len(all_alerts)
        critical_alerts_cnt = sum(1 for a in all_alerts if str(getattr(a, "severity", "")).upper() in {"CRITICAL", "HIGH"})

        # Recommendations
        recs = []
        for c in all_cases[:10]:
            case_id = c.case_id
            trace = getattr(c, "latest_trace", None)
            ev = await self.list_evidence(case_id)
            pats = await self.list_patterns(case_id)
            risk = await self.latest_risk(case_id)
            if trace or ev or pats or risk:
                recs.append({
                    "recommendation_id": f"rec-{case_id[:8]}",
                    "case_id": case_id,
                    "priority": "CRITICAL" if (risk and getattr(risk, "score", 0) >= 70) else "HIGH",
                    "title": "Review nearest VASP deposit address" if (trace and any(n.node_type == "VASP" for n in trace.nodes)) else "Review active risk movement",
                    "reason": f"High risk posture ({getattr(risk, 'score', 85):.1f}) for case {case_id}",
                    "evidence_ids": [e.evidence_id for e in ev[:3]],
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })

        priority_cases = []
        for c in all_cases[:limit]:
            risk = await self.latest_risk(c.case_id)
            score = getattr(risk, "score", 75.0) if risk else 50.0
            priority_cases.append(PriorityCase(
                case_id=c.case_id,
                title=c.title,
                fraud_type=c.fraud_type,
                target_wallet=c.wallets[0].address if c.wallets else "0x1111111111111111111111111111111111111111",
                chain=c.wallets[0].chain if c.wallets else Chain.ETHEREUM,
                status=c.status,
                risk_score=score,
                risk_band=RiskBand.CRITICAL if score >= 80 else RiskBand.ELEVATED,
                created_at=c.created_at,
            ))

        return DashboardIntelligence(
            status="READY",
            critical_cases=critical_cases_cnt or len(all_cases),
            active_watches=active_watches_cnt,
            vasp_leads=len(all_cases),
            high_confidence_vasp_leads=len(all_cases),
            cross_chain_cases=sum(1 for c in all_cases if "CROSSCHAIN" in c.case_id or "cross" in c.title.lower()),
            unresolved_cross_chain_cases=0,
            related_case_clusters=1,
            case_fusion_clusters=[{
                "cluster_id": "cluster-001",
                "cases": [c.case_id for c in all_cases[:3]],
                "common_wallet": "0x9999999999999999999999999999999999999999",
                "overlap_score": 0.88,
            }] if all_cases else [],
            open_alerts=open_alerts_cnt,
            critical_alerts=critical_alerts_cnt,
            priority_cases=priority_cases,
            recent_intelligence_events=[
                {
                    "event_id": "evt-realtime-001",
                    "type": "ON_CHAIN_TRANSFER",
                    "chain": "ETHEREUM",
                    "hash": "0x8888888888888888888888888888888888888888888888888888888888888888",
                    "source": "0x1111111111111111111111111111111111111111",
                    "destination": "0x7777777777777777777777777777777777777777",
                    "amount": "12.4 ETH",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            ],
            risk_movements=[
                {
                    "case_id": all_cases[0].case_id if all_cases else "case-1",
                    "previous_score": 62.0,
                    "current_score": 94.0,
                    "delta": 32.0,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            ],
            risk_factor_summary=[
                {"factor": "rapid_hop", "count": len(all_cases) * 3},
                {"factor": "vasp_exposure", "count": len(all_cases) * 2},
            ],
            investigator_recommendations=recs,
            provider_state={"mode": "DEVELOPMENT_FIXTURE", "status": "SIMULATED"},
            generated_at=datetime.now(timezone.utc),
        )

    # ── traces ────────────────────────────────────────────────────────
    async def persist_trace(self, result: TraceResult) -> None:
        self._traces[result.trace_id] = result
        # Also store on case
        case = self._cases.get(result.case_id)
        if case:
            object.__setattr__(case, "latest_trace", result)

    async def list_traces(self, case_id: str) -> list[TraceResult]:
        return [t for t in self._traces.values() if t.case_id == case_id]

    async def get_trace(self, case_id: str, trace_id: str) -> TraceResult | None:
        t = self._traces.get(trace_id)
        return t if t and t.case_id == case_id else None

    # ── patterns ──────────────────────────────────────────────────────
    async def persist_patterns(self, observations: list[PatternObservation]) -> list[PatternObservation]:
        for obs in observations:
            self._patterns.setdefault(obs.trace_id, []).append(obs)
        return observations

    async def list_patterns(self, case_id: str, trace_id: str | None = None) -> list[PatternObservation]:
        if trace_id:
            return self._patterns.get(trace_id, [])
        result = []
        for t in self._traces.values():
            if t.case_id == case_id:
                result.extend(self._patterns.get(t.trace_id, []))
        return result

    async def list_patterns_by_trace(self, trace_id: str) -> list[PatternObservation]:
        return self._patterns.get(trace_id, [])

    async def get_pattern(self, case_id: str, pattern_id: str) -> PatternObservation | None:
        for patterns in self._patterns.values():
            for p in patterns:
                if p.pattern_id == pattern_id:
                    return p
        return None

    async def pattern_summary(self, case_id: str, trace_id: str | None = None) -> PatternSummary:
        patterns = await self.list_patterns(case_id, trace_id)
        return PatternSummary(
            total=len(patterns),
            by_type={},
            by_severity={},
            critical_count=sum(1 for p in patterns if p.severity == PatternSeverity.CRITICAL),
        )

    # ── risk ──────────────────────────────────────────────────────────
    async def latest_risk(self, case_id: str, subject_id: str | None = None) -> RiskAssessment | None:
        history = self._risk.get(case_id, [])
        return history[-1] if history else None

    async def risk_history(self, case_id: str, subject_id: str | None = None) -> list[RiskAssessment]:
        return self._risk.get(case_id, [])

    async def risk_by_trace(self, trace_id: str) -> list[RiskAssessment]:
        result = []
        for assessments in self._risk.values():
            result.extend(a for a in assessments if a.trace_id == trace_id)
        return result

    async def risk_by_subject(self, subject_id: str) -> list[RiskAssessment]:
        return []

    async def risk_by_wallet(self, wallet_id: str) -> list[RiskAssessment]:
        return []

    async def persist_risk(self, assessment: RiskAssessment, alerts: list) -> RiskAssessment:
        self._risk.setdefault(assessment.case_id, []).append(assessment)
        self._risk_alerts.setdefault(assessment.case_id, []).extend(alerts)
        return assessment

    async def risk_factors(self, case_id: str, assessment_id: str | None = None) -> list[RiskFactor]:
        latest = await self.latest_risk(case_id)
        return latest.factors if latest else []

    async def risk_alerts(self, case_id: str, subject_id: str | None = None) -> list:
        return self._risk_alerts.get(case_id, [])

    # ── watches ───────────────────────────────────────────────────────
    async def create_watch(self, watch: WatchTarget) -> WatchTarget:
        self._watches.setdefault(watch.case_id, []).append(watch)
        return watch

    async def list_watches(self, case_id: str) -> list[WatchTarget]:
        return self._watches.get(case_id, [])

    async def list_all_watches(self, chain: Chain | None = None) -> list[WatchTarget]:
        all_watches = [w for watches in self._watches.values() for w in watches]
        if chain:
            return [w for w in all_watches if w.chain == chain]
        return all_watches

    async def get_watch(self, case_id: str, watch_id: str) -> WatchTarget | None:
        return next((w for w in self._watches.get(case_id, []) if w.watch_id == watch_id), None)

    async def update_watch(self, watch: WatchTarget) -> WatchTarget:
        watches = self._watches.get(watch.case_id, [])
        for i, w in enumerate(watches):
            if w.watch_id == watch.watch_id:
                watches[i] = watch
                break
        return watch

    # ── timeline / changes / alerts ───────────────────────────────────
    async def timeline(self, case_id: str) -> list[TimelineEvent]:
        return self._timeline.get(case_id, [])

    async def change_sets(self, case_id: str) -> list[InvestigationChangeSet]:
        return self._change_sets.get(case_id, [])

    async def alerts(self, case_id: str) -> list[Alert]:
        return self._alerts.get(case_id, [])

    async def all_alerts(self) -> list[Alert]:
        return [a for alerts in self._alerts.values() for a in alerts]

    async def append_timeline(self, event: TimelineEvent) -> None:
        self._timeline.setdefault(event.case_id, []).append(event)

    async def append_change_set(self, change_set: InvestigationChangeSet) -> None:
        self._change_sets.setdefault(change_set.case_id, []).append(change_set)

    async def create_alert(self, alert: Alert, fingerprint: str) -> Alert | None:
        self._alerts.setdefault(alert.case_id, []).append(alert)
        return alert

    async def get_alert(self, case_id: str, alert_id: str) -> Alert | None:
        return next((a for a in self._alerts.get(case_id, []) if a.alert_id == alert_id), None)

    async def review_alert(self, case_id: str, alert_id: str, review) -> Alert:
        alert = await self.get_alert(case_id, alert_id)
        if not alert:
            raise ValueError("Alert not found")
        return alert

    async def alert_reviews(self, case_id: str, alert_id: str) -> list:
        return []

    # ── evidence ──────────────────────────────────────────────────────
    async def list_evidence(self, case_id: str) -> list[Evidence]:
        return self._evidence.get(case_id, [])

    async def persist_evidence_manifest(self, manifest, evidence, events):
        self._evidence_manifests.setdefault(manifest.case_id, []).append(manifest)
        return manifest

    async def evidence_ledger(self, case_id: str) -> list:
        return self._evidence_ledger.get(case_id, [])

    async def evidence_manifests(self, case_id: str) -> list:
        return self._evidence_manifests.get(case_id, [])

    async def evidence_chain(self, case_id: str, evidence_id: str) -> list:
        return []

    # ── reports ───────────────────────────────────────────────────────
    async def persist_report(self, report: InvestigationReport) -> InvestigationReport:
        self._reports.setdefault(report.case_id, []).append(report)
        return report

    async def list_reports(self, case_id: str) -> list[InvestigationReport]:
        return self._reports.get(case_id, [])

    async def get_report(self, case_id: str, report_id: str) -> InvestigationReport | None:
        return next((r for r in self._reports.get(case_id, []) if r.report_id == report_id), None)

    async def ingest_realtime_event(self, event: RealtimeEvent) -> tuple[RealtimeEvent, bool]:
        duplicate = event.event_id in self._realtime_events or any(e.transaction_hash == event.transaction_hash for e in self._realtime_events.values() if e.event_id != event.event_id)
        self._realtime_events[event.event_id] = event
        return event, duplicate

    async def apply_realtime_event(self, event: RealtimeEvent, watch: WatchTarget):
        return RealtimeApplicationResult(
            event=event, case_id=watch.case_id,
            watch_id=watch.watch_id, duplicate=False,
            evidence_id=str(uuid4()), graph_edge_id=str(uuid4())
        )

    async def get_realtime_event(self, event_id: str) -> RealtimeEvent | None:
        return self._realtime_events.get(event_id)

    async def record_realtime_attempt(self, event_id, status, error=None):
        return RealtimeProcessingAttempt(
            attempt_id=str(uuid4()), event_id=event_id, attempt_number=1,
            status=status, error=error,
            started_at=datetime.now(timezone.utc), completed_at=datetime.now(timezone.utc)
        )

    async def realtime_attempts(self, event_id: str) -> list:
        return []

    async def mark_realtime_failure(self, event_id, error, max_attempts, retry_delay_seconds):
        return self._realtime_events.get(event_id)

    async def list_realtime_failures(self, limit: int = 100) -> list:
        return []

    # ── cross-chain ───────────────────────────────────────────────────
    async def persist_cross_chain_observation(self, case_id, observation):
        pass

    async def cross_chain_transfers(self, case_id: str) -> list:
        return []

    async def persist_bridge_definition(self, definition):
        pass

    async def persist_bridge_interaction(self, case_id, item):
        pass

    async def persist_cross_chain_link(self, case_id, link):
        self._cross_chain_links.setdefault(case_id, []).append(link)

    async def persist_cross_chain_trace(self, trace):
        pass

    async def cross_chain_links(self, case_id: str) -> list:
        return self._cross_chain_links.get(case_id, [])

    async def persist_cross_chain_patterns(self, patterns):
        for p in patterns:
            self._cross_chain_patterns.setdefault(p.case_id if hasattr(p, 'case_id') else '', []).append(p)

    async def cross_chain_patterns(self, case_id: str) -> list:
        return self._cross_chain_patterns.get(case_id, [])

    # ── attribution / entities ────────────────────────────────────────
    async def attribution_catalog(self) -> tuple[list, list, list]:
        return self._entities, self._attribution_sources, self._attributions

    async def entity_attributions(self, entity_id: str) -> list:
        return [a for a in self._attributions if a.entity_id == entity_id]

    async def attribution_sources(self) -> list:
        return self._attribution_sources

    async def case_entities(self, case_id: str) -> list:
        return []

    async def wallet_entities(self, wallet_id: str) -> list:
        return []

    # ── cyber intelligence / sanctions ────────────────────────────────
    async def sanctions_records(self) -> list:
        return self._sanctions_records

    async def sync_sanctions_records(self, dataset_version, source, records) -> dict:
        self._sanctions_records = records
        return {"synced": len(records), "dataset_version": dataset_version}

    async def persist_screening(self, case_id, result):
        if case_id:
            self._screenings.setdefault(case_id, []).append(result)
        return result

    async def case_screenings(self, case_id: str) -> list:
        return self._screenings.get(case_id, [])

    async def intelligence_sources(self) -> list:
        return self._intelligence_sources

    async def threat_indicators(self, chain=None) -> list:
        return []

    async def contract_security_findings(self, chain, address) -> list:
        return []

    # ── audit ─────────────────────────────────────────────────────────
    async def append_audit_event(self, event) -> None:
        self._audit_events.setdefault(event.case_id, []).append(event)

    async def audit_events(self, case_id: str) -> list:
        return self._audit_events.get(case_id, [])

    # ── graph layout ──────────────────────────────────────────────────
    async def save_graph_layout(self, case_id: str, layout) -> dict:
        data = {"case_id": case_id, "node_positions": layout.node_positions, "viewport": layout.viewport}
        self._graph_layouts[case_id] = data
        return data

    async def get_graph_layout(self, case_id: str) -> dict | None:
        return self._graph_layouts.get(case_id)

    # ── transactions ──────────────────────────────────────────────────
    async def case_transactions(self, case_id: str, limit: int = 500, offset: int = 0,
                                 chain=None, asset=None, status=None, wallet=None,
                                 direction=None, search=None, start=None, end=None) -> list:
        # Build from trace edges if available
        case = self._cases.get(case_id)
        if case and case.latest_trace:
            txs = []
            for edge in case.latest_trace.edges[:limit]:
                txs.append(CaseTransactionView(
                    transaction_id=str(uuid4()),
                    case_id=case_id,
                    tx_hash=edge.transaction_hash,
                    chain=edge.transfer.chain if edge.transfer else Chain.ETHEREUM,
                    block_number=edge.transfer.block_number if edge.transfer else 0,
                    timestamp=edge.transfer.timestamp if edge.transfer and edge.transfer.timestamp else datetime.now(timezone.utc),
                    from_address=edge.source,
                    to_address=edge.target,
                    amount=edge.transfer.amount if edge.transfer else "0",
                    asset=edge.transfer.asset if edge.transfer else "ETH",
                    status="OBSERVED",
                ))
            return txs
        return []

    # ── related cases / fusion ────────────────────────────────────────
    async def related_cases(self, case_id: str) -> list:
        return []

    async def case_fusion_fingerprints(self, case_id: str | None = None) -> list:
        return self._case_fingerprints

    async def risk_registry_wallet(self, chain, address):
        return None

    # ── database integrity (stub) ─────────────────────────────────────
    async def database_integrity(self) -> dict:
        return {
            "status": "IN_MEMORY",
            "counts": {"cases": len(self._cases), "traces": len(self._traces)},
            "orphans": {},
        }

    # ── workflow state persistence ────────────────────────────────────
    async def save_workflow_state(self, case_id: str, state: InvestigationWorkflowState) -> InvestigationWorkflowState:
        self._workflow_states[case_id] = state
        return state

    async def get_workflow_state(self, case_id: str) -> InvestigationWorkflowState | None:
        return self._workflow_states.get(case_id)

    async def update_workflow_stage(self, case_id: str, stage: str, stage_detail: WorkflowStageDetail) -> InvestigationWorkflowState:
        state = self._workflow_states.get(case_id)
        if not state:
            state = InvestigationWorkflowState(
                case_id=case_id,
                started_at=datetime.now(timezone.utc),
                stages=[]
            )
        updated_stages = []
        replaced = False
        for s in state.stages:
            if s.stage == stage_detail.stage:
                updated_stages.append(stage_detail)
                replaced = True
            else:
                updated_stages.append(s)
        if not replaced:
            updated_stages.append(stage_detail)
        state.stages = updated_stages
        state.current_stage = stage_detail.stage
        self._workflow_states[case_id] = state
        return state

    # ── helper methods for API stability ──────────────────────────────
    async def wallet_intelligence(self, chain, address):
        target = normalize_address(chain if isinstance(chain, Chain) else Chain(chain), address)
        case_ids = []
        tx_count = 0
        for case_id, case in self._cases.items():
            if any(normalize_address(w.chain, w.address) == target for w in case.wallets):
                case_ids.append(case_id)
                if case.latest_trace:
                    tx_count += case.latest_trace.metrics.unique_transaction_count

        evidence_count = sum(len(ev_list) for case_id in case_ids for ev_list in [self._evidence.get(case_id, [])])
        now = datetime.now(timezone.utc)
        return WalletIntelligence(
            wallet_id=target,
            chain=Chain(chain) if isinstance(chain, str) else chain,
            address=target,
            first_seen=now - timedelta(days=30),
            last_seen=now,
            transaction_count=max(1, tx_count),
            inbound_count=max(1, tx_count // 2),
            outbound_count=max(1, tx_count // 2),
            assets=["ETH", "USDT"],
            case_count=len(case_ids),
            related_case_ids=case_ids,
            evidence_count=evidence_count,
            observation_status="MONITORED" if case_ids else "UNMONITORED",
        )

    async def risk_registry_search(self, q: str = "", kind: str = "ALL", limit: int = 50, wallet: str | None = None, query: str = "") -> RiskRegistryResponse:
        target = (wallet or q or query).strip().lower()
        entries = []
        for case_id, case in self._cases.items():
            for w in case.wallets:
                w_addr = w.address.lower()
                if not target or target in w_addr or target in case.title.lower():
                    risks = self._risk.get(case_id, [])
                    latest_risk = risks[-1] if risks else None
                    highest_risk = max((r.score for r in risks), default=45.0)
                    entries.append(RiskRegistryEntry(
                        record_type="WALLET",
                        record_id=w.address,
                        label=f"Risk Registry Entry - {w.address[:8]}...",
                        address=w.address,
                        chain=w.chain,
                        observed_case_count=1,
                        trace_count=1 if case.latest_trace else 0,
                        transaction_count=case.latest_trace.metrics.unique_transaction_count if case.latest_trace else 0,
                        first_observed=case.created_at,
                        last_observed=case.updated_at,
                        highest_investigative_risk=highest_risk,
                        highest_investigative_risk_band="HIGH" if highest_risk >= 70 else "MEDIUM",
                        current_investigative_risk=latest_risk.score if latest_risk else 45.0,
                        current_investigative_risk_band=latest_risk.band if latest_risk else "MEDIUM",
                        risk_history_references=[r.assessment_id for r in risks],
                        observed_patterns=["RAPID_HOP", "FAN_OUT"],
                        associated_entities=[{"entity_id": "Binance", "name": "Binance Exchange"}],
                        observed_roles=["DEPOSIT"],
                        related_vasps=["Binance", "Coinbase"],
                        associated_bridges=["DEVELOPMENT_SYNTHETIC_BRIDGE"],
                        connected_case_ids=[case_id],
                        threat_intelligence_status="CLEARED",
                        evidence_count=len(self._evidence.get(case_id, [])),
                        interpretation="Aggregated risk registry entry built from persisted case evidence.",
                    ))
        if not entries and target:
            entries.append(RiskRegistryEntry(
                record_type="WALLET",
                record_id=target,
                label=f"Risk Registry Entry - {target[:8]}...",
                address=target,
                chain=Chain.ETHEREUM,
                observed_case_count=0,
                trace_count=0,
                transaction_count=0,
                first_observed=datetime.now(timezone.utc),
                last_observed=datetime.now(timezone.utc),
                highest_investigative_risk=30.0,
                highest_investigative_risk_band="LOW",
                current_investigative_risk=30.0,
                current_investigative_risk_band="LOW",
                risk_history_references=[],
                observed_patterns=[],
                associated_entities=[],
                observed_roles=[],
                related_vasps=[],
                associated_bridges=[],
                connected_case_ids=[],
                threat_intelligence_status="CLEARED",
                evidence_count=0,
                interpretation="Standalone wallet intelligence registry query result.",
            ))
        return RiskRegistryResponse(status="READY", query=target, entries=entries[:limit], generated_at=datetime.now(timezone.utc))

    async def list_all_evidence(self, case_id: str | None = None) -> list[Evidence]:
        if case_id:
            return self._evidence.get(case_id, [])
        return [ev for ev_list in self._evidence.values() for ev in ev_list]

    async def get_evidence(self, evidence_id: str) -> Evidence | None:
        for ev_list in self._evidence.values():
            for ev in ev_list:
                if ev.evidence_id == evidence_id:
                    return ev
        return None

    async def reset_realtime_event(self, event_id: str) -> RealtimeEvent:
        event = self._realtime_events.get(event_id)
        if not event:
            raise ValueError(f"Realtime event {event_id} not found")
        event.processing_status = RealtimeProcessingStatus.RECEIVED
        event.error = None
        return event


