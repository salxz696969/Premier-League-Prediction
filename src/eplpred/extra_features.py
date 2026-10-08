"""Extra features from other data sources, added on top of ``features.py``.

* Schedule / fatigue (all seasons): every competition, not just the league
    rest_days_all     days since the team's previous match in ANY competition
    matches_14d       matches played in the previous 14 days
    europe_before     played a Champions/Europa League match in the 4 days before
    europe_after      has a Champions/Europa League match in the 4 days after
                      (fixtures are known in advance; teams often rotate)
    after_intl_break  first league match after an international break
* Players (2016-17 onwards): see ``players.py``
* Managers (when the manager data is available): see ``managers.py``

Missing data (e.g. Europa League before 2020-21, players before 2016-17) is
left as NaN; the models handle it (see ``models.py``).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config, other_competitions, players
from .features import build_features, feature_columns

EUROPE_DAYS = 4
CONGESTION_DAYS = 14

SCHEDULE_COLUMNS = ["rest_days_all", "matches_14d", "europe_before", "europe_after", "after_intl_break"]
PLAYER_COLUMNS = ["xi_influence", "xi_ict", "xi_value", "key_missing"]


def schedule_features(matches: pd.DataFrame, other: pd.DataFrame, intl_days: pd.DatetimeIndex) -> pd.DataFrame:
    """Fatigue and congestion features for both teams of every match."""
    league = pd.concat(
        [
            matches[["match_id", "season", "date", "home_team"]].rename(columns={"home_team": "team"}).assign(side="home"),
            matches[["match_id", "season", "date", "away_team"]].rename(columns={"away_team": "team"}).assign(side="away"),
        ]
    )
    intl = np.sort(intl_days.values)
    rows = []
    for team, games in league.groupby("team"):
        games = games.sort_values("date")
        cups = other[other["team"] == team]
        all_dates = np.sort(np.concatenate([games["date"].values, cups["date"].values]))
        euro = np.sort(cups.loc[cups["competition"].isin(other_competitions.EUROPEAN), "date"].values)
        prev_league = games["date"].shift(1).values
        prev_season = games["season"].shift(1).values
        for (mid, season, date, side), prev, prev_s in zip(
            games[["match_id", "season", "date", "side"]].itertuples(index=False), prev_league, prev_season
        ):
            d = np.datetime64(date)
            before = all_dates[all_dates < d]
            rest = (d - before[-1]).astype("timedelta64[D]").astype(int) if len(before) else np.nan
            window = d - np.timedelta64(CONGESTION_DAYS, "D")
            same_season = prev_s == season
            if same_season and not pd.isna(prev):
                lo, hi = np.searchsorted(intl, [np.datetime64(prev), d], side="right")
                after_break = float(hi > lo)
            else:
                after_break = 0.0
            rows.append({
                "match_id": mid,
                "side": side,
                "rest_days_all": min(rest, 21) if same_season else 21,
                "matches_14d": float(((all_dates >= window) & (all_dates < d)).sum()),
                "europe_before": float(((euro >= d - np.timedelta64(EUROPE_DAYS, "D")) & (euro < d)).any()),
                "europe_after": float(((euro > d) & (euro <= d + np.timedelta64(EUROPE_DAYS, "D"))).any()),
                "after_intl_break": after_break,
            })
    table = pd.DataFrame(rows).pivot(index="match_id", columns="side")
    table.columns = [f"{side}_{col}" for col, side in table.columns]
    return table


def build_extended_features(matches: pd.DataFrame, base: pd.DataFrame | None = None) -> pd.DataFrame:
    """Base features + schedule + player (+ manager) features."""
    feats = base if base is not None else build_features(matches)
    other = other_competitions.load_other_matches(matches)
    sched = schedule_features(matches, other, other_competitions.international_dates())
    feats = feats.join(sched, on="match_id")

    player = players.team_player_features(matches)
    feats = feats.join(player, on="match_id")
    first_fpl = feats["season"] < players.FIRST_FPL_SEASON
    for side in ("home", "away"):
        cols = [f"{side}_{c}" for c in PLAYER_COLUMNS]
        feats.loc[first_fpl, cols] = np.nan

    from . import managers  # optional data source

    if managers.available():
        feats = feats.join(managers.manager_features(matches), on="match_id")

    feats["rest_all_diff"] = feats["home_rest_days_all"] - feats["away_rest_days_all"]
    feats["xi_influence_diff"] = feats["home_xi_influence"] - feats["away_xi_influence"]
    feats["xi_value_diff"] = feats["home_xi_value"] - feats["away_xi_value"]
    return feats


def extended_feature_columns(feats: pd.DataFrame | None = None) -> list[str]:
    cols = feature_columns()
    for c in SCHEDULE_COLUMNS + PLAYER_COLUMNS:
        cols += [f"home_{c}", f"away_{c}"]
    cols += ["rest_all_diff", "xi_influence_diff", "xi_value_diff"]
    from . import managers

    if managers.available():
        cols += managers.MANAGER_COLUMNS
    if feats is not None:
        cols = [c for c in cols if c in feats.columns]
    return cols


def save_extended_features(matches: pd.DataFrame) -> pd.DataFrame:
    feats = build_extended_features(matches)
    feats.to_csv(config.PROCESSED_DIR / "features_extended.csv", index=False)
    return feats


def load_extended_features() -> pd.DataFrame:
    path = config.PROCESSED_DIR / "features_extended.csv"
    if not path.exists():
        from .data import load_matches

        return save_extended_features(load_matches())
    return pd.read_csv(path, parse_dates=["date"])
