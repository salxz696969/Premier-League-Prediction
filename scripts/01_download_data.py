"""Step 1: download the raw CSV files and build data/processed/matches.csv.

The raw files are already committed in data/raw/, so this works offline.
Use --force to download fresh copies.

Run:  uv run python scripts/01_download_data.py
"""

import sys

from eplpred import data

if __name__ == "__main__":
    data.download_raw(force="--force" in sys.argv)
    matches = data.build_matches()
    print(f"Saved {len(matches):,} matches to data/processed/matches.csv\n")
    print(data.data_summary(matches).T.to_string(header=False))
