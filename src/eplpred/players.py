"""Player influence from Fantasy Premier League data (2016-17 onwards).

The FPL "influence" score (part of its ICT index, made by Opta) rates how much
a player affected a match: goals, assists, key passes, tackles, saves, ...
We use it to measure how strong the *starting eleven* of a team is.

For every Premier League match and team:
* xi_influence  - sum of the starters' average influence per 90 minutes
                  in their *earlier* matches (the current match is never used)
* xi_ict        - the same with the full ICT index (influence + creativity + threat)
* xi_value      - total FPL price of the starters (set before the match)
* key_missing   - how many of the team's 5 most influential recent players
                  are not in the starting eleven

Team sheets are published an hour before kick-off, so knowing who starts is
pre-match information. FPL only records "starts" from 2022-23; before that the
11 players with the most minutes count as the starting eleven (checked against
the real "starts" column in ``scripts/check_player_data.py``).

Source: vaastav/Fantasy-Premier-League (MIT), see SOURCES.md.
"""

from __future__ import annotations

import io
import re
import unicodedata
import urllib.request

import numpy as np
import pandas as pd

from . import config

FIRST_FPL_SEASON = 2016
RAW = config.RAW_DIR / "players"
BASE_URL = "https://raw.githubusercontent.com/vaastav/Fantasy-Premier-League/master/data"
PRIOR_APPEARANCES = 15  # how many earlier appearances a player's rating is based on
MIN_PRIOR_MINUTES = 180  # below this a player's rating is "unknown"
KEY_PLAYERS = 5
KEY_WINDOW = 10  # "recent" = the team's previous 10 matches

FPL_NAMES = {
    "Man City": "Manchester City",
    "Man Utd": "Manchester United",
    "Spurs": "Tottenham Hotspur",
    "Newcastle": "Newcastle United",
    "West Ham": "West Ham United",
    "West Brom": "West Bromwich Albion",
    "Wolves": "Wolverhampton",
    "Brighton": "Brighton & Hove Albion",
    "Leicester": "Leicester City",
    "Leeds": "Leeds United",
    "Norwich": "Norwich City",
    "Stoke": "Stoke City",
    "Swansea": "Swansea City",
    "Cardiff": "Cardiff City",
    "Hull": "Hull City",
    "Huddersfield": "Huddersfield Town",
    "Ipswich": "Ipswich Town",
    "Luton": "Luton Town",
    "Sheffield Utd": "Sheffield United",
    "Nott'm Forest": "Nottingham Forest",
}
KEEP = ["name", "element", "fixture", "kickoff_time", "was_home", "opponent_team", "minutes", "starts",
        "influence", "creativity", "threat", "ict_index", "value", "team", "position",
        "goals_scored", "assists", "clean_sheets", "goals_conceded", "saves", "yellow_cards", "red_cards",
        "bonus", "total_points"]
POSITIONS = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD", 5: "MGR"}


def season_label(year: int) -> str:
    return f"{year}-{(year + 1) % 100:02d}"


def _get(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=180) as response:
        return response.read()


def download(force: bool = False) -> None:
    """Keep a compact copy of each season's player-match file in data/raw/players/."""
    RAW.mkdir(parents=True, exist_ok=True)
    teams_path = RAW / "master_team_list.csv"
    if not teams_path.exists() or force:
        teams_path.write_bytes(_get(f"{BASE_URL}/master_team_list.csv"))
    for year in range(FIRST_FPL_SEASON, config.LAST_SEASON + 1):
        path = RAW / f"fpl_{season_label(year)}.csv.gz"
        if path.exists() and not force:
            continue
        print(f"Downloading FPL {season_label(year)} ...")
        df = pd.read_csv(io.BytesIO(_get(f"{BASE_URL}/{season_label(year)}/gws/merged_gw.csv")),
                         encoding="utf-8", encoding_errors="replace", low_memory=False)
        df[[c for c in KEEP if c in df.columns]].to_csv(path, index=False, compression="gzip")

    for year in range(FIRST_FPL_SEASON, config.LAST_SEASON + 1):
        path = RAW / f"players_{season_label(year)}.csv"
        if path.exists() and not force:
            continue
        raw = pd.read_csv(io.BytesIO(_get(f"{BASE_URL}/{season_label(year)}/players_raw.csv")), low_memory=False)
        raw[["id", "first_name", "second_name", "web_name", "element_type"]].to_csv(path, index=False)


def player_key(name: str) -> str:
    """'Aaron_Cresswell_454' / 'Aaron Cresswell' -> 'aaron cresswell'."""
    name = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode()
    name = re.sub(r"[_\s]+\d+$", "", name).replace("_", " ")
    return " ".join(name.lower().split())


