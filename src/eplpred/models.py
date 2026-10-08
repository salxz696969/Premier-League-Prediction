"""Step 3 - the models we compare.

Every model has the same two methods:

    model.fit(train_df)               # learn from past matches
    model.predict_proba(test_df)      # -> array (n_matches, 3) for H, D, A

so the evaluation code can treat them all the same way. We always predict
*probabilities*, not just a single class: "Arsenal 55 % / draw 25 % /
Chelsea 20 %" is much more useful than "Arsenal win", and it lets us use
proper scoring rules (log loss, RPS) to judge the models.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import poisson
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, PoissonRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from . import config
from .features import feature_columns

OUTCOMES = config.OUTCOMES


def _ordered_proba(classifier, X) -> np.ndarray:
    """Return probabilities with columns in the fixed order H, D, A."""
    proba = classifier.predict_proba(X)
    order = [list(classifier.classes_).index(c) for c in OUTCOMES]
    return proba[:, order]


class BaseModel:
    name = "base"
    description = ""

    def fit(self, train: pd.DataFrame) -> "BaseModel":
        raise NotImplementedError

    def predict_proba(self, test: pd.DataFrame) -> np.ndarray:
        raise NotImplementedError


class HistoricalFrequency(BaseModel):
    """Baseline: always predict how often H/D/A happened in the past.

    Its most likely outcome is always "home win", so its accuracy equals the
    home-win rate. Any useful model has to beat this.
    """

    name = "Baseline: home-win rate"

    def fit(self, train):
        self.freq_ = train["result"].value_counts(normalize=True).reindex(OUTCOMES).to_numpy()
        return self

    def predict_proba(self, test):
        return np.tile(self.freq_, (len(test), 1))


class SklearnClassifier(BaseModel):
    """Wraps any scikit-learn classifier with missing-value handling."""

    def __init__(self, name, estimator, columns=None, scale=False, missing_indicator=False):
        self.name = name
        self.estimator = estimator
        self.columns = columns
        self.scale = scale
        # Adds a 0/1 "was missing" column per feature, for data that only
        # exists in some seasons (players, managers).
        self.missing_indicator = missing_indicator

    def fit(self, train):
        steps = [SimpleImputer(strategy="median", add_indicator=self.missing_indicator)]
        if self.scale:
            steps.append(StandardScaler())
        self.columns_ = self.columns or feature_columns()
        self.pipeline_ = make_pipeline(*steps, self.estimator).fit(train[self.columns_], train["result"])
        return self

    def predict_proba(self, test):
        return _ordered_proba(self.pipeline_, test[self.columns_])


class PoissonGoals(BaseModel):
    """Predict each team's number of goals, then turn goals into H/D/A.

    Goals in football are well described by a Poisson distribution
    (Maher, 1982; Dixon & Coles, 1997). We fit one Poisson regression for
    home goals and one for away goals, then add up the probabilities of all
    scorelines 0-0 ... 10-10:  P(home win) = sum of P(h, a) with h > a, etc.
    A bonus: this model can also give the most likely exact score.
    """

    name = "Poisson goals model"
    max_goals = 10

    def __init__(self, alpha: float = 0.1, columns=None, missing_indicator=False):
        self.alpha = alpha
        self.columns = columns
        self.missing_indicator = missing_indicator

    def _pipeline(self):
        return make_pipeline(
            SimpleImputer(strategy="median", add_indicator=self.missing_indicator),
            StandardScaler(),
            PoissonRegressor(alpha=self.alpha, max_iter=1000),
        )

    def fit(self, train):
        self.columns_ = self.columns or feature_columns()
        self.home_ = self._pipeline().fit(train[self.columns_], train["home_goals"])
        self.away_ = self._pipeline().fit(train[self.columns_], train["away_goals"])
        return self

    def expected_goals(self, test) -> tuple[np.ndarray, np.ndarray]:
        return self.home_.predict(test[self.columns_]), self.away_.predict(test[self.columns_])

    def score_matrix(self, lam_home: float, lam_away: float) -> np.ndarray:
        goals = np.arange(self.max_goals + 1)
        return np.outer(poisson.pmf(goals, lam_home), poisson.pmf(goals, lam_away))

    def predict_proba(self, test):
        rows = []
        for lh, la in zip(*self.expected_goals(test)):
            grid = self.score_matrix(lh, la)
            rows.append([np.tril(grid, -1).sum(), np.trace(grid), np.triu(grid, 1).sum()])
        proba = np.array(rows)
        return proba / proba.sum(axis=1, keepdims=True)


class Ensemble(BaseModel):
    """Average the probabilities of several models ("wisdom of crowds")."""

    def __init__(self, name, members):
        self.name = name
        self.members = members

    def fit(self, train):
        for member in self.members:
            member.fit(train)
        return self

    def predict_proba(self, test):
        return np.mean([m.predict_proba(test) for m in self.members], axis=0)


def make_models(columns: list[str] | None = None) -> list[BaseModel]:
    """All models in the comparison. Settings were chosen on seasons before
    2014-15 only (see ``scripts/tune_models.py``), never on the test seasons.

    ``columns`` swaps in a different feature list (e.g. the extended features);
    by default the 49 base features are used.
    """
    rs = config.RANDOM_STATE
    extra = {"columns": columns, "missing_indicator": columns is not None}

    def lr():
        return SklearnClassifier("Logistic regression", LogisticRegression(C=0.01, max_iter=2000), scale=True, **extra)

    def gb():
        return SklearnClassifier(
            "Gradient boosting",
            HistGradientBoostingClassifier(
                learning_rate=0.03, max_iter=200, max_depth=2, min_samples_leaf=80, l2_regularization=1.0, random_state=rs
            ),
            **extra,
        )

    return [
        HistoricalFrequency(),
        SklearnClassifier("Elo only (logistic regression)", LogisticRegression(max_iter=1000), columns=["elo_diff"]),
        lr(),
        SklearnClassifier(
            "Random forest",
            RandomForestClassifier(
                n_estimators=500, min_samples_leaf=40, max_features="sqrt", n_jobs=-1, random_state=rs
            ),
            **extra,
        ),
        gb(),
        PoissonGoals(alpha=0.1, **extra),
        Ensemble("Ensemble (LR + GB + Poisson)", [lr(), gb(), PoissonGoals(alpha=0.1, **extra)]),
    ]
