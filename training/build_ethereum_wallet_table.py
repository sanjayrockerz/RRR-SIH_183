"""Build the RRR Ethereum V2 wallet table from the raw dataset only."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data" / "Datasets" / "transaction_dataset.csv"
OUT = ROOT / "data" / "Datasets" / "processed" / "rrr_ethereum_wallet_features_v2.parquet"
ART = ROOT / "artifacts"

BASE = {
    "incoming_tx_count": "Received Tnx", "outgoing_tx_count": "Sent tnx", "total_tx_count": "total transactions (including tnx to create contract",
    "unique_senders": "Unique Received From Addresses", "unique_receivers": "Unique Sent To Addresses",
    "total_value_in": "total ether received", "total_value_out": "total Ether sent", "mean_value_in": "avg val received", "mean_value_out": "avg val sent",
    "min_value_in": "min value received", "max_value_in": "max value received ", "min_value_out": "min val sent", "max_value_out": "max val sent",
    "activity_duration": "Time Diff between first and last (Mins)", "sent_interarrival_mean": "Avg min between sent tnx", "received_interarrival_mean": "Avg min between received tnx",
    "created_contract_count": "Number of Created Contracts", "token_transfer_count": " Total ERC20 tnxs", "unique_contract_count": " ERC20 uniq rec contract addr",
}
COUNT_FEATURES = {"incoming_tx_count", "outgoing_tx_count", "total_tx_count", "unique_senders", "unique_receivers", "created_contract_count", "token_transfer_count", "unique_contract_count"}
SUM_FEATURES = {"incoming_tx_count", "outgoing_tx_count", "total_tx_count", "total_value_in", "total_value_out", "created_contract_count", "token_transfer_count"}
MEAN_PAIRS = {"mean_value_in": ("total_value_in", "incoming_tx_count"), "mean_value_out": ("total_value_out", "outgoing_tx_count"), "sent_interarrival_mean": (None, "outgoing_tx_count"), "received_interarrival_mean": (None, "incoming_tx_count")}
MIN_FEATURES = {"min_value_in", "min_value_out"}
MAX_FEATURES = {"max_value_in", "max_value_out", "activity_duration"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""): h.update(b)
    return h.hexdigest()


def numeric(df: pd.DataFrame, col: str) -> pd.Series:
    return pd.to_numeric(df[col], errors="coerce")


def main() -> None:
    raw = pd.read_csv(DATASET)
    raw["address"] = raw["Address"].astype(str).str.lower()
    raw["original_label"] = pd.to_numeric(raw["FLAG"], errors="coerce")
    raw["normalized_label"] = raw["original_label"].map({0: 0, 1: 1})
    if raw["normalized_label"].isna().any() or not set(raw["normalized_label"].astype(int).unique()) <= {0, 1}:
        raise ValueError("Unexpected FLAG values; supervised build stopped")

    conflicts = raw.groupby("address")["normalized_label"].nunique()
    conflict_addresses = sorted(conflicts[conflicts > 1].index.tolist())
    (ART / "ethereum_label_conflicts.json").write_text(json.dumps({"conflicting_addresses": conflict_addresses, "count": len(conflict_addresses), "action": "excluded from supervised training"}, indent=2), encoding="utf-8")
    raw = raw[~raw.address.isin(conflict_addresses)].copy()

    for feature, source in BASE.items(): raw[feature] = numeric(raw, source)
    # The 829 rows with missing ERC20 numeric fields have all ERC20 activity fields
    # missing and no non-null ERC20 activity value; this is a dataset no-activity code.
    erc_numeric = [
        " Total ERC20 tnxs", " ERC20 total Ether received", " ERC20 total ether sent",
        " ERC20 total Ether sent contract", " ERC20 uniq sent addr", " ERC20 uniq rec addr",
        " ERC20 uniq sent addr.1", " ERC20 uniq rec contract addr",
        " ERC20 avg time between sent tnx", " ERC20 avg time between rec tnx",
        " ERC20 avg time between rec 2 tnx", " ERC20 avg time between contract tnx",
        " ERC20 min val rec", " ERC20 max val rec", " ERC20 avg val rec",
        " ERC20 min val sent", " ERC20 max val sent", " ERC20 avg val sent",
        " ERC20 min val sent contract", " ERC20 max val sent contract", " ERC20 avg val sent contract",
        " ERC20 uniq sent token name", " ERC20 uniq rec token name",
    ]
    erc_null_rows = raw[erc_numeric].isna().any(axis=1)
    erc_any_nonnull = raw.loc[erc_null_rows, erc_numeric].notna().any(axis=1).sum()
    if erc_any_nonnull:
        raise ValueError("ERC20 null semantics are mixed; refusing zero-fill")
    raw["erc20_missing_indicator"] = erc_null_rows.astype(int)
    raw["token_transfer_count"] = raw["token_transfer_count"].fillna(0)
    raw["unique_contract_count"] = raw["unique_contract_count"].fillna(0)
    raw["created_contract_count"] = raw["created_contract_count"].fillna(0)

    def aggregate(group: pd.DataFrame) -> pd.Series:
        out = {"address": group.name, "dataset_source": "transaction_dataset.csv", "original_label": int(group.original_label.iloc[0]), "normalized_label": int(group.normalized_label.iloc[0])}
        for f in BASE:
            s = group[f]
            if f in SUM_FEATURES: out[f] = float(s.fillna(0).sum())
            elif f in MIN_FEATURES: out[f] = float(s.dropna().min()) if s.notna().any() else 0.0
            elif f in MAX_FEATURES: out[f] = float(s.dropna().max()) if s.notna().any() else 0.0
            elif f in {"unique_senders", "unique_receivers", "unique_contract_count"}: out[f] = float(s.fillna(0).max())
            else: out[f] = float(s.fillna(0).mean())
        out["mean_value_in"] = out["total_value_in"] / out["incoming_tx_count"] if out["incoming_tx_count"] else 0.0
        out["mean_value_out"] = out["total_value_out"] / out["outgoing_tx_count"] if out["outgoing_tx_count"] else 0.0
        out["sent_interarrival_mean"] = float(np.average(group.sent_interarrival_mean.fillna(0), weights=group.outgoing_tx_count.clip(lower=0))) if group.outgoing_tx_count.sum() else 0.0
        out["received_interarrival_mean"] = float(np.average(group.received_interarrival_mean.fillna(0), weights=group.incoming_tx_count.clip(lower=0))) if group.incoming_tx_count.sum() else 0.0
        out["erc20_missing_indicator"] = int(group.erc20_missing_indicator.max())
        return pd.Series(out)

    table = raw.groupby("address", sort=True, group_keys=False).apply(aggregate, include_groups=False).reset_index(drop=True)
    table["unique_counterparties"] = table.unique_senders + table.unique_receivers
    table["in_out_tx_ratio"] = table.incoming_tx_count / table.outgoing_tx_count.replace(0, np.nan)
    table["out_in_value_ratio"] = table.total_value_out / table.total_value_in.replace(0, np.nan)
    table["net_flow_ratio"] = (table.total_value_in - table.total_value_out) / (table.total_value_in.abs() + table.total_value_out.abs()).replace(0, np.nan)
    table["counterparty_reuse_count"] = (table.total_tx_count - table.unique_counterparties).clip(lower=0)
    table["counterparty_reuse_ratio"] = table.counterparty_reuse_count / table.total_tx_count.replace(0, np.nan)
    table["transactions_per_active_period"] = table.total_tx_count / (table.activity_duration / 1440).clip(lower=1)
    table["contract_interaction_count"] = table.created_contract_count
    table["contract_interaction_ratio"] = table.contract_interaction_count / table.total_tx_count.replace(0, np.nan)
    log_sources = ["incoming_tx_count", "outgoing_tx_count", "total_tx_count", "unique_senders", "unique_receivers", "unique_counterparties", "total_value_in", "total_value_out", "activity_duration", "token_transfer_count", "unique_contract_count", "created_contract_count"]
    for f in log_sources: table[f"log1p_{f}"] = np.log1p(table[f].clip(lower=0))
    feature_order = [c for c in table.columns if c not in {"address", "dataset_source", "original_label", "normalized_label"}]
    table[feature_order] = table[feature_order].replace([np.inf, -np.inf], np.nan).fillna(0).astype(float)
    table["feature_schema_version"] = "RRRFeatureSchemaV2"
    table = table[["address", "dataset_source", "original_label", "normalized_label", "feature_schema_version"] + feature_order]
    OUT.parent.mkdir(parents=True, exist_ok=True); table.to_parquet(OUT, index=False)

    excluded = ["median_value_in", "median_value_out", "median_interarrival_time", "min_interarrival_time", "max_interarrival_time", "burstiness", "in_degree", "out_degree", "total_degree", "degree_imbalance", "in_out_degree_ratio", "fan_in_score", "fan_out_score", "graph_activity_density", "native_transfer_count", "token_transfer_ratio", "dataset_source", "chain_name", "RiskEngine_score", "Chainabuse_result", "VASP_attribution"]
    specs = []
    for f in feature_order:
        src = BASE.get(f, "derived from approved RRRFeatureSchemaV2 primitives")
        specs.append({"feature_name": f, "source_columns": [src] if isinstance(src, str) else src, "calculation": "direct numeric mapping" if f in BASE else "deterministic runtime-compatible derivation", "runtime_derivation": "PostgreSQL normalized transfer summary / Alchemy-compatible wallet history; contract fields from persisted contract/token transfers", "normalization": "log1p" if f.startswith("log1p_") else "none", "missing_value_handling": "ERC20 nulls filled 0 only after verifying all ERC20 activity fields are jointly null; other numeric NaN/zero denominators -> 0", "leakage_status": "approved; no labels, future fields, source identifiers, threat intelligence, risk engine, case fusion, or VASP attribution"})
    schema = {"schema_version": "RRRFeatureSchemaV2", "feature_order": feature_order, "features": specs, "excluded_features": excluded, "label_contract": {"0": "LICIT_LIKE", "1": "HIGH_RISK_LIKE"}, "source_limitations": ["No raw transaction hash/from/to/timestamp/block columns; graph fields are excluded."]}
    (ART / "rrr_feature_schema_v2.json").write_text(json.dumps(schema, indent=2), encoding="utf-8")
    contract = {"source_dataset": "Ethereum Fraud Detection Dataset", "local_file": "data/Datasets/transaction_dataset.csv", "mapping": {"0": "LICIT_LIKE", "1": "HIGH_RISK_LIKE"}, "original_field": "FLAG", "normalized_field": "normalized_label", "raw_counts": {"FLAG=0": 7662, "FLAG=1": 2179}, "label_scope": "Behavioural fraud-indicator target normalized for RRR; not a claim of criminality.", "verified_by_user": True}
    (ART / "ethereum_label_contract.json").write_text(json.dumps(contract, indent=2), encoding="utf-8")
    summary = {"raw_rows": len(raw), "usable_wallets": len(table), "duplicate_address_rows": int(len(raw) - raw.address.nunique()), "conflicting_addresses_excluded": len(conflict_addresses), "class_distribution": {"LICIT_LIKE": int((table.normalized_label == 0).sum()), "HIGH_RISK_LIKE": int((table.normalized_label == 1).sum())}, "feature_count": len(feature_order), "feature_order": feature_order, "raw_sha256": sha256(DATASET), "processed_sha256": sha256(OUT), "erc20_null_decision": "jointly-null ERC20 activity fields interpreted as no ERC20 activity and zero-filled; indicator retained"}
    (ART / "ethereum_wallet_table_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__": main()
