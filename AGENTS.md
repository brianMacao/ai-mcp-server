# Coding Assistant 協作指引

## 項目範圍

本倉庫只維護 `ai-mcp-server`：一個本地工具集合，包含三個獨立進程入口（MCP server stdio、CLI、
Web UI），把多個 (api_key, base_url) 收編成統一的能力池，讓 Agent 透過 MCP 查詢與調用各種模型
（chat / vision / reasoning / embedding / image_gen / tts / stt / rerank）。

- **Python 包**：`src/ai_mcp_server/`
- **CLI 入口**：`ai-mcp`（由 `pyproject.toml` 定義 entry point；含 `endpoint` / `model` / `meta` / `worker` / `ui` 子命令）
- **MCP server 入口**：`ai-mcp-server`（stdio 模式，被 Agent 客戶端拉起；啟動時內含背景 worker task）
- **Web UI 入口**：`ai-mcp ui`（FastAPI + Jinja2 + uvicorn；綁定 `127.0.0.1`，無認證）
- **本地數據**：`~/.ai-mcp-server/db.sqlite3`（WAL 模式），api_key 以 Fernet 加密儲存

新增工作默認限制在 `src/ai_mcp_server/`、`tests/`、`assets/`、`docs/`。不要新增無關 workspace
或包；舊文檔中的舊結構引用只作背景。

## 後端架構原則：解讀 X

本項目採「**邏輯單一後端**」：三個進程入口（MCP server / CLI / Web UI）**不共享進程**，但**共享
同一份 `application/*` 業務邏輯與同一個 SQLite**。

- 每個入口進程都 `import ai_mcp_server.application.*` 直接 in-process 調業務函數。
- **不**走 subprocess 反代、**不**走 HTTP 反代到「那個唯一後端」。
- 真相在 SQLite（WAL 模式 + `busy_timeout=5000` 支援多進程並發讀寫）。
- 探活異步化：UI / CLI / MCP 任一入口都可以 enqueue `probe_jobs`；worker 由 MCP server
  進程內背景 asyncio task 承擔，CLI `endpoint probe` 也可同步消化 queue 至清空。

## 設計哲學

- **橋樑優先，不做攔截**：MCP server 對上游 API 盡量原樣透傳；除了協議格式轉換與能力路由，
  不對 messages、tool_calls、parameters 做業務語義改寫。
- **KISS 版分層**：Python 單體；分層用來讓代碼有清晰落點，不是引入厚重架構儀式。
  先問落點：它代表 MCP tool 入口、用戶動作編排、能力解析、provider 防腐、儲存基礎能力，
  還是純工具函數。
- **靜態優先、探活兜底**：能力標籤先信靜態映射與第三方 metadata；探活只在用戶手動觸發時跑，
  不在 server 啟動或 tool 調用路徑上偷偷打 API。
- **可追溯與可預測**：不要隱藏錯誤或風險；上游 API 的錯誤原樣冒泡到 Agent，附帶足夠 context
  讓 Agent 能決策重試或換模型。失敗可定位優先於表面成功率。
- **簡單但不混亂**：能用簡單函數清楚表達的邏輯就保持簡單；一旦涉及跨 provider、跨能力路由
  或多來源融合，必須回到清晰分層和可測邊界。

## 名詞與交付面

- **MCP server**：本倉庫主交付物，stdio 模式長駐進程，由 Agent 客戶端（Claude Desktop、
  Cursor、Cline 等）按需拉起。
- **MCP tool**：暴露給 Agent 的 6 個 tool —— `usage_guide` / `list_models` / `invoke_model` /
  `model_performance` / `refresh_endpoint` / `add_models`。
- **endpoint**：用戶登記的一組 (name, base_url, api_key, provider_type)，代表一個上游 API。
- **model**：endpoint 下發現的單一模型，附帶 capabilities 標籤（vision / tool_call / context_length 等）。
- **capability**：模型能力標籤，融合來源有四：用戶覆寫 > 探活結果 > 第三方 metadata (LiteLLM)
  > 內建靜態映射表。
