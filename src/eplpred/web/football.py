"""Data for the football-app pages: matches, match centre, tables, teams, players.

Everything comes from the same real data as the rest of the project:
Football-Data.co.uk (league matches and stats), engsoccerdata + openfootball
(cup and European matches), Fantasy Premier League (players, line-ups) and
this project's own Elo ratings and predictions.

Club crests come from github.com/luukhopman/football-logos (see logos.py);
clubs without one get a badge drawn from the club's colours and a three-letter code.
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

from .. import config, logos, other_competitions, players

# Three-letter code and main colour of every club in the data (public facts).
CLUBS = {
    "Arsenal": ("ARS", "#EF0107"), "Aston Villa": ("AVL", "#670E36"), "Birmingham City": ("BIR", "#0000FF"),
    "Blackburn Rovers": ("BLB", "#009EE0"), "Blackpool": ("BLP", "#F68712"), "Bolton Wanderers": ("BOL", "#263C7E"),
    "Bournemouth": ("BOU", "#DA291C"), "Bradford City": ("BRA", "#7A0026"), "Brentford": ("BRE", "#E30613"),
    "Brighton & Hove Albion": ("BHA", "#0057B8"), "Burnley": ("BUR", "#6C1D45"), "Cardiff City": ("CAR", "#0070B5"),
    "Charlton Athletic": ("CHA", "#D4021D"), "Chelsea": ("CHE", "#034694"), "Coventry City": ("COV", "#59CBE8"),
    "Crystal Palace": ("CRY", "#1B458F"), "Derby County": ("DER", "#1A1A1A"), "Everton": ("EVE", "#003399"),
    "Fulham": ("FUL", "#1A1A1A"), "Huddersfield Town": ("HUD", "#0E63AD"), "Hull City": ("HUL", "#F5A12D"),
    "Ipswich Town": ("IPS", "#3A64A3"), "Leeds United": ("LEE", "#1D428A"), "Leicester City": ("LEI", "#003090"),
    "Liverpool": ("LIV", "#C8102E"), "Luton Town": ("LUT", "#F78F1E"), "Manchester City": ("MCI", "#6CABDD"),
    "Manchester United": ("MUN", "#DA291C"), "Middlesbrough": ("MID", "#E11B22"), "Newcastle United": ("NEW", "#241F20"),
    "Norwich City": ("NOR", "#00A650"), "Nottingham Forest": ("NFO", "#DD0000"), "Portsmouth": ("POR", "#001489"),
    "Queens Park Rangers": ("QPR", "#1D5BA4"), "Reading": ("REA", "#004494"), "Sheffield United": ("SHU", "#EE2737"),
    "Southampton": ("SOU", "#D71920"), "Stoke City": ("STK", "#E03A3E"), "Sunderland": ("SUN", "#EB172B"),
    "Swansea City": ("SWA", "#121212"), "Tottenham Hotspur": ("TOT", "#132257"), "Watford": ("WAT", "#FBEE23"),
    "West Bromwich Albion": ("WBA", "#122F67"), "West Ham United": ("WHU", "#7A263A"), "Wigan Athletic": ("WIG", "#1D59AF"),
    "Wolverhampton": ("WOL", "#FDB913"),
}
# Short names for small screens, as football apps use them.
SHORT = {
    "Manchester United": "Man Utd", "Manchester City": "Man City", "Tottenham Hotspur": "Spurs",
    "Wolverhampton": "Wolves", "Wolverhampton Wanderers": "Wolves", "Brighton & Hove Albion": "Brighton",
    "Brighton and Hove Albion": "Brighton", "Newcastle United": "Newcastle", "West Ham United": "West Ham",
    "Nottingham Forest": "Nott'm Forest", "Crystal Palace": "Palace", "Leeds United": "Leeds",
    "Leicester City": "Leicester", "Sheffield United": "Sheffield Utd", "West Bromwich Albion": "West Brom",
    "Queens Park Rangers": "QPR", "Huddersfield Town": "Huddersfield", "Blackburn Rovers": "Blackburn",
    "Bolton Wanderers": "Bolton", "Wigan Athletic": "Wigan", "Charlton Athletic": "Charlton",
    "Birmingham City": "Birmingham", "Cardiff City": "Cardiff", "Swansea City": "Swansea", "Stoke City": "Stoke",
    "Norwich City": "Norwich", "Derby County": "Derby", "Ipswich Town": "Ipswich", "Luton Town": "Luton",
    "Hull City": "Hull", "Coventry City": "Coventry", "Bradford City": "Bradford", "Sheffield Wednesday": "Sheffield Wed",
    "Paris Saint-Germain": "PSG", "Paris Saint-Germain FC": "PSG", "Bayer 04 Leverkusen": "Leverkusen",
    "Borussia Dortmund": "Dortmund", "Borussia Mönchengladbach": "Gladbach", "Bor. Mönchengladbach": "Gladbach",
    "Atlético Madrid": "Atlético", "Atletico Madrid": "Atlético", "Club Atlético de Madrid": "Atlético",
    "FC Internazionale Milano": "Inter", "Internazionale": "Inter", "Sporting Clube de Portugal": "Sporting",
    "Sport Lisboa e Benfica": "Benfica", "Olympique Lyonnais": "Lyon", "Olympique de Marseille": "Marseille",
}


def short_name(team: str) -> str:
    if team in SHORT:
        return SHORT[team]
    return re.sub(r"^(?:FC|AFC|AC|AS|SSC|SL|SK|FK|CF|RC|PFC)\s+|\s+(?:FC|AFC|CF|SK|BK|FK)$", "", team)


LIGHT = {"#6CABDD", "#FBEE23", "#FDB913", "#59CBE8", "#F5A12D", "#F78F1E", "#F68712"}

COMPETITION_ORDER = ["premier_league", "fa_cup", "league_cup", "champions_league", "europa_league"]
COMPETITION_NAMES = {"premier_league": "Premier League", **other_competitions.COMPETITIONS}
STATS = [("Shots", "shots"), ("Shots on target", "shots_on_target"), ("Corners", "corners"),
         ("Fouls", "fouls"), ("Yellow cards", "yellows"), ("Red cards", "reds")]
def round_name(raw: str) -> str:
    """Make round names from the different sources consistent and readable."""
    r = str(raw).strip()
    r = re.sub(r"^Finals,\s*", "", r)
    low = r.lower()
    if re.fullmatch(r"\d+", r):
        return f"Round {r}"
    if low.startswith(("group", "gruppe")):
        return "Second group stage" if low.endswith("-inter") else "Group stage"
    if low.startswith("league,"):
        return "League phase"
    m = re.fullmatch(r"q-(\d)", low)
    if m:
        return f"Qualifying round {m.group(1)}"
    return {
        "q-po": "Play-off round", "playoffs": "Play-offs", "r16": "Round of 16", "round of 16": "Round of 16",
        "qf": "Quarter-final", "quarterfinals": "Quarter-final", "quarter-final": "Quarter-final",
        "sf": "Semi-final", "s": "Semi-final", "semi": "Semi-final", "semifinals": "Semi-final", "semi-final": "Semi-final",
        "f": "Final", "final": "Final", "prelim": "Preliminary round", "sechzehntelfinale": "Round of 32",
    }.get(low, re.sub(r"^Playoffs, Matchday.*", "Play-offs", r))


def badge(team: str) -> dict:
    code, color = CLUBS.get(team, (team.replace(" ", "")[:3].upper(), "#8E8E93"))
    return {"name": team, "short": short_name(team), "code": code, "color": color, "ink": "#1D1D1F" if color in LIGHT else "#FFFFFF",
            "pl": team in CLUBS, "logo": logos.logo_url(team)}


def _num(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    return int(v) if float(v).is_integer() else float(v)


def _week_key(date: pd.Timestamp) -> pd.Timestamp:
    """Fri-Mon = one weekend round, Tue-Thu = one midweek round."""
    wd = date.weekday()
    if wd in (1, 2, 3):
        return date + pd.Timedelta(days=2 - wd)  # that week's Wednesday
    return date + pd.Timedelta(days=(5 - wd) if wd in (4, 5) else (-1 if wd == 6 else -2))  # the Saturday


class Football:
    def __init__(self, project):
        self.p = project
        f = project.features
        self.m = f.copy()
        self.m["date"] = pd.to_datetime(self.m["date"])
        self.by_id = self.m.set_index("match_id")
        preds = project.predictions[project.predictions["model"] == project.best_model]
        self.pred = preds.set_index("match_id")[["prob_H", "prob_D", "prob_A", "predicted"]]
        self._cups = None
        self._players = None
        self._rounds: dict[int, list] = {}

    # ------------------------------------------------------------------
    @property
    def cups(self) -> pd.DataFrame:
        if self._cups is None:
            self._cups = other_competitions.load_cup_matches(self.p.matches)
        return self._cups

    @property
    def players(self) -> pd.DataFrame:
        if self._players is None:
            pm = self.p.explorer.frame("players").copy()
            pm["date"] = pd.to_datetime(pm["date"])
            pm["key"] = pm["player"].str.lower()
            self._players = pm
        return self._players

    def seasons(self) -> list[str]:
        return list(dict.fromkeys(self.m["season_label"]))[::-1]

    def competitions(self, season: str) -> list[dict]:
        cups = self.cups[self.cups["season_label"] == season]
        out = [{"key": "premier_league", "name": "Premier League", "matches": int((self.m["season_label"] == season).sum())}]
        for comp in COMPETITION_ORDER[1:]:
            n = int((cups["competition"] == comp).sum())
            if n:
                out.append({"key": comp, "name": COMPETITION_NAMES[comp], "matches": n})
        return out

    # ------------------------------------------------------------------
    # Match lists
    # ------------------------------------------------------------------
    def _rounds_for(self, season: str) -> list[dict]:
        if season not in self._rounds:
            games = self.m[self.m["season_label"] == season].sort_values(["date", "home_team"])
            keys = games["date"].map(_week_key)
            rounds = []
            for key, block in games.groupby(keys, sort=True):
                rounds.append({
                    "key": key.date().isoformat(),
                    "matchweek": int(np.median(block["matchweek"])),
                    "start": block["date"].min().date().isoformat(), "end": block["date"].max().date().isoformat(),
                    "ids": block["match_id"].tolist(),
                })
            self._rounds[season] = rounds
        return self._rounds[season]

    def _card(self, r) -> dict:
        mid = int(r.match_id)
        pred = self.pred.loc[mid] if mid in self.pred.index else None
        out = {
            "id": mid, "competition": "premier_league", "date": r.date.date().isoformat(),
            "home": badge(r.home_team), "away": badge(r.away_team),
            "home_goals": _num(r.home_goals), "away_goals": _num(r.away_goals), "result": r.result,
            "ht": f"{_num(r.home_ht_goals)}-{_num(r.away_ht_goals)}" if pd.notna(r.home_ht_goals) else None,
        }
        if pred is not None:
            out["prediction"] = {"H": float(pred.prob_H), "D": float(pred.prob_D), "A": float(pred.prob_A), "pick": pred.predicted}
        return out

    def matches(self, season: str, competition: str, round_key: str | None = None) -> dict:
        if competition == "premier_league":
            rounds = self._rounds_for(season)
            if not rounds:
                raise ValueError(f"Unknown season {season!r}")
            idx = next((i for i, r in enumerate(rounds) if r["key"] == round_key), len(rounds) - 1)
            rnd = rounds[idx]
            games = self.by_id.loc[rnd["ids"]].reset_index().sort_values(["date", "home_team"])
            return {
                "competition": competition, "season": season,
                "rounds": [{k: r[k] for k in ("key", "matchweek", "start", "end")} for r in rounds],
                "round_index": idx, "matches": [self._card(r) for r in games.itertuples()],
            }
        cups = self.cups[(self.cups["season_label"] == season) & (self.cups["competition"] == competition)].copy()
        if cups.empty:
            raise ValueError("No matches for this competition and season")
        cups["round"] = cups["round"].map(round_name)
        order = list(dict.fromkeys(cups.sort_values("date")["round"]))
        rounds = [{"key": rd, "matchweek": None, "label": rd,
                   "start": cups[cups["round"] == rd]["date"].min().date().isoformat(),
                   "end": cups[cups["round"] == rd]["date"].max().date().isoformat()} for rd in order]
        idx = next((i for i, r in enumerate(rounds) if r["key"] == round_key), len(rounds) - 1)
        games = cups[cups["round"] == rounds[idx]["key"]].sort_values("date")
        return {
            "competition": competition, "season": season, "rounds": rounds, "round_index": idx,
            "matches": [{
                "id": None, "competition": competition, "date": g.date.date().isoformat(),
                "home": badge(g.home_team), "away": badge(g.away_team),
                "home_goals": _num(g.home_goals), "away_goals": _num(g.away_goals),
                "note": " · ".join(x for x in ["a.e.t." if g.extra_time else "", (f"pens {g.penalties}" if g.penalties and g.penalties[0].isdigit() else g.penalties)] if x),
            } for g in games.itertuples()],
        }

    # ------------------------------------------------------------------
    # Match centre
    # ------------------------------------------------------------------
    def _form(self, team: str, before: pd.Timestamp, n: int = 5) -> list[dict]:
        m = self.m
        games = m[((m["home_team"] == team) | (m["away_team"] == team)) & (m["date"] < before)].sort_values("date").tail(n)
        out = []
        for g in games.itertuples():
            home = g.home_team == team
            gf, ga = (g.home_goals, g.away_goals) if home else (g.away_goals, g.home_goals)
            out.append({"id": int(g.match_id), "res": "W" if gf > ga else "D" if gf == ga else "L",
                        "opponent": badge(g.away_team if home else g.home_team), "home": home,
                        "score": f"{int(g.home_goals)}-{int(g.away_goals)}", "date": g.date.date().isoformat()})
        return out

    def match(self, match_id: int) -> dict:
        if match_id not in self.by_id.index:
            raise ValueError(f"Unknown match {match_id}")
        r = self.by_id.loc[match_id]
        stats = [{"label": label, "home": _num(r[f"home_{k}"]), "away": _num(r[f"away_{k}"])} for label, k in STATS]
        m = self.m
        pair = {r.home_team, r.away_team}
        h2h = m[(m["home_team"].isin(pair)) & (m["away_team"].isin(pair)) & (m["date"] < r.date)].sort_values("date").tail(6)
        out = {
            "card": self._card(next(self.by_id.loc[[match_id]].reset_index().itertuples())),
            "season": r.season_label, "referee": None if pd.isna(r.referee) else r.referee,
            "stats": stats,
            "before": {
                "elo": {"home": float(r.home_elo), "away": float(r.away_elo)},
                "position": {"home": _num(r.home_position), "away": _num(r.away_position)},
                "form": {"home": self._form(r.home_team, r.date), "away": self._form(r.away_team, r.date)},
            },
            "h2h": [{"id": int(g.match_id), "date": g.date.date().isoformat(), "season": g.season_label,
                     "home": badge(g.home_team), "away": badge(g.away_team),
                     "home_goals": int(g.home_goals), "away_goals": int(g.away_goals)} for g in h2h.iloc[::-1].itertuples()],
            "bookmaker": None if pd.isna(r.book_prob_H) else {"H": float(r.book_prob_H), "D": float(r.book_prob_D), "A": float(r.book_prob_A)},
            "lineups": None,
        }
        if r.season >= players.FIRST_FPL_SEASON:
            pm = self.players[self.players["match_id"] == match_id]
            if len(pm):
                out["lineups"] = {side: self._lineup(pm[pm["team"] == team]) for side, team in (("home", r.home_team), ("away", r.away_team))}
        return out

    def _lineup(self, rows: pd.DataFrame) -> dict:
        def player(p):
            return {"name": p.name, "short": p.short_name if isinstance(p.short_name, str) else p.player.split()[-1],
                    "key": p.key, "position": p.position, "minutes": int(p.minutes), "goals": int(p.goals_scored),
                    "assists": int(p.assists), "yellow": int(p.yellow_cards), "red": int(p.red_cards),
                    "points": int(p.total_points), "influence": float(p.influence)}
        order = {"GK": 0, "DEF": 1, "MID": 2, "FWD": 3}
        rows = rows[rows["position"] != "MGR"]
        xi = rows[rows["starter"]].assign(o=lambda d: d["position"].map(order)).sort_values(["o", "influence"], ascending=[True, False])
        subs = rows[(~rows["starter"]) & (rows["minutes"] > 0)].sort_values("minutes", ascending=False)
        lines = [xi[xi["position"] == pos] for pos in ("GK", "DEF", "MID", "FWD")]
        formation = "-".join(str(len(l)) for l in lines[1:] if len(l))
        best = xi.sort_values("total_points", ascending=False).head(1)
        return {"formation": formation, "lines": [[player(p) for p in l.itertuples()] for l in lines],
                "subs": [player(p) for p in subs.itertuples()],
                "best": player(next(best.itertuples())) if len(best) else None}

    # ------------------------------------------------------------------
    # League table with form
    # ------------------------------------------------------------------
    def table(self, season: str) -> dict:
        games = self.m[self.m["season_label"] == season].sort_values("date")
        if games.empty:
            raise ValueError(f"Unknown season {season!r}")
        from .api import league_table

        table = league_table(games)
        for row in table:
            row["team"] = badge(row["team"])
            row["form"] = [f["res"] for f in self._form(row["team"]["name"], games["date"].max() + pd.Timedelta(days=1))]
        return {"season": season, "table": table, "teams": len(table)}

    # ------------------------------------------------------------------
    # Team page
    # ------------------------------------------------------------------
    def team(self, name: str, season: str) -> dict:
        m = self.m
        league = m[(m["season_label"] == season) & ((m["home_team"] == name) | (m["away_team"] == name))].sort_values("date")
        if league.empty:
            raise ValueError(f"{name} did not play in the Premier League in {season}")
        table = {r["team"]["name"]: r for r in self.table(season)["table"]}
        row = table[name]
        results = [{**self._card(g), "competition_name": "Premier League"} for g in league.itertuples()]
        cups = self.cups[(self.cups["season_label"] == season) & ((self.cups["home_team"] == name) | (self.cups["away_team"] == name))]
        for g in cups.itertuples():
            results.append({"id": None, "competition": g.competition, "competition_name": g.competition_name,
                            "round": round_name(g.round), "date": g.date.date().isoformat(),
                            "home": badge(g.home_team), "away": badge(g.away_team),
                            "home_goals": _num(g.home_goals), "away_goals": _num(g.away_goals)})
        results.sort(key=lambda x: x["date"])
        elo = [{"date": g.date.date().isoformat(), "elo": round(float(g.home_elo if g.home_team == name else g.away_elo), 1)} for g in league.itertuples()]
        seasons = sorted(set(m.loc[(m["home_team"] == name), "season_label"]))
        top, manager = [], None
        if int(season[:4]) >= players.FIRST_FPL_SEASON:
            pm = self.players[(self.players["season_label"] == season) & (self.players["team"] == name)]
            mgr = pm[pm["position"] == "MGR"]
            if len(mgr):
                manager = mgr.groupby("player")["minutes"].size().idxmax()
            top = self._player_rows(pm[pm["position"] != "MGR"]).head(8).to_dict(orient="records")
        return {"team": badge(name), "season": season, "seasons": seasons[::-1], "row": row,
                "results": results, "elo": elo, "top_players": top, "manager": manager,
                "manager_note": "Managers are only in the data for 2024-25 (from FPL's Assistant Manager game)."}

    # ------------------------------------------------------------------
    # Players
    # ------------------------------------------------------------------
    @staticmethod
    def _player_rows(pm: pd.DataFrame) -> pd.DataFrame:
        if pm.empty:
            return pd.DataFrame(columns=["key", "name", "full_name", "team", "position", "apps", "starts", "minutes", "goals", "assists", "clean_sheets", "points", "influence", "price"])
        g = pm.sort_values("date").groupby("key")
        out = pd.DataFrame({
            "name": g["name"].last(), "full_name": g["player"].last(), "team": g["team"].last(), "position": g["position"].last(),
            "apps": g["minutes"].apply(lambda s: int((s > 0).sum())), "starts": g["starter"].sum().astype(int),
            "minutes": g["minutes"].sum().astype(int), "goals": g["goals_scored"].sum().astype(int),
            "assists": g["assists"].sum().astype(int), "clean_sheets": g["clean_sheets"].sum().astype(int),
            "points": g["total_points"].sum().astype(int),
            "influence": (g["influence"].sum() / g["minutes"].sum().replace(0, np.nan) * 90).round(1).fillna(0),
            "price": (g["price_m"].last()).round(1),
        }).reset_index()
        out["team_badge"] = out["team"].map(badge)
        return out.sort_values(["points", "minutes"], ascending=False)

    def player_list(self, season: str, team: str = "", position: str = "", q: str = "", sort: str = "points",
                    page: int = 0, size: int = 30) -> dict:
        pm = self.players[(self.players["season_label"] == season) & (self.players["position"] != "MGR")]
        if team:
            pm = pm[pm["team"] == team]
        if position:
            pm = pm[pm["position"] == position]
        rows = self._player_rows(pm)
        rows = rows[rows["apps"] > 0]
        if q:
            hit = lambda col: rows[col].str.lower().str.contains(q.lower(), regex=False)
            rows = rows[hit("name") | hit("full_name")]
        if sort in rows.columns:
            rows = rows.sort_values([sort, "minutes"], ascending=False)
        total = len(rows)
        chunk = rows.iloc[page * size:(page + 1) * size]
        seasons = sorted(self.players["season_label"].unique())[::-1]
        teams = sorted(self.players.loc[self.players["season_label"] == season, "team"].unique())
        return {"season": season, "seasons": seasons, "teams": teams, "total": total, "page": page, "size": size,
                "players": chunk.replace({np.nan: None}).to_dict(orient="records")}

    def player(self, key: str) -> dict:
        pm = self.players[(self.players["key"] == key) & (self.players["position"] != "MGR")]
        if pm.empty:
            raise ValueError(f"Unknown player {key!r}")
        by_season = []
        for season, rows in pm.groupby("season_label"):
            r = self._player_rows(rows).iloc[0].to_dict()
            r["season"] = season
            by_season.append(r)
        recent = pm.sort_values("date").tail(12).iloc[::-1]
        games = []
        for g in recent.itertuples():
            mr = self.by_id.loc[g.match_id] if g.match_id in self.by_id.index else None
            if mr is None:
                continue
            home = mr.home_team == g.team
            games.append({"id": int(g.match_id), "date": g.date.date().isoformat(), "home": home,
                          "opponent": badge(mr.away_team if home else mr.home_team),
                          "score": f"{int(mr.home_goals)}-{int(mr.away_goals)}",
                          "res": ("W" if (mr.home_goals > mr.away_goals) == home and mr.home_goals != mr.away_goals else "D" if mr.home_goals == mr.away_goals else "L"),
                          "minutes": int(g.minutes), "goals": int(g.goals_scored), "assists": int(g.assists),
                          "points": int(g.total_points)})
        trend = pm.sort_values("date").groupby("season_label").apply(
            lambda d: float(d["influence"].sum() / max(d["minutes"].sum(), 1) * 90), include_groups=False)
        last = pm.sort_values("date").iloc[-1]
        return {"key": key, "name": last["name"], "full_name": last.player, "team": badge(last.team), "position": last.position,
                "price": round(float(last.price_m), 1), "seasons": by_season[::-1], "recent": games,
                "influence_by_season": [{"season": s, "influence": round(v, 1)} for s, v in trend.items()],
                "career": {k: int(sum(s[k] for s in by_season)) for k in ("apps", "minutes", "goals", "assists", "points")}}
