"""Interactive demo: pick two teams and get win/draw/loss probabilities.

Run:  uv run --extra app python app.py      then open http://127.0.0.1:7860
"""

import gradio as gr

from eplpred import data
from eplpred.predict import Predictor

predictor = Predictor(data.load_matches())


def predict(home_team: str, away_team: str):
    if home_team == away_team:
        return {"Pick two different teams": 1.0}, ""
    p = predictor.predict(home_team, away_team)
    probs = {f"{home_team} win": p.home_win, "Draw": p.draw, f"{away_team} win": p.away_win}
    detail = (
        f"**Expected goals:** {p.expected_home_goals:.2f} - {p.expected_away_goals:.2f}  \n"
        f"**Most likely score:** {p.most_likely_score}"
    )
    return probs, detail


with gr.Blocks(title="Premier League match predictor") as demo:
    gr.Markdown(
        "# Premier League match predictor\n"
        "Trained on every Premier League match from 2000-01 to 2025-26 "
        "(data: Football-Data.co.uk). Uses each team's latest Elo rating, form and league position."
    )
    with gr.Row():
        home = gr.Dropdown(predictor.teams, value="Arsenal", label="Home team")
        away = gr.Dropdown(predictor.teams, value="Chelsea", label="Away team")
    button = gr.Button("Predict", variant="primary")
    probabilities = gr.Label(label="Probabilities", num_top_classes=3)
    details = gr.Markdown()
    button.click(predict, inputs=[home, away], outputs=[probabilities, details])

if __name__ == "__main__":
    demo.launch()
