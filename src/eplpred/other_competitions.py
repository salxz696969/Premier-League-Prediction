"""Other competitions: FA Cup, League Cup, Champions League, Europa League
and international breaks.

We only need *when* each Premier League team played, to measure fatigue and
fixture congestion. Results of these matches are not used.

Sources (see SOURCES.md):
* engsoccerdata (James Curley, GPL-2 or later): FA Cup and League Cup up to 2018-19,
  European Cup / Champions League up to 2015-16.
* openfootball (CC0): Champions League 2011-12 onwards, Europa
  League 2020-21 onwards, FA Cup and EFL Cup 2018-19 onwards.
* martj42/international_results (CC0): every men's international match,
  used to find international breaks.
"""

from __future__ import annotations

import io
import re
import urllib.error
import urllib.request

import pandas as pd

from . import config

RAW = config.RAW_DIR / "other_competitions"
ENGSOCCER_URL = "https://raw.githubusercontent.com/jalapic/engsoccerdata/master/data-raw/{name}.csv"
OPENFOOTBALL_EUROPE = "https://raw.githubusercontent.com/openfootball/champions-league/master/{season}/{file}.txt"
OPENFOOTBALL_ENGLAND = "https://raw.githubusercontent.com/openfootball/england/master/{season}/{file}.txt"
INTERNATIONALS_URL = "https://raw.githubusercontent.com/martj42/international_results/master/results.csv"

COMPETITIONS = {
    "fa_cup": "FA Cup",
    "league_cup": "League Cup",
    "champions_league": "Champions League",
    "europa_league": "Europa League",
}
EUROPEAN = {"champions_league", "europa_league"}

# Names in the cup files -> our names (after the generic clean-up below).
NAME_FIXES = {
    "wolverhampton wanderers": "Wolverhampton",
    "wolves": "Wolverhampton",
    "bournemouth": "Bournemouth",
    "brighton hove albion": "Brighton & Hove Albion",
    "brighton": "Brighton & Hove Albion",
    "manchester utd": "Manchester United",
    "man united": "Manchester United",
    "man city": "Manchester City",
    "spurs": "Tottenham Hotspur",
    "tottenham": "Tottenham Hotspur",
    "newcastle": "Newcastle United",
    "west ham": "West Ham United",
    "west brom": "West Bromwich Albion",
    "sheffield utd": "Sheffield United",
    "nottm forest": "Nottingham Forest",
    "qpr": "Queens Park Rangers",
}


def season_label(year: int) -> str:
    return f"{year}-{(year + 1) % 100:02d}"


# --------------------------------------------------------------------------
# Download (files are kept in data/raw/other_competitions/ for offline use)
# --------------------------------------------------------------------------
def _get(url: str) -> bytes | None:
    try:
        with urllib.request.urlopen(url, timeout=120) as response:
            return response.read()
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise


def download(force: bool = False) -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    for name in ("facup", "leaguecup", "champs"):
        path = RAW / "engsoccerdata" / f"{name}.csv"
        if path.exists() and not force:
            continue
        print(f"Downloading engsoccerdata {name} ...")
        path.parent.mkdir(parents=True, exist_ok=True)
        df = pd.read_csv(io.BytesIO(_get(ENGSOCCER_URL.format(name=name))), low_memory=False)
        df[df["Season"] >= config.FIRST_SEASON - 1].to_csv(path, index=False)

    for year in range(config.FIRST_SEASON, config.LAST_SEASON + 1):
        season = season_label(year)
        for url, file in [
            (OPENFOOTBALL_EUROPE, "cl"),
            (OPENFOOTBALL_EUROPE, "el"),
            (OPENFOOTBALL_ENGLAND, "facup"),
            (OPENFOOTBALL_ENGLAND, "eflcup"),
        ]:
            path = RAW / "openfootball" / season / f"{file}.txt"
            missing_marker = path.with_suffix(".missing")
            if (path.exists() or missing_marker.exists()) and not force:
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            content = _get(url.format(season=season, file=file))
            if content is None:
                missing_marker.write_text("not available in openfootball\n")
            else:
                print(f"Downloading openfootball {season}/{file} ...")
                path.write_bytes(content)

    path = RAW / "internationals" / "results.csv"
    if not path.exists() or force:
        print("Downloading international results ...")
        path.parent.mkdir(parents=True, exist_ok=True)
        df = pd.read_csv(io.BytesIO(_get(INTERNATIONALS_URL)))
        df[df["date"] >= f"{config.FIRST_SEASON}-07-01"].to_csv(path, index=False)


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------
def clean_name(name: str) -> str:
    """'Arsenal FC (ENG)' -> 'arsenal', 'AFC Bournemouth' -> 'bournemouth'."""
    name = re.sub(r"\([A-Z]{3}\)", "", str(name))
    name = name.replace("&", " ").replace("'", "").replace(".", " ")
    words = [w for w in name.lower().split() if w not in {"fc", "afc"}]
    return " ".join(words)


