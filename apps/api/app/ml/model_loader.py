from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from ..config import settings

logger = logging.getLogger("crypto_fraud_intelligence")

ROOT = Path(__file__).resolve().parents[4]
def _configured_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


MODEL_PATH = _configured_path(settings.rrr_ml_model_path)
METADATA_PATH = _configured_path(settings.rrr_ml_metadata_path)
INTEGRITY_PATH = ROOT / "artifacts" / "ml_frozen_model_integrity.json"
EXPECTED_MODEL_SHA256 = "5d36a620e91c39e521a953714196bdd09fec28d73560d8c98755514579257da5"
EXPECTED_METADATA_SHA256 = "0e6db36935b6e21688b1eab24297c3fc2981bb950db00886e5d52f085c29725c"


class FrozenModelError(RuntimeError):
    pass


@dataclass(frozen=True)
class LoadedWalletRiskModel:
    model: object
    metadata: dict


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""): digest.update(block)
    return digest.hexdigest()


def _load_uncached() -> LoadedWalletRiskModel:
    if not MODEL_PATH.exists() or not METADATA_PATH.exists() or not INTEGRITY_PATH.exists():
        raise FrozenModelError("Frozen Ethereum model artifacts are not configured")
    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8")); integrity = json.loads(INTEGRITY_PATH.read_text(encoding="utf-8"))
    if integrity.get("status") != "FROZEN_READ_ONLY": raise FrozenModelError("Frozen model integrity status is invalid")
    if _sha256(MODEL_PATH) != EXPECTED_MODEL_SHA256 or _sha256(METADATA_PATH) != EXPECTED_METADATA_SHA256 or _sha256(MODEL_PATH) != integrity.get("model_sha256") or _sha256(METADATA_PATH) != integrity.get("metadata_sha256"):
        raise FrozenModelError("Frozen model hash does not match the approved integrity manifest")
    order = metadata.get("feature_order")
    if metadata.get("feature_schema_version") != "RRRFeatureSchemaV2" or not isinstance(order, list) or len(order) != 41 or len(set(order)) != 41:
        raise FrozenModelError("Frozen metadata feature schema is invalid")
    try:
        import joblib
        bundle = joblib.load(MODEL_PATH)
    except Exception as exc:
        raise FrozenModelError("Frozen model could not be loaded") from exc
    model = bundle.get("model") if isinstance(bundle, dict) else bundle
    bundle_order = bundle.get("feature_order") if isinstance(bundle, dict) else None
    if bundle_order != order or getattr(model, "n_features_in_", 41) != 41: raise FrozenModelError("Frozen model feature order/count mismatch")
    logger.info("ml_model_loaded", extra={"model_version": metadata.get("model_version"), "feature_schema_version": metadata.get("feature_schema_version")})
    return LoadedWalletRiskModel(model=model, metadata=metadata)


@lru_cache(maxsize=1)
def get_wallet_risk_model() -> LoadedWalletRiskModel:
    return _load_uncached()


def load_model():
    """Backward-compatible loader; failures are explicit to the inference layer."""
    return get_wallet_risk_model()


def model_integrity_status() -> dict:
    """Safe startup/status probe; never returns artifact contents or secrets."""
    try:
        if not MODEL_PATH.exists() or not METADATA_PATH.exists():
            return {"status": "FAILED_INTEGRITY", "detail": "Frozen model artifact is missing"}
        model_hash, metadata_hash = _sha256(MODEL_PATH), _sha256(METADATA_PATH)
        if model_hash != EXPECTED_MODEL_SHA256 or metadata_hash != EXPECTED_METADATA_SHA256:
            return {"status": "FAILED_INTEGRITY", "detail": "Frozen model hash does not match the approved manifest", "model_sha256": model_hash, "metadata_sha256": metadata_hash}
        get_wallet_risk_model()
        return {"status": "READY", "model_sha256": model_hash, "metadata_sha256": metadata_hash}
    except FrozenModelError as exc:
        return {"status": "FAILED_INTEGRITY", "detail": str(exc)}
    except Exception:
        return {"status": "FAILED", "detail": "Frozen model could not be loaded"}
