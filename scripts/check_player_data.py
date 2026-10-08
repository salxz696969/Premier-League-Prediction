"""How good is "the 11 players with the most minutes" as a stand-in for the
real starting eleven? Checked on matches where FPL recorded real starts.

Run:  uv run python scripts/check_player_data.py
"""

import pandas as pd

from eplpred import players

if __name__ == "__main__":
    frames = []
    for year in range(2022, 2026):
        df = pd.read_csv(players.RAW / f"fpl_{players.season_label(year)}.csv.gz", low_memory=False)
        df["was_home"] = df["was_home"].astype(str).str.lower().eq("true")
        home_id = df[~df["was_home"]].groupby("fixture")["opponent_team"].first()
        away_id = df[df["was_home"]].groupby("fixture")["opponent_team"].first()
        df["team_id"] = df["fixture"].map(home_id).where(df["was_home"], df["fixture"].map(away_id))
        real = df["starts"].fillna(0).eq(1)
        full = real.groupby([df["fixture"], df["team_id"]]).transform("sum").eq(11)
        rank = df.groupby(["fixture", "team_id"])["minutes"].rank(method="first", ascending=False)
        proxy = (rank <= 11) & (df["minutes"] > 0)
        frames.append(pd.DataFrame({"real": real[full], "proxy": proxy[full]}))
    both = pd.concat(frames)
    agree = (both["real"] & both["proxy"]).sum() / both["real"].sum()
    print(f"Team sheets checked: {int(both['real'].sum() / 11):,}")
    print(f"Real starters also picked by the minutes rule: {agree:.1%}")
    print(f"=> on average {11 * (1 - agree):.2f} of 11 starters per team are guessed wrong")
