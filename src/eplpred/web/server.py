"""The UI and API, served by Waitress locally and in production.

    uv run python app.py          ->  open http://127.0.0.1:8000

URLs
----
/                         the single-page UI (static/index.html)
/healthz                  readiness (data and model are loaded before listening)
/api/overview             headline numbers
/api/predict?home=&away=  predict one fixture
/api/teams                current Elo ranking
/api/elo?team=A&team=B    Elo history of one or more teams
/api/models               evaluation results
/api/evaluation           every evaluation metric (precision, recall, F1, AUC, ...)
/api/seasons              list of seasons
/api/season?label=2019-20 league table (+ predictions for test seasons)
/api/datasets             every dataset the project uses (source, licence, file)
/api/data?dataset=...     one page of rows (filters: q, season, team; sort, dir, page, size)
/api/data.csv?dataset=... the same rows as a CSV download
"""

from __future__ import annotations

import json
import mimetypes
import threading
import webbrowser
from http import HTTPStatus
from pathlib import Path
from urllib.parse import parse_qs

import numpy as np
from waitress import create_server

from .api import ProjectData

STATIC_DIR = Path(__file__).parent / "static"


def _json_default(value):
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(f"Cannot serialise {type(value)}")


def make_application(project: ProjectData):
    routes = {
        "/healthz": lambda q: {"status": "ok"},
        "/api/overview": lambda q: project.overview(),
        "/api/predict": lambda q: project.predict(q["home"][0], q["away"][0]),
        "/api/teams": lambda q: project.teams(),
        "/api/elo": lambda q: project.elo_history(q.get("team", [])),
        "/api/models": lambda q: project.models(),
        "/api/evaluation": lambda q: project.evaluation(),
        "/api/seasons": lambda q: project.seasons(),
        "/api/season": lambda q: project.season(q["label"][0]),
        "/api/datasets": lambda q: project.explorer.catalogue(),
        "/api/data": lambda q: project.explorer.page(q["dataset"][0], q),
    }

    def application(environ, start_response):
        method = environ["REQUEST_METHOD"]
        extra_headers = []
        if method not in ("GET", "HEAD"):
            status, body, content_type = HTTPStatus.METHOD_NOT_ALLOWED, b"Method not allowed", "text/plain"
            extra_headers.append(("Allow", "GET, HEAD"))
        else:
            path_name = environ.get("PATH_INFO", "/")
            if path_name == "/api/data.csv":
                query = parse_qs(environ.get("QUERY_STRING", ""))
                try:
                    key = query["dataset"][0]
                    status, body, content_type = HTTPStatus.OK, project.explorer.csv(key, query), "text/csv"
                    extra_headers.append(("Content-Disposition", f'attachment; filename="{key}.csv"'))
                except (KeyError, ValueError) as error:
                    status, body, content_type = HTTPStatus.BAD_REQUEST, str(error).encode(), "text/plain"
            elif path_name in routes:
                try:
                    result = routes[path_name](parse_qs(environ.get("QUERY_STRING", "")))
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
            ("Content-Type", f"{content_type}; charset=utf-8"),
            ("Content-Length", str(len(body))),
            ("Cache-Control", "no-store"),
            *extra_headers,
        ])
        return [] if method == "HEAD" else [body]

    return application


def serve(host: str = "127.0.0.1", port: int = 8000, open_browser: bool = True) -> None:
    print("Loading data and training the final model (a few seconds) ...", flush=True)
    project = ProjectData()
    # Warm the cache with the default fixture so the first click is instant.
    project.predict(*project.default_fixture())
    server = create_server(make_application(project), host=host, port=port, threads=4)
    url = f"http://{host}:{server.effective_port}"
    print(f"Ready: open {url}  (press Ctrl+C to stop)", flush=True)
    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.run()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.close()
