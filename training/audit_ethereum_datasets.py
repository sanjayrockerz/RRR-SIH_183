"""Local-only audit of all Ethereum-shaped CSV/Parquet datasets.

This intentionally does not infer label semantics from column names or values.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "Datasets"
OUT = ROOT / "artifacts" / "ethereum_dataset_audit.json"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load(path: Path) -> pd.DataFrame:
    return pd.read_parquet(path) if path.suffix.lower() == ".parquet" else pd.read_csv(path)


def candidate(path: Path, frame: pd.DataFrame) -> tuple[bool, str]:
    name = path.name.lower()
    cols = {str(c).lower() for c in frame.columns}
    if "ethereum" in name or "eth" in name:
        return True, "filename"
    if {"address", "flag"}.issubset(cols):
        address = next(c for c in frame.columns if str(c).lower() == "address")
        if any(str(v).lower().startswith("0x") for v in frame[address].dropna().head(100)):
            return True, "Ethereum hexadecimal wallet addresses plus FLAG"
    if "rrr_ethereum_wallet_features_v2" in name:
        return True, "derived Ethereum wallet table"
    return False, "not Ethereum-shaped from local schema/address evidence"


def find_col(frame: pd.DataFrame, terms: tuple[str, ...]):
    for c in frame.columns:
        lc = str(c).lower()
        if any(t in lc for t in terms):
            return str(c)
    return None


def find_exact_semantic(frame: pd.DataFrame, candidates: tuple[str, ...]):
    normalized = {str(c).strip().lower(): str(c) for c in frame.columns}
    for name in candidates:
        if name in normalized:
            return normalized[name]
    return None


def audit(path: Path) -> dict:
    frame = load(path)
    is_candidate, basis = candidate(path, frame)
    address = find_col(frame, ("address", "wallet", "account"))
    tx_hash = find_exact_semantic(frame, ("transaction hash", "tx hash", "txid", "hash"))
    sender = find_exact_semantic(frame, ("from", "sender", "source", "from_address", "sender_address", "input_address"))
    receiver = find_exact_semantic(frame, ("to", "receiver", "destination", "to_address", "receiver_address", "output_address"))
    timestamp = find_exact_semantic(frame, ("timestamp", "datetime", "date", "block_timestamp"))
    block = find_exact_semantic(frame, ("block", "block_number", "blocknumber"))
    value = find_exact_semantic(frame, ("value", "amount", "eth_value", "native_value", "total ether sent", "total ether received"))
    labels = [str(c) for c in frame.columns if any(x in str(c).lower() for x in ("flag", "label", "class", "fraud", "scam", "licit", "illicit"))]
    label_values = {}
    for c in labels:
        vc = frame[c].value_counts(dropna=False)
        label_values[c] = {str(k): int(v) for k, v in vc.items()}
    duplicate_tx = int(frame[tx_hash].duplicated(keep=False).sum()) if tx_hash else None
    return {
        "filename": str(path.relative_to(ROOT)), "sha256": sha256(path),
        "ethereum_candidate": is_candidate, "candidate_basis": basis,
        "rows": int(len(frame)), "unique_wallet_addresses": int(frame[address].nunique(dropna=True)) if address else None,
        "columns": [str(c) for c in frame.columns], "dtypes": {str(c): str(t) for c, t in frame.dtypes.items()},
        "candidate_columns": {"address": address, "transaction_hash": tx_hash, "sender": sender, "receiver": receiver, "timestamp": timestamp, "block_number": block, "eth_or_token_value": value},
        "label_columns": labels, "label_values": label_values,
        "label_definitions_verifiable_from_local_files": False,
        "label_definition_evidence": "No local data dictionary, source citation, or authoritative label mapping was found for this dataset.",
        "null_counts": {str(c): int(v) for c, v in frame.isna().sum().items() if int(v)},
        "duplicate_rows": int(frame.duplicated().sum()), "duplicate_transaction_rows": duplicate_tx,
        "duplicate_wallet_addresses": int(frame[address].duplicated(keep=False).sum()) if address else None,
        "conflicting_labels_by_address": None if not address or not labels else {c: int((frame.groupby(address)[c].nunique(dropna=False) > 1).sum()) for c in labels},
        "provenance": "Local workspace only; no internet or external source metadata used.",
    }


def main() -> None:
    reports = []
    for path in sorted(DATA.rglob("*")):
        if path.suffix.lower() not in {".csv", ".parquet"}:
            continue
        try:
            reports.append(audit(path))
        except Exception as exc:
            reports.append({"filename": str(path.relative_to(ROOT)), "audit_error": repr(exc)})
    ethereum = [r for r in reports if r.get("ethereum_candidate")]
    result = {
        "generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "scope": "All recursively discovered local CSV/Parquet files; Ethereum candidates identified only from actual local schemas and values.",
        "datasets_discovered": len(ethereum), "datasets": ethereum,
        "non_ethereum_inventory": [r["filename"] for r in reports if not r.get("ethereum_candidate") and "filename" in r],
        "label_semantics_status": "BLOCKED_UNVERIFIED",
        "blocking_reason": "The raw Ethereum-shaped dataset exposes FLAG values but local files do not verify whether 0/1 mean LICIT_LIKE/HIGH_RISK_LIKE. No supervised label contract may be created from this evidence.",
        "training_allowed": False,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
