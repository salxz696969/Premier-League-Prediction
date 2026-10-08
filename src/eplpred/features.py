"""Step 2 - turn the match table into pre-match features.

The golden rule: a feature for a match may only use information that was
known *before kick-off*. Every statistic below is computed from earlier
matches only (``shift(1)`` = "exclude the current match"), and
``tests/test_no_leakage.py`` checks this automatically.

Feature families
----------------
* Elo rating           - long-term team strength (see ``elo.py``)
* Recent form          - points per game over the last 5 matches
* Weighted averages    - goals, shots, shots on target, corners for/against,
                         exponentially weighted so recent games count more
* Home/away form       - points per game in the last 5 home (or away) games
* Season so far        - points per game, goal difference per game and
                         league position before this match
* Last season          - final league position, promoted or not
* Rest                 - days since the team's previous league match
* Head-to-head         - points per game in the last 6 meetings
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config
from .elo import EloParams, compute_elo

FORM_WINDOW = 5
EWM_SPAN = 10
H2H_WINDOW = 6
MAX_REST_DAYS = 21
NOT_IN_LEAGUE_POSITION = 21  # "last season position" for promoted teams

# Per-match statistics that we average over each team's previous matches.
TEAM_STATS = [
    "goals_for",
    "goals_against",
    "shots_for",
    "shots_against",
    "sot_for",
    "sot_against",
    "corners_for",
    "corners_against",
    "sot_share",
    "points",
]


# --------------------------------------------------------------------------
# 1) One row per team per match ("long" format)
# --------------------------------------------------------------------------
def to_team_matches(matches: pd.DataFrame) -> pd.DataFrame:
    """Each match becomes two rows: one from each team's point of view."""
    def side(prefix: str, other: str, is_home: int) -> pd.DataFrame:
        out = pd.DataFrame(
            {
                "match_id": matches["match_id"],
                "season": matches["season"],
                "date": matches["date"],
                "team": matches[f"{prefix}_team"],
                "opponent": matches[f"{other}_team"],
                "is_home": is_home,
                "goals_for": matches[f"{prefix}_goals"],
                "goals_against": matches[f"{other}_goals"],
                "shots_for": matches[f"{prefix}_shots"],
                "shots_against": matches[f"{other}_shots"],
                "sot_for": matches[f"{prefix}_shots_on_target"],
                "sot_against": matches[f"{other}_shots_on_target"],
                "corners_for": matches[f"{prefix}_corners"],
                "corners_against": matches[f"{other}_corners"],
            }
        )
        return out

    long = pd.concat([side("home", "away", 1), side("away", "home", 0)], ignore_index=True)
    total_sot = long["sot_for"] + long["sot_against"]
    long["sot_share"] = np.where(total_sot > 0, long["sot_for"] / total_sot.replace(0, np.nan), 0.5)
    long["points"] = np.select(
        [long["goals_for"] > long["goals_against"], long["goals_for"] == long["goals_against"]],
        [3.0, 1.0],
        0.0,
    )
    long.loc[long["goals_for"].isna(), "points"] = np.nan  # unplayed fixture
    return long.sort_values(["team", "date"]).reset_index(drop=True)


def _add_spell_id(long: pd.DataFrame) -> pd.DataFrame:
    """A 'spell' = consecutive Premier League seasons of one team.

    Form is reset when a team returns after relegation: its matches from years
    ago say little about the team that comes back up.
    """
    seasons = long[["team", "season"]].drop_duplicates().sort_values(["team", "season"])
    new_spell = seasons.groupby("team")["season"].diff().ne(1)
    seasons["spell"] = new_spell.groupby(seasons["team"]).cumsum()
    return long.merge(seasons, on=["team", "season"], how="left")


# --------------------------------------------------------------------------
# 2) Rolling statistics from previous matches only
# --------------------------------------------------------------------------
def add_rolling_features(long: pd.DataFrame) -> pd.DataFrame:
    long = _add_spell_id(long).sort_values(["team", "date"]).reset_index(drop=True)
    by_spell = long.groupby(["team", "spell"], sort=False)

    # shift(1) moves every value one match down, so the current match is
    # never included in its own average.
    for stat in TEAM_STATS:
        long[f"ewm_{stat}"] = by_spell[stat].transform(
            lambda s: s.shift(1).ewm(span=EWM_SPAN, min_periods=1).mean()
        )
    long["form5_ppg"] = by_spell["points"].transform(
        lambda s: s.shift(1).rolling(FORM_WINDOW, min_periods=1).mean()
    )
    long["spell_matches"] = by_spell.cumcount()

    # Form at this venue only (home form for home games, away form for away games).
    long["venue_form5_ppg"] = long.groupby(["team", "spell", "is_home"], sort=False)["points"].transform(
        lambda s: s.shift(1).rolling(FORM_WINDOW, min_periods=1).mean()
    )

    # Days of rest since the previous league match.
    long["rest_days"] = long.groupby("team")["date"].diff().dt.days.clip(upper=MAX_REST_DAYS)
    long.loc[long["season"].ne(long.groupby("team")["season"].shift(1)), "rest_days"] = MAX_REST_DAYS

    # Head-to-head: points per game in the last meetings with this opponent.
    by_pair = long.groupby(["team", "opponent"], sort=False)["points"]
    long["h2h_ppg"] = by_pair.transform(lambda s: s.shift(1).rolling(H2H_WINDOW, min_periods=1).mean())
    long["h2h_meetings"] = by_pair.cumcount().clip(upper=H2H_WINDOW)

    # Season so far (cumulative sums of the previous matches of this season).
    by_season = long.groupby(["team", "season"], sort=False)
    played = by_season.cumcount()
    prev_points = by_season["points"].transform(lambda s: s.shift(1).cumsum())
    prev_gd = by_season["goals_for"].transform(lambda s: s.shift(1).cumsum()) - by_season[
        "goals_against"
    ].transform(lambda s: s.shift(1).cumsum())
    long["season_matches_played"] = played
    long["season_ppg"] = prev_points / played.replace(0, np.nan)
    long["season_gd_per_game"] = prev_gd / played.replace(0, np.nan)
    return long


