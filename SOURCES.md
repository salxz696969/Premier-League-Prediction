# Sources

Everything this project uses or builds on, so you can cite it in a report.

## Data

| # | Source | What we use | Licence | Link |
|---|---|---|---|---|
| 1 | **Football-Data.co.uk** (Joseph Buchdahl) | Results, half-time scores, shots, shots on target, corners, fouls, cards, referees for every Premier League match 2000-01 to 2025-26 | Free to download (see the site for terms) | https://www.football-data.co.uk/englandm.php |
| 2 | **DataHub "football-datasets"** (GitHub mirror of source 1) | The season CSVs are downloaded from this mirror | Public Domain Dedication and License (PDDL) v1.0 | https://github.com/datasets/football-datasets |
| 3 | **Club Football Match Data (2000-2025)** by Adam Gábor | Bet365 pre-match odds (originally from Football-Data.co.uk), used **only as a benchmark**, never as a model input | MIT | https://github.com/xgabora/Club-Football-Match-Data-2000-2025 |
| 4 | **engsoccerdata** (James Curley) | FA Cup and League Cup dates 2000-01 to 2017-18, Champions League 2000-01 to 2010-11 (fatigue features) | GPL-2 or later | https://github.com/jalapic/engsoccerdata |
| 5 | **openfootball** (football.db) | Champions League 2011-12 to 2025-26, Europa League 2020-21 to 2024-25, FA Cup and EFL Cup 2018-19 to 2024-25 | CC0 1.0 | https://github.com/openfootball/champions-league, https://github.com/openfootball/england |
| 6 | **International football results** (Mart Jürisoo) | Dates of men's international matches, to find international breaks | CC0 1.0 | https://github.com/martj42/international_results |
| 7 | **Fantasy Premier League historical data** (Vaastav Anand) | Player minutes, starts, FPL influence / ICT index and prices per match, 2016-17 to 2025-26 | MIT | https://github.com/vaastav/Fantasy-Premier-League |
| 8 | **transfermarkt-datasets** (dcaribou on GitHub), *optional, not included yet* | Managers of both teams per match, 2012-13 onwards | CC0 1.0 | https://github.com/dcaribou/transfermarkt-datasets |

FPL's influence score comes from the Premier League's official Fantasy game (its ICT index is built on Opta match data). Football-Data.co.uk and Fantasy Premier League are the original sources behind rows 1–3 and 7.

The raw files are saved in `data/raw/` exactly as downloaded (FPL and engsoccerdata files are trimmed to the columns and seasons used). `scripts/01_download_data.py` reproduces them.

**Suggested citation for the data**

> Football-Data.co.uk (2026). *England Premier League historical results and match statistics, 2000/01–2025/26*. Retrieved via DataHub football-datasets (https://github.com/datasets/football-datasets) on 8 October 2026.
>
> Gábor, A. (2026). *Club Football Match Data (2000–2025)* [Data set]. GitHub. https://github.com/xgabora/Club-Football-Match-Data-2000-2025

## Methods

| Topic | Reference | Where it's used |
|---|---|---|
| Elo rating system | Elo, A. E. (1978). *The Rating of Chessplayers, Past and Present*. Arco. | `src/eplpred/elo.py` |
| Elo for football (goal-difference multiplier, home advantage) | World Football Elo Ratings, https://www.eloratings.net/about; ClubElo, http://clubelo.com/System | `src/eplpred/elo.py` |
| Elo works well for football prediction | Hvattum, L. M., & Arntzen, H. (2010). Using ELO ratings for match result prediction in association football. *International Journal of Forecasting*, 26(3), 460–470. https://doi.org/10.1016/j.ijforecast.2009.10.002 | Elo-only baseline model |
| Poisson model for goals | Maher, M. J. (1982). Modelling association football scores. *Statistica Neerlandica*, 36(3), 109–118. https://doi.org/10.1111/j.1467-9574.1982.tb00782.x | `PoissonGoals` in `src/eplpred/models.py` |
| Poisson model for betting markets | Dixon, M. J., & Coles, S. G. (1997). Modelling association football scores and inefficiencies in the football betting market. *Journal of the Royal Statistical Society: Series C*, 46(2), 265–280. https://doi.org/10.1111/1467-9876.00065 | `PoissonGoals` |
| Ranked Probability Score (RPS) | Constantinou, A. C., & Fenton, N. E. (2012). Solving the problem of inadequate scoring rules for assessing probabilistic football forecast models. *Journal of Quantitative Analysis in Sports*, 8(1). https://doi.org/10.1515/1559-0410.1418 | `src/eplpred/evaluation.py` |
| Brier score | Brier, G. W. (1950). Verification of forecasts expressed in terms of probability. *Monthly Weather Review*, 78(1), 1–3. | `src/eplpred/evaluation.py` |
| Bookmaker odds as a benchmark | Štrumbelj, E. (2014). On determining probability forecasts from betting odds. *International Journal of Forecasting*, 30(4), 934–943. https://doi.org/10.1016/j.ijforecast.2014.02.008 | Margin removal in `src/eplpred/data.py` |
| Walk-forward (time-series) evaluation | Hyndman, R. J., & Athanasopoulos, G. (2021). *Forecasting: Principles and Practice* (3rd ed.), §5.10 "Time series cross-validation". https://otexts.com/fpp3/tscv.html | `src/eplpred/evaluation.py` |
| Home advantage disappeared without fans (COVID-19) | McCarrick, D., Bilalic, M., Neave, N., & Wolfson, S. (2021). Home advantage during the COVID-19 pandemic: Analyses of European football leagues. *Psychology of Sport and Exercise*, 56, 102013. https://doi.org/10.1016/j.psychsport.2021.102013 | Discussion of 2020-21 results |
| Permutation feature importance | Breiman, L. (2001). Random forests. *Machine Learning*, 45, 5–32. https://doi.org/10.1023/A:1010933404324 | `scripts/04_make_figures.py` |
| Machine-learning library | Pedregosa, F. et al. (2011). Scikit-learn: Machine learning in Python. *Journal of Machine Learning Research*, 12, 2825–2830. | All models |

## Software

Python, pandas, NumPy, SciPy, scikit-learn, matplotlib, pytest. The web app uses only the Python standard library and plain HTML/CSS/JavaScript.

## Design

The web app follows Apple's interface design principles as summarised in the **apple-design** skill by Emil Kowalski (https://github.com/emilkowalski/skills), which draws on Apple WWDC talks such as *Designing Fluid Interfaces* (2018) and *The Details of UI Typography* (2020).
