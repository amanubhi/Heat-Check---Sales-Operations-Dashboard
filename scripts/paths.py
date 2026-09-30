"""Central place for every folder/file path used by the pipeline.

All paths are built from the repository root (the folder that contains
`scripts/`), so the scripts work no matter where the repo is cloned and
no path is ever hardcoded.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

RAW_DIR = ROOT / "data" / "raw"
CLEAN_DIR = ROOT / "data" / "clean"
CLEANING_LOG = ROOT / "data" / "cleaning_log.md"
DB_PATH = ROOT / "data" / "heatcheck.db"

SQL_FILE = ROOT / "sql" / "analysis.sql"
SQL_RESULTS_DIR = ROOT / "outputs" / "sql_results"

EXCEL_PATH = ROOT / "excel" / "HeatCheck_Dashboard.xlsx"
DOCS_DIR = ROOT / "docs"
TEMPLATE_DIR = ROOT / "scripts" / "templates"


def ensure_dirs() -> None:
    """Create output folders if they do not exist yet."""
    for folder in (RAW_DIR, CLEAN_DIR, SQL_RESULTS_DIR, EXCEL_PATH.parent, DOCS_DIR):
        folder.mkdir(parents=True, exist_ok=True)
