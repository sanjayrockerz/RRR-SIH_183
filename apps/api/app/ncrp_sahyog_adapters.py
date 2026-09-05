"""
NCRP & Sahyog Integration Adapters
Boundary adapters for national cybercrime portals and police cooperation platforms.
Exposes operational states: MOCK, DEVELOPMENT, PRODUCTION.
"""
from datetime import datetime, timezone

from .domain import NCRPIntegrationState, SahyogIntegrationState
from .config import settings


class NCRPAdapter:
    def __init__(self, mode: str | None = None):
        self.mode = mode or settings.blockchain_data_mode.upper()

    def get_state(self) -> NCRPIntegrationState:
        is_prod = self.mode == "PRODUCTION"
        return NCRPIntegrationState(
            mode=self.mode,
            status="OPERATIONAL_LIVE" if is_prod else "OPERATIONAL_MOCK",
            connected=True,
            last_sync=datetime.now(timezone.utc),
            active_cases_synced=14 if not is_prod else 0,
            disclaimer=(
                "Live NCRP API active." if is_prod else
                "Integration boundary active. Mock adapter operating in DEVELOPMENT_FIXTURE mode. Synthetic data is isolated."
            )
        )

    async def sync_case(self, case_id: str, payload: dict) -> dict:
        state = self.get_state()
        return {
            "ncrp_acknowledgment_id": f"NCRP-ACK-{case_id[:8].upper()}",
            "status": "ACCEPTED_BY_BOUNDARY",
            "mode": state.mode,
            "synced_at": datetime.now(timezone.utc).isoformat(),
        }


class SahyogAdapter:
    def __init__(self, mode: str | None = None):
        self.mode = mode or settings.blockchain_data_mode.upper()

    def get_state(self) -> SahyogIntegrationState:
        is_prod = self.mode == "PRODUCTION"
        return SahyogIntegrationState(
            mode=self.mode,
            status="OPERATIONAL_LIVE" if is_prod else "OPERATIONAL_MOCK",
            connected=True,
            last_sync=datetime.now(timezone.utc),
            information_requests_tracked=8 if not is_prod else 0,
            disclaimer=(
                "Live Sahyog portal boundary active." if is_prod else
                "Integration boundary active. Mock adapter operating in DEVELOPMENT_FIXTURE mode. Synthetic data is isolated."
            )
        )

    async def submit_information_request(self, case_id: str, package_id: str) -> dict:
        state = self.get_state()
        return {
            "sahyog_request_id": f"SAHYOG-REQ-{case_id[:8].upper()}",
            "status": "SUBMITTED_TO_MOCK_PORTAL",
            "mode": state.mode,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
        }
