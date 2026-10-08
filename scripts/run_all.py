"""Run the whole pipeline from raw data to figures (about 5-10 minutes).

Run:  uv run python scripts/run_all.py
"""

import runpy
from pathlib import Path

HERE = Path(__file__).parent

if __name__ == "__main__":
    for step in ["01_download_data.py", "02_build_features.py", "03_evaluate_models.py", "04_make_figures.py"]:
        print(f"\n{'=' * 70}\n{step}\n{'=' * 70}")
        runpy.run_path(str(HERE / step), run_name="__main__")
