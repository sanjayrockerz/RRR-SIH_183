from datetime import datetime, timezone
import json
from sklearn.ensemble import RandomForestClassifier
from training_common import ART, FEATURE_COLUMNS, load_splits, metrics, print_metrics

def main():
    parts = load_splits(); train, val, test = parts["train"], parts["validation"], parts["test"]
    model = RandomForestClassifier(n_estimators=300, class_weight="balanced", n_jobs=-1, random_state=42, max_features="sqrt")
    model.fit(train[FEATURE_COLUMNS], train.label)
    proba = model.predict_proba(test[FEATURE_COLUMNS])[:, 1]; result = metrics(test.label, (proba >= 0.5).astype(int), proba)
    payload = {"model_name": "RandomForest baseline", "model_version": "rrr_wallet_rf_baseline_v1", "threshold": 0.5, "training_timestamp": datetime.now(timezone.utc).isoformat(), "rows": {k: len(v) for k, v in parts.items()}, "metrics": result}
    (ART / "baseline_metrics.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print_metrics("Random Forest", result); print(json.dumps(result["confusion_matrix"]))
    return result
if __name__ == "__main__": main()
