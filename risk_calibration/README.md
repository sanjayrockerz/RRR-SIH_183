# Risk Calibration Corpus and Harness

This directory contains the deterministic test corpus and evaluation runner for the **RRR-Realtime RiskEngine**.

## Files
- `scenarios.json`: Ground-truth test scenarios `RISK-001` through `RISK-010`.
- `expected_results.json`: Target score bounds, allowed risk bands, and reproducibility criteria.
- `risk_evaluation.py`: Automated calibration test runner.

## Usage
Run the evaluation harness:
```powershell
$env:PYTHONPATH="apps/api"; .\apps\api\.venv\Scripts\python.exe risk_calibration/risk_evaluation.py
```
