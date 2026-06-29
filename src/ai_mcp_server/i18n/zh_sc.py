"""i18n strings: Simplified Chinese."""
from __future__ import annotations

from typing import Any

STRINGS: dict[str, Any] = {
    "lang_name": "简体中文",
    "init_title": "ai-mcp 初始设定",
    "init_step_endpoint": "Step {n}/{total}: 注册 endpoint",
    "init_step_clients": "Step {n}: 自动配置 MCP Client（可按 Ctrl+C 跳过）",
    "init_step_claude": "Step {n}: 配置 Claude Desktop",
    "endpoint_name_prompt": "Endpoint 名称 (例: openrouter)",
    "endpoint_url_prompt": "Base URL (例: https://api.openai.com/v1)",
    "endpoint_key_prompt": "API key (输入时不可见)",
    "endpoint_provider_prompt": "Provider 类型",
    "endpoint_added": "已登记 endpoint: {name}",
    "endpoint_exists_error": "Endpoint {name!r} 已经存在",
    "discover_start": "正在发现模型 ...",
    "discover_done": "发现 {n} 个模型",
    "discover_failed": "模型发现失败: {error}",
    "client_detect_start": "扫描已安装的 MCP Client ...",
    "client_found": "检测到 {name}",
    "client_not_found": "{name}（未安装）",
    "client_write_prompt": "要写入 {name} 配置吗?",
    "client_written": "已写入 {name}: {path}",
    "client_backup_created": "原配置已备份至 {path}",
    "client_skip": "跳过 {name}",
    "trae_project_prompt": "Trae 是项目级配置 (当前目录: {dir})。要写入吗?",
    "init_done": "✅ 完成！",
    "init_next_ui": "启动 Web UI:   ai-mcp ui",
    "init_next_probe": "探活模型:     ai-mcp endpoint probe <name>",
    "init_next_restart": "重启 MCP client 以加载新配置",
    "yes": "y",
    "no": "N",
    "error_uv_missing": "未检测到 uv，请先安装: https://docs.astral.sh/uv/getting-started/installation/",
    "ui_expose_warning": "!!! 你正将 UI 暴露到本地以外的网络。请设置 AI_MCP_UI_TOKEN；设置后非静态路由都需要 ?token=xxx。",
    "ui_starting": "ai-mcp ui 就绪",
}
