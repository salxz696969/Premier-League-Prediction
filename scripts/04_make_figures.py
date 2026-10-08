"""Step 4: draw every chart in reports/figures/ and compute feature importance.

Run:  uv run python scripts/04_make_figures.py
"""

import numpy as np
import pandas as pd

from eplpred import config, data, evaluation, features, plots
from eplpred.evaluation import BOOKMAKER
from eplpred.models import make_models

ORIGINAL_PROJECT_ACCURACY = 0.4748  # v1 random forest, final test (docs/architecture.md of v1)
BIG_SIX = ["Manchester City", "Liverpool", "Arsenal", "Chelsea", "Manchester United", "Tottenham Hotspur"]


def best_model_name(overall: pd.DataFrame) -> str:
    candidates = overall[~overall["model"].isin([BOOKMAKER, plots.BASELINE])]
    return candidates.sort_values("rps").iloc[0]["model"]


def permutation_importance(feats: pd.DataFrame, model_name: str, repeats: int = 5) -> pd.DataFrame:
    """Shuffle one feature at a time and measure how much worse RPS gets.

    Trained on 2001-02 ... 2021-22, measured on 2022-23 ... 2025-26.
    """
    model = next(m for m in make_models() if m.name == model_name)
    train = feats[feats["season"].between(config.FIRST_TRAIN_SEASON, 2021)]
    test = feats[feats["season"] >= 2022].reset_index(drop=True)
    model.fit(train)
    base = evaluation.ranked_probability_score(model.predict_proba(test), test["result"])
    rng = np.random.default_rng(config.RANDOM_STATE)
    rows = []
    for col in features.feature_columns():
        scores = []
        for _ in range(repeats):
            shuffled = test.copy()
            shuffled[col] = rng.permutation(shuffled[col].to_numpy())
            scores.append(evaluation.ranked_probability_score(model.predict_proba(shuffled), test["result"]) - base)
        rows.append({"feature": col, "importance": np.mean(scores), "std": np.std(scores)})
    table = pd.DataFrame(rows).sort_values("importance", ascending=False).reset_index(drop=True)
    table["label"] = table["feature"].map(features.FEATURE_DESCRIPTIONS).fillna(table["feature"])
    return table


def original_project_comparison(predictions: pd.DataFrame) -> pd.DataFrame:
    """Score our models on exactly the matches the original project tested on.

    The original data stopped in March 2020 (COVID-19 pause) and its test set
    was the last 20 % of match dates: 8 Feb - 9 Mar 2020 (38 matches).
    Small sample, so treat differences of a few % as noise.
    """
    subset = predictions[predictions["date"].between("2020-02-08", "2020-03-09")]
    table = evaluation.summarise(subset)[["model", "matches", "accuracy"]]
    original = pd.DataFrame([{"model": "Original project (v1 random forest)", "matches": subset["match_id"].nunique(),
                              "accuracy": ORIGINAL_PROJECT_ACCURACY}])
    return pd.concat([table, original], ignore_index=True)


if __name__ == "__main__":
    matches = data.load_matches()
    feats = features.load_features()
    predictions = pd.read_csv(config.PREDICTIONS_CSV, parse_dates=["date"])
    overall = pd.read_csv(config.RESULTS_CSV)
    by_season = pd.read_csv(config.RESULTS_BY_SEASON_CSV)
    best = best_model_name(overall)
    print(f"Best model (lowest RPS): {best}")

    plots.outcomes_by_season(matches)
    plots.elo_history(feats, BIG_SIX)
    plots.model_comparison(overall, best)
    plots.accuracy_by_season(by_season, best)
    plots.calibration(predictions, best)
    plots.confusion(predictions, best)

    comparison = original_project_comparison(predictions)
    comparison.to_csv(config.REPORTS_DIR / "comparison_with_original.csv", index=False)
    plots.season_2019_comparison(comparison)
    print("\nSame test matches as the original project:")
    print(comparison.round(4).to_string(index=False))

    print("\nComputing permutation importance (Logistic regression) ...")
    importance = permutation_importance(feats, "Logistic regression")
    importance.to_csv(config.REPORTS_DIR / "feature_importance.csv", index=False)
    plots.feature_importance(importance)
    print(importance.head(10).round(5).to_string(index=False))
    print(f"\nFigures saved to {config.FIGURES_DIR.relative_to(config.ROOT)}/")
