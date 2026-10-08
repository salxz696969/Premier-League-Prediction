"""Predict any fixture between two teams from the latest season.

Run:  uv run python scripts/predict_match.py "Arsenal" "Chelsea"
      uv run python scripts/predict_match.py --list        (show team names)
"""

import sys

from eplpred import data
from eplpred.predict import Predictor, current_teams

if __name__ == "__main__":
    matches = data.load_matches()
    if len(sys.argv) != 3:
        print(__doc__)
        print("Teams:", ", ".join(current_teams(matches)))
        sys.exit(0 if "--list" in sys.argv else 1)
    print("Training the final model on all seasons ...\n")
    print(Predictor(matches).predict(sys.argv[1], sys.argv[2]))
