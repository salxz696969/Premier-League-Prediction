"""The UI and API, served by Waitress locally and in production.

    uv run python app.py          ->  open http://127.0.0.1:8000

URLs
----
/                         the single-page UI (static/index.html)
/healthz                  readiness: 503 with loading progress until the data and model are loaded, then 200
/api/overview             headline numbers
/api/predict?home=&away=  predict one fixture
/api/teams                current Elo ranking
/api/elo?team=A&team=B    Elo history of one or more teams
/api/models               evaluation results
/api/evaluation           every evaluation metric (precision, recall, F1, AUC, ...)
/api/seasons              list of seasons
/api/season?label=2019-20 league table (+ predictions for test seasons)
/api/story                report (HTML) and slides, from the current results
/figures/<name>.png       the charts in reports/figures
/logos/<name>.png         club crests (data/raw/logos)
/downloads/slides.pptx    the slides as PowerPoint (docs/slides.pptx)
/downloads/REPORT.md      the report as Markdown (docs/REPORT.md)
/api/datasets             every dataset the project uses (source, licence, file)
/api/data?dataset=...     one page of rows (filters: q, season, team; sort, dir, page, size)
/api/data.csv?dataset=... the same rows as a CSV download
"""

from __future__ import annotations

import json
import mimetypes
import threading
import time
import traceback
import webbrowser
from http import HTTPStatus
from pathlib import Path
from urllib.parse import parse_qs

import numpy as np
from waitress import create_server

from .. import config, logos
from .api import ProjectData

STATIC_DIR = Path(__file__).parent / "static"
FIGURES_DIR = config.FIGURES_DIR
DOCS_DIR = config.ROOT / "docs"
DOWNLOADS = {
    "slides.pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "REPORT.md": "text/markdown",
}


def _json_default(value):
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(f"Cannot serialise {type(value)}")


def _one(query: dict, name: str) -> str:
    return (query.get(name) or [""])[0]


class Startup:
    """Loads the project in a background thread while the server already
    answers: the page shows a loading screen and /healthz reports progress."""

    STEPS = ["Loading matches and features", "Training the model with player data", "Loading the results",
             "Preparing matches, tables and players", "Preparing the evaluation and the report"]

    def __init__(self):
        self.project: ProjectData | None = None
        self.step, self.done, self.error = self.STEPS[0], 0, None

    def advance(self, step: str) -> None:
        self.done = self.STEPS.index(step)
        self.step = step
        print(f"  {step} ...", flush=True)

    def run(self) -> None:
        try:
            project = ProjectData(progress=self.advance)
            # Warm every lazy part so no page waits on its first visit.
            self.advance("Preparing matches, tables and players")
            football = project.football
            season = football.seasons()[0]
            football.competitions(season)
            football.table(season)
            football.player_list(season)
            self.advance("Preparing the evaluation and the report")
            project.evaluation()
            project.story()
            project.predict(*project.default_fixture())
            self.done, self.project = len(self.STEPS), project
        except Exception as error:  # shown on the loading screen and in the log
            traceback.print_exc()
            self.error = f"{type(error).__name__}: {error}"

    def status(self) -> dict:
        if self.project is not None:
            return {"status": "ok"}
        return {"status": "error" if self.error else "loading", "step": self.step, "done": self.done,
                "total": len(self.STEPS), "error": self.error}


def _routes(project: ProjectData) -> dict:
    return {
        "/api/overview": lambda q: project.overview(),
        "/api/predict": lambda q: project.predict(q["home"][0], q["away"][0]),
        "/api/teams": lambda q: project.teams(),
        "/api/elo": lambda q: project.elo_history(q.get("team", [])),
        "/api/models": lambda q: project.models(),
        "/api/evaluation": lambda q: project.evaluation(),
        "/api/seasons": lambda q: project.seasons(),
        "/api/season": lambda q: project.season(q["label"][0]),
        "/api/story": lambda q: project.story(),
        "/api/football/overview": lambda q: {"seasons": project.football.seasons(),
                                             "competitions": project.football.competitions(_one(q, "season") or project.football.seasons()[0])},
        "/api/football/matches": lambda q: project.football.matches(_one(q, "season"), _one(q, "competition") or "premier_league", _one(q, "round") or None),
        "/api/football/match": lambda q: project.football.match(int(_one(q, "id"))),
        "/api/football/table": lambda q: project.football.table(_one(q, "season")),
        "/api/football/team": lambda q: project.football.team(_one(q, "name"), _one(q, "season")),
        "/api/football/players": lambda q: project.football.player_list(
            _one(q, "season"), _one(q, "team"), _one(q, "position"), _one(q, "q"), _one(q, "sort") or "points", int(_one(q, "page") or 0)),
        "/api/football/player": lambda q: project.football.player(_one(q, "key")),
        "/api/datasets": lambda q: project.explorer.catalogue(),
        "/api/data": lambda q: project.explorer.page(q["dataset"][0], q),
    }


