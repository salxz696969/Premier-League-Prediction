"""Choose model settings using ONLY seasons before the test period.

Validation = walk-forward over 2010-11 ... 2013-14 (train on everything
before each season). The test seasons (2014-15 onwards) are never looked at
here, so the final results in reports/ are an honest out-of-sample test.

Run:  uv run python scripts/tune_models.py
"""

import itertools

import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression

from eplpred import config, data, evaluation, features
from eplpred.elo import EloParams
from eplpred.models import PoissonGoals, SklearnClassifier

VALIDATION_SEASONS = range(2010, 2014)


def validate(feats, model) -> float:
    """Mean RPS over the validation seasons (lower is better)."""
    feats = feats[feats["season"] >= config.FIRST_TRAIN_SEASON]
    preds = []
    for season in VALIDATION_SEASONS:
        train, test = feats[feats["season"] < season], feats[feats["season"] == season]
        preds.append(evaluation._prediction_frame(test, model.name, model.fit(train).predict_proba(test)))
    return evaluation.summarise(pd.concat(preds)).loc[0, "rps"]


def main():
    matches = data.load_matches()

    print("1) Elo settings (scored with an Elo-only model)")
    best = None
    for k, hfa in itertools.product([10, 15, 20, 30], [50, 65, 80]):
        feats = features.build_features(matches, EloParams(k=k, home_advantage=hfa))
        rps = validate(feats, SklearnClassifier("elo", LogisticRegression(max_iter=1000), columns=["elo_diff"]))
        print(f"   K={k:<3} home advantage={hfa:<3} RPS={rps:.4f}")
        best = min(best or (rps, k, hfa), (rps, k, hfa))
    print(f"   -> best: K={best[1]}, home advantage={best[2]}\n")

    feats = features.build_features(matches, EloParams(k=best[1], home_advantage=best[2]))

    print("2) Logistic regression regularisation C")
    for c in [0.001, 0.01, 0.1, 1.0]:
        print(f"   C={c:<6} RPS={validate(feats, SklearnClassifier('lr', LogisticRegression(C=c, max_iter=2000), scale=True)):.4f}")

    print("3) Random forest min_samples_leaf")
    for leaf in [10, 40, 100]:
        rf = RandomForestClassifier(n_estimators=300, min_samples_leaf=leaf, n_jobs=-1, random_state=0)
        print(f"   leaf={leaf:<4} RPS={validate(feats, SklearnClassifier('rf', rf)):.4f}")

    print("4) Gradient boosting depth / learning rate")
    for depth, lr in itertools.product([2, 3, 5], [0.03, 0.1]):
        gb = HistGradientBoostingClassifier(learning_rate=lr, max_iter=200, max_depth=depth,
                                            min_samples_leaf=80, l2_regularization=1.0, random_state=0)
        print(f"   depth={depth} lr={lr:<5} RPS={validate(feats, SklearnClassifier('gb', gb)):.4f}")

    print("5) Poisson model regularisation alpha")
    for alpha in [0.01, 0.1, 1.0, 10.0]:
        print(f"   alpha={alpha:<5} RPS={validate(feats, PoissonGoals(alpha=alpha)):.4f}")


if __name__ == "__main__":
    main()
