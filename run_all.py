"""Run the entire Heat Check pipeline, end to end.

Usage (from the repo root):   python run_all.py

Order: generate data -> clean -> load SQLite -> run SQL -> Excel -> web dashboard.
Stops immediately if any step fails.
"""
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STEPS = [
    ("1. Generate synthetic raw data", "generate_data.py"),
    ("2. Clean data + add calculated fields", "clean_data.py"),
    ("3a. Load clean data into SQLite", "build_database.py"),
    ("3b. Run SQL analysis queries", "run_sql_analysis.py"),
    ("4. Build Excel dashboard", "build_excel.py"),
    ("5. Build web dashboard (docs/index.html)", "export_dashboard_data.py"),
]

start = time.time()
for title, script in STEPS:
    print(f"\n{'=' * 70}\n{title}  ->  scripts/{script}\n{'=' * 70}", flush=True)
    t0 = time.time()
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / script)], cwd=ROOT)
    if result.returncode != 0:
        sys.exit(f"\nStep failed: {script} (exit code {result.returncode})")
    print(f"[done in {time.time() - t0:.1f}s]")

print(f"\nPipeline finished in {time.time() - start:.1f}s. Open docs/index.html in a browser to see the dashboard.")