# --------------------------------------------------------------------------
# 3) League table: position before each match + last season's final position
# --------------------------------------------------------------------------
def league_positions_before_match(matches: pd.DataFrame) -> pd.DataFrame:
    """Simulate the league table and record both teams' positions before kick-off.

    Teams are ranked by points, then goal difference, then goals scored
    (the official Premier League tie-breakers).
    """
    home_pos = np.full(len(matches), np.nan)
    away_pos = np.full(len(matches), np.nan)
    final_tables: dict[int, dict[str, int]] = {}
    # Plain Python lists are much faster to loop over than DataFrame rows.
    cols = ["season", "date", "home_team", "away_team", "home_goals", "away_goals"]
    games_by_season: dict[int, list] = {}
    order = np.argsort(matches["date"].to_numpy(), kind="stable")
    for i, row in zip(order, matches[cols].iloc[order].itertuples(index=False)):
        games_by_season.setdefault(row.season, []).append((i, row))

    for season, games in games_by_season.items():
        teams = sorted({g.home_team for _, g in games} | {g.away_team for _, g in games})
        table = {t: [0, 0, 0] for t in teams}  # points, goal difference, goals for
        day_start = 0
        while day_start < len(games):
            date = games[day_start][1].date
            day_end = day_start
            while day_end < len(games) and games[day_end][1].date == date:
                day_end += 1
            day = games[day_start:day_end]
            started = any(v != [0, 0, 0] for v in table.values())  # no table before match day 1
            order = sorted(teams, key=lambda t: (-table[t][0], -table[t][1], -table[t][2], t))
            ranking = {t: i + 1 for i, t in enumerate(order)} if started else {}
            for i, g in day:
                home_pos[i] = ranking.get(g.home_team, np.nan)
                away_pos[i] = ranking.get(g.away_team, np.nan)
            for _, g in day:  # update the table after the whole day
                if pd.isna(g.home_goals):
                    continue
                hg, ag = int(g.home_goals), int(g.away_goals)
                table[g.home_team][0] += 3 if hg > ag else 1 if hg == ag else 0
                table[g.away_team][0] += 3 if ag > hg else 1 if hg == ag else 0
                table[g.home_team][1] += hg - ag
                table[g.away_team][1] += ag - hg
                table[g.home_team][2] += hg
                table[g.away_team][2] += ag
            day_start = day_end
        order = sorted(teams, key=lambda t: (-table[t][0], -table[t][1], -table[t][2], t))
        final_tables[season] = {t: i + 1 for i, t in enumerate(order)}

    out = pd.DataFrame({"home_position": home_pos, "away_position": away_pos}, index=matches.index)
    prev = {s: final_tables.get(s - 1, {}) for s in final_tables}
    out["home_prev_position"] = [
        prev[s].get(t, NOT_IN_LEAGUE_POSITION) for s, t in zip(matches["season"], matches["home_team"])
    ]
    out["away_prev_position"] = [
        prev[s].get(t, NOT_IN_LEAGUE_POSITION) for s, t in zip(matches["season"], matches["away_team"])
    ]
    # In the very first season there is no "last season" in our data.
    first = matches["season"].eq(matches["season"].min())
    out.loc[first, ["home_prev_position", "away_prev_position"]] = np.nan
    return out


# --------------------------------------------------------------------------
# 4) Put everything back to one row per match
# --------------------------------------------------------------------------
LONG_FEATURES = [f"ewm_{s}" for s in TEAM_STATS] + [
    "form5_ppg",
    "venue_form5_ppg",
    "rest_days",
    "season_ppg",
    "season_gd_per_game",
    "spell_matches",
]


