from ai_mcp_server.utils import path_util


def test_default_data_dir_is_home_relative_and_cwd_independent(monkeypatch, tmp_path):
    monkeypatch.delenv("AI_MCP_CONFIG_DIR", raising=False)
    monkeypatch.delenv("AI_MCP_DB_PATH", raising=False)
    home = tmp_path / "home"
    monkeypatch.setattr(path_util.Path, "home", classmethod(lambda cls: home))
    monkeypatch.chdir(tmp_path)

    assert path_util.data_dir() == home / ".ai-mcp-server"
    assert path_util.db_path() == home / ".ai-mcp-server" / "db.sqlite3"
    assert path_util.litellm_metadata_path() == home / ".ai-mcp-server" / "litellm_metadata.json"


def test_relative_env_paths_are_cwd_relative(monkeypatch, tmp_path):
    path = tmp_path / "custom-data"
    monkeypatch.setenv("AI_MCP_CONFIG_DIR", "custom-data")
    monkeypatch.setenv("AI_MCP_DB_PATH", "custom-data/custom.sqlite3")
    monkeypatch.chdir(tmp_path)

    assert path_util.data_dir() == path
    assert path_util.db_path() == path / "custom.sqlite3"
