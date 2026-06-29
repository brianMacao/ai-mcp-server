# ai-mcp-server

**語言：** [English](README.md) | 繁體中文 | [简体中文](README.zh-CN.md)

本地 MCP 橋樑：一次登記多組 `(api_key, base_url)`，讓 Agent 可以按模型能力自動查詢與調用合適的模型，例如 chat、vision、reasoning、embedding、image_gen、tts、stt、rerank。

三個入口：

- **`ai-mcp`**：CLI，用於管理 endpoint、查詢模型、觸發探活、初始化 MCP client 設定。
- **`ai-mcp-server`**：MCP stdio server，由 Claude Desktop、Cursor、Cline、Trae 等客戶端拉起。
- **`ai-mcp ui`**：本地 Web 管理介面，FastAPI + Jinja2，預設綁定 `127.0.0.1`。

## 安裝

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

## 快速開始

```bash
# 互動式初始設定
ai-mcp init

# 或逐步設定：
ai-mcp endpoint add --name openrouter --base-url https://openrouter.ai/api/v1 --key sk-...
ai-mcp endpoint probe openrouter
ai-mcp model list --capability vision

# 啟動 Web UI
ai-mcp ui
# → http://127.0.0.1:8765/

# 啟動 MCP server
ai-mcp-server
```

## MCP Tools

`ai-mcp-server` 暴露 6 個 MCP tool：

- `usage_guide`：動態 inventory、能力分佈與推薦使用方式。
- `list_models`：按能力、context length、endpoint、探活狀態篩選模型。
- `invoke_model`：透傳 chat / embedding / image_gen / tts / stt / rerank 請求；TTS 音訊會以 `audio_base64` 放在 JSON body 內返回。
- `model_performance`：查看近期每個模型的調用次數、成功率與延遲。
- `refresh_endpoint`：刷新模型列表並入隊異步能力探活。
- `add_models`：為不提供 `/v1/models` 的 endpoint 手動登記模型，或讓 Agent 登記使用者已確認的模型特性。

## 模型特性登記

能力使用 canonical 名稱，例如 `text_chat`、`vision`、`audio_tts`、`audio_stt`、`embedding`、`rerank`。手動登記流程也接受常用別名，例如 `tts`、`stt`、`asr`，並會在內部正規化。

目前靜態識別包含：

- `seed-tts-2.0` → `audio_tts`
- `volc.seedasr.sauc.duration` → `audio_stt`

透過 CLI 登記模型特性：

```bash
ai-mcp model add --endpoint volc seed-tts-2.0 --capability audio_tts
ai-mcp model add --endpoint volc volc.seedasr.sauc.duration --features asr=true
ai-mcp model add --endpoint volc custom-model --features text_chat=true,context_length=32000
ai-mcp model override volc custom-model --capability vision=false
```

透過 Web UI 登記：

```bash
ai-mcp ui
# 開啟 http://127.0.0.1:8765/
# 在 Models 手動新增，或到 Overrides 新增 / 更新特性覆寫。
```

透過 MCP client / Agent 登記：

1. 先調用 `usage_guide`。
2. 若要標記某些能力為 true，調用 `add_models` 並傳入 `capabilities`。
3. 若要明確登記 true / false 或 context length，傳入 `feature_overrides`。

MCP 參數範例：

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

## Claude Desktop / Trae / Codex 設定

`ai-mcp init` 會嘗試自動偵測已安裝的 MCP client 並寫入設定。

手動設定範例：

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

**Trae / Trae CN**（專案根目錄 `.mcp.json`）：

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

## 環境變數

| 變數 | 用途 | 預設值 |
|---|---|---|
| `AI_MCP_CONFIG_DIR` | 覆寫資料 / 設定目錄 | `~/.ai-mcp-server` |
| `AI_MCP_DB_PATH` | SQLite database 路徑 | `$AI_MCP_CONFIG_DIR/db.sqlite3` |
| `AI_MCP_MASTER_KEY` | Fernet master key，用於加密 api_key | 自動產生並寫入系統 keyring |
| `AI_MCP_UI_TOKEN` | Web UI 對外暴露時使用的 access token | 無 |

## 開發

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
