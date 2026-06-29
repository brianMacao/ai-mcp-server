"""Auto-configure MCP client configs (Claude Desktop, Codex, Trae, Trae CN).

Each client has a different config format and path. We detect, backup, and
merge the ai-mcp-server entry into the existing config without overwriting
other servers.
"""
from __future__ import annotations

import json
import os
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MCP_SERVER_NAME = "ai-mcp"

# How the Python package is invoked inside the client config.
MCP_SERVER_COMMAND = "uv"
MCP_SERVER_ARGS = ["run", "--from", "ai-mcp-server", "ai-mcp-server"]
PROJECT_CONFIG_CWD = "."
PROJECT_CONFIG_ENV = {"AI_MCP_CONFIG_DIR": ".data"}


@dataclass
class ClientConfig:
    display_name: str
    config_path: Path | None  # None if not found
    exists: bool
    install_instructions: str


def _resolve_home(path_parts: str) -> Path:
    return Path.home() / path_parts


def _find_claude_desktop() -> ClientConfig:
    candidates: list[Path] = []
    if os.name == "nt":
        candidates.append(Path(os.environ.get("APPDATA", "")) / "Claude" / "claude_desktop_config.json")
    else:
        candidates.append(_resolve_home("Library/Application Support/Claude/claude_desktop_config.json"))
        candidates.append(Path.home() / ".config" / "Claude" / "claude_desktop_config.json")
    for p in candidates:
        if p.exists():
            return ClientConfig("Claude Desktop", p, True, "")
    return ClientConfig("Claude Desktop", candidates[0] if candidates else None, False,
                        "Download from https://claude.ai/download")


def _find_codex() -> ClientConfig:
    p = _resolve_home(".codex/config.toml")
    return ClientConfig("Codex Desktop", p, p.exists(),
                        "Download from https://openai.com/codex")


def _find_trae(project_dir: str) -> ClientConfig:
    p = Path(project_dir) / ".mcp.json"
    return ClientConfig("Trae (intl)", p, p.exists(),
                        "Download from https://trae.ai")


def _find_trae_cn(project_dir: str) -> ClientConfig:
    p = Path(project_dir) / ".mcp.json"
    return ClientConfig("Trae CN", p, p.exists(),
                        "Download from https://trae.cn")


def detect_clients(project_dir: str | None = None) -> list[ClientConfig]:
    cwd = project_dir or os.getcwd()
    return [
        _find_claude_desktop(),
        _find_codex(),
        _find_trae(cwd),
        _find_trae_cn(cwd),
    ]


def backup_config(path: Path) -> Path:
    backup = path.with_suffix(path.suffix + ".bak")
    shutil.copy2(path, backup)
    return backup


# ---- read/write per format ----


def read_claude_config(path: Path) -> dict[str, Any]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def write_claude_config(path: Path, config: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if "mcpServers" not in config:
        config["mcpServers"] = {}
    config["mcpServers"][MCP_SERVER_NAME] = {
        "command": MCP_SERVER_COMMAND,
        "args": MCP_SERVER_ARGS,
    }
    if path.exists():
        backup_config(path)
    path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_codex_config(path: Path) -> dict[str, Any]:
    """Parse Codex TOML config into a dict-compatible structure."""
    if not path.exists():
        return {"mcp_servers": {}}
    import tomllib
    try:
        with path.open("rb") as f:
            return tomllib.load(f)
    except tomllib.TOMLDecodeError:
        # If parsing fails, treat as empty to be safe.
        return {"mcp_servers": {}}


def write_codex_config(path: Path, config: dict[str, Any]) -> None:
    """Merge ai-mcp server into Codex TOML config."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    if path.exists():
        backup_config(path)
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)

    section = "[mcp_servers.ai-mcp]"
    if any(section in line for line in lines):
        # Already exists, don't duplicate.
        return

    lines.append(f"\n{section}\n")
    lines.append(f'command = "{MCP_SERVER_COMMAND}"\n')
    args_str = "[{}]".format(", ".join(f'"{a}"' for a in MCP_SERVER_ARGS))
    lines.append(f"args = {args_str}\n")
    path.write_text("".join(lines), encoding="utf-8")


def read_trae_config(path: Path) -> dict[str, Any]:
    """Trae uses .mcp.json at project root, same format as Cursor mcp.json."""
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def write_trae_config(path: Path, config: dict[str, Any]) -> None:
    """Write/merge into project-level .mcp.json (Trae/Cursor format)."""
    if "mcpServers" not in config:
        config["mcpServers"] = {}
    config["mcpServers"][MCP_SERVER_NAME] = {
        "command": MCP_SERVER_COMMAND,
        "args": MCP_SERVER_ARGS,
        "transport": "stdio",
        "cwd": PROJECT_CONFIG_CWD,
        "env": PROJECT_CONFIG_ENV,
    }
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
            if "mcpServers" in existing:
                existing["mcpServers"].update(config["mcpServers"])
            else:
                existing["mcpServers"] = config["mcpServers"]
            config = existing
        except json.JSONDecodeError:
            backup_config(path)
    elif path.exists():
        backup_config(path)
    path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# Formatter per client type
CLIENT_FORMATTERS: dict[str, Callable[[Path], dict[str, Any]]] = {
    "Claude Desktop": read_claude_config,
    "Codex Desktop": read_codex_config,
    "Trae (intl)": read_trae_config,
    "Trae CN": read_trae_config,
}

CLIENT_WRITERS: dict[str, Callable[[Path, dict[str, Any]], None]] = {
    "Claude Desktop": write_claude_config,
    "Codex Desktop": write_codex_config,
    "Trae (intl)": write_trae_config,
    "Trae CN": write_trae_config,
}
