"""The web UI's data layer and server (no browser needed)."""

import json
import threading
import urllib.error
import urllib.request
from waitress import create_server

import pytest

from eplpred.web.api import ProjectData, league_table
from eplpred.web.server import make_application


@pytest.fixture(scope="module")
def project():
    return ProjectData()


@pytest.fixture(scope="module")
def base_url(project):
    server = create_server(make_application(project), host="127.0.0.1", port=0)
    threading.Thread(target=server.run, daemon=True).start()
    yield f"http://127.0.0.1:{server.effective_port}"
    server.close()
    server.task_dispatcher.shutdown()


def get(url):
    with urllib.request.urlopen(url, timeout=60) as response:
        return response.status, response.read()


def test_prediction_probabilities_sum_to_one(project):
    home, away = project.default_fixture()
    p = project.predict(home, away)
    assert sum(p["probabilities"].values()) == pytest.approx(1)
    assert len(p["top_scores"]) == 5
    assert p["home_stats"]["elo"] is not None


def test_league_table_matches_known_season(project):
    season = project.matches[project.matches["season_label"] == "2015-16"]
    table = league_table(season)
    assert table[0]["team"] == "Leicester City" and table[0]["points"] == 81
    assert all(r["played"] == 38 for r in table)


def test_test_seasons_have_predictions(project):
    assert project.season("2019-20")["matches"]
    assert project.season("2005-06")["matches"] is None


def test_every_endpoint_answers(base_url):
    for path in ["/", "/healthz", "/app.js", "/app.css", "/api/overview", "/api/teams", "/api/models",
                 "/api/seasons", "/api/season?label=2019-20", "/api/elo?team=Arsenal"]:
        status, body = get(base_url + path)
        assert status == 200, path
    overview = json.loads(get(base_url + "/api/overview")[1])
    assert overview["matches"] == 9880


def test_bad_requests_are_rejected(base_url):
    with pytest.raises(urllib.error.HTTPError) as err:
        get(base_url + "/api/predict?home=Nowhere&away=Arsenal")
    assert err.value.code == 400
    with pytest.raises(urllib.error.HTTPError) as err:
        get(base_url + "/../pyproject.toml")
    assert err.value.code == 404


def test_health_and_head_requests(base_url):
    assert json.loads(get(base_url + "/healthz")[1]) == {"status": "ok"}
    request = urllib.request.Request(base_url + "/", method="HEAD")
    with urllib.request.urlopen(request, timeout=10) as response:
        assert response.status == 200
        assert int(response.headers["Content-Length"]) > 0
        assert response.read() == b""


def test_post_is_rejected(base_url):
    request = urllib.request.Request(base_url + "/healthz", method="POST")
    with pytest.raises(urllib.error.HTTPError) as err:
        urllib.request.urlopen(request, timeout=10)
    assert err.value.code == 405
    assert err.value.headers["Allow"] == "GET, HEAD"


def test_explanation_reproduces_the_prediction(project):
    """The step-by-step explanation must give exactly the model's own numbers."""
    import math

    home, away = project.default_fixture()
    p = project.predict(home, away)
    e = p["explain"]
    for side in ("home", "away"):
        d = e["sides"][side]
        total = sum(i["contribution"] for i in d["items"]) + d["other_contribution"] + d["indicator_contribution"]
        assert math.exp(d["intercept"] + total) == pytest.approx(d["expected_goals"])
        assert d["expected_goals"] == pytest.approx(p["expected_goals"][side])
    for o in ("H", "D", "A"):
        assert e["outcome"][o] == pytest.approx(p["probabilities"][o])


def test_evaluation_report_metrics(project):
    report = project.evaluation()
    for entry in report["entries"]:
        assert 0 < entry["accuracy"] < 1
        assert sum(c["support"] for c in entry["per_class"]) == entry["matches"]
        assert sum(map(sum, entry["confusion"])) == entry["matches"]
        correct = sum(entry["confusion"][i][i] for i in range(3))
        assert correct / entry["matches"] == pytest.approx(entry["accuracy"])


def test_data_explorer_filters_and_csv(base_url):
    catalogue = json.loads(get(base_url + "/api/datasets")[1])
    assert len(catalogue["datasets"]) == 8
    page = json.loads(get(base_url + "/api/data?dataset=matches&season=2015-16&team=Leicester%20City")[1])
    assert page["matching"] == 38
    status, body = get(base_url + "/api/data.csv?dataset=matches&season=2015-16&team=Leicester%20City")
    assert status == 200 and len(body.decode().strip().splitlines()) == 39
    with pytest.raises(urllib.error.HTTPError):
        get(base_url + "/api/data?dataset=nope")
