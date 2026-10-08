"""A tiny web server for the UI, using only Python's standard library.

    uv run python app.py          ->  open http://127.0.0.1:8000

URLs
----
/                         the single-page UI (static/index.html)
/api/overview             headline numbers
/api/predict?home=&away=  predict one fixture
/api/teams                current Elo ranking
/api/elo?team=A&team=B    Elo history of one or more teams
/api/models               evaluation results
/api/seasons              list of seasons
/api/season?label=2019-20 league table (+ predictions for test seasons)
"""

from __future__ import annotations

import json
import mimetypes
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import numpy as np

from .api import ProjectData

STATIC_DIR = Path(__file__).parent / "static"


def _json_default(value):
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(f"Cannot serialise {type(value)}")


def make_handler(project: ProjectData):
    routes = {
        "/api/overview": lambda q: project.overview(),
        "/api/predict": lambda q: project.predict(q["home"][0], q["away"][0]),
        "/api/teams": lambda q: project.teams(),
        "/api/elo": lambda q: project.elo_history(q.get("team", [])),
        "/api/models": lambda q: project.models(),
        "/api/seasons": lambda q: project.seasons(),
        "/api/season": lambda q: project.season(q["label"][0]),
    }

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            url = urlparse(self.path)
            if url.path in routes:
                try:
                    body = routes[url.path](parse_qs(url.query))
                    self._send(HTTPStatus.OK, json.dumps(body, default=_json_default).encode(), "application/json")
                except (KeyError, ValueError) as error:
                    message = json.dumps({"error": str(error).strip("'\"")}).encode()
                    self._send(HTTPStatus.BAD_REQUEST, message, "application/json")
                return
            name = "index.html" if url.path in ("", "/") else url.path.lstrip("/")
            path = (STATIC_DIR / name).resolve()
            if not path.is_file() or STATIC_DIR.resolve() not in path.parents:
                self._send(HTTPStatus.NOT_FOUND, b"Not found", "text/plain")
                return
            content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            self._send(HTTPStatus.OK, path.read_bytes(), content_type)

        def _send(self, status, body: bytes, content_type: str):
            self.send_response(status)
            self.send_header("Content-Type", f"{content_type}; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):  # keep the terminal quiet
            pass

    return Handler


def serve(host: str = "127.0.0.1", port: int = 8000, open_browser: bool = True) -> None:
    print("Loading data and training the final model (a few seconds) ...")
    project = ProjectData()
    # Warm the cache with the default fixture so the first click is instant.
    project.predict(*project.default_fixture())
    server = ThreadingHTTPServer((host, port), make_handler(project))
    url = f"http://{host}:{port}"
    print(f"Ready: open {url}  (press Ctrl+C to stop)")
    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
