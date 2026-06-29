"""i18n strings: Traditional Chinese (Hong Kong / Taiwan)."""
from __future__ import annotations

from typing import Any

STRINGS: dict[str, Any] = {
    "lang_name": "繁體中文",
    "init_title": "ai-mcp 初始設定",
    "init_step_endpoint": "步驟 {n}/{total}: 註冊 endpoint",
    "init_step_clients": "步驟 {n}: 自動配置 MCP Client（可按 Ctrl+C 跳過）",
    "init_step_claude": "步驟 {n}: 配置 Claude Desktop",
    "endpoint_name_prompt": "Endpoint 名稱 (例: openrouter)",
    "endpoint_url_prompt": "Base URL (例: https://api.openai.com/v1)",
    "endpoint_key_prompt": "API key (輸入時不可見)",
    "endpoint_provider_prompt": "Provider 類型",
    "endpoint_added": "已登記 endpoint: {name}",
    "endpoint_exists_error": "Endpoint {name!r} 已經存在",
    "discover_start": "正在發現模型 ...",
    "discover_done": "發現 {n} 個模型",
    "discover_failed": "模型發現失敗: {error}",
    "client_detect_start": "掃描已安裝的 MCP Client ...",
    "client_found": "偵測到 {name}",
    "client_not_found": "{name}（未安裝）",
    "client_write_prompt": "要寫入 {name} 配置嗎?",
    "client_written": "已寫入 {name}: {path}",
    "client_backup_created": "原配置已備份至 {path}",
    "client_skip": "跳過 {name}",
    "trae_project_prompt": "Trae 是專案級配置 (當前目錄: {dir})。要寫入嗎?",
    "init_done": "✅ 完成！",
    "init_next_ui": "啟動 Web UI:   ai-mcp ui",
    "init_next_probe": "探活模型:     ai-mcp endpoint probe <name>",
    "init_next_restart": "重啟 MCP client 以載入新配置",
    "yes": "y",
    "no": "N",
    "error_uv_missing": "未檢測到 uv，請先安裝: https://docs.astral.sh/uv/getting-started/installation/",
    "ui_expose_warning": "!!! 你正將 UI 暴露到本機以外的網絡。請設置 AI_MCP_UI_TOKEN；設置後非靜態路由都需要 ?token=xxx。",
    "ui_starting": "ai-mcp ui 就緒",
}
