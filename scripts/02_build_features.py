"""Step 2: compute the pre-match features -> data/processed/features.csv

Run:  uv run python scripts/02_build_features.py
"""

from eplpred import data, features

if __name__ == "__main__":
    feats = features.save_features(data.load_matches())
    cols = features.feature_columns()
    print(f"Built {len(cols)} features for {len(feats):,} matches -> data/processed/features.csv")
    example = feats[(feats["season_label"] == "2019-20") & (feats["home_team"] == "Liverpool")].iloc[-1]
    print(f"\nExample: {example['home_team']} vs {example['away_team']} on {example['date'].date()}")
    print(example[["home_elo", "away_elo", "home_form5_ppg", "away_form5_ppg", "home_position", "away_position"]].to_string())
