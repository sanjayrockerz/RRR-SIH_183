"""Address-safe Ethereum Behaviour Model V2 training and evaluation."""
from __future__ import annotations

import hashlib
import json
import random
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (accuracy_score, average_precision_score, confusion_matrix,
                             f1_score, precision_recall_curve, precision_score,
                             recall_score, roc_auc_score)
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

ROOT = Path(__file__).resolve().parents[1]; ART = ROOT / "artifacts"; MODELS = ROOT / "models"
TABLE = ROOT / "data" / "Datasets" / "processed" / "rrr_ethereum_wallet_features_v2.parquet"
META = {"address", "dataset_source", "original_label", "normalized_label", "feature_schema_version"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""): h.update(b)
    return h.hexdigest()


def evaluate(y, prob, threshold):
    pred = (np.asarray(prob) >= threshold).astype(int); cm = confusion_matrix(y, pred, labels=[0, 1])
    return {"accuracy": float(accuracy_score(y, pred)), "precision": float(precision_score(y, pred, zero_division=0)), "recall": float(recall_score(y, pred, zero_division=0)), "illicit_f1": float(f1_score(y, pred, zero_division=0)), "macro_f1": float(f1_score(y, pred, average="macro", zero_division=0)), "roc_auc": float(roc_auc_score(y, prob)), "pr_auc": float(average_precision_score(y, prob)), "confusion_matrix": cm.tolist()}


def threshold_table(y, prob):
    rows = []
    for t in np.round(np.arange(0.05, 0.951, 0.01), 2):
        p = (prob >= t).astype(int); cm = confusion_matrix(y, p, labels=[0, 1])
        rows.append({"threshold": float(t), "precision": float(precision_score(y, p, zero_division=0)), "recall": float(recall_score(y, p, zero_division=0)), "illicit_f1": float(f1_score(y, p, zero_division=0)), "false_positives": int(cm[0, 1]), "false_negatives": int(cm[1, 0])})
    return pd.DataFrame(rows)


def row_dict(row):
    return {k: (float(v) if isinstance(v, (np.floating, float)) else int(v) if isinstance(v, (np.integer, int)) else v) for k, v in row.to_dict().items()}


def select_points(tab):
    balanced = tab.sort_values(["illicit_f1", "recall", "precision", "threshold"], ascending=[False, False, False, True]).iloc[0]
    hr_pool = tab[tab.precision >= 0.30]
    high_recall = (hr_pool if len(hr_pool) else tab).sort_values(["recall", "precision", "illicit_f1", "threshold"], ascending=[False, False, False, True]).iloc[0]
    hp_pool = tab[(tab.recall >= 0.30) & (tab.precision >= 0.40)]
    high_precision = (hp_pool if len(hp_pool) else tab).sort_values(["precision", "illicit_f1", "recall", "threshold"], ascending=[False, False, False, True]).iloc[0]
    return {"HIGH_RECALL": row_dict(high_recall), "BALANCED_MAX_F1": row_dict(balanced), "HIGH_PRECISION": row_dict(high_precision)}


def psi(a, b):
    a = np.asarray(a, float); b = np.asarray(b, float); edges = np.unique(np.quantile(a, np.linspace(0, 1, 11)))
    if len(edges) < 2: return 0.0
    edges[0] -= 1e-9; edges[-1] += 1e-9
    pa = np.maximum(np.histogram(a, edges)[0] / len(a), 1e-6); pb = np.maximum(np.histogram(b, edges)[0] / len(b), 1e-6)
    return float(np.sum((pb - pa) * np.log(pb / pa)))


def train_model(params, weight, train, val, features):
    model = XGBClassifier(objective="binary:logistic", eval_metric="aucpr", n_estimators=1000, early_stopping_rounds=50, n_jobs=-1, random_state=42, scale_pos_weight=weight, **params)
    model.fit(train[features], train.normalized_label, eval_set=[(val[features], val.normalized_label)], verbose=False)
    prob = model.predict_proba(val[features])[:, 1]
    tab = threshold_table(val.normalized_label.to_numpy(), prob); point = tab.sort_values(["illicit_f1", "recall", "precision"], ascending=False).iloc[0]
    return model, prob, tab, point


