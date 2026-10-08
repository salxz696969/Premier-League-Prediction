FROM ghcr.io/astral-sh/uv:0.12.21 AS uv
FROM python:3.13-slim

COPY --from=uv /uv /bin/uv
ENV UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    OPENBLAS_NUM_THREADS=1 \
    OMP_NUM_THREADS=1 \
    MPLCONFIGDIR=/tmp/matplotlib \
    HOST=0.0.0.0 \
    PORT=8000
WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev --python /usr/local/bin/python
COPY app.py ./
COPY data/processed/matches.csv ./data/processed/matches.csv
# All raw data (the Data page shows every source) and the charts, report and slides
COPY data/raw ./data/raw
COPY reports/*.csv ./reports/
COPY reports/figures ./reports/figures
COPY docs/REPORT.md docs/slides.json docs/slides.pptx ./docs/
COPY scripts/02_build_features.py ./scripts/02_build_features.py
# Generate features at build time; the runtime filesystem can stay read-only.
RUN .venv/bin/python scripts/02_build_features.py

USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=5s --start-period=120s --retries=6 \
    CMD ["/app/.venv/bin/python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4).read()"]
CMD ["/app/.venv/bin/python", "app.py", "--no-browser"]
