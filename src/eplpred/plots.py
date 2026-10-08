"""Step 5 - the figures in ``reports/figures`` (used by the README).

All charts share one style: light background, thin marks, a muted grid and
a colour-blind-safe palette. Charts that compare many models draw the other
models in grey and colour only the ones the chart is about.
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from . import config
from .evaluation import BOOKMAKER

# Colour-blind-safe categorical palette (fixed order) + text/grid tones.
BLUE, ORANGE, AQUA, YELLOW, MAGENTA, GREEN, VIOLET, RED = (
    "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#d12f2f",
)
SEQUENTIAL = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
GREY = "#b4b2ab"
TEXT = "#0b0b0b"
TEXT_2 = "#52514e"
SURFACE = "#fcfcfb"

plt.rcParams.update(
    {
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "axes.edgecolor": GREY,
        "axes.labelcolor": TEXT_2,
        "axes.titlecolor": TEXT,
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.color": "#e6e5e0",
        "grid.linewidth": 0.8,
        "xtick.color": TEXT_2,
        "ytick.color": TEXT_2,
        "font.size": 10.5,
        "legend.frameon": False,
        "lines.linewidth": 2,
    }
)

BASELINE = "Baseline: home-win rate"


def _save(fig, name: str) -> None:
    config.FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(config.FIGURES_DIR / name, dpi=160, bbox_inches="tight")
    plt.close(fig)


def _model_colour(model: str, best_model: str) -> str:
    if model == BOOKMAKER:
        return RED
    if model == best_model:
        return BLUE
    return GREY


def model_comparison(overall: pd.DataFrame, best_model: str) -> None:
    """Accuracy and RPS per model - two separate charts (different scales)."""
    for metric, label, fmt, name, higher_better in [
        ("accuracy", "Accuracy on 2014-15 to 2025-26 (higher is better)", "{:.1%}", "model_accuracy.png", True),
        ("rps", "Ranked Probability Score (lower is better)", "{:.4f}", "model_rps.png", False),
    ]:
        table = overall.sort_values(metric, ascending=not higher_better)
        fig, ax = plt.subplots(figsize=(8, 4.2))
        colours = [_model_colour(m, best_model) for m in table["model"]]
        bars = ax.barh(table["model"], table[metric], color=colours, height=0.6)
        ax.invert_yaxis()
        ax.grid(axis="y", visible=False)
        lo = table[metric].min()
        hi = table[metric].max()
        pad = (hi - lo) * 0.6 if metric == "rps" else 0
        ax.set_xlim(lo - pad if metric == "rps" else 0, hi + (hi - lo) * 0.25 + (0.05 if metric == "accuracy" else 0))
        for bar, value in zip(bars, table[metric]):
            ax.text(bar.get_width(), bar.get_y() + bar.get_height() / 2, "  " + fmt.format(value),
                    va="center", color=TEXT, fontsize=9.5)
        ax.set_title(label)
        ax.set_xlabel("")
        if metric == "accuracy":
            ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
        _save(fig, name)


def accuracy_by_season(by_season: pd.DataFrame, best_model: str) -> None:
    fig, ax = plt.subplots(figsize=(9, 4.4))
    for model, colour, style in [(BOOKMAKER, RED, "-"), (best_model, BLUE, "-"), (BASELINE, GREY, "--")]:
        rows = by_season[by_season["model"] == model]
        ax.plot(rows["season_label"], rows["accuracy"], style, color=colour, marker="o", markersize=5, label=model)
    ax.set_title("Accuracy per test season")
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.tick_params(axis="x", rotation=45)
    ax.legend(loc="lower left")
    _save(fig, "accuracy_by_season.png")


def calibration(predictions: pd.DataFrame, best_model: str) -> None:
    """Are the probabilities honest? If we say 60 %, does it happen 60 % of the time?"""
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.2), sharey=True)
    bins = np.linspace(0, 1, 11)
    for ax, outcome, title in zip(axes, config.OUTCOMES, ["Home win", "Draw", "Away win"]):
        ax.plot([0, 1], [0, 1], color=GREY, linewidth=1, linestyle="--", label="Perfect calibration")
        for model, colour in [(best_model, BLUE), (BOOKMAKER, RED)]:
            rows = predictions[predictions["model"] == model]
            prob = rows[f"prob_{outcome}"]
            happened = rows["result"].eq(outcome)
            groups = pd.cut(prob, bins)
            table = pd.DataFrame({"p": prob, "y": happened}).groupby(groups, observed=True).agg(
                p=("p", "mean"), y=("y", "mean"), n=("y", "size")
            )
            table = table[table["n"] >= 20]
            ax.plot(table["p"], table["y"], marker="o", markersize=5, color=colour, label=model)
        ax.set_title(title)
        ax.set_xlabel("Predicted probability")
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
    axes[0].set_ylabel("How often it actually happened")
    axes[0].legend(loc="upper left", fontsize=9)
    _save(fig, "calibration.png")


def confusion(predictions: pd.DataFrame, model: str) -> None:
    rows = predictions[predictions["model"] == model]
    labels = config.OUTCOMES
    matrix = pd.crosstab(rows["result"], rows["predicted"]).reindex(index=labels, columns=labels, fill_value=0)
    share = matrix.div(matrix.sum(axis=1), axis=0)
    fig, ax = plt.subplots(figsize=(5.2, 4.4))
    cmap = matplotlib.colors.LinearSegmentedColormap.from_list("blue", SEQUENTIAL)
    ax.imshow(share.to_numpy(), cmap=cmap, vmin=0, vmax=1)
    names = ["Home win", "Draw", "Away win"]
    ax.set_xticks(range(3), names)
    ax.set_yticks(range(3), names)
    ax.grid(False)
    for i in range(3):
        for j in range(3):
            value = share.iat[i, j]
            ax.text(j, i, f"{value:.0%}\n({matrix.iat[i, j]})", ha="center", va="center",
                    color="white" if value > 0.5 else TEXT, fontsize=10)
    ax.set_xlabel("Predicted")
    ax.set_ylabel("Actual result")
    ax.set_title(f"What the model predicts\n({model})", fontsize=11)
    _save(fig, "confusion_matrix.png")


def feature_importance(importance: pd.DataFrame) -> None:
    table = importance.head(15).iloc[::-1]
    fig, ax = plt.subplots(figsize=(8, 5.2))
    ax.barh(table["label"], table["importance"], color=BLUE, height=0.6, xerr=table["std"],
            error_kw={"ecolor": TEXT_2, "elinewidth": 1, "capsize": 0})
    ax.grid(axis="y", visible=False)
    ax.set_title("Which features matter most? (permutation importance)")
    ax.set_xlabel("Increase in RPS when the feature is shuffled (higher = more important)")
    _save(fig, "feature_importance.png")


def outcomes_by_season(matches: pd.DataFrame) -> None:
    share = pd.crosstab(matches["season_label"], matches["result"], normalize="index")[config.OUTCOMES]
    fig, ax = plt.subplots(figsize=(10, 4.2))
    for outcome, colour, name in zip(config.OUTCOMES, [BLUE, GREY, RED], ["Home win", "Draw", "Away win"]):
        ax.plot(share.index, share[outcome], color=colour, marker="o", markersize=4, label=name)
    covid = list(share.index).index("2020-21")
    ax.axvspan(covid - 0.5, covid + 0.5, color="#f0efec", zorder=0)
    ax.text(covid, 0.585, "no fans\n(COVID-19)", ha="center", va="top", color=TEXT_2, fontsize=8.5)
    ax.set_title("How often does each result happen? (every season 2000-01 to 2025-26)")
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.set_ylim(0, 0.6)
    ax.tick_params(axis="x", rotation=60)
    ax.legend(ncol=3, loc="lower left")
    _save(fig, "outcomes_by_season.png")


def elo_history(features: pd.DataFrame, teams: list[str]) -> None:
    long = pd.concat(
        [
            features[["date", "home_team", "home_elo"]].set_axis(["date", "team", "elo"], axis=1),
            features[["date", "away_team", "away_elo"]].set_axis(["date", "team", "elo"], axis=1),
        ]
    ).sort_values("date")
    palette = [BLUE, RED, AQUA, YELLOW, MAGENTA, VIOLET]
    fig, ax = plt.subplots(figsize=(11, 5))
    for team, colour in zip(teams, palette):
        rows = long[long["team"] == team].set_index("date")["elo"].rolling(5, min_periods=1).mean()
        # Break the line while a team is out of the league (e.g. Man City 2001-02).
        gap = rows.index.to_series().diff().dt.days.gt(150).cumsum()
        for i, (_, part) in enumerate(rows.groupby(gap.to_numpy())):
            ax.plot(part.index, part.to_numpy(), color=colour, linewidth=1.6, label=team if i == 0 else None)
    ax.set_title("Elo rating of the 'big six' since 2000 (computed by this project)")
    ax.set_ylabel("Elo rating before the match")
    ax.legend(ncol=3, loc="lower right", fontsize=9)
    _save(fig, "elo_history.png")


def season_2019_comparison(table: pd.DataFrame) -> None:
    """Compare with the original project on the same test matches (Feb-Mar 2020)."""
    rows = table.sort_values("accuracy")
    fig, ax = plt.subplots(figsize=(8, 4.4))
    colours = [RED if m == BOOKMAKER else TEXT_2 if m.startswith("Original") else GREY if m == BASELINE
               else BLUE for m in rows["model"]]
    bars = ax.barh(rows["model"], rows["accuracy"], color=colours, height=0.6)
    for bar in bars:
        ax.text(bar.get_width(), bar.get_y() + bar.get_height() / 2, f"  {bar.get_width():.1%}", va="center", fontsize=9.5)
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0, rows["accuracy"].max() * 1.18)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.set_title("The original test set (38 matches, Feb-Mar 2020) is too small:\neven \"always pick the home team\" scores as well as the best models", fontsize=11.5)
    _save(fig, "season_2019_20_vs_original.png")


def extended_comparison(results: pd.DataFrame) -> None:
    """Change in RPS from adding each kind of extra data (with 95 % intervals).

    Left of zero = the extra data made predictions better.
    """
    rows = results[results["rps_change"].notna()].copy()
    sets = list(dict.fromkeys(rows["feature_set"]))
    models = list(dict.fromkeys(rows["model"]))
    colours = dict(zip(sets, [BLUE, VIOLET, AQUA, GREY]))
    fig, ax = plt.subplots(figsize=(9, 1.0 + 0.9 * len(models)))
    step = 0.8 / max(1, len(sets))
    for j, fset in enumerate(sets):
        part = rows[rows["feature_set"] == fset].set_index("model").reindex(models)
        y = np.arange(len(models)) + (j - (len(sets) - 1) / 2) * step
        ax.errorbar(part["rps_change"], y,
                    xerr=[part["rps_change"] - part["rps_change_low"], part["rps_change_high"] - part["rps_change"]],
                    fmt="o", color=colours[fset], ecolor=colours[fset], elinewidth=1.5, capsize=0, markersize=6, label=fset)
    ax.axvline(0, color=TEXT_2, linewidth=1)
    ax.set_yticks(range(len(models)), models)
    ax.invert_yaxis()
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Change in RPS vs base features  (← better   |   worse →)")
    ax.set_title("Does extra data help? Test seasons 2018-19 to 2025-26")
    ax.legend(loc="lower right", fontsize=9)
    _save(fig, "extended_comparison.png")
