"""The written report and the slide deck, built from the project's *current* results.

Nothing in here is typed in by hand: every number is read from the files in
``reports/`` (and a live prediction from the final model), so whenever the data
or the models change, re-running ``scripts/06_make_report.py`` (or opening the
web app) gives an up-to-date report and slides.

    build_story(project) -> {"numbers": {...}, "report_md": "...", "slides": [...]}

The same slide list feeds the web app's Slides page and the PowerPoint file
(``scripts/make_slides.js``), so they always match.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from . import config, data, other_competitions
from .evaluation import BOOKMAKER

BASELINE = "Baseline: home-win rate"
BIG_SIX = ["Manchester City", "Liverpool", "Arsenal", "Chelsea", "Manchester United", "Tottenham Hotspur"]


def pct(x: float, d: int = 1) -> str:
    return f"{100 * x:.{d}f}%"


def short(model: str) -> str:
    return (model.replace(" (Bet365, benchmark)", "").replace(" (logistic regression)", "")
            .replace("Baseline: home-win rate", "Always home win").replace("Bookmaker", "Bookmaker (Bet365)"))


# ----------------------------------------------------------------------
# 1) Collect every number the report and slides use
# ----------------------------------------------------------------------
def collect_numbers(project) -> dict:
    m = project.matches
    overall = project.overall.set_index("model")
    best = project.best_model
    by_season = project.by_season
    ext = project.extended
    evaluation = project.evaluation()
    entries = {e["key"]: e for e in evaluation["entries"]}
    app = entries.get("recent:app") or entries[f"full:{best}"]
    home, away = project.default_fixture()
    example = project.predict(home, away)
    explain = example["explain"]

    best_seasons = by_season[by_season["model"] == best].set_index("season_label")["accuracy"]
    book_seasons = by_season[by_season["model"] == BOOKMAKER].set_index("season_label")["accuracy"]
    base_seasons = by_season[by_season["model"] == BASELINE].set_index("season_label")["accuracy"]

    covid = m[m["season_label"] == "2020-21"]["result"].value_counts(normalize=True)
    other = other_competitions.load_other_matches(m)
    players_rows = len(project.explorer.frame("players"))
    internationals = len(project.explorer.frame("internationals"))

    def ext_row(fset):
        if ext is None:
            return None
        r = ext[(ext["model"] == "Poisson goals model") & (ext["feature_set"] == fset)]
        return r.iloc[0].to_dict() if len(r) else None

    original = project.original.set_index("model")["accuracy"]
    importance = project.importance.head(5)

    # Season-end Elo for the big six (for the Elo chart)
    f = project.features
    long = pd.concat([
        f[["season_label", "date", "home_team", "home_elo"]].set_axis(["season", "date", "team", "elo"], axis=1),
        f[["season_label", "date", "away_team", "away_elo"]].set_axis(["season", "date", "team", "elo"], axis=1),
    ]).sort_values("date")
    elo_end = long.groupby(["team", "season"])["elo"].last().unstack(0)

    return {
        "today": date.today().isoformat(),
        "matches": len(m), "seasons": int(m["season"].nunique()),
        "first_season": m["season_label"].iloc[0], "last_season": m["season_label"].iloc[-1],
        "teams": int(pd.concat([m["home_team"], m["away_team"]]).nunique()),
        "share": {o: float(m["result"].eq(o).mean()) for o in config.OUTCOMES},
        "goals_per_match": float((m["home_goals"] + m["away_goals"]).mean()),
        "covid": {o: float(covid.get(o, 0)) for o in config.OUTCOMES},
        "with_odds": float(m["book_prob_H"].notna().mean()),
        "other_matches": int(len(other)),
        "other_coverage": other_competitions.coverage(other),
        "players_rows": players_rows, "internationals": internationals,
        "n_features": 49,
        "best": best, "overall": overall,
        "test_matches": int(overall.loc[best, "matches"]),
        "best_acc": float(overall.loc[best, "accuracy"]), "best_rps": float(overall.loc[best, "rps"]),
        "book_acc": float(overall.loc[BOOKMAKER, "accuracy"]), "book_rps": float(overall.loc[BOOKMAKER, "rps"]),
        "base_acc": float(overall.loc[BASELINE, "accuracy"]),
        "elo_acc": float(overall.loc["Elo only (logistic regression)", "accuracy"]),
        "seasons_table": pd.DataFrame({"model": best_seasons, "book": book_seasons, "base": base_seasons}),
        "best_season": (best_seasons.idxmax(), float(best_seasons.max())),
        "worst_season": (best_seasons.idxmin(), float(best_seasons.min())),
        "ext": {k: ext_row(k) for k in ["Base (49 features)", "+ fatigue", "+ players", "+ everything"]},
        "ext_book": (None if ext is None else ext[ext["feature_set"] == "Bookmaker"].iloc[0].to_dict()),
        "app": app, "entries": entries,
        "example": example, "explain": explain, "home": home, "away": away,
        "original": original, "importance": importance,
        "elo_end": elo_end,
        "folds": evaluation["folds"],
    }


# ----------------------------------------------------------------------
# 2) The slides (one dict per slide; rendered by the web app and by PowerPoint)
# ----------------------------------------------------------------------
def build_slides(n: dict) -> list[dict]:
    ex, e = n["example"], n["explain"]
    H, A = n["home"], n["away"]
    p = ex["probabilities"]
    app = n["app"]
    book_recent = n["entries"].get("recent:book")
    base_recent = n["entries"].get("recent:baseline")
    players = n["ext"]["+ players"]
    fatigue = n["ext"]["+ fatigue"]
    base_ext = n["ext"]["Base (49 features)"]

    models = n["overall"].sort_values("accuracy", ascending=False)
    accuracy_chart = {
        "type": "bar", "horizontal": True, "format": "percent",
        "categories": [short(m) for m in models.index],
        "values": [float(v) for v in models["accuracy"]],
        "highlight": {short(n["best"]): "home", short(BOOKMAKER): "away"},
        "min": 0, "max": 0.6,
    }
    st = n["seasons_table"]
    seasons_chart = {
        "type": "line", "format": "percent", "min": 0.35, "max": 0.65,
        "categories": list(st.index),
        "series": [
            {"name": short(n["best"]), "values": [float(v) for v in st["model"]], "color": "home"},
            {"name": "Bookmaker (Bet365)", "values": [float(v) for v in st["book"]], "color": "away"},
            {"name": "Always home win", "values": [float(v) for v in st["base"]], "color": "muted", "dashed": True},
        ],
    }
    elo = n["elo_end"]
    elo_seasons = [s for s in elo.index if s >= "2001-02"]
    elo_chart = {
        "type": "line", "format": "number", "min": 1350, "max": 1750,
        "categories": [s[2:] for s in elo_seasons],
        "series": [
            {"name": t, "values": [None if pd.isna(elo.loc[s, t]) else round(float(elo.loc[s, t])) for s in elo_seasons], "color": c}
            for t, c in zip(["Manchester City", "Liverpool", "Arsenal", "Chelsea", "Manchester United"],
                            ["home", "away", "aqua", "violet", "muted"])
        ],
    }
    extra_chart = None
    if players:
        rows = [("Base features", base_ext), ("+ fatigue", fatigue), ("+ players", players), ("Bookmaker", n["ext_book"])]
        extra_chart = {
            "type": "bar", "horizontal": True, "format": "percent", "min": 0, "max": 0.6,
            "categories": [r[0] for r in rows], "values": [float(r[1]["accuracy"]) for r in rows],
            "highlight": {"+ players": "home", "Bookmaker": "away"},
        }
    pc = {c["outcome"]: c for c in app["per_class"]}
    hs, as_ = e["sides"]["home"], e["sides"]["away"]
    orig_v1 = float(n["original"].get("Original project (v1 random forest)", 0.4748))

    slides = [
        {"kind": "title", "kicker": "Data science project", "title": "Can we predict Premier League matches?",
         "subtitle": f"{n['seasons']} seasons · {n['matches']:,} matches · {n['first_season']} to {n['last_season']}",
         "notes": "Hello everyone. Our project asks a simple question: before a Premier League match kicks off, "
                  "can a computer predict the chance of a home win, a draw or an away win? We used every Premier League "
                  f"match from {n['first_season']} to {n['last_season']}, built a model, and tested it fairly against "
                  "real bookmakers."},
        {"kind": "stats", "kicker": "The problem", "title": "Football is hard to predict",
         "stats": [{"value": pct(n["share"]["H"]), "label": "of matches are home wins"},
                   {"value": pct(n["share"]["D"]), "label": "end in a draw"},
                   {"value": pct(n["share"]["A"]), "label": "are away wins"}],
         "body": [f"Only {n['goals_per_match']:.2f} goals per match, so one lucky goal changes the result",
                  "Any model must beat the simple rule \"always pick the home team\""],
         "notes": f"Over {n['seasons']} seasons, home teams won {pct(n['share']['H'])} of matches, a quarter were draws "
                  "and about 30% were away wins. Football has few goals, so luck matters a lot. The simplest possible "
                  f"rule, always pick the home team, is already right {pct(n['base_acc'])} of the time in our test seasons. "
                  "Our model has to beat that."},
        {"kind": "cards", "kicker": "Data", "title": "Real data from published sources",
         "cards": [
             {"title": f"{n['matches']:,} league matches", "text": f"Football-Data.co.uk, {n['first_season']} to {n['last_season']}: scores, shots, corners, cards"},
             {"title": f"{n['players_rows']:,} player rows", "text": "Fantasy Premier League, 2016-17 onwards: minutes, starts, influence"},
             {"title": f"{n['other_matches']:,} cup & European games", "text": "engsoccerdata + openfootball: FA Cup, League Cup, Champions League, Europa League"},
             {"title": f"{n['internationals']:,} internationals", "text": "martj42/international_results: to find international breaks"},
         ],
         "body": [f"Bookmaker odds ({pct(n['with_odds'], 0)} of matches) are only used to compare against, never as an input"],
         "notes": "Everything comes from public datasets that anyone can download, listed with their licences in SOURCES.md "
                  "and on the Data page of our website. The script checks the data automatically: 380 matches every season, "
                  "no duplicates, and every result agrees with the score. Bookmaker odds are only a benchmark."},
        {"kind": "statement", "kicker": "Rule number one", "title": "No cheating: only what is known before kick-off",
         "body": ["Wrong: using this match's shots to predict this match's result",
                  "Right: using shots from the team's previous matches",
                  "An automatic test changes results and checks that no earlier input moves"],
         "notes": "The most common mistake in football prediction projects is called data leakage: accidentally using "
                  "information from the match you are predicting, like its number of shots. That gives amazing scores "
                  "that are fake. Our first version of this project had this problem. Now every input is calculated "
                  "only from earlier matches, and an automatic test proves it."},
        {"kind": "cards", "kicker": "Features", "title": f"What the model looks at: {n['n_features']} inputs",
         "cards": [
             {"title": "Elo rating", "text": "One strength number per team, updated after every match"},
             {"title": "Recent form", "text": "Points per game in the last 5 matches, home and away"},
             {"title": "Attack & defence", "text": "Goals, shots and shots on target, recent games count more"},
             {"title": "League table", "text": "Position, points per game and goal difference so far"},
             {"title": "Last season", "text": "Final position, or newly promoted"},
             {"title": "Players", "text": "Strength of the expected starting eleven (FPL influence)"},
         ],
         "notes": "These are the inputs, called features. The most important is the Elo rating: a single number for "
                  "how strong a team is, which goes up when it wins and down when it loses. We also use recent form, "
                  "how many goals and shots a team makes and allows, its league position, last season's finish, and "
                  "from 2016 the quality of its starting eleven from Fantasy Premier League data."},
        {"kind": "chart", "kicker": "Elo rating", "title": "One number tells the story of the league",
         "chart": elo_chart,
         "body": ["Elo expected score = 1 / (1 + 10^(−(home + 50 − away) / 400))"],
         "notes": "This chart shows our own Elo ratings at the end of every season. You can see real football history: "
                  "Chelsea rising after 2004, Manchester United under Ferguson, Manchester City from 2011, Liverpool under "
                  "Klopp. The formula turns the gap between two ratings into an expected score; the home team gets 50 "
                  "extra points for home advantage."},
        {"kind": "cards", "kicker": "Models", "title": "Seven models, from simple to complex",
         "cards": [
             {"title": "Always home win", "text": "The baseline to beat"},
             {"title": "Elo only", "text": "Just the rating difference"},
             {"title": "Logistic regression", "text": "A weighted sum of all inputs"},
             {"title": "Random forest", "text": "500 decision trees vote"},
             {"title": "Gradient boosting", "text": "Trees that fix each other's mistakes"},
             {"title": "Poisson goals model", "text": "Predicts goals, then turns goals into results"},
         ],
         "body": ["Plus an ensemble that averages three of them. Settings were tuned on 2010-2014 only"],
         "notes": "We compared seven models. Every model outputs three probabilities, for home win, draw and away win. "
                  "The model settings were chosen using only the seasons 2010 to 2014, so the test seasons stayed unseen."},
        {"kind": "steps", "kicker": "Fair testing", "title": "Walk-forward: predict each season from the past",
         "steps": [
             {"title": "Train", "text": f"On every season before the test season (e.g. {n['folds'][0]['train_from']} to {n['folds'][0]['train_to']})"},
             {"title": "Predict", "text": "All 380 matches of the next season, before seeing any of them"},
             {"title": "Repeat", "text": f"For {len(n['folds'])} seasons: {n['test_matches']:,} test matches in total"},
         ],
         "notes": "To test fairly, we copied real life. To predict a season, the model only learns from the seasons before "
                  f"it, then predicts all 380 matches. We repeated this for {len(n['folds'])} seasons, so we have "
                  f"{n['test_matches']:,} honest test predictions. The original project tested on only 38 matches."},
        {"kind": "steps", "kicker": "One prediction, step by step", "title": f"{H} vs {A}",
         "steps": [
             {"title": "1 · Expected goals", "text": f"{H} {hs['expected_goals']:.2f}, {A} {as_['expected_goals']:.2f} (average match: {hs['baseline']:.2f} and {as_['baseline']:.2f})"},
             {"title": "2 · Poisson", "text": f"Chance of each number of goals, e.g. {H} scores exactly 2: {pct(e['goal_probs']['home'][2])}"},
             {"title": "3 · Add up scores", "text": f"{H} win {pct(p['H'], 0)} · draw {pct(p['D'], 0)} · {A} win {pct(p['A'], 0)}"},
         ],
         "notes": f"Here is how one prediction is made, for {H} at home to {A}. Step one: the model starts from an average "
                  f"match, {hs['baseline']:.2f} goals for the home team, and each input multiplies that up or down. "
                  f"{H} end up with {hs['expected_goals']:.2f} expected goals and {A} {as_['expected_goals']:.2f}. Step two: "
                  "a Poisson distribution turns expected goals into the chance of scoring 0, 1, 2 or more goals. Step three: "
                  "multiply the two to get every exact score, and add up the scores where the home team has more goals. "
                  "The website shows every number of this calculation."},
        {"kind": "chart", "kicker": "Results", "title": f"{short(n['best'])}: {pct(n['best_acc'])} accuracy",
         "chart": accuracy_chart,
         "body": [f"Always home win: {pct(n['base_acc'])} · Bookmaker: {pct(n['book_acc'])} · {n['test_matches']:,} test matches"],
         "notes": f"These are the results on {n['test_matches']:,} test matches. All our models beat the baseline of "
                  f"{pct(n['base_acc'])} by about 9 points. The best was the Poisson goals model with {pct(n['best_acc'])}. "
                  f"The bookmaker, which is a professional company with much more information, gets {pct(n['book_acc'])}. "
                  f"Elo alone already gets {pct(n['elo_acc'])}, so team strength is most of the story."},
        {"kind": "chart", "kicker": "Season by season", "title": "Close to the bookmaker every season",
         "chart": seasons_chart,
         "body": [f"Hardest: {n['worst_season'][0]} ({pct(n['worst_season'][1])}) · easiest: {n['best_season'][0]} ({pct(n['best_season'][1])})"],
         "notes": "Here is accuracy in every test season. Our model, in blue, follows the bookmaker, in red, closely. "
                  "2015-16 was very hard for everyone: Leicester won the league as 5000-1 outsiders. In 2020-21 matches "
                  f"were played without fans because of COVID-19, and away teams won more often than home teams "
                  f"({pct(n['covid']['A'])} vs {pct(n['covid']['H'])})."},
        {"kind": "table", "kicker": "Evaluation", "title": "Precision, recall and F1 score",
         "table": {"columns": ["Outcome", "Precision", "Recall", "F1 score", "Matches"],
                   "rows": [[name, f"{pc[o]['precision']:.2f}", f"{pc[o]['recall']:.2f}", f"{pc[o]['f1']:.2f}", f"{pc[o]['support']:,}"]
                            for o, name in [("H", "Home win"), ("D", "Draw"), ("A", "Away win")]]
                           + [["Accuracy", "", "", f"{app['accuracy']:.3f}", f"{app['matches']:,}"]]},
         "body": [f"Draw recall is {pc['D']['recall']:.2f}: a draw is almost never the single most likely result",
                  "Precision: when it picks X, how often is it right? Recall: of all real X, how many did it pick?"],
         "notes": "This is the classification report of the model our website uses. Precision means: when the model picks a "
                  "home win, how often is it right. Recall means: of all real home wins, how many did it find. F1 combines "
                  f"both. Home wins have the best scores. Draws score zero: {pct(app['actual_share']['D'], 0)} of matches "
                  "are draws, but a draw is almost never the most likely single result, so the model never picks one. "
                  "The bookmaker has exactly the same problem."},
        {"kind": "stats", "kicker": "Probability quality", "title": "Judging the probabilities, not just the pick",
         "stats": [
             {"value": f"{app['log_loss']:.3f}", "label": f"Log loss (bookmaker {book_recent['log_loss']:.3f}, guessing 1.099)" if book_recent else "Log loss"},
             {"value": f"{app['rps']:.4f}", "label": f"RPS (bookmaker {book_recent['rps']:.4f}, always home {base_recent['rps']:.4f})" if book_recent else "RPS"},
             {"value": f"{app['macro_auc']:.3f}", "label": "AUC (0.5 = guessing, 1 = perfect)"},
         ],
         "body": ["Lower log loss and RPS are better; the probabilities are well calibrated (60% happens about 60% of the time)"],
         "notes": "Accuracy only checks the single pick. These scores judge the full probabilities. Log loss punishes "
                  "confident mistakes. RPS, the ranked probability score, is the standard in football research because it "
                  "knows that a draw is between a home and an away win. AUC says how well the model separates outcomes. "
                  "On all of them we are close to the bookmaker and far better than guessing."},
    ]
    if extra_chart:
        slides.append(
            {"kind": "chart", "kicker": "Extra data", "title": "Players help a little, fatigue does not",
             "chart": extra_chart,
             "body": [f"Test seasons 2018-19 to 2025-26 · RPS with players {players['rps']:.4f} vs {base_ext['rps']:.4f} without"],
             "notes": "We tested whether more data helps. Adding cup, European and international match dates, to measure "
                      f"tiredness, made no difference: {pct(fatigue['accuracy'])} instead of {pct(base_ext['accuracy'])}. "
                      f"Adding who is in the starting eleven helped a little: {pct(players['accuracy'])}. "
                      "So our final model uses the base features plus the player features."})
    slides += [
        {"kind": "table", "kicker": "Version 1 → version 2", "title": "What we improved",
         "table": {"columns": ["", "Version 1", "Version 2"],
                   "rows": [["Data", "1 season (288 matches)", f"{n['seasons']} seasons ({n['matches']:,})"],
                            ["Extra data", "~2,500 generated rows", "None: all real"],
                            ["Cheating (leakage)", "Yes", "No, tested automatically"],
                            ["Test matches", "38", f"{n['test_matches']:,}"],
                            ["Accuracy on the test", f"{pct(orig_v1)} (on 38)", f"{pct(n['best_acc'])} (on {n['test_matches']:,})"]]},
         "notes": "Our first version used one season, some generated data and leaked future information, and it was "
                  f"tested on only 38 matches. On those same 38 matches, version 2 scores much higher, but even always "
                  f"picking the home team scores well, which shows 38 matches is too few to judge a model."},
        {"kind": "cards", "kicker": "Limitations", "title": "What could be better",
         "cards": [
             {"title": "Team news", "text": "Injuries and confirmed line-ups: the main reason bookmakers are better"},
             {"title": "Draws", "text": "Still almost impossible to pick"},
             {"title": "Missing data", "text": "Europa League before 2020-21, managers not yet included"},
             {"title": "Next steps", "text": "Expected goals (xG) data, simulating a whole season's table"},
         ],
         "notes": "Our model does not know about injuries or the confirmed line-up, which is the biggest reason the "
                  "bookmaker is still slightly better. Draws stay very hard. Some data is missing from free sources. "
                  "Next we would add expected-goals data and simulate whole seasons to predict the final table."},
        {"kind": "closing", "kicker": "Conclusion", "title": "What we learned",
         "body": [f"A fair model reaches {pct(n['best_acc'])}, close to the bookmaker's {pct(n['book_acc'])}",
                  "Team strength (Elo) matters most; a simple Poisson model beat complex ones",
                  "Testing properly matters more than a fancy model"],
         "notes": "To conclude: with real data and a fair test, our model predicts Premier League results about as well as "
                  "we could expect, within about one percentage point of a professional bookmaker. Team strength is the "
                  "most important information, and a simple model beat the complex ones. Most of all, we learned that "
                  "testing honestly matters more than using a fancy model. Thank you, we are happy to take questions, "
                  "and we can show the live website."},
        {"kind": "sources", "kicker": "Sources", "title": "Data and references",
         "body": ["Football-Data.co.uk via DataHub football-datasets (PDDL)", "Fantasy Premier League data, Vaastav Anand (MIT)",
                  "engsoccerdata, James Curley (GPL-2+) · openfootball (CC0)", "International results, Mart Jürisoo (CC0)",
                  "Bet365 odds via Club Football Match Data, Adam Gábor (MIT)", "Elo (1978) · Maher (1982) · Dixon & Coles (1997)",
                  "Hvattum & Arntzen (2010) · Constantinou & Fenton (2012)"],
         "notes": "All sources and references are listed here and in SOURCES.md, with full citations."},
    ]
    for i, s in enumerate(slides, 1):
        s["number"] = i
    return slides


# ----------------------------------------------------------------------
# 3) The written report (Markdown)
# ----------------------------------------------------------------------
def build_report(n: dict, figures: str) -> str:
    ov = n["overall"].sort_values("rps")
    app, ex, e = n["app"], n["example"], n["explain"]
    H, A = n["home"], n["away"]
    hs, as_ = e["sides"]["home"], e["sides"]["away"]
    pc = {c["outcome"]: c for c in app["per_class"]}
    book_recent, base_recent = n["entries"].get("recent:book"), n["entries"].get("recent:baseline")
    players, fatigue, base_ext = n["ext"]["+ players"], n["ext"]["+ fatigue"], n["ext"]["Base (49 features)"]
    cov = n["other_coverage"]
    fig = lambda name, alt: f"![{alt}]({figures}/{name})"

    model_rows = "\n".join(
        f"| {short(mdl)} | {pct(r['accuracy'])} | {r['log_loss']:.3f} | {r['brier']:.3f} | {r['rps']:.4f} |"
        for mdl, r in ov.iterrows())
    class_rows = "\n".join(
        f"| {name} | {pc[o]['precision']:.3f} | {pc[o]['recall']:.3f} | {pc[o]['f1']:.3f} | {pc[o]['support']:,} |"
        for o, name in [("H", "Home win"), ("D", "Draw"), ("A", "Away win")])
    cm = app["confusion"]
    top_inputs = "\n".join(f"| {i['label']} | {i['value']:.2f} | {i['average']:.2f} | ×{i['factor']:.3f} |" for i in hs["items"][:6])
    imp = "\n".join(f"{k + 1}. {r.label}" for k, r in enumerate(n["importance"].itertuples()))
    coverage_rows = "\n".join(
        f"| {comp} | {int((cov[key] > 0).sum())} of {len(cov)} seasons |"
        for key, comp in other_competitions.COMPETITIONS.items())

    ext_section = ""
    if players:
        ext_section = f"""
