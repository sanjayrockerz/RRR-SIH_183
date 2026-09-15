from __future__ import annotations

import hashlib
import json
import logging
import math
from datetime import datetime, timezone
from pathlib import Path

from ..domain import Chain, normalize_address
from .schemas import MLFeatureVector

ROOT = Path(__file__).resolve().parents[4]
METADATA_PATH = ROOT / "models" / "rrr_ethereum_wallet_xgb_v2_metadata.json"
logger = logging.getLogger("crypto_fraud_intelligence")


class FeatureSchemaError(RuntimeError):
    pass


class InsufficientDataError(RuntimeError):
    pass


def frozen_feature_order() -> list[str]:
    try:
        metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
        order = metadata["feature_order"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise FeatureSchemaError("Frozen feature metadata is unavailable") from exc
    if len(order) != 41 or len(set(order)) != 41:
        raise FeatureSchemaError("Frozen metadata must define exactly 41 unique features")
    return list(order)


FEATURES = frozen_feature_order() if METADATA_PATH.exists() else []


def _address(chain: Chain | str, address: str) -> str:
    chain = Chain(str(chain).lower()) if not isinstance(chain, Chain) else chain
    return normalize_address(chain, address)


def _number(value) -> float:
    try:
        value = float(value)
        return value if math.isfinite(value) else 0.0
    except (TypeError, ValueError):
        return 0.0


def _row_value(row, key: str):
    try:
        return row[key]
    except (KeyError, TypeError):
        return None


async def _load_rows(repo, chain: Chain, address: str, observation_cutoff: datetime | None):
    if hasattr(repo, "ml_transaction_rows"):
        return await repo.ml_transaction_rows(chain, address, observation_cutoff)
    query = """
        SELECT t.tx_hash,t.from_address,t.to_address,t.timestamp,t.native_value,t.raw_reference,
               tt.transfer_id,tt.transfer_type,tt.contract_address,tt.source_address,tt.destination_address
        FROM transactions t
        LEFT JOIN transaction_transfers tt ON tt.transaction_id=t.transaction_id
        WHERE t.chain=$1 AND (lower(t.from_address)=lower($2) OR lower(t.to_address)=lower($2))
    """
    args = [chain, address]
    if observation_cutoff is not None:
        query += " AND (t.timestamp IS NULL OR t.timestamp <= $3)"
        args.append(observation_cutoff)
    query += " ORDER BY t.timestamp NULLS LAST,t.tx_hash,tt.transfer_id"
    async with repo._require_pool().acquire() as conn:
        return await conn.fetch(query, *args)


def _is_contract_creation(row, destination: str) -> bool:
    if destination:
        return False
    raw = _row_value(row, "raw_reference") or {}
    if isinstance(raw, str):
        try: raw = json.loads(raw)
        except ValueError: raw = {}
    return bool(raw.get("contract_creation") or raw.get("to") is None or raw.get("method") == "eth_getTransactionByHash")


async def extract_features(repo, chain: Chain | str, address: str, observation_cutoff: datetime | None = None) -> dict[str, float]:
    chain = Chain(str(chain).lower()) if not isinstance(chain, Chain) else chain
    if chain != Chain.ETHEREUM:
        raise FeatureSchemaError("Frozen Ethereum model does not support this chain")
    address = _address(chain, address)
    rows = await _load_rows(repo, chain, address, observation_cutoff)
    if not rows:
        raise InsufficientDataError("No persisted transactions for wallet")

    tx = {}
    token_transfers = set(); contracts = set(); created_contracts = set()
    for row in rows:
        tx_hash = str(_row_value(row, "tx_hash") or "")
        if tx_hash and tx_hash not in tx:
            tx[tx_hash] = row
        transfer_type = str(_row_value(row, "transfer_type") or "native").lower()
        contract = str(_row_value(row, "contract_address") or "").lower()
        if transfer_type != "native" or contract:
            token_transfers.add((tx_hash, transfer_type, contract, str(_row_value(row, "transfer_id") or "")))
            if contract: contracts.add(contract)

    def source(row): return str(_row_value(row, "from_address") or "").lower()
    def target(row): return str(_row_value(row, "to_address") or "").lower()
    incoming = [row for row in tx.values() if target(row) == address.lower()]
    outgoing = [row for row in tx.values() if source(row) == address.lower()]
    values_in = [_number(_row_value(row, "native_value")) for row in incoming]
    values_out = [_number(_row_value(row, "native_value")) for row in outgoing]
    timestamps = sorted([_row_value(row, "timestamp") for row in tx.values() if _row_value(row, "timestamp") is not None])
    incoming_times = sorted([_row_value(row, "timestamp") for row in incoming if _row_value(row, "timestamp") is not None])
    outgoing_times = sorted([_row_value(row, "timestamp") for row in outgoing if _row_value(row, "timestamp") is not None])
    gaps = [(timestamps[i] - timestamps[i - 1]).total_seconds() / 60 for i in range(1, len(timestamps))]
    incoming_gaps = [(incoming_times[i] - incoming_times[i - 1]).total_seconds() / 60 for i in range(1, len(incoming_times))]
    outgoing_gaps = [(outgoing_times[i] - outgoing_times[i - 1]).total_seconds() / 60 for i in range(1, len(outgoing_times))]
    senders = {source(row) for row in incoming if source(row)}; receivers = {target(row) for row in outgoing if target(row)}
    for row in tx.values():
        if _is_contract_creation(row, target(row)): created_contracts.add(str(_row_value(row, "tx_hash")))
    duration = (timestamps[-1] - timestamps[0]).total_seconds() / 60 if len(timestamps) >= 2 else 0.0
    total = len(tx); unique_cp = len(senders | receivers)
    mean = lambda xs: sum(xs) / len(xs) if xs else 0.0
    base = {
        "incoming_tx_count": len(incoming), "outgoing_tx_count": len(outgoing), "total_tx_count": total,
        "unique_senders": len(senders), "unique_receivers": len(receivers), "total_value_in": sum(values_in), "total_value_out": sum(values_out),
        "mean_value_in": mean(values_in), "mean_value_out": mean(values_out), "min_value_in": min(values_in, default=0.0), "max_value_in": max(values_in, default=0.0),
        "min_value_out": min(values_out, default=0.0), "max_value_out": max(values_out, default=0.0), "activity_duration": duration,
        "sent_interarrival_mean": mean([g for g in outgoing_gaps if g >= 0]), "received_interarrival_mean": mean([g for g in incoming_gaps if g >= 0]),
        "created_contract_count": len(created_contracts), "token_transfer_count": len(token_transfers), "unique_contract_count": len(contracts),
        "erc20_missing_indicator": 1 if not token_transfers else 0,
    }
    base["unique_counterparties"] = unique_cp
    base["in_out_tx_ratio"] = base["incoming_tx_count"] / base["outgoing_tx_count"] if base["outgoing_tx_count"] else 0.0
    base["out_in_value_ratio"] = base["total_value_out"] / base["total_value_in"] if base["total_value_in"] else 0.0
    base["net_flow_ratio"] = (base["total_value_in"] - base["total_value_out"]) / (abs(base["total_value_in"]) + abs(base["total_value_out"])) if (base["total_value_in"] or base["total_value_out"]) else 0.0
    base["counterparty_reuse_count"] = max(total - unique_cp, 0); base["counterparty_reuse_ratio"] = base["counterparty_reuse_count"] / total if total else 0.0
    base["transactions_per_active_period"] = total / max(duration / 1440, 1.0)
    base["contract_interaction_count"] = base["created_contract_count"]
    base["contract_interaction_ratio"] = base["contract_interaction_count"] / total if total else 0.0
    for name in ("incoming_tx_count", "outgoing_tx_count", "total_tx_count", "unique_senders", "unique_receivers", "unique_counterparties", "total_value_in", "total_value_out", "activity_duration", "token_transfer_count", "unique_contract_count", "created_contract_count"):
        base[f"log1p_{name}"] = math.log1p(max(base[name], 0.0))
    order = frozen_feature_order()
    result = {name: float(base.get(name, 0.0)) for name in order}
    validate_feature_dict(result, order)
    logger.info("ml_feature_extraction_completed", extra={"chain": chain.value, "address": address, "transaction_count": total, "feature_count": len(order)})
    return result


def validate_feature_dict(features: dict[str, float], order: list[str] | None = None) -> None:
    order = order or frozen_feature_order()
    if list(features) != list(order): raise FeatureSchemaError("Runtime feature order does not match frozen metadata")
    if set(features) != set(order): raise FeatureSchemaError("Runtime feature names do not match frozen metadata")
    for name in order:
        if not isinstance(features[name], (int, float)) or not math.isfinite(float(features[name])):
            raise FeatureSchemaError(f"Invalid numeric feature: {name}")


def feature_hash(features: dict[str, float], *, address: str = "", chain: str = "ethereum", schema_version: str = "RRRFeatureSchemaV2", observation_cutoff: datetime | None = None) -> str:
    order = frozen_feature_order(); validate_feature_dict(features, order)
    payload = {"feature_order": order, "feature_values": [float(features[name]) for name in order], "schema_version": schema_version, "address": address, "chain": chain, "observation_cutoff": observation_cutoff.isoformat() if observation_cutoff else None}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


async def build_feature_vector(repo, case_id: str | None, chain: Chain | str, address: str, observation_cutoff: datetime | None = None) -> MLFeatureVector:
    chain = Chain(str(chain).lower()) if not isinstance(chain, Chain) else chain; normalized = _address(chain, address)
    features = await extract_features(repo, chain, normalized, observation_cutoff)
    timestamps = None
    return MLFeatureVector(feature_schema_version=json.loads(METADATA_PATH.read_text())["feature_schema_version"], address=normalized, chain=chain.value, case_id=case_id, observation_time=timestamps, observation_cutoff=observation_cutoff, features=features, feature_hash=feature_hash(features, address=normalized, chain=chain.value, schema_version=json.loads(METADATA_PATH.read_text())["feature_schema_version"], observation_cutoff=observation_cutoff))
