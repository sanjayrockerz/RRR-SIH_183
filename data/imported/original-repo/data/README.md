# /data

Download scripts and the fusion overlay generator — the project's defensible, reproducible innovation.

- `download.py` — pulls PaySim, IEEE-CIS, and Elliptic via the Kaggle API into `raw/`; reads a local
  UNSW-NB15 CSV from `raw/` if present.
- `build_overlay.py` (Day 0 deliverable, not yet written) — synthesizes the cyber↔fraud correlation
  overlay: assigns synthetic user/device/IP identities to transactions, injects cyber-compromise
  events preceding a slice of frauds, and emits `processed/transactions.csv` +
  `processed/fused_events.csv`.
- `raw/` — gitignored. Populated by `download.py` and manual UNSW-NB15 drop-in.
- `processed/` — gitignored. Output of the overlay generator; consumed by `/ml` and `/graph`.

See root `CLAUDE.md` for the full data plan and scope rules.
