import numpy as np
import pandas as pd
import pytest

from eplpred.evaluation import ranked_probability_score, score


def test_perfect_prediction_scores_zero():
    results = pd.Series(["H", "D", "A"])
    proba = np.eye(3)
    s = score(proba, results)
    assert s["accuracy"] == 1
    assert s["rps"] == pytest.approx(0)
    assert s["brier"] == pytest.approx(0)


def test_rps_rewards_near_misses():
    """If the home team wins, predicting a draw is less wrong than an away win."""
    home_win = pd.Series(["H"])
    said_draw = ranked_probability_score(np.array([[0.0, 1.0, 0.0]]), home_win)
    said_away = ranked_probability_score(np.array([[0.0, 0.0, 1.0]]), home_win)
    assert said_draw < said_away


def test_log_loss_uses_probability_of_actual_result():
    s = score(np.array([[0.5, 0.3, 0.2]]), pd.Series(["D"]))
    assert s["log_loss"] == pytest.approx(-np.log(0.3))
