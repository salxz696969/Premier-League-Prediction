"""The data behind the web UI, as plain Python dicts (easy to test).

Every function here returns something that can be turned into JSON directly.
``server.py`` only maps URLs to these functions.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd

from .. import config, data, features
from ..elo import compute_elo
from ..evaluation import BOOKMAKER
from ..predict import Predictor, explain_prediction
from .data_explorer import DataExplorer

BASELINE = "Baseline: home-win rate"


class ProjectData:
    """Loads everything once at start-up so every request is fast."""

    def __init__(self):
        self.matches = data.load_matches()
        self.features = features.load_features()
        self.predictor = Predictor(self.matches)
        _, self.final_elo = compute_elo(self.matches)  # ratings after the last match
        self.overall = pd.read_csv(config.RESULTS_CSV)
        self.by_season = pd.read_csv(config.RESULTS_BY_SEASON_CSV)
        self.predictions = pd.read_csv(config.PREDICTIONS_CSV, parse_dates=["date"])
        self.importance = pd.read_csv(config.REPORTS_DIR / "feature_importance.csv")
        self.original = pd.read_csv(config.REPORTS_DIR / "comparison_with_original.csv")
        extended = config.REPORTS_DIR / "extended_results.csv"
        self.extended = pd.read_csv(extended) if extended.exists() else None
        ext_preds = config.REPORTS_DIR / "extended_predictions.csv"
        self.extended_predictions = pd.read_csv(ext_preds, parse_dates=["date"]) if ext_preds.exists() else None
        self._evaluation = None
        self.explorer = DataExplorer()
        candidates = self.overall[~self.overall["model"].isin([BOOKMAKER, BASELINE])]
        self.best_model = candidates.sort_values("rps").iloc[0]["model"]
        self._predict = lru_cache(maxsize=512)(self._predict_uncached)

    # ------------------------------------------------------------------
    # Overview
    # ------------------------------------------------------------------
    def overview(self) -> dict:
        m = self.matches
        best = self.overall[self.overall["model"] == self.best_model].iloc[0]
        book = self.overall[self.overall["model"] == BOOKMAKER].iloc[0]
        base = self.overall[self.overall["model"] == BASELINE].iloc[0]
        return {
            "matches": int(len(m)),
            "seasons": int(m["season"].nunique()),
            "teams": int(pd.concat([m["home_team"], m["away_team"]]).nunique()),
            "first_season": m["season_label"].iloc[0],
            "last_season": m["season_label"].iloc[-1],
            "test_matches": int(best["matches"]),
            "best_model": self.best_model,
            "best_accuracy": float(best["accuracy"]),
            "bookmaker_accuracy": float(book["accuracy"]),
            "baseline_accuracy": float(base["accuracy"]),
            "n_features": len(features.feature_columns()),
            "teams_now": self.predictor.teams,
            "default_fixture": list(self.default_fixture()),
        }

    # ------------------------------------------------------------------
    # Predict
    # ------------------------------------------------------------------
    def _predict_uncached(self, home: str, away: str) -> dict:
        p = self.predictor.predict(home, away)
        f = p.features

        def side(prefix: str) -> dict:
            return {
                "elo": f.get(f"{prefix}_elo"),
                "form": f.get(f"{prefix}_form5_ppg"),
                "venue_form": f.get(f"{prefix}_venue_form5_ppg"),
                "position": f.get(f"{prefix}_position"),
                "prev_position": f.get(f"{prefix}_prev_position"),
                "goals_for": f.get(f"{prefix}_ewm_goals_for"),
                "goals_against": f.get(f"{prefix}_ewm_goals_against"),
                "sot_share": f.get(f"{prefix}_ewm_sot_share"),
                "season_ppg": f.get(f"{prefix}_season_ppg"),
                "promoted": bool(f.get(f"{prefix}_promoted", 0)),
                "xi_influence": f.get(f"{prefix}_xi_influence"),
                "xi_value": f.get(f"{prefix}_xi_value"),
                "key_missing": f.get(f"{prefix}_key_missing"),
            }

        def lineup(team: str) -> dict | None:
            if not self.predictor.use_players:
                return None
            info = self.predictor.lineups[team]
            return {"players": info["players"], "missing": info["missing"]}

        return {
            "home": home,
            "away": away,
            "probabilities": {"H": p.home_win, "D": p.draw, "A": p.away_win},
            "expected_goals": {"home": p.expected_home_goals, "away": p.expected_away_goals},
            "most_likely_score": p.most_likely_score,
            "top_scores": [{"score": s, "probability": pr} for s, pr in p.top_scores],
            "home_stats": side("home"),
            "away_stats": side("away"),
            "home_lineup": lineup(home),
            "away_lineup": lineup(away),
            "h2h_home_ppg": f.get("h2h_home_ppg"),
            "h2h_meetings": int(f.get("h2h_meetings", 0)),
            "explain": explain_prediction(self.predictor, home, away),
            "model": self.predictor.model.name,
            "as_of": self.matches["date"].max().date().isoformat(),
        }

    def default_fixture(self) -> tuple[str, str]:
        teams = self.predictor.teams
        if "Arsenal" in teams and "Chelsea" in teams:
            return "Arsenal", "Chelsea"
        return teams[0], teams[1]

    def predict(self, home: str, away: str) -> dict:
        return self._predict(home, away)

    def evaluation(self) -> dict:
        if self._evaluation is None:
            self._evaluation = evaluation_report(self.predictions, self.extended_predictions, self.best_model)
        return self._evaluation

    # ------------------------------------------------------------------
    # Teams
    # ------------------------------------------------------------------
    def _team_long(self) -> pd.DataFrame:
        f = self.features
        cols = ["date", "season_label"]
        home = f[cols + ["home_team", "home_elo"]].set_axis(cols + ["team", "elo"], axis=1)
        away = f[cols + ["away_team", "away_elo"]].set_axis(cols + ["team", "elo"], axis=1)
        return pd.concat([home, away]).sort_values("date")

    def teams(self) -> dict:
        """Current Elo ranking of this season's teams + every team ever."""
        ratings = self.final_elo
        current = sorted(self.predictor.teams, key=lambda t: -ratings[t])
        last_season = self.matches[self.matches["season"] == self.matches["season"].max()]
        table = league_table(last_season)
        pos = {row["team"]: row["position"] for row in table}
        all_teams = sorted(set(self.matches["home_team"]) | set(self.matches["away_team"]))
        seasons_played = {
            t: int(self.matches.loc[(self.matches["home_team"] == t), "season"].nunique()) for t in all_teams
        }
        return {
            "ranking": [
                {"team": t, "elo": round(ratings[t], 1), "position": pos.get(t), "seasons": seasons_played[t]}
                for t in current
            ],
            "all_teams": all_teams,
        }

    def elo_history(self, teams: list[str]) -> dict:
        long = self._team_long()
        series = {}
        for team in teams:
            rows = long[long["team"] == team]
            if rows.empty:
                continue
            series[team] = [
                {"date": d.date().isoformat(), "elo": round(float(e), 1), "season": s}
                for d, e, s in zip(rows["date"], rows["elo"], rows["season_label"])
            ]
        return {"series": series}

    # ------------------------------------------------------------------
    # Models
    # ------------------------------------------------------------------
    def models(self) -> dict:
        preds = self.predictions[self.predictions["model"] == self.best_model]
        labels = config.OUTCOMES
        confusion = (
            pd.crosstab(preds["result"], preds["predicted"]).reindex(index=labels, columns=labels, fill_value=0)
        )
        calibration = {}
        bins = np.linspace(0, 1, 11)
        for model in [self.best_model, BOOKMAKER]:
            rows = self.predictions[self.predictions["model"] == model]
            prob, happened = rows["prob_H"], rows["result"].eq("H")
            groups = pd.cut(prob, bins)
            t = pd.DataFrame({"p": prob, "y": happened}).groupby(groups, observed=True).agg(
                p=("p", "mean"), y=("y", "mean"), n=("y", "size")
            )
            t = t[t["n"] >= 20]
            calibration[model] = [{"predicted": float(a), "actual": float(b), "n": int(n)} for a, b, n in t.to_numpy()]
        top = self.importance.head(12)
        return {
            "best_model": self.best_model,
            "bookmaker": BOOKMAKER,
            "baseline": BASELINE,
            "overall": _records(self.overall),
            "by_season": _records(self.by_season),
            "confusion": {"labels": labels, "matrix": confusion.to_numpy().tolist()},
            "calibration_home_win": calibration,
            "importance": [
                {"feature": r.label, "importance": float(r.importance), "std": float(r.std)} for r in top.itertuples()
            ],
            "original": _records(self.original),
            "extended": _records(self.extended) if self.extended is not None else None,
        }

    # ------------------------------------------------------------------
    # Seasons
    # ------------------------------------------------------------------
    def seasons(self) -> dict:
        tested = set(self.predictions["season_label"])
        labels = list(dict.fromkeys(self.matches["season_label"]))
        return {"seasons": [{"label": s, "tested": s in tested} for s in labels]}

    def season(self, label: str) -> dict:
        games = self.matches[self.matches["season_label"] == label]
        if games.empty:
            raise ValueError(f"Unknown season {label!r}")
        result = {
            "label": label,
            "table": league_table(games),
            "outcomes": {o: int(games["result"].eq(o).sum()) for o in config.OUTCOMES},
            "goals_per_match": float((games["home_goals"] + games["away_goals"]).mean()),
            "matches": None,
        }
        preds = self.predictions[self.predictions["season_label"] == label]
        if not preds.empty:
            mine = preds[preds["model"] == self.best_model].set_index("match_id")
            book = preds[preds["model"] == BOOKMAKER].set_index("match_id")
            rows = []
            for mid, r in mine.sort_values("date").iterrows():
                b = book.loc[mid]
                rows.append({
                    "date": r["date"].date().isoformat(),
                    "home": r["home_team"],
                    "away": r["away_team"],
                    "score": f"{int(r['home_goals'])}-{int(r['away_goals'])}",
                    "result": r["result"],
                    "prob": {"H": r["prob_H"], "D": r["prob_D"], "A": r["prob_A"]},
                    "predicted": r["predicted"],
                    "book_predicted": b["predicted"],
                })
            result["matches"] = rows
            result["accuracy"] = float(np.mean([m["predicted"] == m["result"] for m in rows]))
            result["book_accuracy"] = float(np.mean([m["book_predicted"] == m["result"] for m in rows]))
        return result


