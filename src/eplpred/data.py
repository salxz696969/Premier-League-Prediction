"""Step 1 - download the raw data and turn it into one clean match table.

Output: ``data/processed/matches.csv`` with one row per Premier League match
(2000-01 to 2025-26), full team names, match statistics and, where available,
the bookmaker's pre-match probabilities (used only as a benchmark).
"""

from __future__ import annotations

import io
import urllib.request

import numpy as np
import pandas as pd

from . import config

# Columns we keep from Football-Data.co.uk, renamed to readable names.
# "home_*" = statistic of the home team, "away_*" = of the away team.
FOOTBALL_DATA_COLUMNS = {
    "Date": "date",
    "HomeTeam": "home_team",
    "AwayTeam": "away_team",
    "FTHG": "home_goals",
    "FTAG": "away_goals",
    "FTR": "result",
    "HTHG": "home_ht_goals",
    "HTAG": "away_ht_goals",
    "Referee": "referee",
    "HS": "home_shots",
    "AS": "away_shots",
    "HST": "home_shots_on_target",
    "AST": "away_shots_on_target",
    "HF": "home_fouls",
    "AF": "away_fouls",
    "HC": "home_corners",
    "AC": "away_corners",
    "HY": "home_yellows",
    "AY": "away_yellows",
    "HR": "home_reds",
    "AR": "away_reds",
}


def season_code(start_year: int) -> str:
    """2019 -> '1920' (the file naming used by Football-Data.co.uk)."""
    return f"{start_year % 100:02d}{(start_year + 1) % 100:02d}"


def season_label(start_year: int) -> str:
    """2019 -> '2019-20' (the label we show in tables and plots)."""
    return f"{start_year}-{(start_year + 1) % 100:02d}"


def _download(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=120) as response:
        return response.read()


def download_raw(force: bool = False) -> None:
    """Download every season file plus the odds file into ``data/raw``.

    Files that already exist are skipped, so the raw data committed to the
    repository is used as-is unless ``force=True``.
    """
    fd_dir = config.RAW_DIR / "football-data"
    fd_dir.mkdir(parents=True, exist_ok=True)
    for year in range(config.FIRST_SEASON, config.LAST_SEASON + 1):
        path = fd_dir / f"season-{season_code(year)}.csv"
        if path.exists() and not force:
            continue
        print(f"Downloading {season_label(year)} ...")
        path.write_bytes(_download(config.FOOTBALL_DATA_URL.format(code=season_code(year))))

    odds_path = config.RAW_DIR / "odds" / "epl_odds.csv"
    if not odds_path.exists() or force:
        print("Downloading odds (large file, Premier League rows are kept) ...")
        odds_path.parent.mkdir(parents=True, exist_ok=True)
        all_leagues = pd.read_csv(io.BytesIO(_download(config.ODDS_URL)), low_memory=False)
        epl = all_leagues[all_leagues["Division"].eq("E0")]
        keep = ["MatchDate", "HomeTeam", "AwayTeam", "FTResult", "OddHome", "OddDraw", "OddAway"]
        epl[keep].to_csv(odds_path, index=False)


def standard_team_name(name: str) -> str:
    name = str(name).strip()
    return config.TEAM_ALIASES.get(name, name)


def load_results() -> pd.DataFrame:
    """Read every season file and stack them into one table."""
    frames = []
    for year in range(config.FIRST_SEASON, config.LAST_SEASON + 1):
        path = config.RAW_DIR / "football-data" / f"season-{season_code(year)}.csv"
        season = pd.read_csv(path)
        season = season[list(FOOTBALL_DATA_COLUMNS)].rename(columns=FOOTBALL_DATA_COLUMNS)
        season.insert(0, "season", year)
        frames.append(season)
    return pd.concat(frames, ignore_index=True)


def load_odds() -> pd.DataFrame:
    """Bookmaker odds -> 'fair' probabilities (the bookmaker's margin removed).

    Decimal odds of 2.0 mean an implied probability of 1/2.0 = 50 %. The three
    implied probabilities add up to slightly more than 100 % (that extra is the
    bookmaker's profit margin), so we divide by their sum to normalise them.
    """
    odds = pd.read_csv(config.RAW_DIR / "odds" / "epl_odds.csv")
    odds = odds.rename(columns={"MatchDate": "date", "HomeTeam": "home_team", "AwayTeam": "away_team"})
    odds["date"] = pd.to_datetime(odds["date"])
    for col in ("home_team", "away_team"):
        odds[col] = odds[col].map(standard_team_name)
    implied = 1.0 / odds[["OddHome", "OddDraw", "OddAway"]]
    total = implied.sum(axis=1, skipna=False)
    odds["book_prob_H"] = implied["OddHome"] / total
    odds["book_prob_D"] = implied["OddDraw"] / total
    odds["book_prob_A"] = implied["OddAway"] / total
    odds["book_margin"] = total - 1.0
    return odds[["date", "home_team", "away_team", "book_prob_H", "book_prob_D", "book_prob_A", "book_margin"]]


def build_matches() -> pd.DataFrame:
    """Clean, check and merge the raw files into ``data/processed/matches.csv``."""
    matches = load_results()
    matches = matches.dropna(subset=["home_team", "away_team", "result"])
    matches["date"] = pd.to_datetime(matches["date"])
    for col in ("home_team", "away_team"):
        matches[col] = matches[col].map(standard_team_name)

    int_cols = [c for c in matches.columns if c.startswith(("home_", "away_")) and c not in ("home_team", "away_team")]
    matches[int_cols] = matches[int_cols].apply(pd.to_numeric, errors="coerce")

    # Sanity checks: a broken download should fail loudly, not silently.
    per_season = matches.groupby("season").size()
    assert (per_season == 380).all(), f"Expected 380 matches per season:\n{per_season[per_season != 380]}"
    assert not matches.duplicated(["date", "home_team", "away_team"]).any(), "Duplicate matches"
    expected = np.select(
        [matches["home_goals"] > matches["away_goals"], matches["home_goals"] < matches["away_goals"]],
        ["H", "A"],
        "D",
    )
    assert (expected == matches["result"]).all(), "Result does not match the score"

    matches = matches.merge(load_odds(), on=["date", "home_team", "away_team"], how="left")
    matches = matches.sort_values(["date", "home_team"]).reset_index(drop=True)
    matches.insert(0, "match_id", np.arange(len(matches)))
    matches.insert(2, "season_label", matches["season"].map(season_label))

    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    matches.to_csv(config.MATCHES_CSV, index=False)
    return matches


def load_matches() -> pd.DataFrame:
    return pd.read_csv(config.MATCHES_CSV, parse_dates=["date"])


def data_summary(matches: pd.DataFrame) -> pd.DataFrame:
    """Small table used in the README / notebook to describe the dataset."""
    return pd.DataFrame(
        {
            "matches": [len(matches)],
            "seasons": [matches["season"].nunique()],
            "teams": [pd.concat([matches["home_team"], matches["away_team"]]).nunique()],
            "first_match": [matches["date"].min().date()],
            "last_match": [matches["date"].max().date()],
            "home_win_%": [round(100 * matches["result"].eq("H").mean(), 1)],
            "draw_%": [round(100 * matches["result"].eq("D").mean(), 1)],
            "away_win_%": [round(100 * matches["result"].eq("A").mean(), 1)],
            "with_odds_%": [round(100 * matches["book_prob_H"].notna().mean(), 1)],
        }
    )