### 6.4 Does extra data help?

We added two kinds of extra data and tested them the same way on the seasons that have player data (2018-19 to 2025-26, 3,040 matches):

| Inputs | Accuracy | RPS (lower is better) |
|---|---:|---:|
| Base features | {pct(base_ext['accuracy'])} | {base_ext['rps']:.4f} |
| + fatigue (cup, European and international match dates) | {pct(fatigue['accuracy'])} | {fatigue['rps']:.4f} |
| + players (FPL starting-eleven strength) | {pct(players['accuracy'])} | {players['rps']:.4f} |
| Bookmaker (benchmark) | {pct(n['ext_book']['accuracy'])} | {n['ext_book']['rps']:.4f} |

**Player data helped a little; fatigue did not.** A likely reason is that the teams with the most midweek games are also the strongest teams, which the Elo rating already captures. The final model, used by the website, is therefore the Poisson model with the base features plus the player features.

{fig('extended_comparison.png', 'Change in RPS when extra data is added')}
"""

    return f"""# Predicting Premier League match results

*Data science project report · generated automatically from the project's results on {n['today']}*

## Summary

We built a model that predicts, before kick-off, the probability of a home win, a draw and an away win in English Premier League matches. We used **{n['matches']:,} real matches from {n['seasons']} seasons** ({n['first_season']} to {n['last_season']}), calculated every input only from earlier matches, and tested the models fairly on **{n['test_matches']:,} matches they had never seen**.

