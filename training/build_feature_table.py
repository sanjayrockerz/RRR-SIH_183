"""Build the leakage-safe RRRFeatureSchemaV1 supervised table."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
from feature_config import FEATURE_COLUMNS, FEATURE_SCHEMA_VERSION, META_COLUMNS

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "Datasets"
OUT = DATA / "processed" / "rrr_wallet_features_v1.parquet"
ART = ROOT / "artifacts"
ART.mkdir(exist_ok=True); OUT.parent.mkdir(exist_ok=True)

def build():
    classes = pd.read_csv(DATA / "wallets_classes.csv", dtype={"address": "string", "class": "Int64"})
    labels = classes.loc[classes["class"].isin([1, 2]), ["address", "class"]].copy()
    labels["label"] = (labels["class"] == 1).astype("int8")
    labels = labels.drop(columns="class")
    feat_cols = ["address", "Time step", "num_txs_as_sender", "num_txs_as receiver", "lifetime_in_blocks", "total_txs", "btc_sent_mean", "btc_received_mean", "btc_sent_total", "btc_received_total"]
    features = pd.read_csv(DATA / "wallets_features.csv", usecols=feat_cols)
    features = features.rename(columns={"Time step": "time_step", "num_txs_as_sender": "outgoing_tx_count", "num_txs_as receiver": "incoming_tx_count", "btc_received_total": "total_in", "btc_sent_total": "total_out", "btc_received_mean": "mean_in", "btc_sent_mean": "mean_out", "lifetime_in_blocks": "activity_duration"})
    before = len(features); exact_duplicates = int(features.duplicated(keep="first").sum()); features = features.drop_duplicates(keep="first")
    key_dupes = int(features.duplicated(["address", "time_step"], keep=False).sum())
    numeric = [c for c in features.columns if c not in {"address", "time_step"}]
    # Exact duplicates are removed above. If the same key still has conflicting values, mean numeric fields deterministically.
    conflicts = int(features.groupby(["address", "time_step"], sort=False).size().gt(1).sum())
    if conflicts:
        features = features.groupby(["address", "time_step"], as_index=False, sort=False)[numeric].mean()
    features["out_in_ratio"] = features["outgoing_tx_count"] / features["incoming_tx_count"].replace(0, np.nan)
    features["out_in_ratio"] = features["out_in_ratio"].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    features["burstiness"] = features["total_txs"] / (1.0 + features["activity_duration"].clip(lower=0))
    # Topology-only graph features. No labels are joined or used here.
    edges = pd.read_csv(DATA / "AddrAddr_edgelist.csv", dtype="string")
    source = edges["input_address"]; target = edges["output_address"]
    in_degree = target.value_counts(sort=False); out_degree = source.value_counts(sort=False)
    # Grouping the two columns directly avoids any label-derived graph statistic.
    unique_in = edges.groupby("output_address", sort=False)["input_address"].nunique()
    unique_out = edges.groupby("input_address", sort=False)["output_address"].nunique()
    graph = pd.DataFrame({"address": pd.Index(set(in_degree.index) | set(out_degree.index), dtype="string")})
    graph["in_degree"] = graph["address"].map(in_degree).fillna(0)
    graph["out_degree"] = graph["address"].map(out_degree).fillna(0)
    graph["unique_senders"] = graph["address"].map(unique_in).fillna(0)
    graph["unique_receivers"] = graph["address"].map(unique_out).fillna(0)
    graph["total_degree"] = graph["in_degree"] + graph["out_degree"]
    graph["fan_in_score"] = graph["in_degree"] / graph["total_degree"].replace(0, np.nan)
    graph["fan_out_score"] = graph["out_degree"] / graph["total_degree"].replace(0, np.nan)
    graph["repeated_counterparty_ratio"] = (1.0 - (graph["unique_senders"] + graph["unique_receivers"]) / graph["total_degree"].replace(0, np.nan)).clip(lower=0, upper=1)
    graph = graph.fillna(0.0)
    data = features.merge(labels, on="address", how="inner", validate="many_to_one").merge(graph, on="address", how="left", validate="many_to_one")
    data["time_step"] = pd.to_numeric(data["time_step"], errors="coerce")
    for c in FEATURE_COLUMNS: data[c] = pd.to_numeric(data[c], errors="coerce")
    data["label"] = data["label"].astype("int8"); data["feature_schema_version"] = FEATURE_SCHEMA_VERSION
    data = data.sort_values(["address", "time_step"], kind="stable").reset_index(drop=True)
    data.insert(0, "observation_id", data["address"].astype(str) + "@t" + data["time_step"].astype(int).astype(str))
    data = data[META_COLUMNS + FEATURE_COLUMNS]
    assert data[FEATURE_COLUMNS].isna().sum().sum() == 0
    assert np.isfinite(data[FEATURE_COLUMNS].to_numpy(dtype=float)).all()
    data.to_parquet(OUT, index=False)
    earliest = data.groupby("address", sort=False)["time_step"].min()
    group = earliest.map(lambda t: "train" if t <= 34 else "validation" if t <= 41 else "test")
    split = data["address"].map(group)
    manifests = {}
    for name in ["train", "validation", "test"]:
        subset = data.loc[split == name]
        manifests[name] = {"rows": int(len(subset)), "addresses": int(subset["address"].nunique()), "time_steps_present": sorted(subset["time_step"].unique().tolist()), "observation_ids": subset["observation_id"].tolist()}
    (ART / "split_manifests.json").write_text(json.dumps({"strategy": "address_grouped_by_earliest_time_step", "ranges_requested": {"train": [1, 34], "validation": [35, 41], "test": [42, 49]}, "splits": manifests}, indent=2), encoding="utf-8")
    summary = {"generated_at": datetime.now(timezone.utc).isoformat(), "rows": int(len(data)), "licit_count": int((data.label == 0).sum()), "illicit_count": int((data.label == 1).sum()), "unknown_dropped": int((classes["class"] == 3).sum()), "class_ratio_illicit_to_licit": float((data.label == 1).sum() / max((data.label == 0).sum(), 1)), "feature_null_rate": {c: float(data[c].isna().mean()) for c in FEATURE_COLUMNS}, "feature_min": {c: float(data[c].min()) for c in FEATURE_COLUMNS}, "feature_max": {c: float(data[c].max()) for c in FEATURE_COLUMNS}, "duplicate_handling": {"input_rows": before, "exact_duplicate_rows_removed": exact_duplicates, "remaining_same_address_timestep_rows_before_aggregation": key_dupes, "conflicting_address_timestep_groups_aggregated_by_numeric_mean": conflicts, "rule": "Treat each valid wallet-time observation as temporal; remove only byte-for-byte duplicate rows; aggregate conflicting duplicate keys by deterministic numeric mean."}, "schema_version": FEATURE_SCHEMA_VERSION, "feature_columns": FEATURE_COLUMNS, "output": str(OUT.relative_to(ROOT))}
    (ART / "training_dataset_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(OUT), "rows": len(data), "licit": int((data.label == 0).sum()), "illicit": int((data.label == 1).sum()), "unknown_dropped": int((classes["class"] == 3).sum()), "exact_duplicates_removed": exact_duplicates, "conflicting_keys_aggregated": conflicts, "splits": {k: v["rows"] for k, v in manifests.items()}}, indent=2))
    return data, manifests

if __name__ == "__main__": build()
