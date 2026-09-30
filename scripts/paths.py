"""Central place for every folder/file path used by the pipeline.

All paths are built from the repository root (the folder that contains
`scripts/`), so the scripts work no matter where the repo is cloned and
no path is ever hardcoded.

Two datasets are supported:
  * synthetic (default): the public demo data in data/, outputs/, excel/, docs/
  * real: set the environment variable  HEATCHECK_DATASET=real  and every
    input/output moves under private/ (which is git-ignored), so real business
    data can never be committed or published by accident.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATASET = os.environ.get("HEATCHECK_DATASET", "synthetic").lower()
if DATASET not in ("synthetic", "real"):
    raise SystemExit("HEATCHECK_DATASET must be 'synthetic' or 'real'")

BASE = ROOT if DATASET == "synthetic" else ROOT / "private"

RAW_DIR = BASE / "data" / "raw"
CLEAN_DIR = BASE / "data" / "clean"
CLEANING_LOG = BASE / "data" / "cleaning_log.md"
DB_PATH = BASE / "data" / "heatcheck.db"

SQL_FILE = ROOT / "sql" / "analysis.sql"
SQL_RESULTS_DIR = BASE / "outputs" / "sql_results"
SENSITIVITY_DIR = BASE / "outputs" / "sensitivity"

EXCEL_PATH = BASE / "excel" / "HeatCheck_Dashboard.xlsx"
DOCS_DIR = BASE / "docs"
TEMPLATE_DIR = ROOT / "scripts" / "templates"
DATA_TEMPLATES_DIR = ROOT / "data" / "templates"


def ensure_dirs() -> None:
    """Create output folders if they do not exist yet."""
    for folder in (RAW_DIR, CLEAN_DIR, SQL_RESULTS_DIR, SENSITIVITY_DIR, EXCEL_PATH.parent, DOCS_DIR):
        folder.mkdir(parents=True, exist_ok=True)