def make_application(project: ProjectData | Startup):
    """WSGI app. Pass a loaded ProjectData, or a Startup that is still loading."""
    if isinstance(project, Startup):
        startup = project
    else:
        startup = Startup()
        startup.project, startup.done = project, len(Startup.STEPS)
    cache = {}

    def routes() -> dict:
        if "routes" not in cache:
            cache["routes"] = _routes(startup.project)
        return cache["routes"]

    def application(environ, start_response):
        method = environ["REQUEST_METHOD"]
        extra_headers = []
        if method not in ("GET", "HEAD"):
            status, body, content_type = HTTPStatus.METHOD_NOT_ALLOWED, b"Method not allowed", "text/plain"
            extra_headers.append(("Allow", "GET, HEAD"))
        else:
            path_name = environ.get("PATH_INFO", "/")
            ready = startup.project is not None
            # Charts (reports/figures), club crests and the downloadable report / slides (docs/)
            file_dirs = {"/figures/": (FIGURES_DIR, None), "/logos/": (logos.LOGO_DIR, None), "/downloads/": (DOCS_DIR, DOWNLOADS)}
            prefix = next((p_ for p_ in file_dirs if path_name.startswith(p_)), None)
            if path_name == "/healthz":
                status = HTTPStatus.OK if ready else HTTPStatus.SERVICE_UNAVAILABLE
                body, content_type = json.dumps(startup.status()).encode(), "application/json"
            elif not ready and path_name.startswith("/api/"):
                status, content_type = HTTPStatus.SERVICE_UNAVAILABLE, "application/json"
                body = json.dumps({"error": "The app is still loading", "loading": True, **startup.status()}).encode()
                extra_headers.append(("Retry-After", "1"))
            elif prefix:
                folder, allowed = file_dirs[prefix]
                name = path_name[len(prefix):]
                path = (folder / name).resolve()
                if (allowed is not None and name not in allowed) or not path.is_file() or folder.resolve() not in path.parents:
                    status, body, content_type = HTTPStatus.NOT_FOUND, b"Not found", "text/plain"
                else:
                    status, body = HTTPStatus.OK, path.read_bytes()
                    content_type = DOWNLOADS.get(name) or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
                    if prefix == "/downloads/":
                        extra_headers.append(("Content-Disposition", f'attachment; filename="{name}"'))
            elif path_name == "/api/data.csv":
                query = parse_qs(environ.get("QUERY_STRING", ""))
                try:
                    key = query["dataset"][0]
                    status, body, content_type = HTTPStatus.OK, startup.project.explorer.csv(key, query), "text/csv"
                    extra_headers.append(("Content-Disposition", f'attachment; filename="{key}.csv"'))
                except (KeyError, ValueError) as error:
                    status, body, content_type = HTTPStatus.BAD_REQUEST, str(error).encode(), "text/plain"
            elif ready and path_name in routes():
                try:
                    result = routes()[path_name](parse_qs(environ.get("QUERY_STRING", "")))
                    status, body = HTTPStatus.OK, json.dumps(result, default=_json_default).encode()
                except (KeyError, ValueError) as error:
                    status = HTTPStatus.BAD_REQUEST
                    body = json.dumps({"error": str(error).strip("'\"")}).encode()
                content_type = "application/json"
            else:
                name = "index.html" if path_name in ("", "/") else path_name.lstrip("/")
                path = (STATIC_DIR / name).resolve()
                if not path.is_file() or STATIC_DIR.resolve() not in path.parents:
                    status, body, content_type = HTTPStatus.NOT_FOUND, b"Not found", "text/plain"
                else:
                    status, body = HTTPStatus.OK, path.read_bytes()
                    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        start_response(f"{status.value} {status.phrase}", [
            ("Content-Type", f"{content_type}; charset=utf-8" if content_type.startswith(("text/", "application/json", "application/javascript")) else content_type),
            ("Content-Length", str(len(body))),
            ("Cache-Control", "no-store"),
            *extra_headers,
        ])
        return [] if method == "HEAD" else [body]

    return application


def serve(host: str = "127.0.0.1", port: int = 8000, open_browser: bool = True) -> None:
    startup = Startup()
    server = create_server(make_application(startup), host=host, port=port, threads=4)
    url = f"http://{host}:{server.effective_port}"
    print(f"Open {url}  (press Ctrl+C to stop). The page shows a loading screen until the data is ready:", flush=True)

    def load():
        started = time.perf_counter()
        startup.run()
        if startup.project is not None:
            print(f"Ready in {time.perf_counter() - started:.0f} s.", flush=True)

    threading.Thread(target=load, daemon=True).start()
    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.run()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.close()
