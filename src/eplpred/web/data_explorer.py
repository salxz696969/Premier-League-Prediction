"""Browse every dataset behind the project, row by row (the "Data" page).

Each dataset is loaded the first time someone opens it, then kept in memory.
Filtering, sorting and paging happen here on the server, so even the
250,000-row player table stays fast in the browser.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

from .. import config, data, features, other_competitions, players

PAGE_SIZES = (25, 50, 100, 250)


@dataclass
class Dataset:
    key: str
    name: str
    description: str
    source: str
    source_url: str
    licence: str
    kind: str  # "raw" (as downloaded) or "derived" (built by this project)
    loader: Callable[[], pd.DataFrame]
    file: str


def _raw_football_data() -> pd.DataFrame:
    frames = []
    for year in range(config.FIRST_SEASON, config.LAST_SEASON + 1):
        df = pd.read_csv(config.RAW_DIR / "football-data" / f"season-{data.season_code(year)}.csv")
        df.insert(0, "Season", data.season_label(year))
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def _players() -> pd.DataFrame:
    pm = players.load_player_matches(data.load_matches())
    pm.insert(pm.columns.get_loc("player"), "name", pm["player"].map(players.nice_name))
    pm["player"] = pm["player"].map(players.display_name)
    pm["value"] = pm["value"] / 10
    pm.insert(1, "season_label", pm["season"].map(data.season_label))
    return pm.rename(columns={"value": "price_m"})


def _other() -> pd.DataFrame:
    other = other_competitions.load_other_matches(data.load_matches())
    other.insert(1, "season_label", other["season"].map(data.season_label))
    other["competition"] = other["competition"].map(other_competitions.COMPETITIONS)
    return other


def _odds() -> pd.DataFrame:
    odds = pd.read_csv(config.RAW_DIR / "odds" / "epl_odds.csv")
    start = pd.to_datetime(odds["MatchDate"]).map(lambda d: d.year if d.month >= 7 else d.year - 1)
    odds.insert(0, "Season", start.map(data.season_label))
    return odds


def _internationals() -> pd.DataFrame:
    return pd.read_csv(config.RAW_DIR / "other_competitions" / "internationals" / "results.csv")


DATASETS = [
    Dataset("matches", "Premier League matches",
            "One row per match, 2000-01 to 2025-26: score, shots, shots on target, corners, fouls, cards, referee, and the bookmaker's probabilities. Cleaned and checked from the raw files below.",
            "Football-Data.co.uk (via DataHub) + Bet365 odds", "https://www.football-data.co.uk/englandm.php",
            "PDDL / free to download", "derived", data.load_matches, "data/processed/matches.csv"),
    Dataset("football_data_raw", "Raw season files",
            "The 26 season files exactly as downloaded, original column names (FTHG = full-time home goals, HST = home shots on target, ...).",
            "Football-Data.co.uk via DataHub football-datasets", "https://github.com/datasets/football-datasets",
            "PDDL v1.0", "raw", _raw_football_data, "data/raw/football-data/season-*.csv"),
    Dataset("odds", "Bookmaker odds",
            "Bet365 pre-match decimal odds for home win, draw and away win. Only used as a benchmark, never as a model input.",
            "Club Football Match Data (Adam Gábor)", "https://github.com/xgabora/Club-Football-Match-Data-2000-2025",
            "MIT", "raw", _odds, "data/raw/odds/epl_odds.csv"),
    Dataset("players", "FPL player data",
            "One row per player per match, 2016-17 to 2025-26: minutes, starter or not, FPL influence, creativity, threat, ICT index and price.",
            "Fantasy Premier League data (Vaastav Anand)", "https://github.com/vaastav/Fantasy-Premier-League",
            "MIT", "raw", _players, "data/raw/players/fpl_*.csv.gz"),
    Dataset("other_competitions", "Cup and European matches",
            "Every FA Cup, League Cup, Champions League and Europa League match of Premier League clubs (dates, for fatigue).",
            "engsoccerdata + openfootball", "https://github.com/openfootball",
            "GPL-2+ / CC0", "derived", _other, "data/raw/other_competitions/"),
    Dataset("internationals", "International matches",
            "Every men's international match since July 2000, used to find international breaks.",
            "International football results (Mart Jürisoo)", "https://github.com/martj42/international_results",
            "CC0", "raw", _internationals, "data/raw/other_competitions/internationals/results.csv"),
    Dataset("features", "Model inputs (features)",
            "What the model sees for each match: 49 base features (Elo, form, league position, ...) all calculated from earlier matches only.",
            "Built by this project from the match data", "", "", "derived",
            features.load_features, "data/processed/features.csv"),
    Dataset("predictions", "Model predictions",
            "Every prediction made in the walk-forward test (2014-15 to 2025-26), for every model, next to the real result.",
            "Built by this project", "", "", "derived",
            lambda: pd.read_csv(config.PREDICTIONS_CSV), "reports/predictions.csv"),
]

TEAM_COLUMNS = ["home_team", "away_team", "team", "HomeTeam", "AwayTeam", "opponent"]
SEASON_COLUMNS = ["season_label", "Season"]


class DataExplorer:
    def __init__(self):
        self._cache: dict[str, pd.DataFrame] = {}
        self.by_key = {d.key: d for d in DATASETS}

    def frame(self, key: str) -> pd.DataFrame:
        if key not in self.by_key:
            raise ValueError(f"Unknown dataset {key!r}")
        if key not in self._cache:
            df = self.by_key[key].loader()
            for col in df.columns:
                if pd.api.types.is_datetime64_any_dtype(df[col]):
                    df[col] = df[col].dt.strftime("%Y-%m-%d")
            self._cache[key] = df.reset_index(drop=True)
        return self._cache[key]

    def catalogue(self) -> dict:
        return {"datasets": [
            {"key": d.key, "name": d.name, "description": d.description, "source": d.source,
             "source_url": d.source_url, "licence": d.licence, "kind": d.kind, "file": d.file}
            for d in DATASETS
        ]}

    def _filtered(self, key: str, q: dict) -> pd.DataFrame:
        df = self.frame(key)
        mask = np.ones(len(df), dtype=bool)
        season = (q.get("season") or [""])[0]
        if season:
            col = next((c for c in SEASON_COLUMNS if c in df.columns), None)
            if col:
                mask &= (df[col].astype(str) == season).to_numpy()
        team = (q.get("team") or [""])[0]
        if team:
            cols = [c for c in TEAM_COLUMNS if c in df.columns]
            if cols:
                team_mask = np.zeros(len(df), dtype=bool)
                for c in cols:
                    team_mask |= (df[c].astype(str) == team).to_numpy()
                mask &= team_mask
        search = (q.get("q") or [""])[0].strip().lower()
        if search:
            text_mask = np.zeros(len(df), dtype=bool)
            for c in df.columns:
                if df[c].dtype == object or pd.api.types.is_string_dtype(df[c]):
                    text_mask |= df[c].astype(str).str.lower().str.contains(search, regex=False, na=False).to_numpy()
            mask &= text_mask
        out = df[mask]
        sort = (q.get("sort") or [""])[0]
        if sort in out.columns:
            out = out.sort_values(sort, ascending=(q.get("dir") or ["asc"])[0] != "desc", kind="stable", na_position="last")
        return out

    def page(self, key: str, q: dict) -> dict:
        df = self.frame(key)
        out = self._filtered(key, q)
        size = int((q.get("size") or [50])[0])
        size = size if size in PAGE_SIZES else 50
        pages = max(1, -(-len(out) // size))
        page = min(max(0, int((q.get("page") or [0])[0])), pages - 1)
        chunk = out.iloc[page * size:(page + 1) * size]
        season_col = next((c for c in SEASON_COLUMNS if c in df.columns), None)
        team_cols = [c for c in TEAM_COLUMNS if c in df.columns]
        teams = sorted(set().union(*[set(df[c].dropna().astype(str)) for c in team_cols])) if team_cols else []
        return {
            "key": key,
            "columns": [{"name": c, "numeric": bool(pd.api.types.is_numeric_dtype(df[c]))} for c in df.columns],
            "rows": chunk.replace({np.nan: None}).to_numpy().tolist(),
            "total": int(len(df)), "matching": int(len(out)),
            "page": page, "pages": pages, "size": size,
            "seasons": list(dict.fromkeys(df[season_col].astype(str))) if season_col else [],
            "teams": teams if len(teams) <= 400 else [],
        }

    def csv(self, key: str, q: dict) -> bytes:
        buffer = io.StringIO()
        self._filtered(key, q).to_csv(buffer, index=False)
        return buffer.getvalue().encode("utf-8")
