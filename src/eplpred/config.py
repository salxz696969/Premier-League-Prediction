"""Project-wide settings: paths, seasons, data sources and team-name aliases.

Everything that you might want to change for an experiment lives here, so the
rest of the code never hard-codes a path or a magic number.
"""

from pathlib import Path

# --------------------------------------------------------------------------
# Paths (all relative to the repository root, so the project runs anywhere)
# --------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
REPORTS_DIR = ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"

MATCHES_CSV = PROCESSED_DIR / "matches.csv"
FEATURES_CSV = PROCESSED_DIR / "features.csv"
PREDICTIONS_CSV = REPORTS_DIR / "predictions.csv"
RESULTS_CSV = REPORTS_DIR / "results_overall.csv"
RESULTS_BY_SEASON_CSV = REPORTS_DIR / "results_by_season.csv"

# --------------------------------------------------------------------------
# Seasons. A season is named by the year it starts in: 2019 -> "2019-20".
# --------------------------------------------------------------------------
FIRST_SEASON = 2000
LAST_SEASON = 2025  # 2025-26 is the last complete season in the source data

# Walk-forward evaluation: each of these seasons is predicted by a model that
# was trained only on the seasons before it.
FIRST_TEST_SEASON = 2014
# The first season is only used to "warm up" Elo ratings and rolling form.
FIRST_TRAIN_SEASON = 2001

# --------------------------------------------------------------------------
# Data sources (see SOURCES.md for full citations and licences)
# --------------------------------------------------------------------------
# 1) Football-Data.co.uk results + match statistics, via the DataHub mirror
#    on GitHub (Public Domain Dedication and License, PDDL v1.0).
FOOTBALL_DATA_URL = (
    "https://raw.githubusercontent.com/datasets/football-datasets/main/"
    "datasets/premier-league/season-{code}.csv"
)
# 2) "Club Football Match Data (2000-2025)" by Adam Gabor (MIT licence).
#    Also built from Football-Data.co.uk; we only use it for Bet365 odds,
#    which are the bookmaker benchmark (never a model input).
ODDS_URL = (
    "https://raw.githubusercontent.com/xgabora/"
    "Club-Football-Match-Data-2000-2025/main/data/Matches.csv"
)

# --------------------------------------------------------------------------
# Team names: the sources abbreviate names, we show full names everywhere.
# --------------------------------------------------------------------------
TEAM_ALIASES = {
    "Man City": "Manchester City",
    "Man United": "Manchester United",
    "Nott'm Forest": "Nottingham Forest",
    "Nottm Forest": "Nottingham Forest",
    "Newcastle": "Newcastle United",
    "Tottenham": "Tottenham Hotspur",
    "West Ham": "West Ham United",
    "West Brom": "West Bromwich Albion",
    "Wolves": "Wolverhampton",
    "Sheffield United": "Sheffield United",
    "Sheffield Weds": "Sheffield Wednesday",
    "QPR": "Queens Park Rangers",
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
    "Birmingham": "Birmingham City",
    "Blackburn": "Blackburn Rovers",
    "Bolton": "Bolton Wanderers",
    "Bradford": "Bradford City",
    "Charlton": "Charlton Athletic",
    "Coventry": "Coventry City",
    "Derby": "Derby County",
    "Wigan": "Wigan Athletic",
}

# --------------------------------------------------------------------------
# Modelling settings
# --------------------------------------------------------------------------
RANDOM_STATE = 42
OUTCOMES = ["H", "D", "A"]  # home win, draw, away win (column order everywhere)
