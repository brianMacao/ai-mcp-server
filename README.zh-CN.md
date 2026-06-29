# ai-mcp-server

**语言：** [English](README.md) | [繁體中文](README.zh-TW.md) | 简体中文

本地 MCP 桥梁：一次登记多组 `(api_key, base_url)`，让 Agent 可以按模型能力自动查询与调用合适的模型，例如 chat、vision、reasoning、embedding、image_gen、tts、stt、rerank。

三个入口：

- **`ai-mcp`**：CLI，用于管理 endpoint、查询模型、触发探活、初始化 MCP client 配置。
- **`ai-mcp-server`**：MCP stdio server，由 Claude Desktop、Cursor、Cline、Trae 等客户端拉起。
- **`ai-mcp ui`**：本地 Web 管理界面，FastAPI + Jinja2，默认绑定 `127.0.0.1`。

## 安装

### uv

```bash
uv tool install ai-mcp-server
```

### Homebrew

```bash
brew install brianMacao/tap/ai-mcp-server
```

### npm / npx

```bash
npx ai-mcp-server
```

### pip

```bash
pip install ai-mcp-server
```

## 快速开始

```bash
# 交互式初始设置
ai-mcp init

# 或逐步设置：
ai-mcp endpoint add --name openrouter --base-url https://openrouter.ai/api/v1 --key sk-...
ai-mcp endpoint probe openrouter
ai-mcp model list --capability vision

# 启动 Web UI
ai-mcp ui
# → http://127.0.0.1:8765/

# 启动 MCP server
ai-mcp-server
```

## MCP Tools

`ai-mcp-server` 暴露 6 个 MCP tool：

- `usage_guide`：动态 inventory、能力分布与推荐使用方式。
- `list_models`：按能力、context length、endpoint、探活状态筛选模型。
- `invoke_model`：透传 chat / embedding / image_gen / tts / stt / rerank 请求；TTS 音频会以 `audio_base64` 放在 JSON body 内返回。
- `model_performance`：查看近期每个模型的调用次数、成功率与延迟。
- `refresh_endpoint`：刷新模型列表并入队异步能力探活。
- `add_models`：为不提供 `/v1/models` 的 endpoint 手动登记模型，或让 Agent 登记用户已确认的模型特性。

## 模型特性登记

能力使用 canonical 名称，例如 `text_chat`、`vision`、`audio_tts`、`audio_stt`、`embedding`、`rerank`。手动登记流程也接受常用别名，例如 `tts`、`stt`、`asr`，并会在内部标准化。

目前静态识别包含：

- `seed-tts-2.0` → `audio_tts`
- `volc.seedasr.sauc.duration` → `audio_stt`

通过 CLI 登记模型特性：

```bash
ai-mcp model add --endpoint volc seed-tts-2.0 --capability audio_tts
ai-mcp model add --endpoint volc volc.seedasr.sauc.duration --features asr=true
ai-mcp model add --endpoint volc custom-model --features text_chat=true,context_length=32000
ai-mcp model override volc custom-model --capability vision=false
```

通过 Web UI 登记：

```bash
ai-mcp ui
# 打开 http://127.0.0.1:8765/
# 在 Models 手动新增，或到 Overrides 新增 / 更新特性覆盖。
```

通过 MCP client / Agent 登记：

1. 先调用 `usage_guide`。
2. 若要标记某些能力为 true，调用 `add_models` 并传入 `capabilities`。
3. 若要明确登记 true / false 或 context length，传入 `feature_overrides`。

MCP 参数示例：

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

## Claude Desktop / Trae / Codex 配置

`ai-mcp init` 会尝试自动检测已安装的 MCP client 并写入配置。

手动配置示例：

**Claude Desktop** (`claude_desktop_config.json`)：

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

**Trae / Trae CN**（项目根目录 `.mcp.json`）：

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

**Codex Desktop** (`~/.codex/config.toml`)：

```toml
[mcp_servers.ai-mcp]
command = "uv"
args = ["run", "--from", "ai-mcp-server", "ai-mcp-server"]
```

## 环境变量

| 变量 | 用途 | 默认值 |
|---|---|---|
| `AI_MCP_CONFIG_DIR` | 覆盖数据 / 配置目录 | `~/.ai-mcp-server` |
| `AI_MCP_DB_PATH` | SQLite database 路径 | `$AI_MCP_CONFIG_DIR/db.sqlite3` |
| `AI_MCP_MASTER_KEY` | Fernet master key，用于加密 api_key | 自动生成并写入系统 keyring |
| `AI_MCP_UI_TOKEN` | Web UI 对外暴露时使用的 access token | 无 |

## 开发

```bash
git clone https://github.com/brianMacao/ai-mcp-server
cd ai-mcp-server
uv sync

uv run pytest -q

cp .keys.example .keys
source .keys
export AI_MCP_CONFIG_DIR="$(pwd)/.data"
export AI_MCP_MASTER_KEY="$(cat .data/.master_key)"
uv run ai-mcp endpoint add --name test --base-url "$EXAMPLE_URL" --key "$EXAMPLE_API_KEY"
uv run ai-mcp endpoint probe test --capability text_chat -y
```

## License

MIT