- **probe**：能力探活，發最小 payload（內容統一用「1」）驗證模型在某能力上是否真實可用。
- **provider adapter**：協議防腐層，當前只有 `OpenAICompatAdapter`，Anthropic 預留接口。
- **CLI**：`ai-mcp` 命令，用於登記 endpoint、查詢模型、手動覆寫能力、觸發探活。

涉及 **MCP tool / provider adapter / probe / capability resolver** 的修改，最終交付面是
真實 MCP client 拉起 stdio server 後，6 個 tool 的 schema、響應結構與透傳行為。CLI
unit test 只能作為輔助驗證，不能替代「真實 MCP client 串通」這條驗收路徑。

涉及 **CLI** 的修改，最終交付面是 `ai-mcp endpoint add/list/probe`、`ai-mcp model override`
等命令在乾淨環境下能跑通，並正確寫入 / 讀取本地 SQLite。

## 硬性驗收

- 影響 MCP tool 或 provider 透傳時，必須同步核對：tool schema、tool 響應結構、上游 API
  原始錯誤是否被原樣冒泡、stdio 是否仍可正常啟動。
- 影響 capability resolver 時，必須驗證四來源優先級：用戶覆寫 > 探活 > LiteLLM > 靜態表，
  並覆蓋至少一個「四來源衝突」的測試案例。
- 影響儲存層時，必須驗證：api_key 不以明文落盤、SQLite 路徑可由環境變數覆寫、初次運行
  自動建表、向後相容（已存資料可讀）。
- 影響探活時，必須驗證：10 種 probe 都有對應實作；vision/stt 用內建 `assets/probe/`
  資產；探活失敗不污染已知能力標籤、不刪除歷史記錄。
- 不做的事（明確劃線，不要悄悄做）：streaming、自動重試、自動 fallback、
  rate limit、多用戶帳號。
- 發現驗收缺口時，把規則前移到 source/test、PRD、完成報告或本文檔；不要只修當前 bug
  後繼續前進。

## 常用命令

所有命令在倉庫根目錄執行：

```bash
uv sync
uv run ai-mcp --help
uv run ai-mcp endpoint add --name <n> --base-url <url> --key <k>
uv run ai-mcp endpoint list
uv run ai-mcp endpoint probe --all
uv run ai-mcp model override <endpoint> <model_id> --capability vision=true
uv run ai-mcp-server                # 以 stdio 啟動 MCP server（給 MCP client 用）

uv run pytest
uv run ruff check src tests
uv run ruff format src tests
uv run mypy src
```

## MCP Server 開發

- Tool schema 改變時，先更新 `src/ai_mcp_server/server.py` 的 tool 註冊定義，再改 handler。
- 6 個 tool 必須維持「橋樑」語義；`invoke_model` 不要在 messages 上做業務改寫，只做協議
  格式轉換。
- `usage_guide` 的內容必須是運行時動態組裝：當前 endpoint 數、可用能力標籤分佈、近期探活
  狀態。靜態介紹放在 MCP server 的 `instructions` 欄位。
- 新增 MCP tool 之前先問：這能不能用既有 tool 的參數擴展完成？六個 tool 是當前刻意的上限。

## Provider 與能力層

- 新增上游協議時，先在 `src/ai_mcp_server/providers/base.py` 確認 `ProviderAdapter` ABC 已覆蓋
  需要的方法；不夠就先補 ABC，再寫具體 adapter。
- provider 字段差異、錯誤碼轉換、SDK quirks 收斂在 `providers/`，不向 tool 層或 capability
  層泄漏。
- capability resolver 的四來源優先級實作在 `capability/resolver.py`，任何新增來源都要走
  resolver；不要在 tool handler 裡直接讀靜態表或 LiteLLM。
- LiteLLM metadata 拉取要有本地快取與離線降級；不要每次 tool 調用都打網。

