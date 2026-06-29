# ai-mcp-server

**Languages:** English | [繁體中文](README.zh-TW.md) | [简体中文](README.zh-CN.md)

Local MCP bridge: register multiple (api_key, base_url) pairs once, and let your Agent
automatically discover and route to any model with the right capability (chat, vision,
reasoning, embedding, image_gen, tts, stt, rerank).

Three entry points:
- **`ai-mcp`** — CLI (manage endpoints, query models, trigger probes, init wizard)
- **`ai-mcp-server`** — MCP stdio server, launched by Claude Desktop / Cursor / Cline / Trae
- **`ai-mcp ui`** — local Web management dashboard (FastAPI + Jinja2, bound to 127.0.0.1)

## Install

### Option 1: uv (recommended)

```bash
uv tool install ai-mcp-server
```

### Option 2: Homebrew

```bash
brew install brianMacao/tap/ai-mcp-server
```

### Option 3: npm / npx

```bash
npx ai-mcp-server      # auto-installs uv + Python package
```

### Option 4: pip

```bash
pip install ai-mcp-server
```

## Quickstart

```bash
# Interactive first-run wizard
ai-mcp init

# Or step by step:
ai-mcp endpoint add --name openrouter --base-url https://openrouter.ai/api/v1 --key sk-...
ai-mcp endpoint probe openrouter
ai-mcp model list --capability vision

# Start the Web UI
ai-mcp ui
# → http://127.0.0.1:8765/

# Start the MCP server (for Claude Desktop, Cursor, etc.)
ai-mcp-server
```

## MCP Tools

`ai-mcp-server` exposes 6 MCP tools:

- `usage_guide` — dynamic inventory, capability distribution, and routing guidance.
- `list_models` — filter models by capability, context length, endpoint, and probe state.
- `invoke_model` — pass through chat / embedding / image_gen / tts / stt / rerank calls;
  TTS audio is returned as `audio_base64` inside the JSON body.
- `model_performance` — inspect recent per-model call counts, success rate, and latency.
- `refresh_endpoint` — refresh model lists and enqueue asynchronous capability probes.
- `add_models` — manually register models for endpoints without `/v1/models`, or let an
  Agent register user-confirmed model features.

## Model Feature Registration

Capabilities use canonical names such as `text_chat`, `vision`, `audio_tts`,
`audio_stt`, `embedding`, and `rerank`. Common aliases including `tts`, `stt`,
and `asr` are accepted by manual registration flows and normalized internally.

Static recognition includes these known model ids:

- `seed-tts-2.0` → `audio_tts`
- `volc.seedasr.sauc.duration` → `audio_stt`

Register model features from the CLI:

```bash
ai-mcp model add --endpoint volc seed-tts-2.0 --capability audio_tts
ai-mcp model add --endpoint volc volc.seedasr.sauc.duration --features asr=true
ai-mcp model add --endpoint volc custom-model --features text_chat=true,context_length=32000
ai-mcp model override volc custom-model --capability vision=false
```

Register features from the Web UI:

```bash
ai-mcp ui
# Open http://127.0.0.1:8765/
# Use Models -> manual add, or Overrides -> add/update feature override.
```

Register features from an MCP client / Agent:

1. Call `usage_guide`.
2. Use `add_models` with `capabilities` for true capability flags.
3. Use `feature_overrides` for explicit boolean or context-length overrides.

Example MCP arguments:

```json
{
  "endpoint": "volc",
  "model_ids": ["seed-tts-2.0"],
  "feature_overrides": {
    "audio_tts": true,
    "context_length": 32000
  }
}
```

## Claude Desktop / Trae / Codex Configuration

`ai-mcp init` will auto-detect installed MCP clients and configure them.

### Manual configuration

**Claude Desktop** (`claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "ai-mcp": {
      "command": "uv",
      "args": ["run", "--from", "ai-mcp-server", "ai-mcp-server"]
    }
  }
}
```

**Trae / Trae CN** (project root `.mcp.json`):
```json
{
  "mcpServers": {
    "ai-mcp": {
      "command": "uv",
      "args": ["run", "--from", "ai-mcp-server", "ai-mcp-server"],
      "transport": "stdio"
    }
  }
}
```

**Codex Desktop** (`~/.codex/config.toml`):
```toml
[mcp_servers.ai-mcp]
command = "uv"
args = ["run", "--from", "ai-mcp-server", "ai-mcp-server"]
```

## Environment Variables

| Variable | Purpose | Default |
|---|---|---|
| `AI_MCP_CONFIG_DIR` | Override data/config directory | `~/.ai-mcp-server` |
| `AI_MCP_DB_PATH` | SQLite database path | `$AI_MCP_CONFIG_DIR/db.sqlite3` |
| `AI_MCP_MASTER_KEY` | Fernet master key for api_key encryption | auto-generated → system keyring |
| `AI_MCP_UI_TOKEN` | Access token for Web UI when exposed (`--expose`) | none |

## Development

```bash
# Clone and set up
git clone https://github.com/brianMacao/ai-mcp-server
cd ai-mcp-server
uv sync

# Run tests
uv run pytest -q

# Verify against real endpoint
cp .keys.example .keys   # edit with your keys
source .keys
export AI_MCP_CONFIG_DIR="$(pwd)/.data"
export AI_MCP_MASTER_KEY="$(cat .data/.master_key)"  # first run generates this
uv run ai-mcp endpoint add --name test --base-url "$EXAMPLE_URL" --key "$EXAMPLE_API_KEY"
uv run ai-mcp endpoint probe test --capability text_chat -y
```

## License

MIT
