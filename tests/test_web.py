"""The web UI's data layer and server (no browser needed)."""

import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from eplpred.web.api import ProjectData, league_table
from eplpred.web.server import make_handler


@pytest.fixture(scope="module")
def project():
    return ProjectData()


@pytest.fixture(scope="module")
def base_url(project):
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(project))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


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
    for path in ["/", "/app.js", "/app.css", "/api/overview", "/api/teams", "/api/models",
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
