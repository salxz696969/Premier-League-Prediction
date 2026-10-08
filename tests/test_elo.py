import pandas as pd
import pytest

from eplpred.elo import EloParams, compute_elo, expected_home_score, goal_multiplier


def test_equal_teams_without_home_advantage_have_50_percent():
    assert expected_home_score(1500, 1500, home_advantage=0) == pytest.approx(0.5)


def test_home_advantage_helps_home_team():
    assert expected_home_score(1500, 1500, home_advantage=65) > 0.5


def test_bigger_wins_count_more():
    assert goal_multiplier(1) < goal_multiplier(2) < goal_multiplier(4)


def test_ratings_are_zero_sum_and_pre_match():
    games = pd.DataFrame(
        {
            "season": [2000, 2000],
            "date": pd.to_datetime(["2000-08-01", "2000-08-08"]),
            "home_team": ["A", "B"],
            "away_team": ["B", "A"],
            "home_goals": [2, 0],
            "away_goals": [0, 0],
        }
    )
    elo, final = compute_elo(games, EloParams())
    # Before the first match nobody has played, so both start at 1500.
    assert elo.loc[0, "home_elo"] == elo.loc[0, "away_elo"] == 1500
    # A won the first match, so A is rated higher before the second match.
    assert elo.loc[1, "away_elo"] > elo.loc[1, "home_elo"]
    assert sum(final.values()) == pytest.approx(3000)