def starters(df: pd.DataFrame) -> pd.Series:
    """Who started each match.

    FPL's "starts" column is used where it lists a full eleven (2022-23
    onwards, partly). Otherwise the 11 players with the most minutes count as
    the starting eleven (checked against real "starts": see
    scripts/check_player_data.py).
    """
    group = [df["fixture"], df["team_id"]]
    rank = df.groupby(group)["minutes"].rank(method="first", ascending=False)
    proxy = (rank <= 11) & (df["minutes"] > 0)
    if "starts" not in df.columns:
        return proxy
    real = df["starts"].fillna(0).eq(1)
    full_eleven = real.groupby(group).transform("sum").eq(11)
    return real.where(full_eleven, proxy)


def load_player_matches(matches: pd.DataFrame) -> pd.DataFrame:
    """One row per player per Premier League match, matched to our match_ids."""
    master = pd.read_csv(RAW / "master_team_list.csv")
    frames = []
    for year in range(FIRST_FPL_SEASON, config.LAST_SEASON + 1):
        df = pd.read_csv(RAW / f"fpl_{season_label(year)}.csv.gz", low_memory=False)
        df["season"] = year
        df["date"] = pd.to_datetime(df["kickoff_time"], utc=True).dt.tz_convert("Europe/London").dt.tz_localize(None).dt.normalize()
        df["was_home"] = df["was_home"].astype(str).str.lower().eq("true")

        # A fixture's two team ids, from the opponents listed on each side.
        home_id = df[~df["was_home"]].groupby("fixture")["opponent_team"].first()
        away_id = df[df["was_home"]].groupby("fixture")["opponent_team"].first()
        df["team_id"] = np.where(df["was_home"], df["fixture"].map(home_id), df["fixture"].map(away_id))

        names = master[master["season"] == season_label(year)].set_index("team")["team_name"].to_dict()
        if not names and "team" in df.columns:  # newer seasons: learn ids from the 'team' column
            names = df.dropna(subset=["team_id"]).groupby("team_id")["team"].agg(lambda s: s.mode()[0]).to_dict()
        df["team_name"] = df["team_id"].map(names).map(lambda t: FPL_NAMES.get(t, t))
        df["player"] = df["name"].map(player_key)
        info_path = RAW / f"players_{season_label(year)}.csv"
        if info_path.exists():  # position (GK/DEF/MID/FWD) and short name for every season
            info = pd.read_csv(info_path).set_index("id")
            df["position"] = df["element"].map(info["element_type"]).map(POSITIONS)
            df["short_name"] = df["element"].map(info["web_name"])
        df["starter"] = starters(df)
        frames.append(df)
    players = pd.concat(frames, ignore_index=True)

    # Attach our match_id via (date, home team, away team).
    fixtures = players.groupby(["season", "fixture"]).agg(date=("date", "first")).reset_index()
    sides = players.groupby(["season", "fixture", "was_home"])["team_name"].first().unstack()
    fixtures = fixtures.join(sides, on=["season", "fixture"]).rename(columns={True: "home_team", False: "away_team"})
    fixtures = fixtures.merge(matches[["match_id", "date", "home_team", "away_team"]], on=["date", "home_team", "away_team"], how="left")
    players = players.merge(fixtures[["season", "fixture", "match_id"]], on=["season", "fixture"], how="left")
    players = players[players["match_id"].notna()].copy()
    players["match_id"] = players["match_id"].astype(int)
    keep = ["season", "match_id", "date", "team_name", "player", "starter", "minutes",
            "influence", "creativity", "threat", "ict_index", "value"]
    extra = ["position", "short_name", "goals_scored", "assists", "clean_sheets", "goals_conceded", "saves",
             "yellow_cards", "red_cards", "bonus", "total_points"]
    keep += [c for c in extra if c in players.columns]
    return players[keep].rename(columns={"team_name": "team"})


def player_ratings(players: pd.DataFrame) -> pd.DataFrame:
    """Each player's influence and ICT per 90 minutes over his previous
    PRIOR_APPEARANCES appearances (the current match is never included)."""
    df = players.sort_values(["player", "date"]).copy()
    played = df[df["minutes"] > 0]
    by = played.groupby("player", sort=False)
    prior = lambda col: by[col].transform(lambda s: s.shift(1).rolling(PRIOR_APPEARANCES, min_periods=1).sum())
    minutes = prior("minutes")
    df["prior_minutes"] = minutes
    for col in ("influence", "ict_index"):
        df[f"{col}_p90"] = (prior(col) / minutes * 90).where(minutes >= MIN_PRIOR_MINUTES)
    return df


