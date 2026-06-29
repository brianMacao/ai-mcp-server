"""Pytest fixtures: isolated DB + master key per session."""
from __future__ import annotations

import os
from pathlib import Path

import pytest


# Set env vars BEFORE importing the package
@pytest.fixture(scope="session", autouse=True)
def _isolated_env(tmp_path_factory: pytest.TempPathFactory) -> None:
    db_dir = tmp_path_factory.mktemp("ai-mcp-data")
    os.environ["AI_MCP_CONFIG_DIR"] = str(db_dir)
    os.environ["AI_MCP_DB_PATH"] = str(db_dir / "db.sqlite3")
    # Generate a deterministic Fernet key for the test session.
    from cryptography.fernet import Fernet
    os.environ["AI_MCP_MASTER_KEY"] = Fernet.generate_key().decode()
    yield


@pytest.fixture(autouse=True)
def _reset_db_per_test() -> None:
    """Wipe DB before each test; force re-init."""
    from ai_mcp_server.storage import db as db_mod

    p = Path(os.environ["AI_MCP_DB_PATH"])
    if p.exists():
        p.unlink()
    for ext in ("-wal", "-shm"):
        q = Path(str(p) + ext)
        if q.exists():
            q.unlink()
    db_mod._initialised = False
    yield
