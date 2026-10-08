"""The most important test in the project: features must not know the future.

We change the scores of every match on one date, rebuild all features and
check that nothing on or before that date changed. If a feature accidentally
used the current or a later result, this test fails.
"""

import numpy as np
import pandas as pd

from eplpred import features


def _scramble_results_on(matches: pd.DataFrame, date) -> pd.DataFrame:
    changed = matches.copy()
    on_day = changed["date"].eq(date)
    stat_cols = [c for c in changed.columns if c.startswith(("home_", "away_")) and c not in ("home_team", "away_team")]
    changed.loc[on_day, stat_cols] = changed.loc[on_day, stat_cols].to_numpy()[:, ::-1] + 3
    changed.loc[on_day, "home_goals"] = 7
    changed.loc[on_day, "away_goals"] = 0
    changed.loc[on_day, "result"] = "H"
    return changed


def test_features_do_not_use_current_or_future_results(matches):
    cols = features.feature_columns()
    date = matches["date"].sort_values().iloc[len(matches) // 2]

    original = features.build_features(matches).set_index("match_id")
    changed = features.build_features(_scramble_results_on(matches, date)).set_index("match_id")

    up_to_date = original.index[original["date"] <= date]
    pd.testing.assert_frame_equal(original.loc[up_to_date, cols], changed.loc[up_to_date, cols])

    # ...and the change must be visible afterwards (the test can actually fail).
    later = original.index[original["date"] > date]
    assert not np.allclose(
        original.loc[later, "home_elo"].to_numpy(), changed.loc[later, "home_elo"].to_numpy()
    )


def test_feature_columns_exclude_match_statistics():
    """Shots, goals, cards of the match itself must never be model inputs."""
    forbidden = {"home_goals", "away_goals", "home_shots", "away_shots", "home_shots_on_target",
                 "away_shots_on_target", "result", "home_ht_goals", "away_ht_goals",
                 "book_prob_H", "book_prob_D", "book_prob_A"}
    assert not forbidden & set(features.feature_columns())
