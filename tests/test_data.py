from eplpred import config, data


def test_every_season_is_complete():
    m = data.load_matches()
    assert m["season"].nunique() == config.LAST_SEASON - config.FIRST_SEASON + 1
    assert (m.groupby("season").size() == 380).all()


def test_bookmaker_probabilities_sum_to_one():
    m = data.load_matches().dropna(subset=["book_prob_H"])
    total = m[["book_prob_H", "book_prob_D", "book_prob_A"]].sum(axis=1)
    assert ((total - 1).abs() < 1e-9).all()


def test_team_names_are_standardised():
    m = data.load_matches()
    teams = set(m["home_team"]) | set(m["away_team"])
    assert not teams & set(config.TEAM_ALIASES) - set(config.TEAM_ALIASES.values())
    assert "Man City" not in teams and "Nott'm Forest" not in teams
