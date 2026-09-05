# PHASE 8 TEST EXECUTION & REGRESSION REPORT

## Test Execution Summary
Full test execution was completed across the entire project test suite (`apps/api/tests/`), synthetic end-to-end operational pipeline (`test_final_operational_e2e.py`), risk calibration harness (`risk_evaluation.py`), and performance benchmark suite (`benchmark_phase8.py`).

---

## Test Results Breakdown

### 1. Pytest Suite (`apps/api/tests/`)
- **Total Tests Executed**: `117`
- **Passed**: `114`
- **Skipped**: `3` (Postgres live db contract tests skipped when PostgreSQL environment connection is opt-in)
- **Failed**: `0`
- **Pass Rate**: **100%**

### 2. Synthetic E2E Operational Suite (`test_final_operational_e2e.py`)
- `test_full_synthetic_operational_pipeline`: **PASSED**
- `test_unrelated_cases_no_false_correlation`: **PASSED**

### 3. Risk Engine Calibration Harness (`risk_evaluation.py`)
- `RISK-001` to `RISK-010`: **10 PASSED (100%)**

### 4. Performance Benchmark Suite (`benchmark_phase8.py`)
- Latency & NFR targets: **4 PASSED (100%)**

### 5. Frontend Type Check (`investigator-web`)
- Command: `npx tsc -b`
- Result: **0 Errors (PASS)**

---

## Adversarial & False-Positive Test Results
- **Unrelated Cases Correlation**: Verified that two cases sharing only a public bridge or standard VASP deposit address do NOT create a false criminal correlation.
- **Cross-Chain String Similarity**: Verified that `ETH:0x123...` and `BSC:0x123...` remain isolated chain identities and are never merged based on address string equality alone.
- **CSV Formula Injection**: Verified that fields beginning with `=`, `+`, `-`, `@` are safely prefixed with single quote `'` in CSV exports.
