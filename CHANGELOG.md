# Changelog

## v0.1.0 (unreleased)

Initial release.

### Features
- **CLI** (`ai-mcp`): endpoint registration, model discovery, capability probing,
  metadata management, interactive init wizard, worker loop.
- **MCP Server** (`ai-mcp-server`): stdio-mode bridge exposing 6 tools
  (`usage_guide`, `list_models`, `invoke_model`, `model_performance`,
  `refresh_endpoint`, `add_models`) with background probe worker.
- **Web UI** (`ai-mcp ui`): FastAPI + Jinja2 management dashboard (9 pages)
  with SSE progress tracking.
- **10 capability probes**: text_chat, tool_call, vision, reasoning, json_mode,
  embedding, image_gen, audio_tts, audio_stt, rerank.
- **4-source capability resolver**: user override > probe result > LiteLLM
  metadata > static map.
- **Optimistic lock worker**: concurrent-safe probe queue with lease sweep.
- **Client auto-config**: Claude Desktop (JSON), Codex Desktop (TOML),
  Trae / Trae CN (per-project `.mcp.json`).
- **npm thin wrapper** for `npx ai-mcp-server`.
- **Homebrew Formula** for `brew install`.
