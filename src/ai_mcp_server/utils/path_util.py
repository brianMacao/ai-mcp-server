from __future__ import annotations

import os
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PACKAGE_ROOT.parent
PROJECT_ROOT = SRC_ROOT.parent
DATA_DIR_NAME = ".ai-mcp-server"


def _resolve_user_path(value: str) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path.resolve()
    return path.resolve()


def data_dir() -> Path:
    override = os.environ.get("AI_MCP_CONFIG_DIR")
    path = _resolve_user_path(override) if override else Path.home() / DATA_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def db_path() -> Path:
    override = os.environ.get("AI_MCP_DB_PATH")
    if override:
        return _resolve_user_path(override)
    return data_dir() / "db.sqlite3"


def litellm_metadata_path() -> Path:
    return data_dir() / "litellm_metadata.json"


def probe_assets_dir() -> Path:
    candidates = [
        PACKAGE_ROOT / "_assets" / "probe",
        PROJECT_ROOT / "assets" / "probe",
    ]
    for path in candidates:
        if path.exists():
            return path
    return PROJECT_ROOT / "assets" / "probe"