## 探活與資產

- 每種能力對應 `src/ai_mcp_server/probes/<capability>.py` 一個模組，輸入是 (adapter, model_id)，
  輸出是 `ProbeResult{ok: bool, latency_ms: int, raw: dict, error: str|None}`。
- 探活素材集中在 `assets/probe/`：`digit_1.png`（vision）、`digit_1.wav`（stt）。
  不要在代碼裡 hardcode 圖片/音檔，必須從 assets 載入。
- **探活異步化**：所有探活請求一律先 `INSERT INTO probe_jobs` 為 `status=pending`；worker 透過
  樂觀鎖認領 → 0.5s 二次確認 → 執行 → 寫回 `probe_runs` + 更新 `models.capabilities_json`。
- Worker 入口：MCP server 進程啟動時 `asyncio.create_task(worker.run_loop())`；CLI
  `ai-mcp endpoint probe` 與 `ai-mcp worker` 也可同步驅動同一份 worker 代碼。
- 並發控制：worker 啟動時生成 `instance_id = uuid4()`；認領寫入 `claimed_by`、等 0.5 秒、
  二次讀取 `claimed_by`，仍是自己才執行。lease 超時透過 `lease_sweeper` 把孤兒 job 回退為 pending。

## Web UI

- 入口：`ai-mcp ui` 子命令；FastAPI + Jinja2 純後端模板，**不引入 SPA 與前端構建**。
- 預設綁定 `127.0.0.1`，無認證；改為非 loopback host 時 CLI 必須打印大紅警告。
- UI route 必須直接 `import ai_mcp_server.application.*` in-process 調用，不要 subprocess、
  不要 HTTP 反代。
- 探活進度透過 SSE 推送；SSE 必須支援 `Last-Event-Id` 重連。
- 頁面範圍（9 個 MVP 頁面）：Dashboard / Endpoints / Endpoint detail / Models / Model detail /
  Overrides / Probes / Jobs / Meta。新增 UI 頁面前先問：是不是能複用既有 9 個之一？

## 儲存層

```text
src/ai_mcp_server/storage/
├── db.py              # SQLite 連線（WAL + busy_timeout）、schema 初始化、migration
├── crypto.py          # Fernet 加密/解密 api_key
└── dao.py             # endpoints / models / overrides / probe_runs / probe_jobs 五張表的 DAO
```

- 所有連線開啟時設 `PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000`。
- DB 路徑優先順序：環境變數 `AI_MCP_DB_PATH` > `~/.ai-mcp-server/db.sqlite3`。
- Master key 路徑：環境變數 `AI_MCP_MASTER_KEY` > 系統 keyring > 首次運行生成並寫入 keyring。
- 不引入 ORM；用標準庫 `sqlite3` + 薄 DAO 函數即可。
- schema 變動走 `db.py` 的 migration 函數，編號遞增；不要在 DAO 裡偷偷 `ALTER TABLE`。
- 寫操作必須短小，禁用長交易；UI / CLI / MCP 三進程共寫的安全靠 WAL + busy_timeout，不靠 server 端鎖。

## 代碼規範

- exported/public API 使用明確 typing；對外暴露的 dataclass / TypedDict 集中在 `models/`
  或就近模組頂部。
- 源碼中的代碼註釋保持英文；本協作指引、PRD、CHANGELOG 可以使用中文。
- 不要隱藏錯誤或風險；上游 API 的 4xx/5xx 必須帶 status + body 原樣返回給 Agent。
- 可追溯性與行為可預測性優先於表面成功率。
- 優先沿用既有 helper、adapter、resolver；不要繞過 `ProviderAdapter` 直接 `httpx` 打 API，
  也不要繞過 `resolver` 直接讀某一來源。
- 測試覆蓋跟風險走：窄改動跑 focused pytest；跨 provider / capability / MCP tool 改動時跑
  完整 `pytest` + 真實 MCP client 串通驗收。
