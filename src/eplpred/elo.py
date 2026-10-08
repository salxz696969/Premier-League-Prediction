"""Elo ratings - a single number for "how strong is this team right now".

Elo was invented for chess (Elo, 1978) and adapted to football by the
World Football Elo Ratings and ClubElo. The idea:

1. Every team has a rating (average about 1500).
2. Before a match we compute the home team's *expected score*
       E = 1 / (1 + 10 ** (-(R_home + home_advantage - R_away) / 400))
3. After the match the actual score S is 1 (win), 0.5 (draw) or 0 (loss) and
       R_home += K * goal_multiplier * (S - E)
   The away team gets exactly the opposite change, so points are conserved.

Rules specific to this project:
* Big wins move ratings more than narrow wins (``goal_multiplier``).
* Between seasons every rating is pulled 20 % back towards the league mean
  (squads change over the summer).
* Promoted teams start at the average rating of the teams that were relegated
  the season before (they are roughly as strong as the teams they replace).

The key property for us: the rating stored for a match is the rating
*before* that match, so it never contains information from the result.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class EloParams:
    k: float = 10.0
    home_advantage: float = 50.0
    season_regression: float = 0.2
    initial_rating: float = 1500.0


def expected_home_score(home_rating: float, away_rating: float, home_advantage: float) -> float:
    return 1.0 / (1.0 + 10 ** (-(home_rating + home_advantage - away_rating) / 400.0))


def goal_multiplier(goal_diff: int) -> float:
    """Football Elo margin-of-victory multiplier (eloratings.net)."""
    goal_diff = abs(goal_diff)
    if goal_diff <= 1:
        return 1.0
    if goal_diff == 2:
        return 1.5
    return (11.0 + goal_diff) / 8.0


def compute_elo(matches: pd.DataFrame, params: EloParams | None = None) -> tuple[pd.DataFrame, dict[str, float]]:
    """Walk through the matches in date order and record pre-match ratings.

    ``matches`` needs columns: season, date, home_team, away_team, home_goals,
    away_goals. Rows without a score (future fixtures) get a rating but do not
    update anything.

    Returns a DataFrame aligned with ``matches`` (columns ``home_elo``,
    ``away_elo``, ``elo_home_win_expectancy``) and the final ratings.
    """
    params = params or EloParams()
    cols = ["season", "date", "home_team", "away_team", "home_goals", "away_goals"]
    ordered = matches[cols].sort_values(["date", "home_team"])
    ratings: dict[str, float] = {}
    teams_by_season = {
        s: set(g["home_team"]) | set(g["away_team"]) for s, g in ordered.groupby("season")
    }
    seasons = sorted(teams_by_season)

    home_elo = pd.Series(np.nan, index=ordered.index)
    away_elo = pd.Series(np.nan, index=ordered.index)

    current_season = None
    for row in ordered.itertuples():
        if row.season != current_season:
            _start_new_season(ratings, row.season, seasons, teams_by_season, params)
            current_season = row.season

        r_home, r_away = ratings[row.home_team], ratings[row.away_team]
        home_elo[row.Index] = r_home
        away_elo[row.Index] = r_away

        if pd.isna(row.home_goals) or pd.isna(row.away_goals):
            continue  # fixture not played yet
        expected = expected_home_score(r_home, r_away, params.home_advantage)
        actual = 1.0 if row.home_goals > row.away_goals else 0.5 if row.home_goals == row.away_goals else 0.0
        change = params.k * goal_multiplier(int(row.home_goals - row.away_goals)) * (actual - expected)
        ratings[row.home_team] = r_home + change
        ratings[row.away_team] = r_away - change

    out = pd.DataFrame({"home_elo": home_elo, "away_elo": away_elo}).reindex(matches.index)
    out["elo_home_win_expectancy"] = [
        expected_home_score(h, a, params.home_advantage) for h, a in zip(out["home_elo"], out["away_elo"])
    ]
    return out, ratings


def _start_new_season(ratings, season, seasons, teams_by_season, params) -> None:
    """Regress ratings to the mean and give promoted teams a starting rating."""
    teams_now = teams_by_season[season]
    if not ratings:  # very first season in the data: everyone starts equal
        for team in teams_now:
            ratings[team] = params.initial_rating
        return

    previous = seasons[seasons.index(season) - 1]
    teams_before = teams_by_season[previous]
    relegated = teams_before - teams_now
    promoted = teams_now - teams_before

    mean_rating = np.mean([ratings[t] for t in teams_before])
    promoted_rating = np.mean([ratings[t] for t in relegated]) if relegated else params.initial_rating
    for team in teams_before:
        ratings[team] = ratings[team] - params.season_regression * (ratings[team] - mean_rating)
    for team in promoted:
        ratings[team] = promoted_rating
