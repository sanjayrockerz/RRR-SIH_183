from __future__ import annotations

import math


def top_feature_signals(model, feature_order: list[str], features: dict[str, float], limit: int = 5) -> list[dict]:
    contributions = None
    try:
        import xgboost as xgb
        import numpy as np
        matrix = xgb.DMatrix(np.asarray([[features[name] for name in feature_order]], dtype=float), feature_names=feature_order)
        contributions = model.get_booster().predict(matrix, pred_contribs=True)[0][:-1]
    except Exception:
        contributions = None
    if contributions is None:
        importances = getattr(model, "feature_importances_", [0.0] * len(feature_order))
        contributions = [float(i) * (1.0 if features[name] else 0.0) for name, i in zip(feature_order, importances)]
    ranked = sorted(zip(feature_order, contributions), key=lambda item: abs(float(item[1])), reverse=True)
    result = []
    for name, contribution in ranked[:limit]:
        value = float(features[name]); direction = "elevated" if value > 0 else "zero_or_absent"
        result.append({"feature": name, "direction": direction, "value": value, "contribution": float(contribution), "explanation": "contributing model signal; not causal"})
    return result
