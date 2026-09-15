from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, average_precision_score, confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score
from feature_config import FEATURE_COLUMNS

ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT / "data" / "Datasets" / "processed" / "rrr_wallet_features_v1.parquet"
ART = ROOT / "artifacts"; MODELS = ROOT / "models"
ART.mkdir(exist_ok=True); MODELS.mkdir(exist_ok=True)

def load_splits():
    df = pd.read_parquet(TABLE)
    earliest = df.groupby("address", sort=False)["time_step"].min()
    groups = earliest.map(lambda t: "train" if t <= 34 else "validation" if t <= 41 else "test")
    split = df["address"].map(groups)
    return {name: df.loc[split == name].copy() for name in ("train", "validation", "test")}

def metrics(y, pred, proba):
    result = {"accuracy": float(accuracy_score(y, pred)), "precision": float(precision_score(y, pred, zero_division=0)), "recall": float(recall_score(y, pred, zero_division=0)), "f1": float(f1_score(y, pred, zero_division=0)), "macro_f1": float(f1_score(y, pred, average="macro", zero_division=0)), "roc_auc": float(roc_auc_score(y, proba)) if len(np.unique(y)) > 1 else None, "pr_auc": float(average_precision_score(y, proba)) if len(np.unique(y)) > 1 else None, "confusion_matrix": confusion_matrix(y, pred, labels=[0, 1]).tolist(), "class_metrics": {"LICIT": {"precision": float(precision_score(y, pred, pos_label=0, zero_division=0)), "recall": float(recall_score(y, pred, pos_label=0, zero_division=0)), "f1": float(f1_score(y, pred, pos_label=0, zero_division=0))}, "ILLICIT": {"precision": float(precision_score(y, pred, pos_label=1, zero_division=0)), "recall": float(recall_score(y, pred, pos_label=1, zero_division=0)), "f1": float(f1_score(y, pred, pos_label=1, zero_division=0))}}}
    return result

def threshold_search(y, proba):
    rows = []
    for threshold in np.arange(0.20, 0.801, 0.01):
        pred = (proba >= threshold).astype(int)
        rows.append((f1_score(y, pred, pos_label=1, zero_division=0), recall_score(y, pred, pos_label=1, zero_division=0), -abs(precision_score(y, pred, pos_label=1, zero_division=0) - recall_score(y, pred, pos_label=1, zero_division=0)), threshold, precision_score(y, pred, pos_label=1, zero_division=0)))
    # Maximize illicit F1; use recall and then balance as deterministic tie-breakers.
    best = max(rows)
    return {"threshold": float(best[3]), "precision": float(best[4]), "recall": float(best[1]), "f1": float(best[0]), "search_range": [0.20, 0.80], "selection": "maximum illicit F1, then illicit recall"}

def print_metrics(name, result):
    print(f"{name}: accuracy={result['accuracy']:.4f} macro_f1={result['macro_f1']:.4f} illicit_f1={result['class_metrics']['ILLICIT']['f1']:.4f} illicit_recall={result['class_metrics']['ILLICIT']['recall']:.4f} pr_auc={result['pr_auc']:.4f} roc_auc={result['roc_auc']:.4f}")
