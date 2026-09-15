from datetime import datetime, timezone
import json
import joblib
import matplotlib.pyplot as plt
import numpy as np
from xgboost import XGBClassifier
from training_common import ART, MODELS, FEATURE_COLUMNS, load_splits, metrics, print_metrics, threshold_search

def main():
    parts = load_splits(); train, val, test = parts["train"], parts["validation"], parts["test"]
    illicit = int((train.label == 1).sum()); licit = int((train.label == 0).sum()); weight = licit / max(illicit, 1)
    model = XGBClassifier(n_estimators=600, max_depth=6, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8, objective="binary:logistic", eval_metric="aucpr", n_jobs=-1, random_state=42, scale_pos_weight=weight, early_stopping_rounds=40)
    model.fit(train[FEATURE_COLUMNS], train.label, eval_set=[(val[FEATURE_COLUMNS], val.label)], verbose=False)
    val_proba = model.predict_proba(val[FEATURE_COLUMNS])[:, 1]; selected = threshold_search(val.label.to_numpy(), val_proba); threshold = selected["threshold"]
    test_proba = model.predict_proba(test[FEATURE_COLUMNS])[:, 1]; result = metrics(test.label, (test_proba >= threshold).astype(int), test_proba); result["threshold"] = selected
    importance = {name: float(value) for name, value in sorted(zip(FEATURE_COLUMNS, model.feature_importances_), key=lambda x: x[1], reverse=True)}
    metadata = {"model_name": "RRR wallet behaviour XGBoost", "model_version": "rrr_wallet_xgb_v1", "feature_schema_version": "RRRFeatureSchemaV1", "feature_order": FEATURE_COLUMNS, "decision_threshold": threshold, "training_rows": len(train), "train_time_range": [1, 34], "validation_time_range": [35, 41], "test_time_range": [42, 49], "split_strategy": "address grouped by earliest observation time step", "scale_pos_weight": weight, "metrics": result, "validation_threshold_selection": selected, "feature_importance": importance, "training_timestamp": datetime.now(timezone.utc).isoformat()}
    joblib.dump({"model": model, "feature_order": FEATURE_COLUMNS, "threshold": threshold, "schema_version": "RRRFeatureSchemaV1"}, MODELS / "rrr_wallet_xgb_v1.joblib")
    (MODELS / "rrr_wallet_xgb_v1_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    (ART / "xgb_metrics.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    plt.figure(figsize=(11, 7)); names = list(importance)[::-1]; vals = [importance[x] for x in names]; plt.barh(names, vals); plt.title("RRRFeatureSchemaV1 XGBoost feature importance (not causal)"); plt.tight_layout(); plt.savefig(ART / "feature_importance.png", dpi=160); plt.close()
    cm = np.array(result["confusion_matrix"]); plt.figure(figsize=(5, 4)); plt.imshow(cm, cmap="Blues"); plt.title("XGBoost confusion matrix"); plt.xticks([0, 1], ["LICIT", "ILLICIT"]); plt.yticks([0, 1], ["LICIT", "ILLICIT"]); [plt.text(j, i, cm[i, j], ha="center", va="center") for i in range(2) for j in range(2)]; plt.xlabel("Predicted"); plt.ylabel("Actual"); plt.tight_layout(); plt.savefig(ART / "confusion_matrix.png", dpi=160); plt.close()
    (ART / "model_card.md").write_text(f"# RRR Wallet Behaviour Model V1\n\nThis model outputs **HIGH-RISK BEHAVIOUR PROBABILITY**, not criminality, guilt, or scammer status.\n\n- Schema: RRRFeatureSchemaV1\n- Decision threshold: {threshold:.2f}\n- Training split: time steps 1–34\n- Validation split: time steps 35–41\n- Test split: time steps 42–49\n- Graph labels were not used as features.\n- Feature importance is not causal interpretation.\n", encoding="utf-8")
    baseline_path = ART / "baseline_metrics.json"
    if baseline_path.exists():
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))["metrics"]
        comparison = {"RandomForest": {k: baseline[k] for k in ["accuracy", "macro_f1", "roc_auc", "pr_auc"]} | {"illicit_f1": baseline["class_metrics"]["ILLICIT"]["f1"], "illicit_recall": baseline["class_metrics"]["ILLICIT"]["recall"]}, "XGBoost": {k: result[k] for k in ["accuracy", "macro_f1", "roc_auc", "pr_auc"]} | {"illicit_f1": result["class_metrics"]["ILLICIT"]["f1"], "illicit_recall": result["class_metrics"]["ILLICIT"]["recall"]}}
        (ART / "model_comparison.json").write_text(json.dumps(comparison, indent=2), encoding="utf-8")
        print("Random Forest vs XGBoost:", json.dumps(comparison))
    print_metrics("XGBoost", result); print(f"Selected threshold: {threshold:.2f}"); print(json.dumps(result["confusion_matrix"])); return metadata
if __name__ == "__main__": main()