def to_premier_league_name(name: str, pl_teams: dict[str, str]) -> str | None:
    """Map a cup-file name to our Premier League name, or None if not a PL club."""
    key = clean_name(name)
    if key in NAME_FIXES:
        return NAME_FIXES[key]
    return pl_teams.get(key)


_DATE2 = re.compile(r"^\s*(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun) ([A-Z][a-z]{2}) ([0-9]{1,2})(?: ([0-9]{4}))?\s*$")
_MONTHS = {m: i for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}


_SCORE = re.compile(r"(?:(\d+)-(\d+) pen\.\s+)?(\d+)-(\d+)(\s+a\.e\.t\.)?")


def parse_openfootball_full(text: str, start_year: int) -> list[dict]:
    """Every match line of a football.txt file: date, round, teams and score.

    Score formats: "2-1 (1-0)", "4-1 a.e.t. (3-1, 1-0)" (after extra time),
    "4-3 pen. 1-0 a.e.t." (1-0 after extra time, 4-3 on penalties).
    """
    games = []
    date, round_name = None, ""
    for line in text.splitlines():
        if line.startswith("▪"):
            round_name = line.lstrip("▪ ").strip()
            continue
        m = _DATE2.match(line)
        if m:
            month, day, year = _MONTHS[m.group(1)], int(m.group(2)), m.group(3)
            year = int(year) if year else (start_year if month >= 7 else start_year + 1)
            date = pd.Timestamp(year=year, month=month, day=day)
            continue
        if date is None or " v " not in line:
            continue
        body = re.sub(r"^\s*\d{1,2}[.:]\d{2}\s+", "", line).strip()
        home, rest = body.split(" v ", 1)
        parts = re.split(r"\s{2,}", rest.strip(), maxsplit=1)
        away = re.split(r"\s+\d+-\d+|\s+@", parts[0])[0].strip()
        tail = rest[len(away):].strip() if len(parts) == 1 else parts[1]
        score = _SCORE.match(tail.strip()) if tail else None
        games.append({
            "date": date, "round": round_name, "home": home.strip(), "away": away,
            "home_goals": int(score.group(3)) if score else None,
            "away_goals": int(score.group(4)) if score else None,
            "extra_time": bool(score and score.group(5)),
            "penalties": f"{score.group(1)}-{score.group(2)}" if score and score.group(1) else "",
        })
    return games


def parse_openfootball(text: str, start_year: int) -> list[tuple[pd.Timestamp, str, str]]:
    """Return (date, home, away) for every match line in a football.txt file."""
    return [(g["date"], g["home"], g["away"]) for g in parse_openfootball_full(text, start_year)]


def display_club(name: str) -> str:
    """'Bayern München (GER)' -> 'Bayern München'."""
    return re.sub(r"\s*\([A-Z]{3}\)", "", str(name)).strip()


def load_cup_matches(matches: pd.DataFrame) -> pd.DataFrame:
    """Full cup and European matches (round, both teams, score) involving
    a Premier League club of that season. Used by the match centre."""
    rows = []
    for year in range(config.FIRST_SEASON, config.LAST_SEASON + 1):
        season = matches[matches["season"] == year]
        pl = {clean_name(t): t for t in set(season["home_team"]) | set(season["away_team"])}
        start, end = pd.Timestamp(f"{year}-07-01"), pd.Timestamp(f"{year + 1}-06-30")
        games = []
        for name, comp, use in [("facup", "fa_cup", year <= 2017), ("leaguecup", "league_cup", year <= 2017),
                                ("champs", "champions_league", year <= 2010)]:
            if not use:
                continue
            df = _engsoccer(name)
            df = df[df["Season"] == year]
            for r in df.itertuples(index=False):
                hg, ag = (r.hgoal, r.vgoal) if hasattr(r, "hgoal") else (None, None)
                if hg is None or pd.isna(hg):
                    ft = str(getattr(r, "FT", ""))
                    hg, ag = (int(ft.split("-")[0]), int(ft.split("-")[1])) if "-" in ft else (None, None)
                aet = str(getattr(r, "aet", "")).lower() in ("yes", "true", "1")
                pens = getattr(r, "pens", "")
                games.append((comp, {"date": pd.Timestamp(r.Date), "round": str(r.round),
                                     "home": r.home, "away": r.visitor, "home_goals": hg, "away_goals": ag,
                                     "extra_time": aet, "penalties": "" if pd.isna(pens) else str(pens)}))
        for file, comp in [("cl", "champions_league"), ("el", "europa_league"), ("facup", "fa_cup"), ("eflcup", "league_cup")]:
            if (comp == "champions_league" and year <= 2010) or (comp in ("fa_cup", "league_cup") and year <= 2017):
                continue
            path = RAW / "openfootball" / season_label(year) / f"{file}.txt"
            if path.exists():
                games += [(comp, g) for g in parse_openfootball_full(path.read_text(encoding="utf-8"), year)]
        for comp, g in games:
            if not (start <= g["date"] <= end):
                continue
            home_pl, away_pl = to_premier_league_name(g["home"], pl), to_premier_league_name(g["away"], pl)
            home_pl = home_pl if home_pl in pl.values() else None
            away_pl = away_pl if away_pl in pl.values() else None
            if not (home_pl or away_pl):
                continue
            rows.append({
                "season": year, "season_label": season_label(year), "competition": comp,
                "competition_name": COMPETITIONS[comp], "round": g["round"], "date": g["date"],
                "home_team": home_pl or display_club(g["home"]), "away_team": away_pl or display_club(g["away"]),
                "home_is_pl": bool(home_pl), "away_is_pl": bool(away_pl),
                "home_goals": g["home_goals"], "away_goals": g["away_goals"],
                "extra_time": g["extra_time"], "penalties": g["penalties"],
            })
    out = pd.DataFrame(rows).drop_duplicates(["date", "competition", "home_team", "away_team"])
    return out.sort_values(["date", "competition"]).reset_index(drop=True)


