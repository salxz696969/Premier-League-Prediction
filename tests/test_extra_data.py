"""Other competitions, international breaks and player data."""

import pandas as pd

from eplpred import data, other_competitions, players


SAMPLE = """= UEFA Champions League 2019/20
▪ Group B
  Wed Sep 18 2019
    18:55  Olympiakos Piraeus (GRE) v Tottenham Hotspur (ENG)  2-2 (1-2)
  Tue Oct 1
    21:00  Tottenham Hotspur (ENG) v Bayern München (GER)     2-7 (1-2)
  Tue Feb 18
           Tottenham Hotspur (ENG) v RB Leipzig (GER)   0-1
"""


def test_openfootball_parser_reads_dates_and_teams():
    games = other_competitions.parse_openfootball(SAMPLE, 2019)
    assert games[0] == (pd.Timestamp("2019-09-18"), "Olympiakos Piraeus (GRE)", "Tottenham Hotspur (ENG)")
    assert games[1][0] == pd.Timestamp("2019-10-01")
    assert games[2] == (pd.Timestamp("2020-02-18"), "Tottenham Hotspur (ENG)", "RB Leipzig (GER)")  # year rolls over


def test_cup_names_map_to_premier_league_names():
    pl = {other_competitions.clean_name(t): t for t in ["Arsenal", "Wolverhampton", "Bournemouth"]}
    assert other_competitions.to_premier_league_name("Arsenal FC (ENG)", pl) == "Arsenal"
    assert other_competitions.to_premier_league_name("Wolverhampton Wanderers", pl) == "Wolverhampton"
    assert other_competitions.to_premier_league_name("AFC Bournemouth", pl) == "Bournemouth"
    assert other_competitions.to_premier_league_name("Real Madrid (ESP)", pl) is None


def test_every_pl_club_has_domestic_cup_matches():
    matches = data.load_matches()
    other = other_competitions.load_other_matches(matches)
    season = matches[matches["season"] == 2019]
    fa = set(other[(other["season"] == 2019) & (other["competition"] == "fa_cup")]["team"])
    assert set(season["home_team"]) <= fa


def test_player_data_matches_league_matches():
    matches = data.load_matches()
    pm = players.load_player_matches(matches[matches["season"] == 2023])
    assert pm["match_id"].nunique() == 380
    elevens = pm[pm["starter"]].groupby(["match_id", "team"]).size()
    assert elevens.eq(11).mean() > 0.99
