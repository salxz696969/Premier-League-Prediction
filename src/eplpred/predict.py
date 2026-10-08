"""Predict a single fixture with the final model.

The final model (by default the Poisson goals model, which had the best RPS
in the walk-forward test) is trained on *all* seasons, then we build the features of a
hypothetical match "home vs away, played the day after the last match in the
data" using exactly the same feature code as in training. So the prediction
uses each team's latest Elo, form, league position etc.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import config
from . import players
from .features import build_features, feature_columns
from .models import BaseModel, PoissonGoals, make_models


@dataclass
class Prediction:
    home_team: str
    away_team: str
    home_win: float
    draw: float
    away_win: float
    expected_home_goals: float
    expected_away_goals: float
    most_likely_score: str
    # The five most likely exact scores, e.g. [("1-0", 0.12), ...]
    top_scores: list[tuple[str, float]] = field(default_factory=list)
    # The model inputs for this fixture (Elo, form, position, ...)
    features: dict[str, float] = field(default_factory=dict)

    def __str__(self) -> str:
        return (
            f"{self.home_team} vs {self.away_team}\n"
            f"  Home win : {self.home_win:6.1%}\n"
            f"  Draw     : {self.draw:6.1%}\n"
            f"  Away win : {self.away_win:6.1%}\n"
            f"  Expected goals: {self.expected_home_goals:.2f} - {self.expected_away_goals:.2f}"
            f" (most likely score {self.most_likely_score})"
        )


PLAYER_FEATURES = ["xi_influence", "xi_ict", "xi_value", "key_missing"]


def player_columns() -> list[str]:
    return [f"{s}_{c}" for c in PLAYER_FEATURES for s in ("home", "away")] + ["xi_influence_diff", "xi_value_diff"]


def current_teams(matches: pd.DataFrame) -> list[str]:
    last = matches[matches["season"] == matches["season"].max()]
    return sorted(set(last["home_team"]) | set(last["away_team"]))


class Predictor:
    """Train once, then predict as many fixtures as you like."""

    def __init__(self, matches: pd.DataFrame, model_name: str = "Poisson goals model", use_players: bool = True):
        self.matches = matches
        self.features = build_features(matches)
        self.use_players = use_players
        columns = None
        if use_players:
            # Best extended model in scripts/05_extended_experiment.py: base + player features.
            player_matches = players.load_player_matches(matches)
            self.features = self.features.join(players.team_player_features(matches, player_matches), on="match_id")
            self.features["xi_influence_diff"] = self.features["home_xi_influence"] - self.features["away_xi_influence"]
            self.features["xi_value_diff"] = self.features["home_xi_value"] - self.features["away_xi_value"]
            early = self.features["season"] < players.FIRST_FPL_SEASON
            self.features.loc[early, player_columns()] = np.nan
            self.lineups = players.latest_lineups(player_matches)
            columns = feature_columns() + player_columns()
        train = self.features[self.features["season"] >= config.FIRST_TRAIN_SEASON]
        self.model: BaseModel = next(m for m in make_models(columns) if m.name == model_name).fit(train)
        if use_players:
            self.model.name += " + players"
        # The Poisson model also gives expected goals and the most likely score.
        self.poisson = self.model if isinstance(self.model, PoissonGoals) else PoissonGoals().fit(train)
        self.teams = current_teams(matches)

    def _fixture_features(self, home_team: str, away_team: str) -> pd.DataFrame:
        last = self.matches.iloc[-1]
        fixture = pd.DataFrame(
            [{
                "match_id": self.matches["match_id"].max() + 1,
                "season": last["season"],
                "season_label": last["season_label"],
                "date": self.matches["date"].max() + pd.Timedelta(days=1),
                "home_team": home_team,
                "away_team": away_team,
            }]
        )
        combined = pd.concat([self.matches, fixture], ignore_index=True)
        feats = build_features(combined)
        row = feats[feats["match_id"] == fixture.loc[0, "match_id"]].copy()
        if self.use_players:
            # Line-ups aren't known yet: assume each team starts its last eleven.
            for side, team in (("home", home_team), ("away", away_team)):
                for col in PLAYER_FEATURES:
                    row[f"{side}_{col}"] = self.lineups[team][col]
            row["xi_influence_diff"] = row["home_xi_influence"] - row["away_xi_influence"]
            row["xi_value_diff"] = row["home_xi_value"] - row["away_xi_value"]
        return row

    def predict(self, home_team: str, away_team: str) -> Prediction:
        if home_team == away_team:
            raise ValueError("Pick two different teams")
        for team in (home_team, away_team):
            if team not in self.teams:
                raise ValueError(f"Unknown team {team!r}. Choose from: {', '.join(self.teams)}")
        row = self._fixture_features(home_team, away_team)
        proba = self.model.predict_proba(row)[0]
        lam_h, lam_a = (x[0] for x in self.poisson.expected_goals(row))
        grid = self.poisson.score_matrix(lam_h, lam_a)
        best = np.argsort(grid, axis=None)[::-1][:5]
        top_scores = [(f"{h}-{a}", float(grid[h, a])) for h, a in zip(*np.unravel_index(best, grid.shape))]
        cols = feature_columns() + (player_columns() if self.use_players else [])
        inputs = {c: float(v) for c, v in row[cols].iloc[0].items() if pd.notna(v)}
        return Prediction(
            home_team, away_team, *map(float, proba), float(lam_h), float(lam_a), top_scores[0][0], top_scores, inputs
        )
