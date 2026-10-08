"""Step 3: walk-forward evaluation of every model on 12 test seasons.

For each season from 2014-15 to 2025-26 the models are trained on all
earlier seasons and then predict that season. Writes:
  reports/predictions.csv          every prediction of every model
  reports/results_overall.csv      metrics per model over all test seasons
  reports/results_by_season.csv    metrics per model per season

Run:  uv run python scripts/03_evaluate_models.py      (takes a few minutes)
"""

import pandas as pd

from eplpred import config, evaluation, features
from eplpred.models import make_models

pd.set_option("display.width", 140)

if __name__ == "__main__":
    feats = features.load_features()
    print("Walk-forward evaluation:")
    predictions = evaluation.walk_forward(feats, make_models())
    predictions.to_csv(config.PREDICTIONS_CSV, index=False)

    overall = evaluation.summarise(predictions)
    by_season = evaluation.summarise(predictions, by=["season_label"])
    overall.to_csv(config.RESULTS_CSV, index=False)
    by_season.to_csv(config.RESULTS_BY_SEASON_CSV, index=False)

    print("\nResults over all test seasons (sorted by RPS, lower is better):")
    print(overall.round(4).to_string(index=False))
