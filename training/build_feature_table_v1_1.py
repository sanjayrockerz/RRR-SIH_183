"""Build RRRFeatureSchemaV1.1 from the same cleaned observations and graph."""
from pathlib import Path
import numpy as np
import pandas as pd
from feature_config import FEATURE_SCHEMA_VERSION

ROOT = Path(__file__).resolve().parents[1]; DATA = ROOT / "data" / "Datasets"; OUT = DATA / "processed" / "rrr_wallet_features_v1_1.parquet"
BASE_FEATURES = ["incoming_tx_count","outgoing_tx_count","unique_senders","unique_receivers","total_in","total_out","mean_in","mean_out","out_in_ratio","activity_duration","burstiness","in_degree","out_degree","total_degree","fan_in_score","fan_out_score","repeated_counterparty_ratio"]
ADDED_FEATURES = ["min_in","max_in","median_in","min_out","max_out","median_out","total_tx_count","sender_ratio","receiver_ratio","repeated_address_count","observation_lifetime","active_period_count","mean_activity_gap","median_activity_gap","min_activity_gap","max_activity_gap","max_to_mean_out_ratio","max_to_mean_in_ratio","sent_received_ratio","net_flow_ratio","unique_counterparties","counterparty_reuse_count","in_out_degree_ratio","degree_imbalance","graph_activity_density"]
RAW_ADDED_FEATURES = ["min_in","max_in","median_in","min_out","max_out","median_out","total_tx_count","repeated_address_count","observation_lifetime","active_period_count","mean_activity_gap","median_activity_gap","min_activity_gap","max_activity_gap"]
LOG_FEATURES = ["incoming_tx_count","outgoing_tx_count","total_in","total_out","total_tx_count","in_degree","out_degree","total_degree","activity_duration","observation_lifetime","repeated_address_count","unique_counterparties","counterparty_reuse_count"]

