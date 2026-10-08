"""The project's web app: predictor, team ratings, model results, season explorer.

Run:  uv run python app.py        then open http://127.0.0.1:8000
      (add --no-browser to stop it opening a browser tab, --port 8080 to change the port)
"""

import argparse
import os

from eplpred.web.server import serve

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    serve(host=args.host, port=args.port, open_browser=not args.no_browser)
