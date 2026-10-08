"""Step 6: write the report and the slides from the current results.

Writes:
  docs/REPORT.md     the written report (also on the website's Report page)
  docs/slides.json   the slide content (also on the website's Slides page)
  docs/slides.pptx   the same slides as a PowerPoint file, with speaker notes
                     (needs Node.js and `npm install pptxgenjs`; skipped otherwise)

Run this after any change to the data or models (scripts/run_all.py does).

Run:  uv run python scripts/06_make_report.py
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

from eplpred import config
from eplpred.story import build_story
from eplpred.web.api import ProjectData

DOCS = config.ROOT / "docs"

if __name__ == "__main__":
    print("Building report and slides from the current results ...")
    story = build_story(ProjectData(), figures="../reports/figures")
    DOCS.mkdir(exist_ok=True)
    (DOCS / "REPORT.md").write_text(story["report_md"], encoding="utf-8")
    (DOCS / "slides.json").write_text(json.dumps(story["slides"], indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"Saved docs/REPORT.md and docs/slides.json ({len(story['slides'])} slides)")

    node = shutil.which("node")
    script = Path(__file__).with_name("make_slides.js")
    if node:
        env = dict(os.environ)
        npm = shutil.which("npm")
        if npm:  # also find a globally installed pptxgenjs
            global_root = subprocess.run([npm, "root", "-g"], capture_output=True, text=True).stdout.strip()
            env["NODE_PATH"] = os.pathsep.join(filter(None, [env.get("NODE_PATH"), global_root]))
        result = subprocess.run([node, str(script)], cwd=config.ROOT, capture_output=True, text=True, env=env)
        print(result.stdout.strip() or result.stderr.strip())
    else:
        print("Node.js not found: docs/slides.pptx not rebuilt (the website's Slides page still works).")