def load_other_matches(matches: pd.DataFrame) -> pd.DataFrame:
    """All non-league matches of Premier League teams: date, team, competition.

    ``matches`` (our league table) tells us which clubs were in the Premier
    League in each season, so we only keep those.
    """
    rows = []
    for year in range(config.FIRST_SEASON, config.LAST_SEASON + 1):
        season = matches[matches["season"] == year]
        pl = {clean_name(t): t for t in set(season["home_team"]) | set(season["away_team"])}
        start, end = pd.Timestamp(f"{year}-07-01"), pd.Timestamp(f"{year + 1}-06-30")

        sources = []
        # engsoccerdata (CSV) for the seasons openfootball doesn't cover
        for name, comp, use in [
            ("facup", "fa_cup", year <= 2017),
            ("leaguecup", "league_cup", year <= 2017),
            ("champs", "champions_league", year <= 2010),
        ]:
            if use:
                df = _engsoccer(name)
                df = df[df["Season"] == year]
                sources.append((comp, list(zip(pd.to_datetime(df["Date"]), df["home"], df["visitor"]))))
        # openfootball (text) for recent seasons
        for file, comp in [("cl", "champions_league"), ("el", "europa_league"), ("facup", "fa_cup"), ("eflcup", "league_cup")]:
            if comp == "champions_league" and year <= 2010:
                continue
            if comp in ("fa_cup", "league_cup") and year <= 2017:
                continue
            path = RAW / "openfootball" / season_label(year) / f"{file}.txt"
            if path.exists():
                sources.append((comp, parse_openfootball(path.read_text(encoding="utf-8"), year)))

        for comp, games in sources:
            for date, home, away in games:
                if not (start <= date <= end):
                    continue
                for side in (home, away):
                    team = to_premier_league_name(side, pl)
                    if team in pl.values():
                        rows.append({"season": year, "date": date, "team": team, "competition": comp})
    out = pd.DataFrame(rows).drop_duplicates()
    return out.sort_values(["team", "date"]).reset_index(drop=True)


_ENGSOCCER_CACHE: dict[str, pd.DataFrame] = {}


def _engsoccer(name: str) -> pd.DataFrame:
    if name not in _ENGSOCCER_CACHE:
        _ENGSOCCER_CACHE[name] = pd.read_csv(RAW / "engsoccerdata" / f"{name}.csv", low_memory=False)
    return _ENGSOCCER_CACHE[name]


def international_dates() -> pd.DatetimeIndex:
    """Days with many senior international matches = international windows.

    Big summer tournaments are excluded: we only want the breaks *during*
    the Premier League season.
    """
    df = pd.read_csv(RAW / "internationals" / "results.csv", parse_dates=["date"])
    df = df[df["date"].dt.month.isin([8, 9, 10, 11, 12, 1, 2, 3, 4, 5])]
    per_day = df.groupby("date").size()
    return pd.DatetimeIndex(per_day[per_day >= 10].index)


def coverage(other: pd.DataFrame) -> pd.DataFrame:
    """Number of matches of PL teams found per season and competition."""
    table = other.pivot_table(index="season", columns="competition", values="team", aggfunc="size", fill_value=0)
    table.index = [season_label(s) for s in table.index]
    return table.reindex(columns=list(COMPETITIONS), fill_value=0)
