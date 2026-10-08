"""Step 4 - honest evaluation with a walk-forward (season-by-season) test.

For every test season S (2014-15 ... 2025-26):
    train on all seasons before S  ->  predict every match of season S.

This mimics real life: at the start of a season you only know the past.
Randomly shuffled train/test splits would let the model learn from matches
played *after* the ones it predicts, which inflates the scores.

Metrics (lower is better, except accuracy)
------------------------------------------
* Accuracy  - % of matches where the most likely outcome happened.
* Log loss  - punishes confident wrong predictions heavily.
* Brier     - mean squared error of the three probabilities.
* RPS       - Ranked Probability Score, the standard football metric
              (Constantinou & Fenton, 2012). It knows that predicting a draw
              when the home team wins is "less wrong" than predicting an away
              win, because H > D > A is an ordered scale.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config
from .models import BaseModel

OUTCOMES = config.OUTCOMES
BOOKMAKER = "Bookmaker (Bet365, benchmark)"


def one_hot(results: pd.Series) -> np.ndarray:
    return np.column_stack([results.eq(o).to_numpy(float) for o in OUTCOMES])


def ranked_probability_score(proba: np.ndarray, results: pd.Series) -> float:
    observed = one_hot(results)
    cum_diff = np.cumsum(proba, axis=1)[:, :-1] - np.cumsum(observed, axis=1)[:, :-1]
    return float(np.mean(np.sum(cum_diff**2, axis=1) / (len(OUTCOMES) - 1)))


def score(proba: np.ndarray, results: pd.Series) -> dict[str, float]:
    predicted = np.array(OUTCOMES)[proba.argmax(axis=1)]
    observed = one_hot(results)
    return {
        "accuracy": float(np.mean(predicted == results.to_numpy())),
        "log_loss": float(-np.mean(np.log(np.clip((proba * observed).sum(axis=1), 1e-15, 1)))),
        "brier": float(np.mean(np.sum((proba - observed) ** 2, axis=1))),
        "rps": ranked_probability_score(proba, results),
        "predicted_draw_%": float(100 * np.mean(predicted == "D")),
    }


def walk_forward(features: pd.DataFrame, models: list[BaseModel], verbose: bool = True) -> pd.DataFrame:
    """Return one row per (test match, model) with the predicted probabilities."""
    data = features[features["season"] >= config.FIRST_TRAIN_SEASON]
    test_seasons = range(config.FIRST_TEST_SEASON, int(data["season"].max()) + 1)
    keep = ["match_id", "season", "season_label", "date", "home_team", "away_team", "home_goals", "away_goals", "result"]

    rows = []
    for season in test_seasons:
        train = data[data["season"] < season]
        test = data[data["season"] == season]
        for model in models:
            proba = model.fit(train).predict_proba(test)
            rows.append(_prediction_frame(test[keep], model.name, proba))
        book = test[["book_prob_H", "book_prob_D", "book_prob_A"]].to_numpy()
        rows.append(_prediction_frame(test[keep], BOOKMAKER, book))
        if verbose:
            print(f"  {config_label(season)}: trained on {len(train):,} matches, predicted {len(test)}")
    return pd.concat(rows, ignore_index=True)


def config_label(season: int) -> str:
    return f"{season}-{(season + 1) % 100:02d}"


def _prediction_frame(test: pd.DataFrame, model_name: str, proba: np.ndarray) -> pd.DataFrame:
    out = test.copy()
    out.insert(0, "model", model_name)
    for i, outcome in enumerate(OUTCOMES):
        out[f"prob_{outcome}"] = proba[:, i]
    out["predicted"] = np.array(OUTCOMES)[proba.argmax(axis=1)]
    return out


def summarise(predictions: pd.DataFrame, by: list[str] | None = None) -> pd.DataFrame:
    """Metrics per model (and optionally per season)."""
    group_cols = ["model"] + (by or [])
    rows = []
    for keys, group in predictions.groupby(group_cols, sort=False):
        keys = keys if isinstance(keys, tuple) else (keys,)
        proba = group[[f"prob_{o}" for o in OUTCOMES]].to_numpy()
        rows.append({**dict(zip(group_cols, keys)), "matches": len(group), **score(proba, group["result"])})
    table = pd.DataFrame(rows)
    if not by:
        table = table.sort_values("rps").reset_index(drop=True)
    return table
