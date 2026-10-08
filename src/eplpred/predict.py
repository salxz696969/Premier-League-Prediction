"""Predict a single fixture with the final model.

The final model (by default the Poisson goals model, which had the best RPS
in the walk-forward test) is trained on *all* seasons, then we build the features of a
hypothetical match "home vs away, played the day after the last match in the
data" using exactly the same feature code as in training. So the prediction
uses each team's latest Elo, form, league position etc.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import config
from .features import build_features
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

    def __str__(self) -> str:
        return (
            f"{self.home_team} vs {self.away_team}\n"
            f"  Home win : {self.home_win:6.1%}\n"
            f"  Draw     : {self.draw:6.1%}\n"
            f"  Away win : {self.away_win:6.1%}\n"
            f"  Expected goals: {self.expected_home_goals:.2f} - {self.expected_away_goals:.2f}"
            f" (most likely score {self.most_likely_score})"
        )


def current_teams(matches: pd.DataFrame) -> list[str]:
    last = matches[matches["season"] == matches["season"].max()]
    return sorted(set(last["home_team"]) | set(last["away_team"]))


class Predictor:
    """Train once, then predict as many fixtures as you like."""

    def __init__(self, matches: pd.DataFrame, model_name: str = "Poisson goals model"):
        self.matches = matches
        self.features = build_features(matches)
        train = self.features[self.features["season"] >= config.FIRST_TRAIN_SEASON]
        self.model: BaseModel = next(m for m in make_models() if m.name == model_name).fit(train)
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
        return feats[feats["match_id"] == fixture.loc[0, "match_id"]]

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
        h, a = np.unravel_index(grid.argmax(), grid.shape)
        return Prediction(home_team, away_team, *map(float, proba), float(lam_h), float(lam_a), f"{h}-{a}")