def league_table(games: pd.DataFrame) -> list[dict]:
    """Final (or current) table: points, then goal difference, then goals scored."""
    rows = {}
    for g in games[["home_team", "away_team", "home_goals", "away_goals"]].itertuples(index=False):
        for team, gf, ga in ((g.home_team, g.home_goals, g.away_goals), (g.away_team, g.away_goals, g.home_goals)):
            r = rows.setdefault(team, {"team": team, "played": 0, "won": 0, "drawn": 0, "lost": 0, "gf": 0, "ga": 0})
            r["played"] += 1
            r["gf"] += int(gf)
            r["ga"] += int(ga)
            r["won" if gf > ga else "drawn" if gf == ga else "lost"] += 1
    table = list(rows.values())
    for r in table:
        r["gd"] = r["gf"] - r["ga"]
        r["points"] = 3 * r["won"] + r["drawn"]
    table.sort(key=lambda r: (-r["points"], -r["gd"], -r["gf"], r["team"]))
    for i, r in enumerate(table, start=1):
        r["position"] = i
    return table


def _records(df: pd.DataFrame) -> list[dict]:
    return df.replace({np.nan: None}).to_dict(orient="records")


# ----------------------------------------------------------------------
# Evaluation page: every standard metric, computed from saved predictions
# ----------------------------------------------------------------------
def evaluation_report(predictions: pd.DataFrame, extended: pd.DataFrame | None, best_model: str) -> dict:
    from sklearn.metrics import precision_recall_fscore_support, roc_auc_score

    from .. import evaluation as ev

    outcomes = config.OUTCOMES
    entries = []

    def add(key, label, period, rows):
        if rows.empty:
            return
        proba = rows[[f"prob_{o}" for o in outcomes]].to_numpy()
        result = rows["result"].reset_index(drop=True)
        predicted = np.array(outcomes)[proba.argmax(axis=1)]
        s = ev.score(proba, result)
        n = len(rows)
        acc = s["accuracy"]
        half = 1.96 * np.sqrt(acc * (1 - acc) / n)
        prec, rec, f1, sup = precision_recall_fscore_support(result, predicted, labels=outcomes, zero_division=0)
        observed = ev.one_hot(result)
        auc = [float(roc_auc_score(observed[:, i], proba[:, i])) for i in range(3)]
        cm = pd.crosstab(result, predicted).reindex(index=outcomes, columns=outcomes, fill_value=0)
        calib = {}
        for i, o in enumerate(outcomes):
            groups = pd.cut(proba[:, i], np.linspace(0, 1, 11))
            t = pd.DataFrame({"p": proba[:, i], "y": observed[:, i]}).groupby(groups, observed=True).agg(
                p=("p", "mean"), y=("y", "mean"), n=("y", "size"))
            t = t[t["n"] >= 20]
            calib[o] = [{"predicted": float(a), "actual": float(b), "n": int(c)} for a, b, c in t.to_numpy()]
        entries.append({
            "key": key, "label": label, "period": period, "matches": n,
            "accuracy": acc, "accuracy_low": acc - half, "accuracy_high": acc + half,
            "log_loss": s["log_loss"], "brier": s["brier"], "rps": s["rps"],
            "per_class": [{"outcome": o, "precision": float(p_), "recall": float(r_), "f1": float(f_), "support": int(n_)}
                          for o, p_, r_, f_, n_ in zip(outcomes, prec, rec, f1, sup)],
            "macro_f1": float(np.mean(f1)),
            "weighted_f1": float(np.average(f1, weights=sup)),
            "auc": auc, "macro_auc": float(np.mean(auc)),
            "confusion": cm.to_numpy().tolist(),
            "calibration": calib,
            "actual_share": {o: float(result.eq(o).mean()) for o in outcomes},
            "predicted_share": {o: float((predicted == o).mean()) for o in outcomes},
        })

    full = "2014-15 to 2025-26 (12 seasons)"
    for model in [best_model] + [m for m in predictions["model"].unique() if m != best_model]:
        add(f"full:{model}", model, full, predictions[predictions["model"] == model])

    samples = []
    if extended is not None:
        recent = "2018-19 to 2025-26 (8 seasons)"
        app_rows = extended[(extended["model"] == "Poisson goals model") & (extended["feature_set"] == "+ players")]
        add("recent:app", "Poisson goals model + players (used by the app)", recent, app_rows)
        seasons = set(app_rows["season_label"])
        same = predictions[predictions["season_label"].isin(seasons)]
        add("recent:base", f"{best_model} (base features only)", recent, same[same["model"] == best_model])
        add("recent:book", ev.BOOKMAKER, recent, same[same["model"] == ev.BOOKMAKER])
        add("recent:baseline", "Baseline: home-win rate", recent, same[same["model"] == "Baseline: home-win rate"])
        pick = app_rows.sample(n=min(60, len(app_rows)), random_state=config.RANDOM_STATE).sort_values("date")
        for r in pick.itertuples():
            samples.append({
                "date": pd.Timestamp(r.date).date().isoformat(), "season": r.season_label,
                "home": r.home_team, "away": r.away_team,
                "score": f"{int(r.home_goals)}-{int(r.away_goals)}", "result": r.result,
                "prob": {"H": r.prob_H, "D": r.prob_D, "A": r.prob_A},
            })

    folds = []
    for s in sorted(predictions["season"].unique()):
        folds.append({"test": evaluation_label(s), "train_from": evaluation_label(config.FIRST_TRAIN_SEASON),
                      "train_to": evaluation_label(s - 1), "train_matches": int((s - config.FIRST_TRAIN_SEASON) * 380),
                      "test_matches": 380})
    return {"entries": entries, "samples": samples, "folds": folds, "outcomes": outcomes}


def evaluation_label(year: int) -> str:
    return f"{year}-{(year + 1) % 100:02d}"
