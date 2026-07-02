# AI Team OS 生態集成配方

> AI Team OS 定位為"編排其他 Plugin/MCP 的元 Plugin"。本文檔提供與主流開發工具的集成配方，幫助你快速構建適合自己團隊的工作環境。
>
> **原則**: 不寫代碼集成，而是組合現有 MCP server —— AI Team OS 負責編排，第三方 MCP 負責執行。

---

## 目錄

- [配方 1: GitHub 集成](#配方-1-github-集成)
- [配方 2: Slack 集成](#配方-2-slack-集成)
- [配方 3: Linear 集成](#配方-3-linear-集成)
- [配方 4: 全棧開發團隊模板](#配方-4-全棧開發團隊模板)
- [配方組合矩陣](#配方組合矩陣)
- [故障排查](#故障排查)

---

## 配方 1: GitHub 集成

將 GitHub 與 AI Team OS 結合，實現代碼管理、PR 審查、Issue 追蹤的自動化編排。

### 推薦 MCP

| MCP Server | 來源 | 說明 |
|-----------|------|------|
| `github` | [modelcontextprotocol/servers](https://github.com/modelcontextprotocol/servers/tree/main/src/github) | 官方 GitHub MCP server，提供完整的 GitHub API 能力 |

### 安裝配置

在 `.mcp.json` 中添加 GitHub MCP server：

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "<your-token>"
      }
    }
  }
}
```

**Token 獲取**: GitHub Settings > Developer Settings > Personal access tokens > 創建 token，勾選 `repo`、`issues`、`pull_requests` 權限。

### 與 AI Team OS 配合方式

#### 場景 A: Pipeline Deploy 階段自動提交 + 創建 PR

```
工作流:
  1. Agent 完成代碼編寫
  2. AI Team OS pipeline_advance → 進入 deploy 階段
  3. Leader 調用 git_auto_commit 提交代碼
  4. Leader 調用 git_create_pr 創建 PR
  5. GitHub MCP 將 PR 推送到 GitHub
```

OS 工具鏈:
- `git_auto_commit` — 自動提交暫存區代碼
- `git_create_pr` — 創建 Pull Request
- `git_status_check` — 檢查工作區狀態

#### 場景 B: Code Review 雙重審查

```
工作流:
  1. 開發 Agent 提交代碼
  2. AI Team OS debate_code_review 發起內部代碼審查
  3. 審查通過後，創建 GitHub PR
  4. GitHub MCP 讀取 PR 評論，補充外部審查反饋
  5. 最終合並決策由 Leader 統籌
```

OS 工具鏈:
- `debate_code_review` — AI 內部代碼審查（多視角辯論）
- `task_memo_add` — 記錄審查結論

#### 場景 C: Issue 與任務墻雙向映射

```
映射規則:
  GitHub Issue (open)      ↔  AI Team OS 任務 (todo/in_progress)
  GitHub Issue (closed)    ↔  AI Team OS 任務 (completed)
  GitHub Issue label       ↔  AI Team OS 任務 priority/tags
  GitHub Issue assignee    ↔  AI Team OS Agent assignee
```

實踐建議:
- 每次 sprint 開始時，Leader 從 GitHub Issues 同步任務到任務墻
- Agent 完成任務後，由 Leader 關閉對應 GitHub Issue
- 使用 `task_memo_add` 在任務中記錄 GitHub Issue 鏈接

---

## 配方 2: Slack 集成

將 Slack 與 AI Team OS 結合，實現團隊通知、告警和站會摘要的自動推送。

### 推薦 MCP

| MCP Server | 來源 | 說明 |
|-----------|------|------|
| `slack` | [modelcontextprotocol/servers](https://github.com/modelcontextprotocol/servers/tree/main/src/slack) | 官方 Slack MCP server，支持頻道消息讀寫 |

### 安裝配置

在 `.mcp.json` 中添加 Slack MCP server：

```json
{
  "mcpServers": {
    "slack": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-slack"],
      "env": {
        "SLACK_BOT_TOKEN": "<your-bot-token>",
        "SLACK_TEAM_ID": "<your-team-id>"
      }
    }
  }
}
```

**Token 獲取**: Slack App 管理頁 > 創建 App > OAuth & Permissions > 添加 `chat:write`, `channels:read`, `channels:history` 權限 > 安裝到工作區 > 覆制 Bot Token。

### 與 AI Team OS 配合方式

#### 場景 A: Leader 簡報推送

```
工作流:
  1. Loop 結束時，Leader 調用 team_briefing 生成團隊簡報
  2. 簡報內容通過 send_notification 或 Slack MCP 推送到指定頻道
  3. 團隊成員在 Slack 中查看項目進展
```

OS 工具鏈:
- `team_briefing` — 生成團隊工作簡報
- `send_notification` — 通過 Webhook 推送通知（OS 內置）
- `briefing_list` — 查看歷史簡報

#### 場景 B: 錯誤預算 RED 告警

```
工作流:
  1. Watchdog 定期檢查錯誤預算
  2. 當錯誤預算超標 (RED) 時觸發告警
  3. 通過 Slack MCP 向 #ops-alerts 頻道發送告警消息
  4. 包含：超標指標、受影響任務、建議行動
```

OS 工具鏈:
- `error_budget_status` — 查看錯誤預算狀態
- `os_report_issue` — 創建緊急 Issue

#### 場景 C: 每日站會摘要

```
工作流:
  1. Leader 調用 taskwall_view 獲取任務墻狀態
  2. 匯總：昨日完成 / 今日計劃 / 阻塞項
  3. 格式化為站會摘要，推送到 #standup 頻道
  4. 可結合 meeting_conclude 的會議紀要一起發送
```

OS 工具鏈:
- `taskwall_view` — 查看任務墻全局視圖
- `meeting_conclude` — 生成會議紀要
- `loop_status` — 查看當前循環狀態

---

## 配方 3: Linear 集成

將 Linear 與 AI Team OS 結合，實現項目管理工具之間的任務同步。

### 推薦 MCP

| MCP Server | 來源 | 說明 |
|-----------|------|------|
| `linear` | [modelcontextprotocol/servers](https://github.com/modelcontextprotocol/servers/tree/main/src/linear) | Linear MCP server，支持 Issue 和 Project 操作 |

### 安裝配置

在 `.mcp.json` 中添加 Linear MCP server：

```json
{
  "mcpServers": {
    "linear": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-linear"],
      "env": {
        "LINEAR_API_KEY": "<your-api-key>"
      }
    }
  }
}
```

**API Key 獲取**: Linear Settings > API > Personal API keys > 創建新 key。

### 與 AI Team OS 配合方式

#### 場景 A: Linear Issue 與 AI Team OS 任務同步

```
映射規則:
  Linear Issue          ↔  AI Team OS task_create
  Linear Issue status   ↔  task_update status
  Linear assignee       ↔  Agent assignee
  Linear priority       ↔  task priority
  Linear label/project  ↔  task tags
```

實踐建議:
- Sprint 開始時從 Linear 同步 Issue 到 AI Team OS 任務墻
- Agent 完成任務後更新 Linear Issue 狀態
- 使用 task_memo 記錄 Linear Issue ID 建立關聯

#### 場景 B: Sprint 與 Pipeline 映射

```
Linear Sprint 階段      →  AI Team OS Pipeline 階段
  Backlog               →  plan
  In Progress           →  develop
  In Review             →  review
  Done                  →  deploy
```

OS 工具鏈:
- `pipeline_create` — 創建與 Sprint 對應的 Pipeline
- `pipeline_advance` — Sprint 階段推進時同步推進 Pipeline
- `pipeline_status` — 查看 Pipeline 當前狀態

#### 場景 C: 狀態雙向同步

```
工作流:
  1. Linear 中創建新 Issue → Leader 在 OS 中 task_create 對應任務
  2. OS 中任務狀態變更 → Leader 通過 Linear MCP 更新 Issue 狀態
  3. OS 中任務完成 → Leader 關閉 Linear Issue 並記錄完成摘要
```

---

## 配方 4: 全棧開發團隊模板

一個完整的全棧開發團隊配置，組合 AI Team OS + GitHub + Slack，預設前端、後端、測試、DevOps 角色。

### 推薦組合

| 組件 | 用途 |
|------|------|
| AI Team OS | 團隊編排、任務管理、循環驅動 |
| GitHub MCP | 代碼管理、PR、Issue |
| Slack MCP | 團隊通知、告警、站會 |
| Superpowers Skill | 強制 TDD + Git 工作流紀律 |
| VibeSec Skill | 代碼安全審查 |

### MCP 配置

`.mcp.json` 完整示例：

```json
{
  "mcpServers": {
    "ai-team-os": {
      "command": "python",
      "args": ["-m", "aiteam.mcp"],
      "env": {
        "AITEAM_DB_PATH": "./aiteam.db"
      }
    },
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "<your-token>"
      }
    },
    "slack": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-slack"],
      "env": {
        "SLACK_BOT_TOKEN": "<your-bot-token>",
        "SLACK_TEAM_ID": "<your-team-id>"
      }
    }
  }
}
```

### 預設團隊配置

使用 AI Team OS 創建全棧團隊:

```
# Step 1: 創建項目
project_create(name="my-fullstack-app", root_path="/path/to/project")

