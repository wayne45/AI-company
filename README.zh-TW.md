[English](README.md) | [中文](README.zh-CN.md)

# AI Team OS

<!-- Logo placeholder -->
<!-- ![AI Team OS Logo](docs/assets/logo.png) -->

### 你的 AI 編程工具，停止提示就停止工作。我們的不會。

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-19-61DAFB?logo=react)](https://react.dev)
[![MCP](https://img.shields.io/badge/MCP-Protocol-orange)](https://modelcontextprotocol.io)
[![Stars](https://img.shields.io/github/stars/CronusL-1141/AI-company?style=flat)](https://github.com/CronusL-1141/AI-company)

---

AI Team OS 將 Claude Code 變成一家**自運轉 AI 公司**。
你是董事長，AI 是 CEO。設定方向——系統自主執行、學習、持續進化。

---

## 其他 AI 工具的問題

所有 AI 編程助手的工作模式都一樣：你提問，它回答，然後停下來。你一離開，工作就停了。你回來面對的是一個空白的提示框。

AI Team OS 的工作方式不同。

你晚上離開。第二天早上打開電腦，發現：
- CEO 檢查了任務墻，拿起了下一個最高優先級的任務並完成了它
- 遇到需要你審批的阻塞點時，它掛起了那條線程，切換到了並行工作流
- 研究部門的 Agent 掃描了三個競品框架，發現了一個值得采用的技術
- 一場頭腦風暴會議已經召開，5 個 Agent 討論了 4 個方案，最佳方案已經進了任務墻

這些，你一個提示都沒發。系統自己跑起來的。

---

## 它是怎麼工作的

**你是董事長，AI Leader 是 CEO。**

CEO 不等待指令。它檢查任務墻，挑出最高優先級的任務，分配給對應的專業 Agent，推進執行。遇到阻塞，它切換工作流。所有計劃內的工作完成後，研究部門的 Agent 會激活——掃描新技術、組織頭腦風暴會議，把改進方案反饋回系統。

每次失敗都讓系統變得更聰明。"失敗煉金術"提取防御規則，為未來的 Agent 生成培訓案例，提交改進提案——系統對自身的錯誤產生抗體。

---

## 核心能力

### 1. 自主運轉（核心賣點）

CEO 從不空閒。它按任務墻優先級持續推進工作：

- 一個任務完成後，立即檢查任務墻，拿起下一個最高優先級任務
- 遇到需要你審批的阻塞點，掛起該線程，切換到並行工作流
- 批量匯總所有戰略問題，等你回來時統一匯報——不為每個戰術決策打斷你
- 卡死檢測：循環停滯時，系統主動暴露阻塞原因，而不是原地空轉

### 2. 自我進化

系統不只是執行——它在進化：

- **研發循環**：研究 Agent 掃描競品、新框架和社區工具。研究結果提交到頭腦風暴會議，Agent 之間相互挑戰辯論。結論變成實施計劃進入任務墻。
- **失敗煉金術**：每次任務失敗都觸發根因提取、歸類，並產出三類輸出：
  - *抗體* — 失敗經驗存入團隊記憶，防止同類錯誤重現
  - *疫苗* — 高頻失敗模式轉化為任務前預警
  - *催化劑* — 失敗分析結果注入 Agent 的 system prompt，改善下次執行

### 3. 團隊協作（不是單 Agent）

不是一個 Agent，而是一個結構化組織：

- **25 個專業 Agent 模板**（23 個基礎 + 2 個辯論角色），含推薦引擎——工程/測試/研究/管理，開箱即用
- **8 種結構化會議模板**，支持關鍵詞自動匹配，基於六頂思考帽、DACI 框架和 Design Sprint 方法論
- **部門分組管理**——工程部/測試部/研究部，支持跨部門協作
- 每次會議必須產出可執行結論，"討論了但沒決定"不是一個有效結果

### 4. 完全透明

沒有黑盒：

- **決策駕駛艙**：事件流 + 決策時間線 + 意圖透視，每個決策有跡可循
- **活動追蹤**：實時展示每個 Agent 的狀態和當前任務
- **What-If 分析器**：提交前對比多個方案，支持路徑模擬和推薦

### 5. 工作流管道編排

每個任務都遵循結構化、強制執行的工作流——告別臨時性執行：

- **7 種管道模板**：`feature`（Research→Design→Implement→Review→Test→Deploy）、`bugfix`、`research`、`refactor`、`quick-fix`、`spike`、`hotfix`
- **通過 `task_type` 自動掛載**：在 `task_create` 中傳入 `task_type="feature"`，管道自動創建
- **漸進式強制**：hook 檢測無管道任務——軟提醒 → 強提醒 → 第三次硬阻斷（`exit 2`）
- **自動階段推進**：每個階段推薦最適合的 Agent 模板；`pipeline_advance` 自動推進到下一階段
- **最輕量逃生通道**：`quick-fix`（僅 Implement→Test）適用於真正的小改動
- **Channel 通訊系統**：`team:` / `project:` / `global` 三種頻道 + `@mention` 支持
- **辯論模式**：4 輪結構化辯論（Advocate→Critic→Response→Judge）+ `debate_start` / `debate_code_review`
- **Git 自動化**：`git_auto_commit` / `git_create_pr` / `git_status_check` 簡化版本控制
- **語義緩存**：BM25 + Jaccard 相似度匹配，JSON 持久化，TTL 過期
- **執行模式記憶**：成功/失敗模式記錄 + BM25 檢索 + subagent 上下文注入

### 6. 安全與行為強制

內置護欄，系統在無人監督時也不會產生意外：

- **Guardrails L1**：7 種危險模式檢測 + PII 警告 + `InputGuardrailMiddleware`
- **本地 Agent 攔截**：所有非只讀 Agent 必須聲明 `team_name`/`name`，防止遊離後台 Agent
- **S1 安全規則**：正則掃描攔截破壞性命令（rm -rf、force push、硬編碼密鑰），覆蓋大寫標志和 heredoc 模式
- **四層防線規則體系**：48+ 條規則，覆蓋工作流、委派、會話和安全層
- **文件鎖/工作區隔離**：acquire/release/check/list + TTL=300s + hook 警告，防止並發編輯
- **Agent 信任評分**：trust_score (0-1) 隨任務成功/失敗自動調整，加權到 auto_assign
- **Agent Watchdog 心跳**：`agent_heartbeat` / `watchdog_check`，5 分鐘 TTL，自動檢測卡死或崩潰的 Agent
- **SRE 錯誤預算模型**：GREEN/YELLOW/ORANGE/RED 四級響應，滑動窗口 20 任務，`error_budget_status` / `error_budget_update` 工具
- **完成驗證協議**：`verify_completion` 檢查 task 狀態 + memo 存在，防止幻覺"已完成"報告
- **生態集成配方**：4 個預設配方（GitHub / Slack / Linear / 全棧團隊），通過 `ecosystem_recipes()` 工具查詢
- **`find_skill` 三層漸進發現**：快速推薦 → 分類瀏覽 → 完整詳情，降低工具調用開銷

### 7. 零額外成本

100% 運行在你現有的 Claude Code 訂閱套餐內：

- 不調用外部 API，不燒額外 token
- MCP 工具、Hooks 和 Agent 模板全部本地運行
- 完全覆用你的 CC 套餐

### 8. 生態研究平台（v1.5.0 漸進式漏鬥）

項目隔離的**知識庫**，研究產物隨時間累加。每個倉走過 4 階段，token 高效觸發 + append-only 歷史：

- **Stage 0 — 入檔即淺掃**：新入檔倉自動派 `ai-engineer` 出 200-400 字總結（核心功能 / 定位 / 優勢）。8 類失敗處理 + **自學習機制**（同類失敗 ≥ 3 倉 → `pattern_record`，未來 agent 通過 `pattern_search` 讀 lessons 優化策略）。Worker 自動覆活刪庫/私密恢覆 200 的倉
- **Stage 1 — 按需架構分析**：用戶挑研究方向（"memory_system"）→ 批量派 `backend-architect` 讀架構關鍵文件
- **Stage 2 — 多角度辯論**：觸發現有 `debate_start`（**不內建辯論引擎，覆用會議系統**）。會議→生態庫反向寫入 hook 提醒 Leader 把辯論結論回寫到 deep_review
- **Stage 3 — 參考 / 集成標記**：`mark_as_reference` 加 tag 便於未來快速召回（避免重覆深掃）；`start_integration` 觸發現有 `task_create` 啟動實際集成任務
- **項目可定制閾值**：每個項目獨立設 `min_stars` / `top_n` / `refresh_interval_days` / `focus_topics`。AI Team OS 默認：stars ≥ 5K，top 200，關注 claude-code / mcp / agent-framework
- **活躍/全量雙視圖**：數據**永不刪除**。stars 跌出閾值的倉保留（僅 `is_active=False`）；漲回自動激活 + 重新入隊 Stage 0
- **Dashboard `/ecosystem`**：列表帶 stage 徽章 + 研究歷程 timeline + 項目篩選下拉（按項目查看生態庫）+ 候選篩選頁 (`/ecosystem/research`) + 項目設置 tab
- **30+ MCP 工具 / 15+ REST 端點 / SQLite append-only 歷史快照**

---

## 它構建了自己

AI Team OS 管理了自身的開發過程：

- 組織了 5 場多 Agent 辯論式頭腦風暴創新會議
- 對 CrewAI、AutoGen、LangGraph 和 Devin 進行了競品分析
- 完成了 5 個重大創新功能方向的 67 個任務
- 生成了 14 份設計文檔，共 10,000+ 行

這個為你的項目構建東西的系統……構建了它自己。

---

## 與主流方案對比

| 維度 | AI Team OS | CrewAI | AutoGen | LangGraph | Devin |
|------|-----------|--------|---------|-----------|-------|
| **定位** | CC 增強層 OS | 獨立框架 | 獨立框架 | 工作流引擎 | 獨立 AI 工程師 |
| **集成方式** | MCP 協議接入 CC | 獨立 Python 運行 | 獨立 Python 運行 | 獨立 Python 運行 | SaaS 獨立產品 |
| **自主運轉** | 持續循環，從不空閒 | 逐任務執行 | 逐任務執行 | 工作流驅動 | 有限 |
| **會議系統** | 8 種結構化模板，支持關鍵詞自動匹配 | 無 | 有限 | 無 | 無 |
| **失敗學習** | 失敗煉金術（抗體/疫苗/催化劑） | 無 | 無 | 無 | 有限 |
| **決策透明度** | 決策駕駛艙 + 時間線 | 無 | 有限 | 有限 | 黑盒 |
| **工作流編排** | 7 種管道模板 + 漸進式強制 | 無 | 無 | 手動 | 無 |
| **規則體系** | 四層防線（48+ 條）+ 行為強制 | 有限 | 有限 | 無 | 有限 |
| **Agent 模板** | 25 個開箱即用 + 推薦引擎 | 內置角色 | 內置角色 | 無 | 無 |
| **Dashboard** | React 19 可視化 | 商業版 | 無 | 無 | 有 |
| **開源** | MIT | Apache 2.0 | MIT | MIT | 否 |
| **Claude Code 原生** | 是，深度集成 | 否 | 否 | 否 | 否 |
| **額外成本** | $0（僅 CC 訂閱） | 需 API 費用 | 需 API 費用 | 需 API 費用 | $500+/月 |

---

## 系統架構

```
┌─────────────────────────────────────────────────────────────────┐
│                     用戶（董事長）                                │
│                         │                                       │
│                         ▼                                       │
│                   Leader（CEO）                                  │
│            ┌────────────┼────────────┐                          │
│            ▼            ▼            ▼                          │
│       Agent模板      任務墻        會議系統                        │
│      (25個角色)    Loop引擎      (8種模板)                         │
│            │            │            │                          │
│            └────────────┼────────────┘                          │
│                         ▼                                       │
│              ┌──────────────────────┐                           │
│              │   OS 增強層           │                           │
│              │  ┌──────────────┐    │                           │
│              │  │  MCP Server  │    │                           │
│              │  │ (107 tools)  │    │                           │
│              │  └──────┬───────┘    │                           │
│              │         │            │                           │
│              │  ┌──────▼───────┐    │                           │
│              │  │  FastAPI     │    │                           │
│              │  │  REST API    │    │                           │
│              │  └──────┬───────┘    │                           │
│              │         │            │                           │
│              │  ┌──────▼───────┐    │                           │
│              │  │  Dashboard   │    │                           │
│              │  │ (React 19)   │    │                           │
│              │  └──────────────┘    │                           │
│              └──────────────────────┘                           │
│                         │                                       │
│              ┌──────────▼──────────┐                            │
│              │  Storage (SQLite)   │                            │
│              │  + Alembic Migration│                            │
│              │  + Memory System    │                            │
│              └─────────────────────┘                            │
└─────────────────────────────────────────────────────────────────┘
```

### 五層技術架構

```
Layer 5: Web Dashboard    — React 19 + TypeScript + Shadcn UI（18 個頁面）
Layer 4: CLI + REST API   — Typer + FastAPI
Layer 3: Team Orchestrator — LangGraph StateGraph
Layer 2: Memory Manager   — Mem0 / File fallback
Layer 1: Storage          — SQLite（開發環境）/ PostgreSQL（生產環境）+ Alembic 遷移
```

### Hook 系統（9 個生命周期事件 — CC 與 OS 的橋梁）

```
SessionStart     → session_bootstrap.py          — 注入Leader簡報 + 5條核心規則 + 團隊狀態
SessionEnd       → send_event.py                 — 記錄會話結束事件
SubagentStart    → inject_subagent_context.py    — 注入子Agent OS規則（2-Action等）
SubagentStop     → send_event.py                 — 記錄子Agent生命周期事件
PreToolUse       → workflow_reminder.py          — 工作流提醒 + 安全護欄
PostToolUse      → send_event.py                 — 事件轉發到 OS API
UserPromptSubmit → context_monitor.py            — 上下文使用率監控
Stop             → send_event.py                 — 記錄停止事件
PreCompact       → pre_compact_save.py           — 上下文壓縮前自動保存進度
```

---

## 快速安裝（AI 輔助）

告訴 Claude Code：
> "Read https://github.com/CronusL-1141/AI-company/blob/master/INSTALL.md and follow the instructions to install AI Team OS"

Claude Code 會自動讀取安裝指南並引導你完成配置。

---

> **重要提示**：請將 AI Team OS 安裝到系統 Python，而不是項目虛擬環境中。
> 如果安裝在 venv 中，AI Team OS 將只在該特定項目中可用。
> 如果當前已激活 venv，請先執行 `deactivate`，再進行安裝。

---

## 快速開始

### 前置要求

- Python >= 3.11
- [uv](https://docs.astral.sh/uv/getting-started/installation/)（`pip install uv`）
- Claude Code（需要 MCP 支持）
- Node.js >= 20（Dashboard 前端，可選）

> **國內用戶提示**：如果訪問 GitHub 較慢，建議配置代理或使用 Gitee 鏡像（如有）。

### 方式 A：Plugin 安裝（推薦）

```bash
# 安裝 uv（Python 包運行器，MCP 服務器需要）
pip install uv

# 添加 marketplace + 安裝
claude plugin marketplace add github:CronusL-1141/AI-company
claude plugin install ai-team-os

# 重啟 Claude Code — 首次啟動約 30 秒加載依賴
# 後續啟動秒級完成

# 隨時更新到最新版
claude plugin update ai-team-os@ai-team-os
```

> **提示**：首次啟動需要約 30 秒自動配置依賴，僅此一次。後續每次啟動 107 個 MCP 工具即時可用。

### 方式 B：手動安裝

```bash
# Step 1: 克隆倉庫
git clone https://github.com/CronusL-1141/AI-company.git
cd AI-company

# Step 2: 安裝（自動配置 MCP + Hooks + Agent 模板 + API）
python install.py

# Step 3: 重啟 Claude Code，一切自動激活
# API 服務器在 MCP 加載時自動啟動，無需手動操作
# 驗證：在 CC 中運行 → /mcp 查看 ai-team-os 工具是否掛載
```

### 方式 C：PyPI 安裝

```bash
pip install ai-team-os
python -m aiteam.scripts.install
# 重啟 Claude Code，工具自動激活
```

### 驗證安裝

```bash
# 檢查 OS 健康狀態（API 必須已啟動 — 端口可能變化，查看 api_port.txt）
curl http://localhost:8000/api/health
# 期望: {"status": "ok"}

# 通過 CC 創建第一個團隊
# 在 Claude Code 中輸入：
# "幫我創建一個 web 開發團隊，包含前端、後端和測試工程師"
```

### 啟動 Dashboard（可選）

```bash
cd dashboard
npm install
npm run dev
# 訪問 http://localhost:5173
```

---

## Dashboard 截圖

### 指揮中心
![Command Center](docs/screenshots/dashboard-home.png)

### 任務看板
![Task Board](docs/screenshots/task-board.png)

### 項目詳情 & 決策時間線
![Decision Timeline](docs/screenshots/decision-timeline.png)

### 會議室
![Meeting Room](docs/screenshots/meeting-room.png)

### 活動分析
![Analytics](docs/screenshots/analytics.png)

### 事件日志
![Events](docs/screenshots/events.png)

### 自主喚醒系統 — 無人值守任務推進
![Auto-Wake Demo](docs/screenshots/auto-wake-demo.png)

---

## 自主喚醒系統 (Auto-Wake)

AI Team OS 的 Leader 支持定時自動喚醒，在無人值守時自主推進任務：

- 每 10 分鐘自動檢查上下文使用率和待辦任務
- 有待辦任務時自主創建團隊並分配工作
- 需要用戶決策時通過 Briefing 系統異步記錄
- 上下文 > 80% 時自動保存進度並提醒開新 session

---

## 生態集成配方

AI Team OS 的定位是**元 Plugin** — 編排其他 MCP server，而非重新實現它們的功能。預設配方讓你在幾分鐘內集成流行工具：

| 配方 | 集成對象 | 能力 |
|------|---------|------|
| **GitHub** | `@modelcontextprotocol/github` | 自動創建 PR、Issue 跟蹤、代碼審查協調 |
| **Slack** | `@anthropics/slack-mcp` | 團隊通知、決策升級、狀態廣播 |
| **Linear** | `linear-mcp-server` | 任務同步、Sprint 跟蹤、Bug 分流自動化 |
| **全棧團隊** | GitHub + Slack + Linear | 完整開發工作流，跨工具編排 |

使用 `ecosystem_recipes` MCP 工具發現配方，或查看完整指南：[docs/ecosystem-recipes.md](docs/ecosystem-recipes.md)

---

## CC-First 設計原則

AI Team OS 專為 Claude Code 設計，不是獨立框架：

- **MCP 協議原生**：107 個工具全部通過 MCP 注冊 — 無自定義客戶端，無 API 包裝器
- **Hook 驅動生命周期**：9 個 CC 生命周期事件（SessionStart → PreCompact）提供深度集成，無需修改 CC 內部
- **Agent 模板即 `.md` 文件**：安裝到 `~/.claude/agents/`（全局）或 `.claude/agents/`（項目級）— CC 原生 Agent 系統，非自定義抽象
- **運行時零外部依賴**：不調用外部 API，不依賴雲服務 — 100% 在你的 CC 訂閱內運行
- **上下文感知**：Session bootstrap 僅注入 5 條核心規則（從 23 條精簡），subagent 上下文限制 60 行，最大化減少上下文預算占用

---

## MCP 工具一覽

<details>
<summary>展開查看全部 107 個 MCP 工具（22 個模塊）</summary>

### 團隊管理

| 工具 | 說明 |
|------|------|
| `team_create` | 創建 AI Agent 團隊，支持 coordinate/broadcast 模式 |
| `team_status` | 獲取團隊詳情和成員狀態 |
| `team_list` | 列出所有團隊 |
| `team_briefing` | 一次調用獲取團隊全景簡報（成員+事件+會議+待辦） |
| `team_setup_guide` | 根據項目類型推薦團隊角色配置 |

### Agent 管理

| 工具 | 說明 |
|------|------|
| `agent_register` | 注冊新 Agent 到團隊 |
| `agent_update_status` | 更新 Agent 狀態（idle/busy/error） |
| `agent_list` | 列出團隊成員 |
| `agent_template_list` | 獲取可用的 Agent 模板列表 |
| `agent_template_recommend` | 根據任務描述推薦最適合的 Agent 模板 |

### 任務管理

| 工具 | 說明 |
|------|------|
| `task_run` | 執行任務並記錄全程 |
| `task_decompose` | 將覆雜任務分解為子任務 |
| `task_status` | 查詢任務執行狀態 |
| `taskwall_view` | 查看任務墻（全部待辦+進行中+已完成） |
| `task_create` | 創建新任務（支持 `auto_start` 和 `task_type` 管道參數） |
| `task_update` | 局部更新任務字段，自動打時間戳 |
| `task_list_project` | 列出項目下所有任務 |
| `task_auto_match` | 基於任務特征智能匹配最佳 Agent |
| `task_memo_add` | 為任務添加執行備忘記錄 |
| `task_memo_read` | 讀取任務歷史備忘 |

### 管道編排

| 工具 | 說明 |
|------|------|
| `pipeline_create` | 為任務掛載工作流管道（7 種模板：feature/bugfix/research/refactor/quick-fix/spike/hotfix） |
| `pipeline_advance` | 推進管道到下一階段，返回下一階段的 Agent 模板推薦 |

### Loop 循環引擎

| 工具 | 說明 |
|------|------|
| `loop_start` | 啟動自動推進循環 |
| `loop_status` | 查看循環狀態 |
| `loop_next_task` | 獲取下一個待處理任務 |
| `loop_advance` | 推進循環到下一階段 |
| `loop_pause` | 暫停循環 |
| `loop_resume` | 恢覆循環 |
| `loop_review` | 生成循環回顧報告（含失敗分析） |

### 會議系統

| 工具 | 說明 |
|------|------|
| `meeting_create` | 創建結構化會議（8 種模板，關鍵詞自動匹配） |
| `meeting_send_message` | 發送會議消息 |
| `meeting_read_messages` | 讀取會議記錄 |
| `meeting_conclude` | 總結會議結論 |
| `meeting_template_list` | 獲取可用會議模板列表 |
| `meeting_list` | 列出所有會議 |
| `meeting_update` | 更新會議元數據 |

### Channel 通訊

| 工具 | 說明 |
|------|------|
| `channel_send` | 向頻道發送消息（team:/project:/global），支持 @mention |
| `channel_read` | 讀取頻道消息 |
| `channel_mentions` | 獲取 Agent 的未讀 @提及 |

### 文件鎖/工作區隔離

| 工具 | 說明 |
|------|------|
| `file_lock_acquire` | 獲取文件鎖（TTL=300s），防止並發編輯 |
| `file_lock_release` | 釋放文件鎖 |
| `file_lock_check` | 檢查文件是否被鎖定及鎖定者 |
| `file_lock_list` | 列出所有活躍的文件鎖 |

### Git 自動化

| 工具 | 說明 |
|------|------|
| `git_auto_commit` | 自動提交暫存變更並生成提交消息 |
| `git_create_pr` | 從當前分支創建 Pull Request |
| `git_status_check` | 檢查 Git 倉庫狀態 |

### 辯論系統

| 工具 | 說明 |
|------|------|
| `debate_start` | 啟動 4 輪結構化辯論（Advocate→Critic→Response→Judge） |
| `debate_code_review` | 啟動代碼審查辯論會話 |

### 護欄系統

| 工具 | 說明 |
|------|------|
| `guardrail_check` | 對命令字符串執行護欄檢查 |
| `guardrail_check_payload` | 對結構化載荷執行護欄檢查 |

### 執行模式

| 工具 | 說明 |
|------|------|
| `pattern_record` | 記錄成功/失敗執行模式 |
| `pattern_search` | 通過 BM25 檢索執行模式，用於上下文注入 |

### 智能分析

| 工具 | 說明 |
|------|------|
| `failure_analysis` | 失敗煉金術——分析失敗根因，生成抗體/疫苗/催化劑 |
| `what_if_analysis` | What-If 分析器——多方案對比推薦 |
| `decision_log` | 記錄決策到駕駛艙時間線 |
| `context_resolve` | 解析當前上下文，獲取相關背景信息 |

### 記憶系統

| 工具 | 說明 |
|------|------|
| `memory_search` | 全文檢索團隊記憶庫 |
| `team_knowledge` | 獲取團隊知識摘要 |

### 信任與可靠性

| 工具 | 說明 |
|------|------|
| `agent_trust_scores` | 查看所有 Agent 的信任評分 |
| `agent_trust_update` | 手動調整 Agent 的信任評分 |
| `agent_heartbeat` | 發送運行中 Agent 的心跳信號 |
| `watchdog_check` | 檢查卡死的 Agent（5 分鐘 TTL 超時） |
| `error_budget_status` | 查看 SRE 錯誤預算（GREEN/YELLOW/ORANGE/RED） |
| `error_budget_update` | 記錄任務結果到錯誤預算 |
| `verify_completion` | 驗證任務完成狀態（狀態 + memo 檢查，防幻覺） |

### 分析

| 工具 | 說明 |
|------|------|
| `task_execution_trace` | 獲取任務的統一執行時間線 |
| `task_replay` | 回放任務執行歷史 |
| `task_compare` | 並排對比兩次任務執行 |
| `diagnose_task_failure` | 自動診斷任務失敗原因 |

### 簡報系統

| 工具 | 說明 |
|------|------|
| `briefing_add` | 添加待用戶審查的決策項 |
| `briefing_list` | 列出待處理的簡報項 |
| `briefing_resolve` | 以決策解決簡報項 |
| `briefing_dismiss` | 忽略簡報項 |

### 報告（數據庫存儲）

| 工具 | 說明 |
|------|------|
| `report_save` | 保存報告到數據庫，支持項目隔離（研究/設計/分析/會議紀要） |
| `report_list` | 列出報告，支持按項目、類型、作者、主題過濾 |
| `report_read` | 通過報告 ID 讀取報告 |

### 調度器

| 工具 | 說明 |
|------|------|
| `scheduler_create` | 創建定時周期任務 |
| `scheduler_list` | 列出定時任務 |
| `scheduler_delete` | 刪除定時任務 |
| `scheduler_pause` | 暫停定時任務 |

### 緩存管理

| 工具 | 說明 |
|------|------|
| `cache_stats` | 查看語義緩存命中/未命中統計 |
| `cache_clear` | 清空語義緩存 |

### 生態集成

| 工具 | 說明 |
|------|------|
| `ecosystem_recipes` | 發現集成配方（GitHub/Slack/Linear/全棧） |
| `send_notification` | 通過 Slack/webhook 發送通知 |
| `cross_project_send` | 發送跨項目消息 |
| `cross_project_inbox` | 讀取跨項目收件箱 |

### Prompt Registry

| 工具 | 說明 |
|------|------|
| `prompt_version_list` | 列出 Agent 模板版本 |
| `prompt_effectiveness` | 查看模板效果指標 |

### 項目管理

| 工具 | 說明 |
|------|------|
| `project_create` | 創建項目 |
| `project_list` | 列出所有項目 |
| `project_update` | 更新項目設置 |
| `project_delete` | 刪除項目 |
| `project_summary` | 獲取項目快速狀態摘要 |
| `phase_create` | 創建項目階段 |
| `phase_list` | 列出項目階段 |

### 系統運維

| 工具 | 說明 |
|------|------|
| `os_health_check` | OS 健康檢查 |
| `event_list` | 查看系統事件流 |
| `os_report_issue` | 上報問題 |
| `os_resolve_issue` | 標記問題已解決 |
| `agent_activity_query` | 查詢 Agent 活動歷史和統計數據 |
| `find_skill` | 三層漸進技能發現（快速推薦 / 分類瀏覽 / 完整詳情） |
| `team_close` | 關閉團隊並級聯關閉其所有活躍會議 |
| `team_delete` | 刪除團隊 |

</details>

---

## Agent 模板庫

25 個開箱即用的專業 Agent 模板，含推薦引擎，覆蓋完整軟件工程團隊配置。模板安裝到 `plugin/agents/`（項目級）和 `~/.claude/agents/`（全局，跨項目可用）。

### 工程部（13 個模板）

| 模板名 | 角色 | 適用場景 |
|--------|------|---------|
| `engineering-software-architect` | 軟件架構師 | 系統設計、架構評審 |
| `engineering-backend-architect` | 後端架構師 | API 設計、服務架構 |
| `engineering-frontend-developer` | 前端開發工程師 | UI 實現、交互開發 |
| `engineering-ai-engineer` | AI 工程師 | 模型集成、LLM 應用 |
| `engineering-mcp-builder` | MCP 構建專家 | MCP 工具開發 |
| `engineering-code-reviewer` | 代碼審查工程師 | 代碼質量審查、PR 審查 |
| `engineering-database-optimizer` | 數據庫優化師 | 查詢優化、Schema 設計 |
| `engineering-devops-automator` | DevOps 自動化工程師 | CI/CD、基礎設施 |
| `engineering-sre` | 站點可靠性工程師 | 可觀測性、故障處理 |
| `engineering-security-engineer` | 安全工程師 | 安全審查、漏洞分析 |
| `engineering-rapid-prototyper` | 快速原型工程師 | MVP 驗證、快速叠代 |
| `engineering-mobile-developer` | 移動端開發工程師 | iOS/Android 開發 |
| `engineering-git-workflow-master` | Git 工作流專家 | 分支策略、代碼協作 |

### 測試部（4 個模板）

| 模板名 | 角色 | 適用場景 |
|--------|------|---------|
| `testing-qa-engineer` | QA 工程師 | 測試策略、質量保障 |
| `testing-api-tester` | API 測試專家 | 接口測試、契約測試 |
| `testing-bug-fixer` | Bug 修覆專家 | 缺陷分析、根因排查 |
| `testing-performance-benchmarker` | 性能基準測試師 | 性能分析、壓測 |

### 研究與支持（3 個模板）

| 模板名 | 角色 | 適用場景 |
|--------|------|---------|
| `specialized-workflow-architect` | 工作流架構師 | 流程設計、自動化編排 |
| `support-technical-writer` | 技術文檔工程師 | API 文檔、用戶指南 |
| `support-meeting-facilitator` | 會議主持人 | 結構化討論、決策推進 |

### 管理層（2 個模板）

| 模板名 | 角色 | 適用場景 |
|--------|------|---------|
| `management-tech-lead` | 技術 Lead | 技術決策、團隊協調 |
| `management-project-manager` | 項目經理 | 進度管理、風險跟蹤 |

### 辯論角色（2 個模板）

| 模板名 | 角色 | 適用場景 |
|--------|------|---------|
| `debate-advocate` | 辯論倡導者 | 在結構化辯論中提出和捍衛方案 |
| `debate-critic` | 辯論評論者 | 挑戰提案、發現弱點 |

### 通用模板（1 個）

| 模板名 | 角色 | 適用場景 |
|--------|------|---------|
| `team-member` | 通用團隊成員 | 通用型任務的默認角色 |

---

## 路線圖

### 已完成

- [x] 核心 Loop 引擎（LoopEngine + 任務墻 + Watchdog + 回顧）
- [x] 失敗煉金術（抗體 + 疫苗 + 催化劑）
- [x] 決策駕駛艙（事件流 + 時間線 + 意圖透視）
- [x] 事件驅動任務墻 2.0（實時推送 + 智能匹配）
- [x] 團隊活記憶（知識查詢 + 經驗共享）
- [x] What-If 分析器（多方案對比推薦）
- [x] 8 種結構化會議模板，支持關鍵詞自動匹配
- [x] 25 個專業 Agent 模板（23 基礎 + 2 辯論角色），含推薦引擎
- [x] 四層防線規則體系（48+ 條規則）+ 行為強制
- [x] Dashboard 指揮中心（React 19）— 18 個頁面，含 Pipeline / Failures / Prompts / Agent Live Board
- [x] 107 個 MCP 工具，分布在 22 個模塊中
- [x] AWARE 循環記憶系統
- [x] find_skill 三層漸進發現
- [x] task_update API，支持程序化任務管理
- [x] 工作流管道編排（7 種模板 + 自動階段推進 + 漸進式強制）
- [x] 631+ 自動化測試（含 28 個跨功能集成測試）
- [x] Prompt Registry（版本追蹤 + 效果統計）
- [x] BM25 搜索升級（中文 bigram + 英文分詞，搜索質量提升 3-5x）
- [x] 事件日志增強（entity_id / entity_type / state_snapshot 字段）
- [x] CC Plugin Marketplace 正式提交
- [x] 文件鎖/工作區隔離（acquire/release/check/list + TTL=300s）
- [x] Channel 通訊系統（team:/project:/global + @mention）
- [x] 執行模式記憶（成功/失敗記錄 + BM25 檢索）
- [x] Git 自動化工具（git_auto_commit / git_create_pr / git_status_check）
- [x] Guardrails L1（7 種危險模式 + PII 警告）
- [x] Alembic 數據庫遷移系統
- [x] 辯論模式（4 輪結構化辯論 + 代碼審查）
- [x] Agent 信任評分系統（任務成功/失敗自動調整）
- [x] 語義緩存層（BM25 + Jaccard 相似度，TTL 過期）
- [x] 工具分級定義（CORE 15 vs ADVANCED 46）
- [x] Agent Watchdog 心跳系統（5 分鐘 TTL 超時檢測）
- [x] SRE 錯誤預算模型（GREEN/YELLOW/ORANGE/RED 四級響應）
- [x] 完成驗證協議（防幻覺完成檢查）
- [x] 生態集成配方（GitHub/Slack/Linear/全棧團隊預設）
- [x] Session bootstrap 規則壓縮（23 → 5 條核心規則，上下文減少 60%）
- [x] API 原子啟動鎖（多 session 端口沖突防護）
- [x] 自動端口發現（API 自動尋找空閒端口，寫入 `api_port.txt`）
- [x] MCP HTTP Streamable 端點（`/mcp/` 掛載到 FastAPI）
- [x] PyPI 1.2.0 發布（`pip install ai-team-os`）
- [x] INSTALL.md CC 輔助安裝指引

### 進行中 / 計劃中

- [ ] 多用戶隔離（Multi-tenant 支持）
- [ ] 實戰驗證與性能優化
- [x] Claude Code Plugin Marketplace 上架
- [ ] 完整集成測試套件
- [ ] 文檔網站（Docusaurus）
- [ ] 視頻教程系列

---

## 項目結構

```
ai-team-os/
├── src/aiteam/
│   ├── api/           — FastAPI REST 端點
│   ├── mcp/
│   │   ├── server.py  — MCP 服務器入口
│   │   └── tools/     — 22 個工具模塊（共 107 個工具）
│   ├── loop/          — Loop 引擎
│   ├── meeting/       — 會議系統
│   ├── memory/        — 團隊記憶
│   ├── orchestrator/  — 團隊編排器
│   ├── storage/       — 存儲層（SQLite/PostgreSQL）+ Alembic 遷移
│   ├── templates/     — Agent 模板基類
│   ├── hooks/         — CC Hook 腳本（9 個生命周期事件）
│   └── types.py       — 共享類型定義
├── plugin/
│   ├── agents/        — 25 個 Agent 模板（.md）
│   └── .claude-plugin/ — Plugin 清單
├── dashboard/         — React 19 前端（18 個頁面）
├── docs/              — 設計文檔 + 生態集成配方
├── tests/             — 測試套件（631+ 測試）
├── install.py         — 一鍵安裝腳本
└── pyproject.toml
```

---

## 貢獻指南

歡迎貢獻！特別期待以下方向：

- **新 Agent 模板**：如果你有專業角色的提示詞設計，歡迎 PR
- **會議模板擴展**：新的結構化討論模式
- **Bug 修覆**：提 Issue 或直接 PR
- **文檔改善**：發現文檔與代碼不一致，歡迎糾正

```bash
# 開發環境搭建
git clone https://github.com/CronusL-1141/AI-company.git
cd AI-company/ai-team-os
pip install -e ".[dev]"
pytest tests/
```

提 PR 前請確保：
- `ruff check src/` 通過
- `mypy src/` 無新增錯誤
- 相關測試通過

---

## License

MIT License — 詳見 [LICENSE](LICENSE)

---

<div align="center">

**AI Team OS** — 你睡覺，它還在工作。

*Built with Claude Code · Powered by MCP Protocol*

[文檔](docs/) · [Issues](https://github.com/CronusL-1141/AI-company/issues) · [討論區](https://github.com/CronusL-1141/AI-company/discussions)

</div>
