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
def _reset_db_per_test(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Give each test its own DB file and force schema init.

    Windows keeps SQLite files locked while any connection handle is still alive,
    so deleting the same db.sqlite3 before every test can fail with WinError 32.
    A per-test DB path gives us the same isolation without relying on unlink.
    """
    from ai_mcp_server.storage import db as db_mod

    data_dir = tmp_path / "ai-mcp-data"
    monkeypatch.setenv("AI_MCP_CONFIG_DIR", str(data_dir))
    monkeypatch.setenv("AI_MCP_DB_PATH", str(data_dir / "db.sqlite3"))
    db_mod._initialised = False
    yield
    db_mod._initialised = False
