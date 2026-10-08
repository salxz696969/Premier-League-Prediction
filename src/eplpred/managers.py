"""Manager features (needs the Transfermarkt games file, 2012-13 onwards).

Source: dcaribou/transfermarkt-datasets (CC0), file ``games.csv.gz``, which
lists the manager of both teams for every match. Put it at
``data/raw/managers/games.csv.gz`` (``download()`` does this when the host is
reachable). Without the file the project simply runs without these features.

Features, for the home and the away team:
    manager_matches   league matches the manager had been in charge of this club
    new_manager       1 during a manager's first 5 league matches at the club
    manager_ppg       the manager's points per game in earlier league matches
                      (any club, shrunk towards the league average when he has
                      few matches)
"""

from __future__ import annotations

import urllib.request

import numpy as np
import pandas as pd

from . import config

RAW = config.RAW_DIR / "managers" / "games.csv.gz"
URL = "https://pub-e682421888d945d684bcae8890b0ec20.r2.dev/data/games.csv.gz"
NEW_MANAGER_MATCHES = 5
SHRINK_MATCHES = 10
LEAGUE_PPG = 1.37

MANAGER_COLUMNS = [f"{side}_{c}" for side in ("home", "away") for c in ("manager_matches", "new_manager", "manager_ppg")]


def available() -> bool:
    return RAW.exists()


def download() -> None:
    RAW.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(URL, timeout=300) as response:
        RAW.write_bytes(response.read())


def _club_key(name: str) -> str:
    drop = {"football", "club", "fc", "afc", "and", "athletic", "association", "&", "hove", "albion",
            "united", "city", "town", "hotspur", "wanderers", "rovers", "county"}
    return " ".join(w for w in str(name).lower().replace("-", " ").split() if w not in drop)


def load_manager_games(matches: pd.DataFrame) -> pd.DataFrame:
    """Premier League games with both managers, matched to our match_ids."""
    games = pd.read_csv(RAW, low_memory=False)
    games = games[games["competition_id"].eq("GB1")].copy()
    games["date"] = pd.to_datetime(games["date"])
    ours = {_club_key(t): t for t in set(matches["home_team"]) | set(matches["away_team"])}
    ours.update({"wolverhampton": "Wolverhampton", "brighton": "Brighton & Hove Albion",
                 "manchester": None})  # 'manchester' alone is ambiguous
    def our_name(name):
        key = _club_key(name)
        if "manchester" in str(name).lower():
            return "Manchester City" if "city" in str(name).lower() else "Manchester United"
        return ours.get(key)
    games["home_team"] = games["home_club_name"].map(our_name)
    games["away_team"] = games["away_club_name"].map(our_name)
    merged = matches[["match_id", "date", "home_team", "away_team", "home_goals", "away_goals"]].merge(
        games[["date", "home_team", "away_team", "home_club_manager_name", "away_club_manager_name"]],
        on=["date", "home_team", "away_team"], how="inner",
    )
    return merged.rename(columns={"home_club_manager_name": "home_manager", "away_club_manager_name": "away_manager"})


def manager_features(matches: pd.DataFrame) -> pd.DataFrame:
    games = load_manager_games(matches)
    long = pd.concat(
        [
            games.assign(side="home", team=games["home_team"], manager=games["home_manager"],
                         gf=games["home_goals"], ga=games["away_goals"]),
            games.assign(side="away", team=games["away_team"], manager=games["away_manager"],
                         gf=games["away_goals"], ga=games["home_goals"]),
        ]
    )[["match_id", "date", "side", "team", "manager", "gf", "ga"]].sort_values("date")
    long["points"] = np.select([long["gf"] > long["ga"], long["gf"] == long["ga"]], [3.0, 1.0], 0.0)
    long.loc[long["gf"].isna(), "points"] = np.nan

    # Tenure: consecutive matches of this manager at this club, before this match.
    spell = long.groupby("team")["manager"].transform(lambda m: (m != m.shift()).cumsum())
    long["manager_matches"] = long.groupby([long["team"], spell]).cumcount()
    long["new_manager"] = (long["manager_matches"] < NEW_MANAGER_MATCHES).astype(float)

    # Career points per game before this match (shrunk towards the average).
    by_manager = long.groupby("manager")["points"]
    prev_points = by_manager.transform(lambda p: p.shift(1).fillna(0).cumsum())
    prev_games = long.groupby("manager").cumcount()
    long["manager_ppg"] = (prev_points + SHRINK_MATCHES * LEAGUE_PPG) / (prev_games + SHRINK_MATCHES)

    table = long.pivot(index="match_id", columns="side", values=["manager_matches", "new_manager", "manager_ppg"])
    table.columns = [f"{side}_{col}" for col, side in table.columns]
    names = long.pivot(index="match_id", columns="side", values="manager")
    table["home_manager"], table["away_manager"] = names["home"], names["away"]
    return table