# Step 2: 創建團隊
team_create(name="fullstack-team", project_id="<project-id>")

# Step 3: 注冊 Agent 角色
# Leader — 統籌全局
agent_register(name="team-lead", role="leader", team_id="<team-id>")

# 前端開發
agent_register(name="frontend-dev", role="developer",
  skills=["React", "TypeScript", "CSS"],
  team_id="<team-id>")

# 後端開發
agent_register(name="backend-dev", role="developer",
  skills=["Python", "FastAPI", "PostgreSQL"],
  team_id="<team-id>")

# 測試工程師
agent_register(name="qa-engineer", role="tester",
  skills=["pytest", "Playwright", "E2E"],
  team_id="<team-id>")

# DevOps
agent_register(name="devops", role="devops",
  skills=["Docker", "CI/CD", "monitoring"],
  team_id="<team-id>")
```

### 典型工作流

```
Sprint 開始
  │
  ├── Leader: 從 GitHub Issues / Linear 同步任務到任務墻
  ├── Leader: loop_start 啟動工作循環
  │
  ├── 開發階段
  │   ├── frontend-dev: 開發 UI 組件 (配合 Frontend-Design Skill)
  │   ├── backend-dev: 開發 API 端點 (配合 Superpowers TDD)
  │   ├── VibeSec: 代碼安全掃描
  │   └── Leader: 通過 taskwall_view 監控進度
  │
  ├── 審查階段
  │   ├── debate_code_review: AI 內部代碼審查
  │   ├── git_create_pr: 創建 GitHub PR
  │   └── qa-engineer: 運行 E2E 測試
  │
  ├── 部署階段
  │   ├── devops: 構建 Docker 鏡像
  │   ├── git_auto_commit: 提交最終代碼
  │   └── Leader: pipeline_advance 推進到 deploy
  │
  └── 回顧
      ├── loop_review: 循環回顧
      ├── team_briefing: 生成簡報 → Slack 推送
      └── meeting_conclude: 記錄會議紀要
