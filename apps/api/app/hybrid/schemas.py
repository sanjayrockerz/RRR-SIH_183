from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class HybridStatus(StrEnum):
    READY = "READY"
    NO_DATA = "NO_DATA"
    ERROR = "ERROR"


class HybridPriority(StrEnum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class HybridInvestigationIntelligence(BaseModel):
    case_id: str
    generated_at: datetime
    ruleset_version: str
    status: HybridStatus
    deterministic_risk: dict[str, Any] = Field(default_factory=dict)
    ml_behavioural_intelligence: dict[str, Any] = Field(default_factory=dict)
    pattern_summary: dict[str, Any] = Field(default_factory=dict)
    threat_intelligence: dict[str, Any] = Field(default_factory=dict)
    risk_registry_summary: dict[str, Any] = Field(default_factory=dict)
    case_fusion_summary: dict[str, Any] = Field(default_factory=dict)
    vasp_actionability: dict[str, Any] = Field(default_factory=dict)
    realtime_state: dict[str, Any] = Field(default_factory=dict)
    cross_chain: dict[str, Any] = Field(default_factory=dict)
    priority: HybridPriority
    recommendation: str
    reason_codes: list[str] = Field(default_factory=list)
    evidence_refs: list[dict[str, Any]] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    previous_priority: HybridPriority | None = None
    priority_changed: bool = False
    state_hash: str


class HybridSnapshot(BaseModel):
    id: str
    case_id: str
    ruleset_version: str
    priority: HybridPriority
    recommendation_text: str
    reason_codes: list[str] = Field(default_factory=list)
    signal_summary: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: list[dict[str, Any]] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    previous_priority: HybridPriority | None = None
    priority_changed: bool = False
    state_hash: str
    generated_at: datetime
    created_at: datetime
