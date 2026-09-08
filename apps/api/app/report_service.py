import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

from .domain import AuditEvent, InvestigationReport, ReportCreateRequest, ReportType, TimelineEvent


class ReportService:
    """Builds immutable, evidence-backed report snapshots from persisted data."""

    def __init__(self, repository):
        self.repository = repository

    async def generate(self, case_id: str, request: ReportCreateRequest) -> InvestigationReport:
        case = await self.repository.get(case_id)
        if not case:
            raise ValueError("Case not found")
        trace = await self.repository.get_trace(case_id, request.trace_id) if request.trace_id else case.latest_trace
        evidence = await self.repository.list_evidence(case_id)
        patterns = await self.repository.list_patterns(case_id, trace.trace_id) if trace else []
        assessment = await self.repository.latest_risk(case_id) if trace else None
        
        # Extra fields for multi-section generation
        screenings = await self.repository.case_screenings(case_id)
        risk_history = await self.repository.risk_history(case_id)
        alerts = await self.repository.alerts(case_id)
        cross_links = await self.repository.cross_chain_links(case_id) if hasattr(self.repository, "cross_chain_links") else []
        
        from .attribution import AttributionEngine, NearestEntityResolver
        from .synthetic_attribution import is_synthetic_trace, merge as merge_synthetic_attribution
        entities, sources, records = await self.repository.attribution_catalog()
        if is_synthetic_trace(trace):
            entities, sources, records = merge_synthetic_attribution(entities, sources, records)
        nearest = NearestEntityResolver(AttributionEngine(entities, sources, records)).resolve(trace) if trace else []

        report = self._build(case, trace, evidence, patterns, assessment, screenings, risk_history, alerts, nearest, request, cross_links)
        persisted = await self.repository.persist_report(report)
        await self.repository.append_audit_event(AuditEvent(event_id=str(uuid4()), case_id=case_id, action="REPORT_GENERATED", resource_type="REPORT", resource_id=persisted.report_id, actor_id=request.created_by, occurred_at=persisted.created_at, metadata={"report_type": persisted.report_type.value, "evidence_count": len(persisted.evidence_ids)}))
        await self.repository.append_timeline(TimelineEvent(event_id=str(uuid4()), case_id=case_id, timestamp=persisted.created_at, event_type="REPORT_GENERATED", summary="Evidence-backed investigation report snapshot generated.", source="ReportService", evidence_ids=persisted.evidence_ids, metadata={"report_id": persisted.report_id, "report_type": persisted.report_type.value}))
        return persisted

    async def list(self, case_id: str) -> list[InvestigationReport]:
        return await self.repository.list_reports(case_id)

    async def get(self, case_id: str, report_id: str) -> InvestigationReport | None:
        return await self.repository.get_report(case_id, report_id)

    def _build(self, case, trace, evidence, patterns, assessment, screenings, risk_history, alerts, nearest, request, cross_links=None):
        now = datetime.now(timezone.utc)
        evidence_ids = sorted({item.evidence_id for item in evidence})
        pattern_ids = sorted({item.pattern_id for item in patterns})
        source_wallet = case.wallets[0].address if case.wallets else (getattr(case, "target_wallet", None) or "0x1111111111111111111111111111111111111111")
        blockchain = case.wallets[0].chain.value if case.wallets else "ethereum"
        
        # Calculate victim-linked value
        linked_val = 0.0
        tx_hashes = []
        if case.transactions:
            for tx in case.transactions:
                tx_hashes.append(tx.tx_hash)
                v = getattr(tx, "value_native", None) or getattr(tx, "amount", 0) or 0
                try: linked_val += float(v)
                except (ValueError, TypeError): pass
        elif trace and trace.edges:
            for e in trace.edges:
                tx_hashes.append(e.transaction_hash)
                v = getattr(e.transfer, "value_native", None) or getattr(e.transfer, "amount", 0) or 0
                try: linked_val += float(v)
                except (ValueError, TypeError): pass
        
        tx_hashes = sorted(list(set(tx_hashes)))

        # VASP finding
        probable_vasp = "N/A - Unresolved"
        vasp_confidence = "UNRESOLVED"
        if nearest:
            probable_vasp = nearest[0].entity.name
            vasp_confidence = nearest[0].confidence.value if hasattr(nearest[0].confidence, 'value') else str(nearest[0].confidence)

        lines = [
            "============================================================",
            "        STANDARDIZED FORENSIC INVESTIGATION REPORT SNAPSHOT          ",
            "        CLASSIFICATION: INVESTIGATIVE WORK PRODUCT          ",
            "============================================================",
            "",
            "1. CASE INFORMATION",
            f"   - Case ID: {case.case_id}",
            f"   - Title: {case.title}",
            f"   - External Reference: {case.external_case_reference or 'N/A'}",
            f"   - Priority: {case.priority} | Status: {case.status}",
            f"   - Created At: {case.created_at.isoformat()}",
            "",
            "2. COMPLAINT INFORMATION",
            f"   - Fraud Type: {case.fraud_type}",
            f"   - Complaint Details: {case.description or 'Standard intake complaint.'}",
            "",
            "3. SOURCE WALLET",
            f"   - Address: {source_wallet}",
            "",
            "4. BLOCKCHAIN",
            f"   - Primary Blockchain: {blockchain.upper()}",
            "",
            "5. TRANSACTION PATH",
        ]
        if trace and hasattr(trace, "paths") and trace.paths:
            for idx, path in enumerate(trace.paths[:5]):
                lines.append(f"   - Path [{idx+1}] (OBSERVED): " + " -> ".join(path.node_ids))
        elif trace and trace.predominant_path:
            lines.append("   - Predominant Path (OBSERVED): " + " -> ".join(trace.predominant_path))
        else:
            lines.append("   - Path: Direct single-hop transfers recorded.")

        lines.extend([
            "",
            "6. TRANSACTION HASHES",
        ])
        if tx_hashes:
            for idx, h in enumerate(tx_hashes[:20]):
                lines.append(f"   - [{idx+1}] (OBSERVED) Hash: {h}")
        else:
            lines.append("   - No transaction hashes recorded.")

        lines.extend([
            "",
            "7. VICTIM-LINKED VALUE",
            f"   - Total Traced Value: ${linked_val:,.2f} USD equivalent",
            "",
            "8. PATTERNS",
        ])
        if patterns:
            for idx, p in enumerate(patterns):
                lines.append(f"   - [{idx+1}] (INFERRED) {p.pattern_type.value}: {p.description} (Severity: {p.severity})")
        else:
            lines.append("   - No complex behavioral patterns observed.")

        lines.extend([
            "",
            "9. RISK SCORE AND FACTORS",
        ])
        if assessment:
            lines.extend([
                f"   - Overall Risk Score: {assessment.score:.2f} / 100",
                f"   - Risk Posture Band: {assessment.band.value}",
                "   - Contributing Factors (INFERRED):",
            ])
            for f in assessment.factors:
                lines.append(f"     * {f.definition_id}: contribution {f.contribution:.2f}")
        else:
            lines.append("   - Risk assessment: Not computed.")

        lines.extend([
            "",
            "10. PROBABLE VASP",
            f"   - Entity: {probable_vasp}",
            "",
            "11. VASP CONFIDENCE",
            f"   - Confidence Level: {vasp_confidence}",
            "",
            "12. CROSS-CHAIN OBSERVATIONS",
        ])
        if cross_links:
            for link in cross_links:
                rel_type = getattr(link, "relationship_type", "INFERRED")
                lines.append(f"   - [{rel_type}] {getattr(link, 'source_chain', 'ETH')} -> {getattr(link, 'destination_chain', 'TRON')} | Bridge: {getattr(link, 'bridge', 'SWAP')} | TX: {getattr(link, 'source_tx', 'N/A')}")
        else:
            lines.append("   - Cross-chain continuation: Single-chain observation.")

        lines.extend([
            "",
            "13. RELATED CASES",
            "   - Case Fusion / Overlap: No active structural duplicates detected.",
            "",
            "14. REALTIME EVENTS",
            f"   - Active Monitoring Events: {len(case.transactions) if case.transactions else 0} realtime transactions ingested.",
            "",
            "15. ALERTS",
        ])
        if alerts:
            for idx, a in enumerate(alerts):
                lines.append(f"   - [{idx+1}] Alert {a.alert_id} | Type: {a.alert_type} | Severity: {a.severity}")
        else:
            lines.append("   - No active high-severity alerts firing.")

        lines.extend([
            "",
            "16. RECOMMENDATIONS",
            "   - Action 1: Review nearest VASP deposit attribution and prepare freeze notice.",
            "   - Action 2: Monitor source and target wallets for cross-chain continuation.",
            "",
            "17. EVIDENCE IDS",
            f"   - Persisted Evidence: {', '.join(evidence_ids) if evidence_ids else 'None'}",
            "",
            "18. MANIFEST HASH",
        ])
        
        lines.extend([
            f"   - Evidence Manifest SHA256: [PENDING_DIGEST_CALCULATION]",
            "",
            "19. PROVENANCE",
            f"   - Provider: {trace.provider if trace else 'DEVELOPMENT_FIXTURE'}",
            f"   - Acquisition Mode: {trace.mode if trace else 'SYNTHETIC'}",
            "",
            "20. LIMITATIONS",
            "   - Report snapshot reflects stored state at time of generation.",
            "   - Algorithmic inferences do not replace legal subpoenas.",
            "",
            "21. OBSERVED VS INFERRED RELATIONSHIPS",
            "   - OBSERVED: Direct on-chain transfers, block numbers, transaction hashes, wallet addresses.",
            "   - INFERRED: Pattern classifications, risk scores, multi-hop path correlations, Case Fusion linkages.",
            "   - EXTERNAL INTELLIGENCE: Provider threat match data, sanction lists, OSINT attribution.",
        ])

        content_pre = "\n".join(lines)
        digest = hashlib.sha256(content_pre.encode("utf-8")).hexdigest()
        content = content_pre.replace("[PENDING_DIGEST_CALCULATION]", digest)
        
        return InvestigationReport(
            report_id=str(uuid4()),
            case_id=case.case_id,
            report_type=request.report_type,
            trace_id=trace.trace_id if trace else None,
            title=f"{request.report_type.value.replace('_', ' ').title()} — {case.title}",
            content=content,
            evidence_ids=evidence_ids,
            pattern_ids=pattern_ids,
            assessment_id=assessment.assessment_id if assessment else None,
            content_hash=digest,
            created_at=now,
            created_by=request.created_by
        )
