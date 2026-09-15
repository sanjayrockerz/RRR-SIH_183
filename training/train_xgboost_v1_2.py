"""Compare V1.2 temporal, latest-wallet, and aggregate-history formulations."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import (accuracy_score, average_precision_score, confusion_matrix,
                             f1_score, precision_score, recall_score, roc_auc_score)
from xgboost import XGBClassifier

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "Datasets" / "processed"
ART = ROOT / "artifacts"
MODELS = ROOT / "models"
FEATURES = None


def metric_dict(y, prob, threshold):
    pred = (prob >= threshold).astype(int)
    cm = confusion_matrix(y, pred, labels=[0, 1])
    return {
        "accuracy": float(accuracy_score(y, pred)),
        "roc_auc": float(roc_auc_score(y, prob)),
        "pr_auc": float(average_precision_score(y, prob)),
        "illicit_precision": float(precision_score(y, pred, zero_division=0)),
        "illicit_recall": float(recall_score(y, pred, zero_division=0)),
        "illicit_f1": float(f1_score(y, pred, zero_division=0)),
        "macro_f1": float(f1_score(y, pred, average="macro", zero_division=0)),
        "confusion_matrix": cm.tolist(),
    }


def threshold_table(y, prob):
    rows = []
    for threshold in np.round(np.arange(0.05, 0.801, 0.01), 2):
        pred = (prob >= threshold).astype(int)
        cm = confusion_matrix(y, pred, labels=[0, 1])
        rows.append({"threshold": float(threshold), "precision": float(precision_score(y, pred, zero_division=0)), "recall": float(recall_score(y, pred, zero_division=0)), "f1": float(f1_score(y, pred, zero_division=0)), "false_positives": int(cm[0, 1]), "false_negatives": int(cm[1, 0])})
    return pd.DataFrame(rows)


def operating_points(table):
    max_f1 = table.sort_values(["f1", "recall", "precision"], ascending=False).iloc[0]
    recall_candidates = table[table["recall"] >= 0.70]
    recall_70 = recall_candidates.sort_values(["precision", "f1", "threshold"], ascending=[False, False, True]).iloc[0] if len(recall_candidates) else None
    precision_candidates = table[table["precision"] >= 0.50]
    precision_50 = precision_candidates.sort_values(["recall", "f1", "threshold"], ascending=[False, False, True]).iloc[0] if len(precision_candidates) else None

    def serial(row):
        return None if row is None else {k: (float(v) if isinstance(v, (np.floating, float)) else int(v) if isinstance(v, (np.integer, int)) else v) for k, v in row.to_dict().items()}
    return {"MAX_F1": serial(max_f1), "RECALL_70": serial(recall_70), "PRECISION_50": serial(precision_50)}


def split_wallets(frame):
    # Latest timestep determines the period. Each wallet is present exactly once
    # in latest/aggregate datasets; temporal is retained only as a descriptive baseline.
    if frame["address"].duplicated().any():
        raise ValueError("V1.2 wallet-level formulation contains duplicate addresses")
    period = pd.cut(frame["time_step"], [0, 34, 41, 49], labels=["train", "validation", "test"])
    return {name: frame[period == name].copy() for name in ["train", "validation", "test"]}


def fit(train, val, weight):
    model = XGBClassifier(
        n_estimators=600, max_depth=8, min_child_weight=5, learning_rate=0.05,
        subsample=0.85, colsample_bytree=0.85, gamma=0.5, max_delta_step=1,
        objective="binary:logistic", eval_metric="aucpr", n_jobs=-1,
        random_state=42, scale_pos_weight=weight, early_stopping_rounds=35,
    )
    model.fit(train[FEATURES], train.label, eval_set=[(val[FEATURES], val.label)], verbose=False)
    return model


def psi(train, test, feature):
    a = pd.to_numeric(train[feature], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0).to_numpy()
    b = pd.to_numeric(test[feature], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0).to_numpy()
    edges = np.unique(np.quantile(a, np.linspace(0, 1, 11)))
    if len(edges) < 2:
        return 0.0
    edges[0] -= 1e-9; edges[-1] += 1e-9
    pa = np.histogram(a, edges)[0].astype(float); pb = np.histogram(b, edges)[0].astype(float)
    pa = np.maximum(pa / len(a), 1e-6); pb = np.maximum(pb / len(b), 1e-6)
    return float(np.sum((pb - pa) * np.log(pb / pa)))


def main():
    global FEATURES
    variants = {name: pd.read_parquet(PROCESSED / f"rrr_wallet_features_v1_2_{name.lower()}.parquet") for name in ["TEMPORAL", "LATEST_OBSERVATION", "AGGREGATED_HISTORY"]}
    FEATURES = [c for c in variants["LATEST_OBSERVATION"].columns if c not in {"observation_id", "address", "time_step", "label", "feature_schema_version"}]
    weights_by_variant = {}
    results = {}
    threshold_outputs = {}
    model_bundles = {}
    for name, frame in variants.items():
        if name == "TEMPORAL":
            # Descriptive baseline only; preserve V1 address-grouped manifests rather than
            # allowing repeated observations into a new wallet-level comparison.
            manifest = json.loads((ART / "split_manifests.json").read_text(encoding="utf-8"))
            splits = {k: frame[frame.observation_id.isin(set(v["observation_ids"]))].copy() for k, v in manifest["splits"].items()}
        else:
            splits = split_wallets(frame)
        train, val, test = splits["train"], splits["validation"], splits["test"]
        natural = float((train.label == 0).sum()) / max(int((train.label == 1).sum()), 1)
        candidates = [5.0, 10.0, 15.0, natural]
        weight_rows = []
        best = None
        for weight in candidates:
            model = fit(train, val, weight)
            val_prob = model.predict_proba(val[FEATURES])[:, 1]
            tab = threshold_table(val.label.to_numpy(), val_prob)
            op = operating_points(tab)
            chosen = op["MAX_F1"]
            row = {"variant": name, "scale_pos_weight": weight, "validation_pr_auc": float(average_precision_score(val.label, val_prob)), "validation_illicit_f1": chosen["f1"], "validation_illicit_recall": chosen["recall"]}
            weight_rows.append(row)
            key = (row["validation_pr_auc"], row["validation_illicit_f1"], row["validation_illicit_recall"])
            if best is None or key > best["key"]:
                best = {"key": key, "model": model, "weight": weight, "val_prob": val_prob, "table": tab, "points": op, "params": {"max_depth": 8, "min_child_weight": 5, "learning_rate": 0.05, "subsample": 0.85, "colsample_bytree": 0.85, "gamma": 0.5, "max_delta_step": 1, "n_estimators": 600}}
        weights_by_variant[name] = weight_rows
        # MAX_F1 is the selected operating point; requested alternatives remain visible.
        selected_threshold = float(best["points"]["MAX_F1"]["threshold"])
        results[name] = {
            "rows": {k: len(v) for k, v in splits.items()},
            "class_distribution": {k: {"licit": int((v.label == 0).sum()), "illicit": int((v.label == 1).sum()), "illicit_prevalence": float(v.label.mean())} for k, v in splits.items()},
            "selected_scale_pos_weight": best["weight"], "best_hyperparameters": best["params"],
            "validation": metric_dict(val.label.to_numpy(), best["val_prob"], selected_threshold),
            "test": metric_dict(test.label.to_numpy(), best["model"].predict_proba(test[FEATURES])[:, 1], selected_threshold),
            "operating_points": best["points"],
        }
        threshold_outputs[name] = best["table"]
        model_bundles[name] = {"model": best["model"], "threshold": selected_threshold, "splits": splits, "best": best}

    pd.DataFrame([r for rows in weights_by_variant.values() for r in rows]).to_csv(ART / "v1_2_class_weight_search.csv", index=False)
    for name, table in threshold_outputs.items(): table.to_csv(ART / f"v1_2_{name.lower()}_threshold_analysis.csv", index=False)

    # Distribution shift uses the selected latest/aggregate model's top features.
    best_name = max(["LATEST_OBSERVATION", "AGGREGATED_HISTORY"], key=lambda x: (results[x]["validation"]["pr_auc"], results[x]["validation"]["illicit_f1"], results[x]["validation"]["illicit_recall"]))
    importance = dict(zip(FEATURES, model_bundles[best_name]["model"].feature_importances_))
    top15 = sorted(importance, key=importance.get, reverse=True)[:15]
    shifts = {name: {f: {"train_median": float(model_bundles[name]["splits"]["train"][f].median()), "test_median": float(model_bundles[name]["splits"]["test"][f].median()), "median_shift": float(model_bundles[name]["splits"]["test"][f].median() - model_bundles[name]["splits"]["train"][f].median()), "psi": psi(model_bundles[name]["splits"]["train"], model_bundles[name]["splits"]["test"], f)} for f in top15} for name in variants}
    prevalence = {name: {"train": float(model_bundles[name]["splits"]["train"].label.mean()), "test": float(model_bundles[name]["splits"]["test"].label.mean()), "delta": float(model_bundles[name]["splits"]["test"].label.mean() - model_bundles[name]["splits"]["train"].label.mean())} for name in variants}
    (ART / "v1_2_distribution_shift.json").write_text(json.dumps({"top_15_features": top15, "shift": shifts, "class_prevalence": prevalence}, indent=2), encoding="utf-8")

    # The best wallet formulation is saved only when it materially improves test
    # generalization against V1.1 on the requested priority metrics.
    v11 = json.loads((ART / "v1_vs_v1_1_comparison.json").read_text(encoding="utf-8"))["v1_1"]
    chosen_test = results[best_name]["test"]
    materially_better = chosen_test["pr_auc"] > v11["pr_auc"] and chosen_test["illicit_recall"] > v11["illicit_recall"]
    if materially_better:
        b = model_bundles[best_name]
        metadata = {"model_name": "RRR wallet behaviour XGBoost", "model_version": "rrr_wallet_xgb_v1_2", "formulation": best_name, "feature_order": FEATURES, "decision_threshold": b["threshold"], "scale_pos_weight": b["weight"], "best_hyperparameters": b["best"]["params"], "metrics": chosen_test, "training_timestamp": datetime.now(timezone.utc).isoformat(), "providers_called": [], "split_strategy": "wallet-level latest timestep: 1-34 train, 35-41 validation, 42-49 test"}
        joblib.dump({"model": b["model"], "feature_order": FEATURES, "threshold": b["threshold"], "schema_version": "RRRFeatureSchemaV1.2", "formulation": best_name}, MODELS / "rrr_wallet_xgb_v1_2.joblib")
        (MODELS / "rrr_wallet_xgb_v1_2_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    report = {"best_formulation": best_name, "materially_improves_over_v1_1": materially_better, "variants": results, "distribution_shift_artifact": "artifacts/v1_2_distribution_shift.json", "note": "No prior V1/V1.1 dataset or model was overwritten."}
    (ART / "v1_2_comparison.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"best_formulation": best_name, "materially_improves_over_v1_1": materially_better, "variants": {k: {"validation": v["validation"], "test": v["test"], "operating_points": v["operating_points"]} for k, v in results.items()}}, indent=2))


if __name__ == "__main__": main()