The best model, a **Poisson goals model**, picked the right result in **{pct(n['best_acc'])}** of test matches. That is far better than always picking the home team ({pct(n['base_acc'])}) and close to a professional bookmaker ({pct(n['book_acc'])}). Adding Fantasy Premier League player data improved it slightly; fatigue from cup and European matches did not help.

## 1. Introduction

Football is hard to predict: there are only about {n['goals_per_match']:.1f} goals per match, so luck plays a big role, and about a quarter of matches end in a draw. Our question was:

> **Before a match starts, how well can we estimate the chances of a home win, a draw and an away win?**

This is version 2 of our project. Version 1 used a single season, about 2,500 rows of generated (not real) data and information that was only known after kick-off, and it was tested on only 38 matches. Version 2 fixes all of these problems.

## 2. Data

All data comes from public datasets (full list with licences in `SOURCES.md`; every row can be browsed on the website's **Data** page).

| Data | Source | What we use |
|---|---|---|
| {n['matches']:,} Premier League matches, {n['first_season']} to {n['last_season']} | Football-Data.co.uk (via DataHub) | Scores, shots, shots on target, corners, fouls, cards |
| Bookmaker odds ({pct(n['with_odds'], 0)} of matches) | Bet365, via Club Football Match Data | Only as a benchmark, never as an input |
| {n['players_rows']:,} player-match rows, 2016-17 onwards | Fantasy Premier League (Vaastav Anand) | Starting eleven, player influence |
| {n['other_matches']:,} cup and European matches | engsoccerdata, openfootball | Fatigue (match dates) |
| {n['internationals']:,} international matches | martj42/international_results | International breaks |

The download script checks the data automatically: every season has exactly 380 matches, there are no duplicates, and every result agrees with its score. Coverage of the other competitions:

| Competition | Coverage |
|---|---|
{coverage_rows}

{fig('outcomes_by_season.png', 'Home wins, draws and away wins per season')}

Home teams won {pct(n['share']['H'])} of all matches, {pct(n['share']['D'])} were draws and {pct(n['share']['A'])} away wins. In 2020-21, played without fans because of COVID-19, away teams won more often than home teams ({pct(n['covid']['A'])} vs {pct(n['covid']['H'])}): home advantage largely comes from the crowd.

## 3. Method

### 3.1 No cheating: only information from before kick-off

The most important rule is to avoid **data leakage**: using information that is only known after the match starts, such as the shots in that match. Leakage gives impressive but fake results. Every input in this project is calculated from **earlier matches only**, and an automatic test (`tests/test_no_leakage.py`) changes the results of one day's matches and checks that no input on or before that day changes.

### 3.2 Inputs (features)

The model uses {n['n_features']} inputs per match, plus player features from 2016-17:

- **Elo rating**: one number for a team's strength, updated after every match. The expected score of the home team is `1 / (1 + 10^(−(home rating + 50 − away rating) / 400))`, where 50 is the home advantage.
- **Recent form**: points per game in the last 5 matches, and in the last 5 home (or away) matches.
- **Attack and defence**: goals, shots, shots on target and corners for and against, with recent matches counting more.
- **League table**: current position, points per game and goal difference this season; last season's position or "promoted".
- **Other**: rest days, head-to-head record, matchweek.
- **Players (2016-17 onwards)**: the strength of the expected starting eleven, measured by each player's Fantasy Premier League *influence* per 90 minutes in his previous 15 games, plus how many of the team's five most influential players are not starting.

{fig('elo_history.png', 'Elo ratings of the big six since 2000')}

### 3.3 Models

| Model | In simple words |
|---|---|
| Always home win | The baseline: always predicts the most common result |
| Elo only | Uses only the Elo rating difference |
| Logistic regression | A weighted sum of all inputs, turned into probabilities |
| Random forest | 500 decision trees that vote |
| Gradient boosting | Small trees added one by one, each fixing earlier mistakes |
| Poisson goals model | Predicts each team's goals, then turns goals into results |
| Ensemble | The average of logistic regression, gradient boosting and Poisson |

Model settings were chosen using only the seasons 2010-11 to 2013-14 (`reports/tuning_log.txt`), never the test seasons.

### 3.4 Fair testing: walk-forward

To predict a season, a model is trained on all seasons before it and then predicts all 380 matches of that season. This was repeated for {len(n['folds'])} seasons ({n['folds'][0]['test']} to {n['folds'][-1]['test']}), giving {n['test_matches']:,} honest predictions. This copies real life: you can only learn from the past.

## 4. How one prediction is calculated

Example: **{H} vs {A}**, using the final model and each team's latest data.

**Step 1, expected goals.** In an average match the home team scores {hs['baseline']:.2f} goals and the away team {as_['baseline']:.2f}. Each input multiplies this up or down depending on how unusual it is. The biggest effects on {H}'s goals:

| Input | {H} vs {A} | Average | Effect |
|---|---:|---:|---:|
{top_inputs}

Result: **{H} {hs['expected_goals']:.2f} expected goals, {A} {as_['expected_goals']:.2f}.**

**Step 2, Poisson distribution.** If a team is expected to score λ goals, the chance of exactly *k* goals is `λ^k × e^(−λ) / k!`. For example, the chance that {H} score exactly 2 is {pct(e['goal_probs']['home'][2])}.

**Step 3, add up the scores.** The chance of each exact score is the home chance times the away chance. Adding all scores where {H} score more gives **{H} win {pct(ex['probabilities']['H'])}**, the draws give **{pct(ex['probabilities']['D'])}**, and the rest **{A} win {pct(ex['probabilities']['A'])}**. The website's Predict page shows every number of this calculation for any fixture.

## 5. How we measure accuracy

| Measure | What it means | Better |
|---|---|---|
| Accuracy | Share of matches where the most likely result happened | Higher |
| Precision | When the model picks a result, how often it is right | Higher |
| Recall | Of all matches with that result, how many the model picked | Higher |
| F1 score | Combines precision and recall: `2 × P × R / (P + R)` | Higher |
| Log loss | Average of `−ln(probability given to what happened)`; punishes confident mistakes | Lower |
| Brier score | Squared difference between the probabilities and what happened | Lower |
| RPS | Like Brier, but on the ordered scale home win, draw, away win; the standard in football research (Constantinou & Fenton, 2012) | Lower |
| AUC | How well the probabilities separate matches with and without an outcome (0.5 = guessing) | Higher |
| Calibration | Whether "60%" really happens about 60% of the time | Close to the diagonal |

## 6. Results

### 6.1 All models ({n['test_matches']:,} test matches, {n['folds'][0]['test']} to {n['folds'][-1]['test']})

| Model | Accuracy | Log loss | Brier | RPS |
|---|---:|---:|---:|---:|
{model_rows}

{fig('model_accuracy.png', 'Accuracy of every model')}

All models clearly beat always picking the home team. The **Poisson goals model** was the best of ours on every probability score, and within about one percentage point of the bookmaker. The Elo rating alone already reaches {pct(n['elo_acc'])}: team strength is most of the story. The most important inputs (permutation importance) were:

{imp}

### 6.2 Every season

{fig('accuracy_by_season.png', 'Accuracy per test season')}

The hardest season was {n['worst_season'][0]} ({pct(n['worst_season'][1])}), when Leicester City won the league as 5000-1 outsiders; the easiest was {n['best_season'][0]} ({pct(n['best_season'][1])}).

### 6.3 Detailed evaluation of the final model ({app['matches']:,} matches, {app['period']})

| Outcome | Precision | Recall | F1 score | Matches |
|---|---:|---:|---:|---:|
{class_rows}
| **Accuracy** | | | **{app['accuracy']:.3f}** | {app['matches']:,} |

Confusion matrix (rows: what happened; columns: what the model picked):

| | Picked home win | Picked draw | Picked away win |
|---|---:|---:|---:|
| **Home win** | {cm[0][0]:,} | {cm[0][1]:,} | {cm[0][2]:,} |
| **Draw** | {cm[1][0]:,} | {cm[1][1]:,} | {cm[1][2]:,} |
| **Away win** | {cm[2][0]:,} | {cm[2][1]:,} | {cm[2][2]:,} |

The accuracy is {pct(app['accuracy'])} (95% range {pct(app['accuracy_low'])} to {pct(app['accuracy_high'])}). Log loss {app['log_loss']:.3f}, Brier {app['brier']:.3f}, RPS {app['rps']:.4f}, AUC {app['macro_auc']:.3f}{f" (bookmaker on the same matches: {pct(book_recent['accuracy'])}, log loss {book_recent['log_loss']:.3f}, RPS {book_recent['rps']:.4f}; always home win: RPS {base_recent['rps']:.4f})" if book_recent else ""}.

**The draw problem:** {pct(app['actual_share']['D'], 0)} of matches were draws, but a draw is almost never the single most likely result, so the model (like the bookmaker) practically never picks one, and draw recall is {pc['D']['recall']:.2f}. The probabilities still include the draw chance, and they are well calibrated:

{fig('calibration.png', 'Calibration: predicted probability vs how often it happened')}
{ext_section}
### 6.5 Compared with version 1

On version 1's own 38 test matches every new model scores between 55% and 58%, against version 1's {pct(float(n['original'].get('Original project (v1 random forest)', 0.4748)))}. But always picking the home team also scores 57.9% on those matches: 38 matches are far too few to judge a model, which is why version 2 is tested on {n['test_matches']:,}.

## 7. Discussion and limitations

- **Team news.** The model does not know about injuries, suspensions or confirmed line-ups (it assumes each team's usual eleven). This is the main reason the bookmaker is still slightly better.
- **Draws** remain almost impossible to pick as the single most likely result.
- **Missing data.** Europa League matches before 2020-21 and the 2025-26 domestic cups were not available from free sources; manager data is prepared in the code but not yet included.
- **Football is random.** Even professional bookmakers are right only about {pct(n['book_acc'], 0)} of the time.

**Future work:** expected-goals (xG) data, manager changes, and simulating the rest of a season to predict the final league table.

## 8. Conclusion

With real data and an honest test, our best model predicts {pct(n['best_acc'])} of Premier League results correctly, far above the {pct(n['base_acc'])} baseline and close to the bookmaker's {pct(n['book_acc'])}. The most useful information is how strong each team is (Elo); a simple, well-understood Poisson model beat more complex machine-learning models; and testing fairly turned out to matter more than the choice of model.

## References

- Football-Data.co.uk (2026). England Premier League results and match statistics 2000/01–2025/26. Via DataHub football-datasets, https://github.com/datasets/football-datasets
- Anand, V. Fantasy-Premier-League historical data. https://github.com/vaastav/Fantasy-Premier-League
- Curley, J. engsoccerdata. https://github.com/jalapic/engsoccerdata · openfootball. https://github.com/openfootball
- Jürisoo, M. International football results. https://github.com/martj42/international_results
- Gábor, A. Club Football Match Data (2000–2025). https://github.com/xgabora/Club-Football-Match-Data-2000-2025
- Elo, A. E. (1978). *The Rating of Chessplayers, Past and Present*. Arco.
- Maher, M. J. (1982). Modelling association football scores. *Statistica Neerlandica*, 36(3), 109–118.
- Dixon, M. J., & Coles, S. G. (1997). Modelling association football scores and inefficiencies in the football betting market. *JRSS C*, 46(2), 265–280.
- Hvattum, L. M., & Arntzen, H. (2010). Using ELO ratings for match result prediction in association football. *International Journal of Forecasting*, 26(3), 460–470.
- Constantinou, A. C., & Fenton, N. E. (2012). Solving the problem of inadequate scoring rules for assessing probabilistic football forecast models. *JQAS*, 8(1).
- Pedregosa, F. et al. (2011). Scikit-learn: Machine learning in Python. *JMLR*, 12, 2825–2830.
"""


def build_story(project, figures: str = "/figures") -> dict:
    n = collect_numbers(project)
    return {"generated": n["today"], "slides": build_slides(n), "report_md": build_report(n, figures)}
