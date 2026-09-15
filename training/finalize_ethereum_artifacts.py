"""Add reproducibility metadata and explicit cross-dataset comparison notes."""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts"
MODELS = ROOT / "models"


def main():
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip() or None
    path = MODELS / "rrr_ethereum_wallet_xgb_v2_metadata.json"
    if path.exists():
        metadata = json.loads(path.read_text(encoding="utf-8")); metadata["git_commit"] = commit; path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    metrics = json.loads((ART / "ethereum_xgb_metrics.json").read_text(encoding="utf-8"))
    v1 = json.loads((ART / "xgb_metrics.json").read_text(encoding="utf-8"))
    comparison = {
        "ELLIPTIC_ONLY": {"test_metrics": v1.get("metrics", {}), "status": "legacy Elliptic wallet-behaviour experiment; BTC/temporal schema differs"},
        "ETHEREUM_ONLY": {"test_metrics": metrics["test"], "status": "selected Ethereum runtime-compatible model"},
        "ELLIPTIC_PLUS_ETHEREUM": {"status": "NOT_RUN", "reason": "The sources do not share a sufficiently faithful common feature table: Elliptic has BTC/temporal/graph observations while the Ethereum file is wallet-level ETH features without raw transfers or graph edges. Combining them would encode source/units or require unverified imputation."},
        "selection": "Ethereum-only selected for RRR because it is the only model evaluated on the current Ethereum-shaped data and it meets the frozen-test minimum criteria.",
        "dataset_source_and_chain_excluded_from_predictors": True,
    }
    (ART / "ethereum_cross_dataset_comparison.json").write_text(json.dumps(comparison, indent=2), encoding="utf-8")
    print(json.dumps({"git_commit": commit, "metadata_updated": path.exists(), "cross_dataset_artifact": str(ART / 'ethereum_cross_dataset_comparison.json')}, indent=2))


if __name__ == "__main__": main()
