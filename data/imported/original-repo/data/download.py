"""Download raw datasets for the Unified Cyber-Fraud Intelligence Platform.

Pulls PaySim, IEEE-CIS Fraud, and Elliptic Bitcoin via the Kaggle API into data/raw/.
Also checks for a locally-provided UNSW-NB15 CSV in data/raw/ (not always API-pullable —
see Docs/source/MANUAL_SETUP.md for where to get it).

Assumes the `kaggle` CLI/package is already configured with a token at
~/.kaggle/kaggle.json (or %USERPROFILE%\\.kaggle\\kaggle.json on Windows). This script never
asks for, reads, or hardcodes that token — it only shells out to `kaggle`, which handles its
own auth. If `kaggle` isn't configured, this script prints instructions and exits cleanly
instead of failing with a confusing traceback.

Usage:
    python data/download.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

RAW_DIR = Path(__file__).parent / "raw"

# (kaggle dataset/competition slug, is_competition, unzip subfolder name)
DATASETS = [
    {
        "name": "PaySim",
        "slug": "ealaxi/paysim1",
        "is_competition": False,
    },
    {
        "name": "IEEE-CIS Fraud Detection",
        "slug": "ieee-fraud-detection",
        "is_competition": True,
    },
    {
        "name": "Elliptic Bitcoin Dataset",
        "slug": "ellipticco/elliptic-data-set",
        "is_competition": False,
    },
]

UNSW_NB15_HINT = """
UNSW-NB15 was not found in data/raw/.

This dataset provides the cyber-intrusion patterns (impossible-travel logins,
credential-stuffing, etc.) that the fusion overlay generator injects into the cyber event log.
It is not reliably pullable via the Kaggle API, so grab it manually:

  1. Download from the UNSW ADFA site, or a Kaggle mirror search for "UNSW-NB15".
     (CICIDS2017 is an acceptable substitute if UNSW-NB15 is unavailable.)
  2. Drop the CSV(s) into: {raw_dir}

This script will pick it up automatically next time it runs.
"""

KAGGLE_NOT_CONFIGURED_HINT = """
The `kaggle` CLI is not configured on this machine, so PaySim / IEEE-CIS / Elliptic cannot be
downloaded automatically.

To fix this yourself (Claude Code will not do this step — it never handles your credentials):
  1. Log in to https://www.kaggle.com and go to Account -> Settings -> API -> Create New Token.
     This downloads kaggle.json.
  2. Place it at:
       Windows:      C:\\Users\\<you>\\.kaggle\\kaggle.json
       macOS/Linux:  ~/.kaggle/kaggle.json   (then: chmod 600 ~/.kaggle/kaggle.json)
  3. Visit each dataset's Kaggle page while logged in and click "Accept Rules" (required even
     for non-competition datasets in some cases, and mandatory for the IEEE-CIS competition):
       - https://www.kaggle.com/datasets/ealaxi/paysim1
       - https://www.kaggle.com/c/ieee-fraud-detection
       - https://www.kaggle.com/datasets/ellipticco/elliptic-data-set
  4. Re-run: python data/download.py

Do not paste your Kaggle token into Claude Code or share it with anyone.
"""


def kaggle_available() -> bool:
    return shutil.which("kaggle") is not None


def run_kaggle(args: list[str]) -> bool:
    """Run a kaggle CLI command. Returns True on success, False on failure."""
    result = subprocess.run(["kaggle", *args], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ! kaggle command failed: {' '.join(args)}")
        if result.stderr:
            print(f"    {result.stderr.strip()}")
        return False
    return True


def download_dataset(name: str, slug: str, is_competition: bool) -> None:
    dest = RAW_DIR / slug.split("/")[-1]
    dest.mkdir(parents=True, exist_ok=True)
    print(f"-> Downloading {name} ({slug}) into {dest} ...")

    if is_competition:
        ok = run_kaggle(["competitions", "download", "-c", slug, "-p", str(dest)])
    else:
        ok = run_kaggle(["datasets", "download", "-d", slug, "-p", str(dest), "--unzip"])

    if not ok:
        print(f"  Skipped {name}. If this is a 'rules not accepted' error, visit the dataset's "
              f"Kaggle page while logged in and click Accept Rules, then re-run this script.")
        return

    # `datasets download` unzips via --unzip; `competitions download` needs manual unzip.
    if is_competition:
        for zip_path in dest.glob("*.zip"):
            shutil.unpack_archive(str(zip_path), str(dest))
            zip_path.unlink()

    print(f"  Done: {name}")


def check_unsw_nb15() -> None:
    candidates = list(RAW_DIR.glob("*UNSW*NB15*")) + list(RAW_DIR.glob("*unsw*nb15*"))
    if candidates:
        print(f"-> Found local UNSW-NB15 file(s): {[p.name for p in candidates]}")
    else:
        print(UNSW_NB15_HINT.format(raw_dir=RAW_DIR))


def main() -> int:
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    if not kaggle_available():
        print(KAGGLE_NOT_CONFIGURED_HINT)
        check_unsw_nb15()
        return 1

    for ds in DATASETS:
        download_dataset(ds["name"], ds["slug"], ds["is_competition"])

    check_unsw_nb15()
    print("\nAll done. Raw data lives in data/raw/. Next: data/build_overlay.py (not yet written).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