```

---

## 配方組合矩陣

不同團隊規模和場景的推薦組合：

| 場景 | 必需 | 推薦 | 可選 |
|------|------|------|------|
| 個人開發者 | AI Team OS | GitHub MCP | Superpowers |
| 小團隊 (2-5人) | AI Team OS + GitHub | Slack MCP | Linear, VibeSec |
| 全棧團隊 | AI Team OS + GitHub + Slack | Superpowers + VibeSec | Linear, Frontend-Design |
| 開源項目 | AI Team OS + GitHub | code-review Skill | Slack MCP |
| 數據科學團隊 | AI Team OS | Jupyter MCP | claude-mem |

---

## 故障排查

### Q: MCP server 啟動失敗

**A**: 確認依賴已安裝:
```bash
# GitHub/Slack/Linear MCP 都需要 Node.js
node --version  # 需要 >= 18

# 檢查 npx 是否可用
npx --version
```

### Q: GitHub Token 權限不足

**A**: 確認 token 包含以下 scope:
- `repo` — 倉庫訪問
- `read:org` — 組織信息（如需要）
- `workflow` — GitHub Actions（如需要）

### Q: Slack 消息發送失敗

**A**: 檢查以下幾點:
1. Bot Token 是否有 `chat:write` 權限
2. Bot 是否已被邀請到目標頻道（`/invite @your-bot`）
3. `SLACK_TEAM_ID` 是否正確（在 Slack 管理面板查看）

### Q: 多個 MCP server 的 context 消耗過大

**A**: AI Team OS 的建議是**按需啟用**:
- 不要同時啟用所有 MCP server
- 只在需要時在 `.mcp.json` 中添加對應 server
- 如果 context 接近上限，優先保留 AI Team OS 核心功能

### Q: 如何查看可用的集成配方

**A**: 使用 AI Team OS 內置工具:
```
ecosystem_recipes()                              # 查看所有配方
ecosystem_recipes(recipe_id="github")            # 查看特定配方
ecosystem_recipes(recipe_id="fullstack-team")    # 查看全棧團隊模板
```
