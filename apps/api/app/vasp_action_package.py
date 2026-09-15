import hashlib, json
import inspect
from datetime import datetime, timezone
from uuid import uuid4
from .domain import EvidenceManifestRequest, ReportCreateRequest, ReportType, VaspActionPackage

class VaspActionPackageService:
    """Creates append-only coordination snapshots from persisted investigation state."""
    def __init__(self, repository, report_service, evidence_service, candidate_resolver):
        self.repository, self.report_service, self.evidence_service, self.candidate_resolver = repository, report_service, evidence_service, candidate_resolver

    async def generate(self, case_id: str, *, entity_id=None, address=None, created_by=None):
        case = await self.repository.get(case_id)
        if not case: raise ValueError("Case not found")
        candidates = self.candidate_resolver(case.latest_trace)
        if inspect.isawaitable(candidates):
            candidates = await candidates
        selected = next((x for x in candidates if (entity_id and x.entity_id == entity_id) or (address and x.address.lower() == address.lower())), None) or (candidates[0] if candidates else None)
        if not selected or selected.entity_id == "UNRESOLVED" or selected.classification == "UNRESOLVED":
            raise LookupError("VASP_UNRESOLVED")
        report = await self.report_service.generate(case_id, ReportCreateRequest(report_type=ReportType.FUND_FLOW, trace_id=case.latest_trace.trace_id if case.latest_trace else None, created_by=created_by))
        manifest_id, manifest_hash = report.manifest_id, report.manifest_hash
        if not manifest_id and selected.evidence_ids:
            m = await self.evidence_service.create_manifest(case_id, EvidenceManifestRequest(evidence_ids=selected.evidence_ids, created_by=created_by))
            manifest_id, manifest_hash = m.manifest_id, m.content_hash
        trace = case.latest_trace
        path_edges = [e for e in (trace.edges if trace else []) if e.transaction_hash in selected.transaction_hashes]
        payload = {"case_reference": case.external_case_reference, "case_id": case_id, "reported_source_wallet": trace.root_address if trace else None, "chain": selected.chain.value, "vasp_candidate": selected.model_dump(mode="json"), "fund_flow": {"observed_linked_amount": selected.observed_linked_amount, "asset": selected.observed_asset, "source_wallet": trace.root_address if trace else None, "complete_evidence_path": selected.evidence_path, "ordered_transaction_hashes": selected.transaction_hashes, "intermediate_wallets": [e.source for e in path_edges] + ([path_edges[-1].destination] if path_edges else []), "cross_chain_transition_details": [x.model_dump(mode="json") for x in await self.repository.cross_chain_links(case_id)]}, "evidence": {"evidence_ids": selected.evidence_ids, "trace_run_id": trace.trace_id if trace else None, "risk_assessment_id": report.assessment_id, "pattern_observation_ids": report.pattern_ids, "vasp_attribution_references": [selected.attribution_source + ":" + selected.source_version], "cross_chain_correlation_ids": [], "case_fusion_references": []}, "integrity": {"evidence_manifest_id": manifest_id, "sha256_manifest_content_hash": manifest_hash, "generated_at": datetime.now(timezone.utc).isoformat(), "report_package_version": "1.0"}, "investigator_context": {"current_risk_score_band": report.sections.get("risk", {}) if report.sections else {}, "current_recommendations": report.sections.get("recommendations", []) if report.sections else {}}, "limitations": ["Attribution is source-backed intelligence and does not establish ownership or control.", "Cross-chain relationships may be inferred and require investigator review.", "Provider, data coverage, and attribution limitations remain applicable."], "recommended_action": "Investigator review recommended for appropriate VASP coordination."}
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        package = VaspActionPackage(package_id=str(uuid4()), report_id=report.report_id, manifest_id=manifest_id, case_id=case_id, case_reference=case.external_case_reference, source_wallet=trace.root_address if trace else None, vasp_candidate=selected, transaction_hashes=selected.transaction_hashes, evidence_ids=selected.evidence_ids, evidence_manifest_hash=manifest_hash, report_version="1.0", integrity_hash=hashlib.sha256(raw.encode()).hexdigest(), fund_flow=payload["fund_flow"], evidence=payload["evidence"], integrity=payload["integrity"], investigator_context=payload["investigator_context"], limitations=payload["limitations"], generated_at=datetime.now(timezone.utc))
        return await self.repository.persist_vasp_action_package(package)
