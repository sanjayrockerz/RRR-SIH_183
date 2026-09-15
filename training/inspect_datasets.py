"""Streaming first-pass audit for local wallet datasets. No model training."""
from __future__ import annotations
import csv, json, math, sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "Datasets"
OUT = ROOT / "artifacts" / "dataset_report.json"
TMP = ROOT / "tmp" / "dataset_audit.sqlite3"
TMP.parent.mkdir(exist_ok=True)
OUT.parent.mkdir(exist_ok=True)

def infer(value: str):
    if value == "": return "missing"
    try: float(value); return "numeric"
    except ValueError: return "string"

def inspect_file(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        rows = 0; missing = Counter(); samples = {name: [] for name in header}
        types = {name: Counter() for name in header}
        for row in reader:
            rows += 1
            if len(row) != len(header):
                missing["__malformed_rows__"] += 1
                row = (row + [""] * len(header))[:len(header)]
            for name, value in zip(header, row):
                if value == "": missing[name] += 1
                elif len(samples[name]) < 5000: samples[name].append(value)
                types[name][infer(value)] += 1
        dtypes = {}
        for name in header:
            kinds = types[name]
            dtypes[name] = "float64" if kinds["numeric"] and not kinds["string"] else "object"
        return {"path": str(path.relative_to(ROOT)), "format": path.suffix.lower().lstrip("."), "rows": rows, "columns": header, "dtypes_inferred": dtypes, "missing_values": dict(missing), "malformed_rows": missing.get("__malformed_rows__", 0)}

def sqlite_setup():
    if TMP.exists(): TMP.unlink()
    conn = sqlite3.connect(TMP)
    conn.execute("CREATE TABLE classes(address TEXT PRIMARY KEY, class TEXT)")
    conn.execute("CREATE TABLE feature_ids(address TEXT, timestep TEXT)")
    conn.execute("CREATE INDEX feature_address ON feature_ids(address)")
    return conn

def audit_semantics(conn):
    classes = DATA / "wallets_classes.csv"
    features = DATA / "wallets_features.csv"
    edges = DATA / "AddrAddr_edgelist.csv"
    class_counts = Counter(); class_rows = 0; class_duplicates = 0
    with classes.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            class_rows += 1; address = row.get("address", ""); label = row.get("class", "")
            try: conn.execute("INSERT INTO classes VALUES (?,?)", (address, label)); class_counts[label] += 1
            except sqlite3.IntegrityError: class_duplicates += 1
    conn.commit()
    feature_rows = 0; feature_duplicates = 0; timesteps = Counter(); feature_addresses = set()
    with features.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            feature_rows += 1; address = row.get("address", ""); timestep = row.get("Time step", "")
            key = (address, timestep)
            conn.execute("INSERT INTO feature_ids VALUES (?,?)", key)
            feature_addresses.add(address); timesteps[timestep] += 1
    conn.commit()
    # Duplicate feature IDs are address+timestep rows; duplicate wallet IDs are address rows.
    dup_feature_rows = conn.execute("SELECT COUNT(*) - COUNT(DISTINCT address || char(0) || timestep) FROM feature_ids").fetchone()[0]
    edge_rows = 0; self_loops = 0; invalid_edges = 0; nodes = set(); indegree = Counter(); outdegree = Counter()
    with edges.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            source = row.get("input_address", ""); target = row.get("output_address", "")
            edge_rows += 1
            if not source or not target: invalid_edges += 1; continue
            nodes.update((source, target)); outdegree[source] += 1; indegree[target] += 1
            if source == target: self_loops += 1
    label_overlap = conn.execute("SELECT COUNT(DISTINCT f.address) FROM feature_ids f JOIN classes c ON c.address=f.address").fetchone()[0]
    return {"classes": {"rows": class_rows, "duplicate_wallet_ids": class_duplicates, "label_distribution_raw": dict(class_counts), "known_supervised_mapping": {"1": "ILLICIT", "2": "LICIT"}, "unknown_or_other_classes": sorted(k for k in class_counts if k not in {"1", "2"})}, "features": {"rows": feature_rows, "unique_wallet_ids": len(feature_addresses), "duplicate_address_timestep_rows": dup_feature_rows, "time_step_distribution": dict(timesteps), "min_time_step": min((int(x) for x in timesteps if x.isdigit()), default=None), "max_time_step": max((int(x) for x in timesteps if x.isdigit()), default=None)}, "edges": {"rows": edge_rows, "unique_nodes": len(nodes), "self_loops": self_loops, "invalid_rows": invalid_edges, "unique_sources": len(outdegree), "unique_targets": len(indegree), "max_in_degree": max(indegree.values(), default=0), "max_out_degree": max(outdegree.values(), default=0), "schema": {"source": "input_address", "target": "output_address", "amount": None, "asset": None, "timestamp": None, "timestep": None}}, "joins": {"feature_wallet_ids_with_class": label_overlap, "feature_wallet_ids_without_class": len(feature_addresses) - label_overlap, "class_wallet_ids_without_features": class_rows - label_overlap}}

def main():
    files = sorted(p for p in DATA.rglob("*") if p.is_file() and p.suffix.lower() in {".csv", ".parquet"})
    import importlib.util
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "dataset_root": str(DATA), "files": [], "semantic_audit": {}, "rrr_feature_compatibility": {"schema_version": "RRRFeatureSchemaV1", "proposed_features": {}, "incompatible_or_unavailable": []}, "dependencies": {"pandas": bool(importlib.util.find_spec("pandas")), "pyarrow": bool(importlib.util.find_spec("pyarrow")), "xgboost": bool(importlib.util.find_spec("xgboost")), "scikit_learn": bool(importlib.util.find_spec("sklearn")), "joblib": bool(importlib.util.find_spec("joblib")), "matplotlib": bool(importlib.util.find_spec("matplotlib"))}}
    for path in files:
        report["files"].append(inspect_file(path))
    conn = sqlite_setup()
    report["semantic_audit"] = audit_semantics(conn)
    conn.close()
    schema = report["rrr_feature_compatibility"]["proposed_features"]
    tx = ["incoming_tx_count", "outgoing_tx_count", "unique_senders", "unique_receivers", "total_in", "total_out", "mean_in", "mean_out", "out_in_ratio"]
    temporal = ["activity_duration", "burstiness"]
    graph = ["in_degree", "out_degree", "total_degree", "fan_in_score", "fan_out_score", "repeated_counterparty_ratio"]
    case = []
    cross = []
    for group, names in [("transaction", tx), ("temporal", temporal), ("graph", graph), ("case_path", case), ("cross_chain", cross)]:
        schema[group] = {name: {"training": "derivable", "runtime": "derivable_from_persisted_RRR_trace", "leakage_safe": True} for name in names}
    report["rrr_feature_compatibility"]["incompatible_or_unavailable"] = ["asset_diversity: Elliptic++ is BTC-only; not discriminative for training/runtime parity", "mean_interarrival/median_interarrival: dataset has block/timestep summaries, not transaction timestamps", "rapid_forward_ratio: not directly derivable from the static edge list", "hop_distance_from_source/path_depth/amount_retention: case/path context is absent from the wallet labels and edge list has no amounts", "bridge_interaction_count/chain_switch_count: absent from Ellipt++", "clustering_coefficient/local_pagerank: computationally possible but deferred from V1 pending scale/definition validation", "class 3 is UNKNOWN and must be excluded from supervised training", "neighbor ground-truth labels are excluded to prevent leakage", "Chainabuse NO_MATCH must not be used as a supervised label"]
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Dataset audit written: {OUT}")
    for item in report["files"]: print(f"- {item['path']}: {item['rows']:,} rows, {len(item['columns'])} columns")
    s = report["semantic_audit"]
    print(f"- labels (raw): {s['classes']['label_distribution_raw']}; supervised mapping: 1=ILLICIT, 2=LICIT; UNKNOWN/other excluded")
    print(f"- feature wallet×timestep rows: {s['features']['rows']:,}; edge rows: {s['edges']['rows']:,}; graph nodes: {s['edges']['unique_nodes']:,}")
    print(f"- feature/class overlap: {s['joins']['feature_wallet_ids_with_class']:,}; duplicate feature keys: {s['features']['duplicate_address_timestep_rows']:,}")

if __name__ == "__main__": main()
