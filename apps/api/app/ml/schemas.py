from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class MLModelStatus(StrEnum):
    READY = "READY"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    FEATURE_SCHEMA_MISMATCH = "FEATURE_SCHEMA_MISMATCH"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    UNSUPPORTED_CHAIN = "UNSUPPORTED_CHAIN"
    ERROR = "ERROR"


class MLClassification(StrEnum):
    LICIT_LIKE = "LICIT_LIKE"
    HIGH_RISK_LIKE = "HIGH_RISK_LIKE"


class MLFeatureVector(BaseModel):
    feature_schema_version: str
    address: str
    chain: str
    case_id: str | None = None
    observation_time: datetime | None = None
    observation_cutoff: datetime | None = None
    features: dict[str, float]
    feature_hash: str


class MLTopFeature(BaseModel):
    feature: str
    direction: str
    value: float
    contribution: float | None = None
    explanation: str = "contributing model signal; not causal"


class MLInferenceResult(BaseModel):
    inference_id: str | None = None
    model_name: str | None = None
    model_version: str | None = None
    feature_schema_version: str | None = None
    address: str
    chain: str
    case_id: str | None = None
    probability: float | None = Field(default=None, ge=0, le=1)
    classification: MLClassification | None = None
    threshold: float | None = Field(default=None, ge=0, le=1)
    top_features: list[MLTopFeature] = Field(default_factory=list)
    feature_hash: str | None = None
    generated_at: datetime
    observation_cutoff: datetime | None = None
    status: MLModelStatus
    limitations: list[str] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)


class MLWalletAssessment(MLInferenceResult):
    """Persisted append-only assessment domain entity."""
    id: str | None = None
    inference_id: str | None = None
    model_sha256: str | None = None
    metadata_sha256: str | None = None
    features_json: dict[str, float] = Field(default_factory=dict)
    top_features_json: list[dict[str, Any]] = Field(default_factory=list)
    limitations_json: list[str] = Field(default_factory=list)
    created_at: datetime | None = None


class MLRiskAssessRequest(BaseModel):
    address: str | None = Field(default=None, min_length=1, max_length=128)
    chain: str = "ethereum"


class MLRiskAssessment(MLInferenceResult):
    """Compatibility response model for the existing API wiring."""
    inference_id: str
    case_id: str
    model_version: str
    feature_schema_version: str
    probability: float = Field(ge=0, le=1)
    classification: str
    threshold: float = Field(ge=0, le=1)
    feature_hash: str
