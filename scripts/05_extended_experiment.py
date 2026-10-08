"""Step 5: does extra data help? Fatigue (all competitions), players (FPL) and
managers (if available) on top of the 49 base features.

Same walk-forward method as step 3, on the seasons where player data exists
in training too: 2018-19 ... 2025-26 (3,040 matches). Every model is trained
on all earlier seasons; features that don't exist in early seasons are left
missing (the models get a "missing" flag for them).

Writes reports/extended_results.csv, reports/extended_by_season.csv and
reports/figures/extended_comparison.png.

Run:  uv run python scripts/05_extended_experiment.py      (a few minutes)
"""

import numpy as np
import pandas as pd

from eplpred import config, evaluation, extra_features, managers, plots
from eplpred.features import feature_columns
from eplpred.models import make_models

FIRST_TEST = 2018
MODELS = ["Logistic regression", "Gradient boosting", "Poisson goals model", "Ensemble (LR + GB + Poisson)"]


def feature_sets(feats: pd.DataFrame) -> dict[str, list[str]]:
    base = feature_columns()
    sched = [f"{s}_{c}" for c in extra_features.SCHEDULE_COLUMNS for s in ("home", "away")] + ["rest_all_diff"]
    play = [f"{s}_{c}" for c in extra_features.PLAYER_COLUMNS for s in ("home", "away")] + ["xi_influence_diff", "xi_value_diff"]
    sets = {"Base (49 features)": base, "+ fatigue": base + sched, "+ players": base + play}
    if managers.available():
        sets["+ managers"] = base + managers.MANAGER_COLUMNS
    sets["+ everything"] = extra_features.extended_feature_columns(feats)
    return sets


def bootstrap_rps_difference(a: pd.DataFrame, b: pd.DataFrame, n: int = 2000) -> tuple[float, float, float]:
    """Mean RPS(b) - RPS(a) per match with a 95 % bootstrap interval (negative = b better)."""
    def per_match(p):
        proba = p[[f"prob_{o}" for o in config.OUTCOMES]].to_numpy()
        obs = evaluation.one_hot(p["result"])
        diff = np.cumsum(proba, 1)[:, :-1] - np.cumsum(obs, 1)[:, :-1]
        return (diff**2).sum(1) / 2

    a, b = a.sort_values("match_id"), b.sort_values("match_id")
    d = per_match(b) - per_match(a)
    rng = np.random.default_rng(config.RANDOM_STATE)
    boots = [d[rng.integers(0, len(d), len(d))].mean() for _ in range(n)]
    return float(d.mean()), float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))


if __name__ == "__main__":
    feats = extra_features.load_extended_features()
    data = feats[feats["season"] >= config.FIRST_TRAIN_SEASON]
    keep = ["match_id", "season", "season_label", "date", "home_team", "away_team", "home_goals", "away_goals", "result"]

    preds = []
    for set_name, cols in feature_sets(feats).items():
        print(f"{set_name}: {len(cols)} features")
        models = [m for m in make_models(columns=cols) if m.name in MODELS]
        for season in range(FIRST_TEST, config.LAST_SEASON + 1):
            train, test = data[data["season"] < season], data[data["season"] == season]
            for model in models:
                p = evaluation._prediction_frame(test[keep], model.name, model.fit(train).predict_proba(test))
                preds.append(p.assign(feature_set=set_name))
    test = data[data["season"] >= FIRST_TEST]
    book = evaluation._prediction_frame(test[keep], evaluation.BOOKMAKER, test[["book_prob_H", "book_prob_D", "book_prob_A"]].to_numpy())
    preds = pd.concat(preds + [book.assign(feature_set="Bookmaker")], ignore_index=True)

    rows = []
    for (model, fset), group in preds.groupby(["model", "feature_set"], sort=False):
        proba = group[[f"prob_{o}" for o in config.OUTCOMES]].to_numpy()
        rows.append({"model": model, "feature_set": fset, "matches": len(group), **evaluation.score(proba, group["result"])})
    results = pd.DataFrame(rows)

    # Is "+ everything" really better than "Base"? Paired bootstrap on RPS.
    base_name = "Base (49 features)"
    for i, r in results.iterrows():
        if r["feature_set"] in (base_name, "Bookmaker"):
            continue
        a = preds[(preds["model"] == r["model"]) & (preds["feature_set"] == base_name)]
        b = preds[(preds["model"] == r["model"]) & (preds["feature_set"] == r["feature_set"])]
        diff, lo, hi = bootstrap_rps_difference(a, b)
        results.loc[i, ["rps_change", "rps_change_low", "rps_change_high"]] = [diff, lo, hi]
    results.to_csv(config.REPORTS_DIR / "extended_results.csv", index=False)

    by_season = preds.groupby(["model", "feature_set", "season_label"]).apply(
        lambda g: evaluation.score(g[[f"prob_{o}" for o in config.OUTCOMES]].to_numpy(), g["result"])["accuracy"],
        include_groups=False,
    ).rename("accuracy").reset_index()
    by_season.to_csv(config.REPORTS_DIR / "extended_by_season.csv", index=False)
    plots.extended_comparison(results)

    pd.set_option("display.width", 160)
    print("\nTest seasons 2018-19 to 2025-26 (RPS: lower is better; rps_change < 0 = extra data helped)")
    cols = ["model", "feature_set", "accuracy", "rps", "log_loss", "rps_change", "rps_change_low", "rps_change_high"]
    print(results[cols].round(4).to_string(index=False))
