"""Step 1: download the raw data and build data/processed/matches.csv.

Downloads (all kept in data/raw/, so later runs work offline):
  football-data/        Premier League results + match statistics, 2000-01 to 2025-26
  odds/                 Bet365 odds (benchmark only)
  other_competitions/   FA Cup, League Cup, Champions League, Europa League, internationals
  players/              Fantasy Premier League player data, 2016-17 to 2025-26
  managers/             Transfermarkt games with managers (only if the host is reachable)

Use --force to download fresh copies.

Run:  uv run python scripts/01_download_data.py
"""

import sys
import urllib.error

from eplpred import data, managers, other_competitions, players

if __name__ == "__main__":
    force = "--force" in sys.argv
    data.download_raw(force=force)
    other_competitions.download(force=force)
    players.download(force=force)
    if not managers.available():
        try:
            managers.download()
        except (urllib.error.URLError, OSError) as error:
            print(f"Manager data not downloaded ({error}). The project runs without manager features;")
            print(f"see src/eplpred/managers.py for how to add {managers.RAW.relative_to(managers.config.ROOT)}.")
    matches = data.build_matches()
    print(f"Saved {len(matches):,} matches to data/processed/matches.csv\n")
    print(data.data_summary(matches).T.to_string(header=False))
    print("\nOther competitions found (matches of Premier League clubs):")
    print(other_competitions.coverage(other_competitions.load_other_matches(matches)).to_string())
