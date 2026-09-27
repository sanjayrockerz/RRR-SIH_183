from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from uuid import uuid4

from .explanations import top_feature_signals
from .features import FeatureSchemaError, InsufficientDataError, build_feature_vector
from .model_loader import FrozenModelError, get_wallet_risk_model
from .schemas import MLClassification, MLInferenceResult, MLRiskAssessment, MLModelStatus
from ..domain import Chain, normalize_address
from ..runtime_paths import PROJECT_ROOT

logger = logging.getLogger("crypto_fraud_intelligence")


class WalletMLRiskService:
    def __init__(self, repository): self.repository = repository

    async def assess_result(self, case_id: str, address: str, chain: Chain | str, observation_time: datetime | None = None) -> MLInferenceResult:
        generated_at = datetime.now(timezone.utc)
        chain_value = str(chain.value if isinstance(chain, Chain) else chain).lower()
        normalized = normalize_address(Chain(chain_value), address) if chain_value in {"ethereum", "tron"} else address
        if chain_value != Chain.ETHEREUM.value:
            return await self._persist_blocked(case_id, normalized, chain_value, generated_at, MLModelStatus.UNSUPPORTED_CHAIN, ["The frozen V2 model is Ethereum-only; no Tron inference was attempted."])
        try:
            loaded = get_wallet_risk_model(); metadata = loaded.metadata; order = metadata["feature_order"]
            vector = await build_feature_vector(self.repository, case_id, Chain.ETHEREUM, normalized, observation_time)
            probability = float(loaded.model.predict_proba([[vector.features[name] for name in order]])[0][1])
            threshold = float(metadata["threshold"])
            classification = MLClassification.HIGH_RISK_LIKE if probability >= threshold else MLClassification.LICIT_LIKE
            integrity = json.loads((PROJECT_ROOT / "artifacts" / "ml_frozen_model_integrity.json").read_text())
            record = {"inference_id": str(uuid4()), "case_id": case_id, "wallet_id": await self._wallet_id(case_id, Chain.ETHEREUM, normalized), "model_name": metadata["model_name"], "chain": Chain.ETHEREUM.value, "address": normalized, "model_version": metadata["model_version"], "feature_schema_version": metadata["feature_schema_version"], "probability": probability, "classification": classification.value, "threshold": threshold, "top_features": top_feature_signals(loaded.model, order, vector.features, limit=5), "feature_hash": vector.feature_hash, "generated_at": generated_at, "observation_cutoff": observation_time, "status": MLModelStatus.READY.value, "limitations": ["HIGH_RISK_LIKE is behavioural model output, not a criminality determination.", "Ethereum-only frozen model; graph, Chainabuse, RiskEngine, Case Fusion, and VASP attribution are not model inputs."], "features": vector.features, "provenance": {"model_path": "models/rrr_ethereum_wallet_xgb_v2.joblib", "model_sha256": integrity["model_sha256"], "metadata_path": "models/rrr_ethereum_wallet_xgb_v2_metadata.json", "metadata_sha256": integrity["metadata_sha256"], "feature_order_source": "frozen metadata", "runtime_source": "PostgreSQL persisted transactions and transaction_transfers", "observation_cutoff": observation_time.isoformat() if observation_time else None}}
            persisted = await self.repository.persist_ml_inference(record)
            logger.info("ml_inference_completed", extra={"case_id": case_id, "chain": Chain.ETHEREUM.value, "address": normalized, "model_version": metadata["model_version"], "classification": classification.value})
            logger.info("ml_assessment_persisted", extra={"case_id": case_id, "chain": Chain.ETHEREUM.value, "address": normalized, "feature_hash": vector.feature_hash})
            return MLRiskAssessment(**persisted)
        except InsufficientDataError as exc:
            return await self._persist_blocked(case_id, normalized, chain_value, generated_at, MLModelStatus.INSUFFICIENT_DATA, [str(exc), "No classification was produced."])
        except FrozenModelError as exc:
            return await self._persist_blocked(case_id, normalized, chain_value, generated_at, MLModelStatus.NOT_CONFIGURED, [str(exc), "Inference failed closed; no prediction was produced."])
        except FeatureSchemaError as exc:
            return await self._persist_blocked(case_id, normalized, chain_value, generated_at, MLModelStatus.FEATURE_SCHEMA_MISMATCH, [str(exc), "Inference was not called."])

    async def _persist_blocked(self, case_id, address, chain, generated_at, status, limitations):
        logger.warning("ml_inference_blocked", extra={"case_id": case_id, "chain": chain, "address": address, "status": status.value})
        record = {"inference_id": str(uuid4()), "case_id": case_id, "wallet_id": None, "chain": chain, "address": address, "status": status.value, "limitations": limitations, "features": {}, "top_features": [], "generated_at": generated_at, "provenance": {"runtime_source": "PostgreSQL persisted transactions"}}
        try:
            persisted = await self.repository.persist_ml_inference(record)
            logger.info("ml_assessment_persisted", extra={"case_id": case_id, "chain": chain, "address": address, "status": status.value})
            return MLInferenceResult(inference_id=persisted.get("inference_id"), address=address, chain=chain, case_id=case_id, generated_at=generated_at, status=status, limitations=limitations)
        except Exception:
            # A blocked inference must never be converted into an operational error record
            # when persistence itself is unavailable.
            return MLInferenceResult(address=address, chain=chain, case_id=case_id, generated_at=generated_at, status=status, limitations=limitations)

    async def assess(self, case_id: str, address: str, chain: Chain | str) -> MLRiskAssessment | None:
        result = await self.assess_result(case_id, address, chain)
        if result.status != MLModelStatus.READY:
            raise ValueError(result.limitations[0] if result.limitations else result.status.value)
        return result  # type: ignore[return-value]

    async def assess_and_persist_wallet(self, case_id: str, address: str, chain: Chain | str, observation_time: datetime | None = None):
        return await self.assess_result(case_id, address, chain, observation_time)

    async def _wallet_id(self, case_id: str, chain: Chain, address: str):
        case = await self.repository.get(case_id)
        if not case: return None
        match = next((wallet for wallet in case.wallets if normalize_address(chain, wallet.address) == address), None)
        return getattr(match, "wallet_id", None) if match else None


MLInferenceService = WalletMLRiskService
