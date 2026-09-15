from datetime import datetime
from enum import StrEnum
from pydantic import BaseModel, Field

from ..domain import Chain


class ThreatIntelStatus(StrEnum):
    DIRECT_MATCH = "DIRECT_MATCH"
    NO_MATCH = "NO_MATCH"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    ERROR = "ERROR"


class ThreatIntelObservation(BaseModel):
    observation_id: str
    chain: Chain
    address: str
    source: str
    source_version: str
    indicator: str
    match_type: ThreatIntelStatus
    confidence: float | None = Field(default=None, ge=0, le=1)
    reference: str | None = None
    retrieved_at: datetime
    raw_status: ThreatIntelStatus
    case_id: str | None = None
    created_at: datetime


class ThreatIntelProviderResult(BaseModel):
    source: str
    source_version: str
    indicator: str
    match_type: ThreatIntelStatus
    confidence: float | None = Field(default=None, ge=0, le=1)
    reference: str | None = None
    raw_status: ThreatIntelStatus
    retrieved_at: datetime


class ThreatIntelResponse(BaseModel):
    status: str
    chain: Chain | None = None
    address: str | None = None
    observations: list[ThreatIntelObservation] = []
    generated_at: datetime
    limitation: str = "External intelligence is source-backed context, not a criminality finding or clearance result."
