"""i18n strings: English."""
from __future__ import annotations

from typing import Any

STRINGS: dict[str, Any] = {
    "lang_name": "English",
    "init_title": "ai-mcp setup",
    "init_step_endpoint": "Step {n}/{total}: Register endpoint",
    "init_step_clients": "Step {n}: Auto-configure MCP Client (Ctrl+C to skip)",
    "init_step_claude": "Step {n}: Configure Claude Desktop",
    "endpoint_name_prompt": "Endpoint name (e.g. openrouter)",
    "endpoint_url_prompt": "Base URL (e.g. https://api.openai.com/v1)",
    "endpoint_key_prompt": "API key (input hidden)",
    "endpoint_provider_prompt": "Provider type",
    "endpoint_added": "Endpoint registered: {name}",
    "endpoint_exists_error": "Endpoint {name!r} already exists",
    "discover_start": "Discovering models ...",
    "discover_done": "Found {n} models",
    "discover_failed": "Model discovery failed: {error}",
    "client_detect_start": "Scanning for installed MCP Clients ...",
    "client_found": "Detected {name}",
    "client_not_found": "{name} (not installed)",
    "client_write_prompt": "Write config for {name}?",
    "client_written": "Written to {name}: {path}",
    "client_backup_created": "Original config backed up to {path}",
    "client_skip": "Skipped {name}",
    "trae_project_prompt": "Trae uses project-level config (current dir: {dir}). Write?",
    "init_done": "✓ Done!",
    "init_next_ui": "Start Web UI:   ai-mcp ui",
    "init_next_probe": "Probe models:   ai-mcp endpoint probe <name>",
    "init_next_restart": "Restart MCP client to load the new config",
    "yes": "y",
    "no": "N",
    "error_uv_missing": "uv not found. Install: https://docs.astral.sh/uv/getting-started/installation/",
    "ui_expose_warning": "!!! You are exposing the UI beyond localhost. Set AI_MCP_UI_TOKEN; non-static routes require ?token=xxx when it is set.",
    "ui_starting": "ai-mcp ui ready",
}