def main():
    base = pd.read_parquet(DATA / "processed" / "rrr_wallet_features_v1.parquet")
    raw_cols = ["address","Time step","num_txs_as_sender","num_txs_as receiver","btc_received_min","btc_received_max","btc_received_median","btc_sent_min","btc_sent_max","btc_sent_median","total_txs","num_timesteps_appeared_in","blocks_btwn_txs_mean","blocks_btwn_txs_median","blocks_btwn_txs_min","blocks_btwn_txs_max","num_addr_transacted_multiple","lifetime_in_blocks"]
    raw = pd.read_csv(DATA / "wallets_features.csv", usecols=raw_cols).rename(columns={"Time step":"time_step","num_txs_as_sender":"outgoing_tx_count","num_txs_as receiver":"incoming_tx_count","btc_received_min":"min_in","btc_received_max":"max_in","btc_received_median":"median_in","btc_sent_min":"min_out","btc_sent_max":"max_out","btc_sent_median":"median_out","total_txs":"total_tx_count","num_timesteps_appeared_in":"active_period_count","blocks_btwn_txs_mean":"mean_activity_gap","blocks_btwn_txs_median":"median_activity_gap","blocks_btwn_txs_min":"min_activity_gap","blocks_btwn_txs_max":"max_activity_gap","num_addr_transacted_multiple":"repeated_address_count","lifetime_in_blocks":"observation_lifetime"})
    raw = raw.drop_duplicates(keep="first")
    raw["time_step"] = pd.to_numeric(raw["time_step"], errors="coerce")
    num = [c for c in raw.columns if c not in {"address","time_step"}]
    if raw.duplicated(["address","time_step"], keep=False).any(): raw = raw.groupby(["address","time_step"], as_index=False, sort=False)[num].mean()
    raw["observation_id"] = raw["address"].astype(str) + "@t" + raw["time_step"].astype(int).astype(str)
    raw = raw.drop_duplicates("observation_id", keep="first")
    added = raw[["observation_id"] + RAW_ADDED_FEATURES].copy()
    data = base.merge(added, on="observation_id", how="left", validate="one_to_one")
    eps = 1e-9
    data["sender_ratio"] = data["outgoing_tx_count"] / data["total_tx_count"].replace(0, np.nan)
    data["receiver_ratio"] = data["incoming_tx_count"] / data["total_tx_count"].replace(0, np.nan)
    data["max_to_mean_out_ratio"] = data["max_out"] / data["mean_out"].replace(0, np.nan)
    data["max_to_mean_in_ratio"] = data["max_in"] / data["mean_in"].replace(0, np.nan)
    data["sent_received_ratio"] = data["total_out"] / (data["total_in"] + eps)
    data["net_flow_ratio"] = (data["total_in"] - data["total_out"]) / (data["total_in"] + data["total_out"] + eps)
    data["unique_counterparties"] = data["unique_senders"] + data["unique_receivers"]
    data["counterparty_reuse_count"] = (data["total_degree"] - data["unique_counterparties"]).clip(lower=0)
    data["in_out_degree_ratio"] = data["in_degree"] / data["out_degree"].replace(0, np.nan)
    data["degree_imbalance"] = (data["in_degree"] - data["out_degree"]).abs() / data["total_degree"].replace(0, np.nan)
    data["graph_activity_density"] = data["total_degree"] / max(1, int(data["total_degree"].max()))
    data["feature_schema_version"] = "RRRFeatureSchemaV1.1"
    all_features = BASE_FEATURES + ADDED_FEATURES
    for c in all_features: data[c] = pd.to_numeric(data[c], errors="coerce")
    data["sender_ratio"] = data["sender_ratio"].fillna(0); data["receiver_ratio"] = data["receiver_ratio"].fillna(0); data["in_out_degree_ratio"] = data["in_out_degree_ratio"].replace([np.inf,-np.inf],np.nan).fillna(0)
    data["max_to_mean_out_ratio"] = data["max_to_mean_out_ratio"].replace([np.inf,-np.inf],np.nan).fillna(0); data["max_to_mean_in_ratio"] = data["max_to_mean_in_ratio"].replace([np.inf,-np.inf],np.nan).fillna(0)
    data["sent_received_ratio"] = data["sent_received_ratio"].replace([np.inf,-np.inf],np.nan).fillna(0)
    data["net_flow_ratio"] = data["net_flow_ratio"].replace([np.inf,-np.inf],np.nan).fillna(0); data["degree_imbalance"] = data["degree_imbalance"].replace([np.inf,-np.inf],np.nan).fillna(0)
    for c in LOG_FEATURES: data[f"log1p_{c}"] = np.log1p(data[c].clip(lower=0))
    features = all_features + [f"log1p_{c}" for c in LOG_FEATURES]
    data = data[["observation_id","address","time_step","label","feature_schema_version"] + features]
    assert data[features].isna().sum().sum() == 0 and np.isfinite(data[features].to_numpy(dtype=float)).all()
    data.to_parquet(OUT, index=False)
    import json
    schema = {"schema_version":"RRRFeatureSchemaV1.1","base_features":BASE_FEATURES,"added_features":ADDED_FEATURES,"log1p_features":[f"log1p_{c}" for c in LOG_FEATURES],"feature_order":features,"mapping": {"min_in":"btc_received_min → RRR incoming transfer minimum","max_in":"btc_received_max → RRR incoming transfer maximum","median_in":"btc_received_median → RRR incoming transfer median","min_out":"btc_sent_min → RRR outgoing transfer minimum","max_out":"btc_sent_max → RRR outgoing transfer maximum","median_out":"btc_sent_median → RRR outgoing transfer median","total_tx_count":"total_txs → count of persisted transfers","active_period_count":"num_timesteps_appeared_in → number of active observation periods","repeated_address_count":"num_addr_transacted_multiple → repeated counterparty count","mean_activity_gap":"blocks_btwn_txs_mean → mean transaction time gap; runtime uses timestamp gap","graph_features":"AddrAddr_edgelist topology → RRR TraceResult/GraphEdge NetworkX topology","cross_chain_features":"not included: absent from Elliptic++ training data"},"transforms":"log1p applied only to non-negative counts, amounts, degree, lifetime, and counterparty-count features; ratios remain untransformed"}
    (ROOT/"artifacts"/"feature_schema_v1_1.json").write_text(json.dumps(schema,indent=2),encoding="utf-8")
    print(f"Wrote {OUT} rows={len(data):,} features={len(features)}")
if __name__ == "__main__": main()
