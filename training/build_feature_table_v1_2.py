"""Build isolated V1.2 wallet-level dataset formulations.

V1.2 addresses the label/observation mismatch by comparing the existing
observation table with one-row-per-wallet latest and historical aggregates.
No labels are used to construct features and the raw V1/V1.1 tables are not
modified.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "Datasets" / "processed"
ARTIFACTS = ROOT / "artifacts"
SOURCE = PROCESSED / "rrr_wallet_features_v1_1.parquet"

META = {"observation_id", "address", "time_step", "label", "feature_schema_version"}

# These fields are per-observation values in the Elliptic++ table. Counts and
# amounts are additive across distinct observed timesteps; snapshot/cumulative
# fields use max/median rather than being blindly summed.
SUM_FIELDS = {
    "incoming_tx_count", "outgoing_tx_count", "total_in", "total_out",
    "total_tx_count", "repeated_address_count",
}
MAX_FIELDS = {"activity_duration", "observation_lifetime", "active_period_count"}
MEDIAN_FIELDS = {
    "mean_in", "mean_out", "min_in", "max_in", "median_in", "min_out",
    "max_out", "median_out", "mean_activity_gap", "median_activity_gap",
    "min_activity_gap", "max_activity_gap", "burstiness",
}
GRAPH_FIELDS = {
    "in_degree", "out_degree", "total_degree", "fan_in_score", "fan_out_score",
    "repeated_counterparty_ratio", "unique_counterparties",
    "counterparty_reuse_count", "in_out_degree_ratio", "degree_imbalance",
    "graph_activity_density",
}

BASE_FIELDS = [
    "incoming_tx_count", "outgoing_tx_count", "unique_senders", "unique_receivers",
    "total_in", "total_out", "mean_in", "mean_out", "out_in_ratio",
    "activity_duration", "burstiness", "in_degree", "out_degree", "total_degree",
    "fan_in_score", "fan_out_score", "repeated_counterparty_ratio", "min_in", "max_in",
    "median_in", "min_out", "max_out", "median_out", "total_tx_count", "sender_ratio",
    "receiver_ratio", "repeated_address_count", "observation_lifetime", "active_period_count",
    "mean_activity_gap", "median_activity_gap", "min_activity_gap", "max_activity_gap",
    "max_to_mean_out_ratio", "max_to_mean_in_ratio", "sent_received_ratio", "net_flow_ratio",
    "unique_counterparties", "counterparty_reuse_count", "in_out_degree_ratio",
    "degree_imbalance", "graph_activity_density",
]
LOG_SOURCES = [
    "incoming_tx_count", "outgoing_tx_count", "total_in", "total_out", "total_tx_count",
    "in_degree", "out_degree", "total_degree", "activity_duration", "observation_lifetime",
    "repeated_address_count", "unique_counterparties", "counterparty_reuse_count",
]


def clean_ratio(data: pd.DataFrame) -> pd.DataFrame:
    eps = 1e-9
    data["mean_in"] = data["total_in"] / data["incoming_tx_count"].replace(0, np.nan)
    data["mean_out"] = data["total_out"] / data["outgoing_tx_count"].replace(0, np.nan)
    data["out_in_ratio"] = data["total_out"] / (data["total_in"] + eps)
    data["sender_ratio"] = data["outgoing_tx_count"] / data["total_tx_count"].replace(0, np.nan)
    data["receiver_ratio"] = data["incoming_tx_count"] / data["total_tx_count"].replace(0, np.nan)
    data["max_to_mean_out_ratio"] = data["max_out"] / data["mean_out"].replace(0, np.nan)
    data["max_to_mean_in_ratio"] = data["max_in"] / data["mean_in"].replace(0, np.nan)
    data["sent_received_ratio"] = data["total_out"] / (data["total_in"] + eps)
    data["net_flow_ratio"] = (data["total_in"] - data["total_out"]) / (data["total_in"] + data["total_out"] + eps)
    data["in_out_degree_ratio"] = data["in_degree"] / data["out_degree"].replace(0, np.nan)
    data["degree_imbalance"] = (data["in_degree"] - data["out_degree"]).abs() / data["total_degree"].replace(0, np.nan)
    data["unique_counterparties"] = data["unique_senders"] + data["unique_receivers"]
    data["counterparty_reuse_count"] = (data["total_degree"] - data["unique_counterparties"]).clip(lower=0)
    for name in BASE_FIELDS:
        data[name] = pd.to_numeric(data[name], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0)
    for name in LOG_SOURCES:
        data[f"log1p_{name}"] = np.log1p(data[name].clip(lower=0))
    return data


def aggregate(group: pd.DataFrame) -> pd.Series:
    out = {"address": group.name, "time_step": int(group["time_step"].max()), "label": int(group["label"].iloc[0])}
    for field in BASE_FIELDS:
        if field in GRAPH_FIELDS:
            out[field] = float(group[field].iloc[0])
        elif field in SUM_FIELDS:
            out[field] = float(group[field].sum())
        elif field in MAX_FIELDS:
            out[field] = float(group[field].max())
        elif field in MEDIAN_FIELDS:
            out[field] = float(group[field].median())
        else:
            # Derived ratios are recomputed below from aggregated primitives.
            out[field] = float(group[field].median())
    result = pd.Series(out)
    return result


def finalize(data: pd.DataFrame, variant: str, preserve_observation_id: bool = False) -> pd.DataFrame:
    data = clean_ratio(data.copy())
    data["feature_schema_version"] = "RRRFeatureSchemaV1.2"
    if not preserve_observation_id:
        data["observation_id"] = data["address"].astype(str) + "@" + variant.lower()
    cols = ["observation_id", "address", "time_step", "label", "feature_schema_version"] + BASE_FIELDS + [f"log1p_{x}" for x in LOG_SOURCES]
    data = data[cols]
    assert data[BASE_FIELDS + [f"log1p_{x}" for x in LOG_SOURCES]].isna().sum().sum() == 0
    assert np.isfinite(data[BASE_FIELDS + [f"log1p_{x}" for x in LOG_SOURCES]].to_numpy(dtype=float)).all()
    return data


def main() -> None:
    source = pd.read_parquet(SOURCE)
    source = source[source["label"].isin([0, 1])].copy()
    source["time_step"] = pd.to_numeric(source["time_step"], errors="coerce").astype(int)

    latest = source.sort_values(["address", "time_step", "observation_id"]).groupby("address", as_index=False, sort=False).tail(1).copy()
    latest = finalize(latest, "latest_observation")

    # Graph features are already fixed per wallet in V1.1 and are carried once,
    # never recomputed from labels or summed across observations.
    grouped = source.groupby("address", sort=False, observed=True)
    agg_map = {}
    for field in BASE_FIELDS:
        if field in GRAPH_FIELDS:
            agg_map[field] = "first"
        elif field in SUM_FIELDS:
            agg_map[field] = "sum"
        elif field in MAX_FIELDS:
            agg_map[field] = "max"
        else:
            agg_map[field] = "median"
    aggregated = grouped.agg(agg_map).reset_index()
    aggregated["time_step"] = grouped["time_step"].max().to_numpy()
    aggregated["label"] = grouped["label"].first().to_numpy()
    aggregated = finalize(aggregated, "aggregated_history")

    temporal = finalize(source.copy(), "temporal", preserve_observation_id=True)
    outputs = {"TEMPORAL": temporal, "LATEST_OBSERVATION": latest, "AGGREGATED_HISTORY": aggregated}
    for name, frame in outputs.items():
        frame.to_parquet(PROCESSED / f"rrr_wallet_features_v1_2_{name.lower()}.parquet", index=False)

    schema = {
        "schema_version": "RRRFeatureSchemaV1.2",
        "feature_order": BASE_FIELDS + [f"log1p_{x}" for x in LOG_SOURCES],
        "aggregation_rules": {
            "sum": sorted(SUM_FIELDS), "max": sorted(MAX_FIELDS), "median": sorted(MEDIAN_FIELDS),
            "graph_fixed_once": sorted(GRAPH_FIELDS),
            "derived": "Ratios are recomputed after aggregation from aggregated primitive fields; no label fields participate.",
        },
        "source": "rrr_wallet_features_v1_1.parquet derived from Elliptic++ Actors and AddrAddr_edgelist.csv",
        "label_rule": "1=ILLICIT, 0=LICIT; UNKNOWN was excluded before construction.",
        "variants": {name: {"rows": len(frame), "illicit": int(frame.label.sum()), "licit": int((frame.label == 0).sum())} for name, frame in outputs.items()},
    }
    (ARTIFACTS / "feature_schema_v1_2.json").write_text(json.dumps(schema, indent=2), encoding="utf-8")
    summary = {name: {"rows": len(frame), "licit": int((frame.label == 0).sum()), "illicit": int(frame.label.sum()), "latest_timestep_min": int(frame.time_step.min()), "latest_timestep_max": int(frame.time_step.max())} for name, frame in outputs.items()}
    (ARTIFACTS / "v1_2_dataset_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