def main() -> None:
    data = pd.read_parquet(TABLE).copy(); features = [c for c in data.columns if c not in META]
    if data.address.duplicated().any(): raise ValueError("Wallet table contains duplicate addresses")
    addresses = data.address.to_numpy(); y = data.normalized_label.to_numpy()
    train_addr, hold_addr, y_train, y_hold = train_test_split(addresses, y, test_size=0.30, stratify=y, random_state=42)
    val_addr, test_addr = train_test_split(hold_addr, test_size=0.50, stratify=y[np.isin(addresses, hold_addr)], random_state=43)
    train = data[data.address.isin(train_addr)].copy(); val = data[data.address.isin(val_addr)].copy(); test = data[data.address.isin(test_addr)].copy()
    assert not (set(train.address) & set(val.address) or set(train.address) & set(test.address) or set(val.address) & set(test.address))
    splits = {"train": train, "validation": val, "test": test}
    split_base = {k: sorted(v.address.tolist()) for k, v in splits.items()}
    (ART / "splits").mkdir(parents=True, exist_ok=True)
    for name, vals in split_base.items(): (ART / "splits" / f"ethereum_{'val' if name == 'validation' else name}_addresses.json").write_text(json.dumps({"split": name, "strategy": "stratified address-grouped; one wallet-level row per address", "addresses": vals}, indent=2), encoding="utf-8")
    manifest = {"strategy": "stratified address-grouped 70/15/15; test untouched until final evaluation", "splits": {k: {"rows": len(v), "class_distribution": {"LICIT_LIKE": int((v.normalized_label == 0).sum()), "HIGH_RISK_LIKE": int((v.normalized_label == 1).sum())}} for k, v in splits.items()}}
    (ART / "ethereum_split_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    rf = RandomForestClassifier(n_estimators=500, class_weight="balanced", min_samples_leaf=2, random_state=42, n_jobs=-1).fit(train[features], train.normalized_label)
    rf_val_prob = rf.predict_proba(val[features])[:, 1]; rf_test_prob = rf.predict_proba(test[features])[:, 1]
    rf_metrics = {"validation": evaluate(val.normalized_label, rf_val_prob, 0.5), "test": evaluate(test.normalized_label, rf_test_prob, 0.5)}
    (ART / "ethereum_rf_metrics.json").write_text(json.dumps(rf_metrics, indent=2), encoding="utf-8")

    natural = float((train.normalized_label == 0).sum()) / max(int((train.normalized_label == 1).sum()), 1)
    rng = random.Random(42); grid = [{"max_depth": d, "min_child_weight": mc, "learning_rate": lr, "subsample": ss, "colsample_bytree": cs, "gamma": g} for d in (4, 6, 8) for mc in (1, 5, 10) for lr in (0.03, 0.05, 0.08) for ss in (0.75, 0.85, 1.0) for cs in (0.75, 0.85, 1.0) for g in (0, 0.5, 1)]
    configs = rng.sample(grid, 3); weights = [natural * f for f in (0.5, 0.75, 1.0, 1.25, 1.5)]; trials = []
    # Controlled search: 3 conservative parameter draws x 5 prescribed weights.
    best = None
    for params in configs:
        for weight in weights:
            model, prob, tab, point = train_model(params, weight, train, val, features)
            result = {"scale_pos_weight": weight, "params": params, "best_iteration": int(getattr(model, "best_iteration", 999)), "validation_pr_auc": float(average_precision_score(val.normalized_label, prob)), "validation_illicit_f1_at_best_threshold": float(point.illicit_f1), "validation_illicit_recall_at_best_threshold": float(point.recall)}; trials.append(result)
            key = (result["validation_pr_auc"], result["validation_illicit_f1_at_best_threshold"], result["validation_illicit_recall_at_best_threshold"])
            if best is None or key > best["key"]: best = {"key": key, "model": model, "prob": prob, "tab": tab, "weight": weight, "params": params}
    (ART / "ethereum_xgb_search.json").write_text(json.dumps(trials, indent=2), encoding="utf-8")
    points = select_points(best["tab"]); final_threshold = float(points["BALANCED_MAX_F1"]["threshold"])
    val_metrics = evaluate(val.normalized_label, best["prob"], final_threshold)

    # Ablation is validation-only and uses a fixed conservative XGBoost configuration.
    groups = {"A_transaction_only": [c for c in features if c in {"incoming_tx_count", "outgoing_tx_count", "total_tx_count", "unique_senders", "unique_receivers", "total_value_in", "total_value_out", "mean_value_in", "mean_value_out", "min_value_in", "max_value_in", "min_value_out", "max_value_out"}], "B_transaction_temporal": [], "C_transaction_temporal_contract_erc20": [], "D_full_runtime_compatible": features}
    groups["B_transaction_temporal"] = groups["A_transaction_only"] + [c for c in features if c in {"activity_duration", "sent_interarrival_mean", "received_interarrival_mean", "transactions_per_active_period"}]
    groups["C_transaction_temporal_contract_erc20"] = groups["B_transaction_temporal"] + [c for c in features if c in {"created_contract_count", "contract_interaction_count", "contract_interaction_ratio", "token_transfer_count", "unique_contract_count", "erc20_missing_indicator"}]
    ablation = {}
    fixed = {"max_depth": 6, "min_child_weight": 5, "learning_rate": 0.05, "subsample": 0.85, "colsample_bytree": 0.85, "gamma": 0.5}
    for name, cols in groups.items():
        m, p, t, _ = train_model(fixed, natural, train, val, cols); op = select_points(t)["BALANCED_MAX_F1"]; ablation[name] = {"feature_count": len(cols), "validation": evaluate(val.normalized_label, p, float(op["threshold"])), "selected_threshold": op["threshold"]}
    (ART / "ethereum_feature_ablation.json").write_text(json.dumps(ablation, indent=2), encoding="utf-8")

    # Final test is evaluated once, after threshold/model decisions are frozen.
    test_prob = best["model"].predict_proba(test[features])[:, 1]; test_metrics = evaluate(test.normalized_label, test_prob, final_threshold)
    test_metrics.update({"high_risk_wallets_detected": int(((test.normalized_label == 1) & (test_prob >= final_threshold)).sum()), "high_risk_wallets_missed": int(((test.normalized_label == 1) & (test_prob < final_threshold)).sum()), "licit_wallets_falsely_flagged": int(((test.normalized_label == 0) & (test_prob >= final_threshold)).sum())})
    tab = best["tab"]; tab.to_csv(ART / "ethereum_threshold_analysis.csv", index=False)
    pr, rc, _ = precision_recall_curve(val.normalized_label, best["prob"]); plt.figure(figsize=(7, 5)); plt.plot(rc, pr); plt.xlabel("HIGH_RISK_LIKE recall"); plt.ylabel("HIGH_RISK_LIKE precision"); plt.title("Ethereum validation precision-recall curve"); plt.grid(alpha=.2); plt.tight_layout(); plt.savefig(ART / "ethereum_precision_recall_curve.png", dpi=160); plt.close()

    importance = {k: float(v) for k, v in sorted(zip(features, best["model"].feature_importances_), key=lambda x: x[1], reverse=True)}
    drift = {c: {"train_median": float(train[c].median()), "test_median": float(test[c].median()), "psi": psi(train[c], test[c]), "substantial_shift": psi(train[c], test[c]) > 0.25, "train_min": float(train[c].min()), "train_max": float(train[c].max()), "test_min": float(test[c].min()), "test_max": float(test[c].max())} for c in features}
    (ART / "ethereum_distribution_shift.json").write_text(json.dumps({"threshold": 0.25, "features": drift, "class_prevalence": {k: float(v.normalized_label.mean()) for k, v in splits.items()}}, indent=2), encoding="utf-8")
    val_copy = val[["address", "normalized_label"] + features].copy(); val_copy["probability"] = best["prob"]; val_copy["prediction"] = (best["prob"] >= final_threshold).astype(int)
    error_groups = {"false_negatives": val_copy[(val_copy.normalized_label == 1) & (val_copy.prediction == 0)], "false_positives": val_copy[(val_copy.normalized_label == 0) & (val_copy.prediction == 1)], "true_positives": val_copy[(val_copy.normalized_label == 1) & (val_copy.prediction == 1)], "true_negatives": val_copy[(val_copy.normalized_label == 0) & (val_copy.prediction == 0)]}
    error = {"threshold": final_threshold, "counts": {k: len(v) for k, v in error_groups.items()}, "feature_medians": {k: {c: float(v[c].median()) for c in features} for k, v in error_groups.items()}, "interpretation": "Descriptive behavioural differences only; no labels were used to create new features."}
    (ART / "ethereum_error_analysis.json").write_text(json.dumps(error, indent=2), encoding="utf-8")

    # Independent dataset and role-label checks are explicit and local-only.
    independent = [str(p.relative_to(ROOT)) for p in (ROOT / "data" / "Datasets").rglob("*") if p.suffix.lower() in {".csv", ".parquet"} and "transaction_dataset.csv" not in p.name and "rrr_ethereum_wallet_features_v2.parquet" not in p.name and "ethereum" in p.name.lower()]
    role_terms = ("exchange", "custodial", "vasp", "bridge", "mixer", "service", "role")
    role_files = []
    for p in (ROOT / "data" / "Datasets").rglob("*"):
        if p.suffix.lower() in {".csv", ".parquet"}:
            try:
                cols = [str(c).lower() for c in (pd.read_parquet(p, columns=None).head(1).columns if p.suffix.lower() == ".parquet" else pd.read_csv(p, nrows=1).columns)]
                if any(any(t in c for t in role_terms) for c in cols): role_files.append(str(p.relative_to(ROOT)))
            except Exception: pass
    second_report = {"status": "SECOND_ETHEREUM_DATASET_FOUND" if independent else "SECOND_ETHEREUM_DATASET_MISSING", "independent_candidates": independent, "merged_model_trained": False, "reason": "Derived Parquet excluded as dependent output."}
    (ART / "ethereum_cross_dataset_comparison.json").write_text(json.dumps(second_report, indent=2), encoding="utf-8")
    role_report = {"status": "EXCHANGE_ROLE_MODEL_AVAILABLE" if role_files else "EXCHANGE_ROLE_MODEL_BLOCKED: No authoritative exchange/non-exchange labels available.", "candidate_files": role_files, "fraud_label_not_used_as_role_label": True}
    (ART / "ethereum_role_model_audit.json").write_text(json.dumps(role_report, indent=2), encoding="utf-8")

    report = {"model_name": "RRR Ethereum Wallet Behaviour Model V2", "feature_schema_version": "RRRFeatureSchemaV2", "feature_order": features, "training_dataset": "data/Datasets/transaction_dataset.csv", "raw_dataset_sha256": sha256(ROOT / "data" / "Datasets" / "transaction_dataset.csv"), "processed_table_sha256": sha256(TABLE), "natural_imbalance_ratio": natural, "best_hyperparameters": {**best["params"], "n_estimators": 1000, "early_stopping_rounds": 50, "scale_pos_weight": best["weight"]}, "validation": val_metrics, "test": test_metrics, "operating_points": points, "random_forest": rf_metrics, "top_features": importance, "trained_at": datetime.now(timezone.utc).isoformat(), "acceptance": {"preferred": test_metrics["recall"] >= .70 and test_metrics["precision"] >= .40 and test_metrics["illicit_f1"] >= .50 and test_metrics["pr_auc"] >= .50, "minimum": test_metrics["recall"] >= .60 and test_metrics["precision"] >= .30 and test_metrics["illicit_f1"] >= .40 and test_metrics["pr_auc"] >= .50}}
    (ART / "ethereum_xgb_metrics.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    accepted = report["acceptance"]["minimum"]
    if accepted:
        bundle = {"model": best["model"], "feature_order": features, "threshold": final_threshold, "schema_version": "RRRFeatureSchemaV2", "label_contract": {0: "LICIT_LIKE", 1: "HIGH_RISK_LIKE"}}
        joblib.dump(bundle, MODELS / "rrr_ethereum_wallet_xgb_v2.joblib")
        try: commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        except Exception: commit = None
        metadata = {"model_name": "RRR Ethereum Wallet Behaviour Model V2", "model_version": "rrr_ethereum_wallet_xgb_v2", "feature_schema_version": "RRRFeatureSchemaV2", "feature_order": features, "training_dataset_names": ["Ethereum Fraud Detection Dataset"], "dataset_hashes": {"transaction_dataset.csv": report["raw_dataset_sha256"]}, "label_contract": json.load((ART / "ethereum_label_contract.json").open()), "hyperparameters": report["best_hyperparameters"], "class_weighting": {"method": "scale_pos_weight", "natural_ratio": natural, "selected": best["weight"]}, "threshold": final_threshold, "calibration_method": None, "train_validation_test_counts": {k: len(v) for k, v in splits.items()}, "test_metrics": test_metrics, "training_timestamp": report["trained_at"], "git_commit": commit, "limitations": ["Wallet-level aggregate source; no raw transaction hash/from/to/timestamp/block columns; graph fields excluded; HIGH_RISK_LIKE is behavioural and not criminality; not an exchange-role model."]}
        (MODELS / "rrr_ethereum_wallet_xgb_v2_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        plt.figure(figsize=(9, 7)); names = list(importance)[:20]; plt.barh(names[::-1], [importance[n] for n in names][::-1]); plt.tight_layout(); plt.savefig(ART / "ethereum_feature_importance.png", dpi=160); plt.close()
        cm = np.array(test_metrics["confusion_matrix"]); plt.figure(figsize=(5, 4)); plt.imshow(cm, cmap="Blues"); plt.xticks([0, 1], ["LICIT_LIKE", "HIGH_RISK_LIKE"]); plt.yticks([0, 1], ["LICIT_LIKE", "HIGH_RISK_LIKE"]); plt.xlabel("Predicted"); plt.ylabel("Actual"); [plt.text(j, i, cm[i, j], ha="center", va="center") for i in range(2) for j in range(2)]; plt.tight_layout(); plt.savefig(ART / "ethereum_confusion_matrix.png", dpi=160); plt.close()
        (ART / "ethereum_model_card.md").write_text(f"# RRR Ethereum Wallet Behaviour Model V2\n\nThe model estimates HIGH_RISK_LIKE wallet behaviour, not criminality.\n\n- Validation threshold: {final_threshold:.2f}\n- Test precision: {test_metrics['precision']:.4f}\n- Test recall: {test_metrics['recall']:.4f}\n- Test illicit F1: {test_metrics['illicit_f1']:.4f}\n- Test PR-AUC: {test_metrics['pr_auc']:.4f}\n\nChainabuse, RiskEngine, Case Fusion, and VASP attribution are not model features.\n")
    else:
        (ART / "ethereum_model_card.md").write_text("# RRR Ethereum Wallet Behaviour Model V2\n\nNo model saved: minimum acceptance criteria were not met on the untouched test set.\n", encoding="utf-8")
    print(json.dumps({"accepted": accepted, "features": len(features), "counts": {k: len(v) for k, v in splits.items()}, "rf_test": rf_metrics["test"], "xgb_validation": val_metrics, "xgb_test": test_metrics, "threshold": final_threshold, "top10": list(importance)[:10], "second_dataset": second_report, "role_model": role_report}, indent=2))


if __name__ == "__main__": main()
