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
        
        lines = [
            "============================================================",
            "        FORENSIC INVESTIGATION REPORT SNAPSHOT              ",
            "        CLASSIFICATION: INVESTIGATIVE WORK PRODUCT          ",
            "============================================================",
            "",
            "1. CASE INFORMATION",
            f"   - Case ID: {case.case_id}",
            f"   - Title: {case.title}",
            f"   - Fraud Type: {case.fraud_type}",
            f"   - Priority: {case.priority}",
            f"   - Status: {case.status}",
            f"   - Created At: {case.created_at.isoformat()}",
            f"   - Updated At: {case.updated_at.isoformat()}",
            "",
            "2. COMPLAINT INFORMATION",
            f"   - External Reference ID: {case.external_case_reference or 'N/A'}",
            f"   - Description: {case.description or 'No description recorded.'}",
            "",
            "3. INVESTIGATED WALLETS",
        ]
        for w in case.wallets:
            lines.append(f"   - Address: {w.address} ({w.chain.value})")
        
        lines.extend([
            "",
            "4. TRANSACTION TIMELINE",
        ])
        if case.transactions:
            for idx, tx in enumerate(case.transactions[:30]):
                lines.append(f"   - [{idx+1}] TX Hash: {tx.tx_hash} ({tx.chain.value})")
        else:
            lines.append("   - No transactions associated with this case yet.")
            
        lines.extend([
            "",
            "5. FUND-FLOW PATH",
        ])
        if trace and hasattr(trace, "paths") and trace.paths:
            for idx, path in enumerate(trace.paths[:10]):
                lines.append(f"   - Path {idx+1}: " + " -> ".join(path.node_ids))
        else:
            lines.append("   - No fund-flow paths mapped in the current trace.")
            
        lines.extend([
            "",
            "6. GRAPH SUMMARY",
        ])
        if trace:
            lines.extend([
                f"   - Unique Nodes: {trace.metrics.node_count}",
                f"   - Unique Edges: {trace.metrics.edge_count}",
                f"   - Unique Transactions: {trace.metrics.unique_transaction_count}",
                f"   - Unique Assets: {trace.metrics.unique_asset_count if hasattr(trace.metrics, 'unique_asset_count') else 1}",
            ])
        else:
            lines.append("   - Graph summary is unavailable.")

        lines.extend([
            "",
            "7. ENTITY/VASP FINDINGS",
        ])
        if nearest:
            for idx, item in enumerate(nearest[:20]):
                lines.append(f"   - [{idx+1}] VASP Name: {item.entity.name} (Confidence: {item.confidence.value}) at Address: {item.address} (Hop distance: {item.hop_distance})")
        else:
            lines.append("   - No external VASP or Exchange entities identified in paths.")

        lines.extend([
            "",
            "8. SANCTIONS SCREENING",
        ])
        if screenings:
            for idx, s in enumerate(screenings):
                lines.append(f"   - Address: {s.address} ({s.chain.value}) -> Outcome: {s.outcome} (Explanation: {s.explanation})")
        else:
            lines.append("   - No sanctions screening runs recorded for case wallets.")

        lines.extend([
            "",
            "9. THREAT INTELLIGENCE",
        ])
        findings = []
        for e in evidence:
            if e.type == "THREAT_INTEL" or e.type == "SECURITY_FINDING":
                findings.append(e)
        if findings:
            for idx, f in enumerate(findings):
                lines.append(f"   - [{idx+1}] Source: {f.source} | Hash: {f.tx_hash} | Detail: {f.metadata.get('description', 'No details available')}")
        else:
            lines.append("   - No security or threat intelligence findings recorded.")

        lines.extend([
            "",
            "10. DETECTED PATTERNS",
        ])
        if patterns:
            for idx, p in enumerate(patterns):
                lines.append(f"   - [{idx+1}] {p.pattern_type.value}: {p.description} (Severity: {p.severity}) | Evidence: {', '.join(p.evidence_ids) or 'none'}")
        else:
            lines.append("   - No behavioral patterns detected.")

        lines.extend([
            "",
            "11. RISK ASSESSMENT",
        ])
        if assessment:
            lines.extend([
                f"   - Posture Band: {assessment.band.value}",
                f"   - Prioritization Score: {assessment.score:.2f}/100",
                f"   - Calculated At: {assessment.calculated_at.isoformat()}",
                "   - Risk Factors:",
            ])
            for f in assessment.factors:
                lines.append(f"     * {f.definition_id} (Risk Score contribution: {f.contribution:.2f})")
        else:
            lines.append("   - No risk assessment performed yet.")

        lines.extend([
            "",
            "12. RISK CHANGES",
        ])
        if risk_history and len(risk_history) > 1:
            for idx in range(len(risk_history) - 1):
                prev = risk_history[idx+1]
                curr = risk_history[idx]
                lines.append(f"   - Change: {prev.band.value} ({prev.score:.1f}) -> {curr.band.value} ({curr.score:.1f}) at {curr.calculated_at.isoformat()}")
        else:
            lines.append("   - No risk posture updates recorded.")

        lines.extend([
            "",
            "13. ALERTS",
        ])
        if alerts:
            for idx, a in enumerate(alerts):
                lines.append(f"   - [{idx+1}] Alert ID: {a.alert_id} | Type: {a.alert_type} | Severity: {a.severity} | Delta: {a.risk_delta} | Created At: {a.created_at.isoformat()}")
        else:
            lines.append("   - No active alerts generated.")

        lines.extend([
            "",
            "14. EVIDENCE REFERENCES",
        ])
        if evidence:
            for idx, e in enumerate(evidence):
                lines.append(f"   - [{idx+1}] Evidence ID: {e.evidence_id} | Type: {e.type} | Source: {e.source} | Hash: {e.tx_hash} | Captured: {e.captured_at.isoformat()}")
        else:
            lines.append("   - No forensic evidence records persisted in ledger.")

        lines.extend([
            "",
            "15. PROVIDER PROVENANCE",
        ])
        if trace:
            lines.extend([
                f"   - Primary Adapter: {trace.provider}",
                f"   - Execution Mode: {trace.mode}",
                f"   - Wallet Screened: {trace.root_address}",
                f"   - Discovered Transactions: {trace.acquisition.discovered if trace.acquisition else 'N/A'}",
                f"   - Normalized Transactions: {trace.acquisition.normalized if trace.acquisition else 'N/A'}",
                f"   - Persisted Transactions: {trace.acquisition.persisted if trace.acquisition else 'N/A'}",
                f"   - Retrieved At: {trace.acquisition.retrieved_at.isoformat() if trace.acquisition and trace.acquisition.retrieved_at else 'N/A'}",
                f"   - API Key Provenance: Read from ENVIRONMENT config (never exposed)",
            ])
        else:
            lines.append("   - No active provider tracing history available.")

        cross_lines = ["", "16. CROSS-CHAIN INTELLIGENCE"]
        if cross_links:
            for link in cross_links:
                if link.destination and link.correlation_level in {"EXACT", "STRONG"}:
                    cross_lines.append(f"   - {link.source.chain.value.upper()} -> {link.bridge_protocol or link.bridge_id} -> {link.destination.chain.value.upper()} | Source TX: {link.source_transaction_hash} | Destination TX: {link.destination_transaction_hash} | Asset: {link.asset or 'UNKNOWN'} | Amount: {link.amount or 'UNKNOWN'} | Confidence: {link.confidence_band} | Evidence: {', '.join(link.evidence_ids) or 'none'}")
                else:
                    cross_lines.append("   - CROSS-CHAIN LINK: UNKNOWN - No verified destination-chain correlation was established.")
        else:
            cross_lines.append("   - No verified cross-chain correlation was established in this evidence snapshot.")
        lines.extend(cross_lines + [
            "",
            "17. LIMITATIONS",
            "   - This report snapshot captures state at the time of generation.",
            "   - Analytical classifications, attributions, and risk assessment are priorities based on rule criteria and do not constitute legal findings.",
            "   - Integrity checks are based on stored content hashes in the Postgres evidence ledger.",
        ])
        lines.extend([
            "",
            "18. BLOCKCHAIN CYBERSECURITY CONTROL ASSESSMENT",
            "   - Asset and chain exposure: Record every chain, asset, token contract, bridge, and custody boundary observed in the trace.",
            "   - Transaction integrity: Validate transaction hash, block context, confirmation state, reorg status, transfer index, and provider provenance before relying on an observation.",
            "   - Identity and attribution: Treat VASP, exchange, mixer, bridge, contract, and service labels as source-backed intelligence with explicit confidence; do not infer ownership from proximity alone.",
            "   - Sanctions and AML: Screen reported and materially exposed addresses against the configured dataset, retain source/version/retrieval time, and escalate direct or indirect matches for compliance review.",
            "   - Threat intelligence: Correlate wallet, transaction, contract, domain, and scam-infrastructure indicators while preserving the source reference and confidence level.",
            "   - Smart-contract security: Review privileged roles, upgradeability, approvals, proxy implementation, exploit indicators, malicious token behavior, and contract interaction anomalies when contract evidence is present.",
            "   - Cross-chain risk: Identify bridges, wrapped assets, destination recipients, correlation method, confidence, and whether each link is observed or inferred.",
            "   - Monitoring and response: Maintain watch status, alert review history, retry/dead-letter state, reorg handling, and a documented response owner for material changes.",
            "   - Evidence governance: Preserve raw references, normalized records, timestamps, content hashes, chain-of-custody events, and least-privilege access logs.",
            "",
            "19. RECOMMENDED INVESTIGATIVE ACTIONS",
            "   - Preserve the source transaction, block, provider response, and evidence ledger entry before taking enforcement or recovery action.",
            "   - Escalate high or critical risk, direct sanctions matches, confirmed threat indicators, and rapid cross-chain movement according to the organization's incident response policy.",
            "   - Contact the relevant exchange, VASP, bridge, issuer, or custodian through an authenticated channel using only verified identifiers and a minimum-necessary disclosure.",
            "   - Continue real-time monitoring for new inbound/outbound activity, consolidation, peel-chain behavior, mixer interaction, bridge hops, and entity exposure.",
            "   - Re-run attribution and risk assessment after new evidence, provider corrections, chain reorganizations, or intelligence dataset updates.",
            "",
            "20. INTERPRETATION KEY",
            "   - OBSERVED: Directly represented by a persisted blockchain or provider observation.",
            "   - SOURCE-BACKED: Supplied by a configured intelligence, attribution, or sanctions source.",
            "   - INFERRED: Analytical correlation or classification that requires review and should not be presented as fact.",
            "   - NOT CONFIGURED / UNKNOWN: No reliable source result is available; absence of a match is not evidence of absence.",
        ])
        content = "\n".join(lines)
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return InvestigationReport(report_id=str(uuid4()), case_id=case.case_id, report_type=request.report_type, trace_id=trace.trace_id if trace else None, title=f"{request.report_type.value.replace('_', ' ').title()} — {case.title}", content=content, evidence_ids=evidence_ids, pattern_ids=pattern_ids, assessment_id=assessment.assessment_id if assessment else None, content_hash=digest, created_at=now, created_by=request.created_by)