def build_features(matches: pd.DataFrame, elo_params: EloParams | None = None) -> pd.DataFrame:
    """Return ``matches`` with all pre-match feature columns added."""
    matches = matches.sort_values(["date", "home_team"]).reset_index(drop=True)
    long = add_rolling_features(to_team_matches(matches))

    home = long[long["is_home"].eq(1)].set_index("match_id")
    away = long[long["is_home"].eq(0)].set_index("match_id")
    feats = matches.copy()
    for col in LONG_FEATURES:
        feats[f"home_{col}"] = feats["match_id"].map(home[col])
        feats[f"away_{col}"] = feats["match_id"].map(away[col])
    feats["h2h_home_ppg"] = feats["match_id"].map(home["h2h_ppg"])
    feats["h2h_meetings"] = feats["match_id"].map(home["h2h_meetings"])
    feats["matchweek"] = feats["match_id"].map(home["season_matches_played"]) + 1

    elo, _ = compute_elo(feats, elo_params)
    feats = pd.concat([feats, elo, league_positions_before_match(feats)], axis=1)
    feats["home_promoted"] = feats["home_prev_position"].eq(NOT_IN_LEAGUE_POSITION).astype(int)
    feats["away_promoted"] = feats["away_prev_position"].eq(NOT_IN_LEAGUE_POSITION).astype(int)

    # Differences make it easy for every model to compare the two teams.
    feats["elo_diff"] = feats["home_elo"] - feats["away_elo"]
    feats["form_diff"] = feats["home_form5_ppg"] - feats["away_form5_ppg"]
    feats["sot_share_diff"] = feats["home_ewm_sot_share"] - feats["away_ewm_sot_share"]
    feats["goal_diff_form_diff"] = (feats["home_ewm_goals_for"] - feats["home_ewm_goals_against"]) - (
        feats["away_ewm_goals_for"] - feats["away_ewm_goals_against"]
    )
    feats["position_diff"] = feats["away_position"] - feats["home_position"]
    feats["prev_position_diff"] = feats["away_prev_position"] - feats["home_prev_position"]
    feats["rest_diff"] = feats["home_rest_days"] - feats["away_rest_days"]
    return feats


def feature_columns() -> list[str]:
    """The model inputs. Nothing in here is known only after kick-off."""
    cols = []
    for col in LONG_FEATURES:
        if col == "spell_matches":
            continue
        cols += [f"home_{col}", f"away_{col}"]
    cols += [
        "home_elo",
        "away_elo",
        "elo_diff",
        "elo_home_win_expectancy",
        "home_position",
        "away_position",
        "home_prev_position",
        "away_prev_position",
        "home_promoted",
        "away_promoted",
        "h2h_home_ppg",
        "h2h_meetings",
        "matchweek",
        "form_diff",
        "sot_share_diff",
        "goal_diff_form_diff",
        "position_diff",
        "prev_position_diff",
        "rest_diff",
    ]
    return cols


# Human-readable names, used in plots and the README.
FEATURE_DESCRIPTIONS = {
    "elo_diff": "Elo rating difference (home - away)",
    "elo_home_win_expectancy": "Elo expected score of the home team",
    "home_elo": "Home team Elo rating",
    "away_elo": "Away team Elo rating",
    "form_diff": "Points-per-game difference, last 5 matches",
    "sot_share_diff": "Share of shots on target difference (weighted)",
    "goal_diff_form_diff": "Goal difference per game difference (weighted)",
    "position_diff": "League position difference before the match",
    "prev_position_diff": "Last season's position difference",
    "rest_diff": "Rest days difference",
    "h2h_home_ppg": "Home team's points per game in last 6 meetings",
    "matchweek": "Matchweek of the season",
    "h2h_meetings": "Number of recent head-to-head meetings",
}
_STAT_NAMES = {
    "goals_for": "goals scored",
    "goals_against": "goals conceded",
    "shots_for": "shots",
    "shots_against": "shots conceded",
    "sot_for": "shots on target",
    "sot_against": "shots on target conceded",
    "corners_for": "corners",
    "corners_against": "corners conceded",
    "sot_share": "share of shots on target",
    "points": "points",
}
for _side in ("home", "away"):
    _Side = _side.capitalize()
    for _stat, _name in _STAT_NAMES.items():
        FEATURE_DESCRIPTIONS[f"{_side}_ewm_{_stat}"] = f"{_Side} team {_name} per game (weighted)"
    FEATURE_DESCRIPTIONS.update(
        {
            f"{_side}_form5_ppg": f"{_Side} team points per game, last 5",
            f"{_side}_venue_form5_ppg": f"{_Side} team points per game, last 5 {_side} games",
            f"{_side}_rest_days": f"{_Side} team rest days",
            f"{_side}_season_ppg": f"{_Side} team points per game this season",
            f"{_side}_season_gd_per_game": f"{_Side} team goal difference per game this season",
            f"{_side}_position": f"{_Side} team league position",
            f"{_side}_prev_position": f"{_Side} team position last season",
            f"{_side}_promoted": f"{_Side} team is newly promoted",
        }
    )


def save_features(matches: pd.DataFrame) -> pd.DataFrame:
    feats = build_features(matches)
    feats.to_csv(config.FEATURES_CSV, index=False)
    return feats


def load_features() -> pd.DataFrame:
    """Read the saved features, building them first if they don't exist yet."""
    if not config.FEATURES_CSV.exists():
        from .data import load_matches

        return save_features(load_matches())
    return pd.read_csv(config.FEATURES_CSV, parse_dates=["date"])