def team_player_features(matches: pd.DataFrame, player_matches: pd.DataFrame | None = None) -> pd.DataFrame:
    """Per match: home_/away_ xi_influence, xi_ict, xi_value, key_missing."""
    if player_matches is None:
        player_matches = load_player_matches(matches)
    players = player_ratings(player_matches)
    starters = players[players["starter"]].copy()
    # Players with too little history (new signings, youngsters) get the average
    # rating of the team's other starters in that match. (A league-wide default
    # would be computed from all seasons, including future ones: leakage.)
    for col in ("influence", "ict_index"):
        team_avg = starters.groupby(["match_id", "team"])[f"{col}_p90"].transform("mean")
        starters[f"{col}_p90"] = starters[f"{col}_p90"].fillna(team_avg)
    team_match = starters.groupby(["match_id", "team"]).agg(
        xi_influence=("influence_p90", "mean"),
        xi_ict=("ict_index_p90", "mean"),
        xi_value=("value", lambda v: v.mean() / 10),  # FPL prices are in 0.1m
        xi_size=("player", "size"),
    )
    # Express as "a full eleven": average x 11 (so 10-man team sheets aren't penalised).
    for col in ("xi_influence", "xi_ict", "xi_value"):
        team_match[col] *= 11

    # Key players: top-5 by total influence over the team's previous 10 matches.
    key_missing = {}
    for team, rows in players.groupby("team"):
        match_order = rows[["match_id", "date"]].drop_duplicates().sort_values("date")["match_id"].tolist()
        by_match = {m: g for m, g in rows.groupby("match_id")}
        for i, mid in enumerate(match_order):
            recent = match_order[max(0, i - KEY_WINDOW):i]
            if not recent:
                continue
            history = pd.concat([by_match[m] for m in recent])
            top = history.groupby("player")["influence"].sum().nlargest(KEY_PLAYERS).index
            starting = set(by_match[mid].loc[by_match[mid]["starter"], "player"])
            key_missing[(mid, team)] = sum(p not in starting for p in top)
    team_match["key_missing"] = pd.Series(key_missing)
    team_match = team_match.reset_index()

    out = matches[["match_id", "home_team", "away_team"]].copy()
    for side in ("home", "away"):
        part = team_match.rename(columns={"team": f"{side}_team", **{c: f"{side}_{c}" for c in
                                 ["xi_influence", "xi_ict", "xi_value", "xi_size", "key_missing"]}})
        out = out.merge(part, on=["match_id", f"{side}_team"], how="left")
    return out.drop(columns=["home_team", "away_team"]).set_index("match_id")


def display_name(key: str) -> str:
    """'dominic calvert-lewin' -> 'Dominic Calvert-Lewin', "o'brien" -> "O'Brien"."""
    return re.sub(r"(^|[\s\-'])([a-z])", lambda m: m.group(1) + m.group(2).upper(), key)


def latest_lineups(player_matches: pd.DataFrame) -> dict[str, dict]:
    """Each team's expected eleven for its *next* match: the 11 players who
    started most often in its last 5 league matches (one match alone can be
    misleading, e.g. a rotated side on the final day), rated on everything
    up to now.

    Returns {team: {"xi_influence", "xi_ict", "xi_value", "key_missing", "players"}}.
    """
    played = player_matches[player_matches["minutes"] > 0].sort_values(["player", "date"])
    by = played.groupby("player", sort=False)
    now = pd.DataFrame({
        "minutes": by["minutes"].apply(lambda s: s.tail(PRIOR_APPEARANCES).sum()),
        "influence": by["influence"].apply(lambda s: s.tail(PRIOR_APPEARANCES).sum()),
        "ict_index": by["ict_index"].apply(lambda s: s.tail(PRIOR_APPEARANCES).sum()),
    })
    for col in ("influence", "ict_index"):
        now[f"{col}_p90"] = (now[col] / now["minutes"] * 90).where(now["minutes"] >= MIN_PRIOR_MINUTES)

    out = {}
    for team, rows in player_matches.groupby("team"):
        order = rows[["match_id", "date"]].drop_duplicates().sort_values("date")["match_id"].tolist()
        last = rows[rows["match_id"] == order[-1]]
        window = rows[rows["match_id"].isin(order[-5:])]
        usage = window.groupby("player").agg(starts=("starter", "sum"), minutes=("minutes", "sum"))
        chosen = usage.sort_values(["starts", "minutes"], ascending=False).head(11).index
        xi = rows.sort_values("date").groupby("player").last().loc[chosen]
        rating = now.reindex(xi.index)
        for col in ("influence_p90", "ict_index_p90"):
            rating[col] = rating[col].fillna(rating[col].mean())
        recent = rows[rows["match_id"].isin(order[-KEY_WINDOW:])]
        top = recent.groupby("player")["influence"].sum().nlargest(KEY_PLAYERS).index
        ranked = rating.sort_values("influence_p90", ascending=False)
        out[team] = {
            "xi_influence": float(rating["influence_p90"].mean() * 11),
            "xi_ict": float(rating["ict_index_p90"].mean() * 11),
            "xi_value": float(xi["value"].mean() * 11 / 10),
            "key_missing": float(sum(p not in xi.index for p in top)),
            "players": [{"name": display_name(p), "influence_p90": round(float(r), 1)}
                        for p, r in ranked["influence_p90"].items()],
            "missing": [display_name(p) for p in top if p not in xi.index],
            "last_match": last["date"].iloc[0].date().isoformat(),
        }
    return out
