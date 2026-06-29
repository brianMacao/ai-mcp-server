import json

from ai_mcp_server.application import client_config


def test_write_trae_config_uses_relative_project_paths(tmp_path):
    config_path = tmp_path / ".mcp.json"

    client_config.write_trae_config(config_path, {})

    data = json.loads(config_path.read_text(encoding="utf-8"))
    server = data["mcpServers"][client_config.MCP_SERVER_NAME]

    assert server["cwd"] == "."
    assert server["env"] == {"AI_MCP_CONFIG_DIR": ".data"}
    assert str(tmp_path) not in json.dumps(data)
