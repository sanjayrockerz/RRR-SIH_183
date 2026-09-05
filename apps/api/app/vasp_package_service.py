"""
VASPPackageService
Generates VASP Information Packages prepared for authorized investigator review.
Non-automated legal requests; strictly for compliance inquiry preparation.
"""
from uuid import uuid4, uuid5, NAMESPACE_URL
from datetime import datetime, timezone
from hashlib import sha256

from .domain import (
    VASPInformationPackage,
    VaspClassification,
    Chain,
)


class VASPPackageService:
    def __init__(self, repo=None):
        self.repo = repo

    async def generate_package(
        self,
        case_id: str,
        case_wallets: list = None,
        vasp_candidate=None,
        attributions: list = None,
        evidence_records: list = None,
        created_by: str = "investigator-session",
    ) -> VASPInformationPackage:
        reported_wallet = case_wallets[0].address if case_wallets else "UNKNOWN"
        vasp_id = getattr(vasp_candidate, "entity_id", "vasp-unknown")
        vasp_name = getattr(vasp_candidate, "entity_name", "Probable VASP Entity")
        classification = getattr(vasp_candidate, "classification", VaspClassification.PROBABLE)
        confidence = getattr(vasp_candidate, "attribution_confidence", 0.75)
        exposure_usd = getattr(vasp_candidate, "normalized_value_usd", 0.0)

        wallets = [w.address for w in (case_wallets or [])]
        tx_hashes = getattr(vasp_candidate, "supporting_transaction_hashes", [])
        evidence_ids = [e.evidence_id for e in (evidence_records or [])]

        manifest_string = f"{case_id}:{vasp_id}:{','.join(tx_hashes)}:{','.join(evidence_ids)}"
        evidence_manifest_hash = sha256(manifest_string.encode()).hexdigest()

        pkg_id = str(uuid5(NAMESPACE_URL, f"rrr:vasp_package:{case_id}:{vasp_id}"))

        package = VASPInformationPackage(
            package_id=pkg_id,
            case_id=case_id,
            reported_wallet=reported_wallet,
            receiving_vasp_id=vasp_id,
            receiving_vasp_name=vasp_name,
            attribution_classification=classification,
            attribution_confidence=confidence,
            fund_exposure_usd=exposure_usd,
            relevant_wallets=wallets,
            relevant_transactions=tx_hashes,
            supporting_evidence_ids=evidence_ids,
            evidence_manifest_hash=evidence_manifest_hash,
            investigator_notes="Package generated for law enforcement/compliance team review. Submissions to receiving entities require manual authorization.",
            recommended_information_request=(
                f"Formal request to Compliance & Risk Department at {vasp_name}:\n"
                f"Reference Case ID: {case_id}\n"
                f"Subject Transactions: {', '.join(tx_hashes[:5]) if tx_hashes else 'N/A'}\n"
                f"Estimated Actionable Fund Exposure: ${exposure_usd:,.2f} USD\n"
                f"Request: Please verify internal account records for deposit transactions associated with above hashes and provide KYC/account identification details pursuant to formal legal process."
            ),
            created_by=created_by,
            created_at=datetime.now(timezone.utc),
        )

        if self.repo and hasattr(self.repo, "persist_vasp_package"):
            await self.repo.persist_vasp_package(package)

        return package
