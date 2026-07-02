# AI Team OS 安裝指南（供 Claude Code 閱讀）

本文件供 Claude Code (CC) 輔助安裝時閱讀。如果你是人類使用者，請查看 [README.zh-TW.md](README.zh-TW.md)。

---

## 安裝前檢查

安裝前請驗證 Python 環境：

1. 執行：`python -c "import sys; print(sys.executable); print(sys.prefix); print(sys.base_prefix)"`
2. 如果輸出中 `sys.prefix` 包含 `.venv`、`virtualenv` 或 `env` 路徑，**警告使用者**：

   > ⚠️ 警告：你當前處於虛擬環境中（`{sys.prefix}`）。
   > AI Team OS 應安裝到系統 Python，而非專案 venv。
   > 如果安裝在 venv 中，hook 腳本在其他專案中將無法工作。
   > 請先執行 `deactivate`，或打開一個沒有 venv 的新終端，然後重新安裝。

3. 確認 `sys.prefix == sys.base_prefix` — 表示當前在系統 Python 中，可以安全安裝。

---

## 必需：配置設定

AI Team OS 需要在 `~/.claude/settings.json` 中配置特定設定。**執行以下腳本自動完成配置**：

```bash
python -c "
import json, os

p = os.path.join(os.path.expanduser('~'), '.claude', 'settings.json')
os.makedirs(os.path.dirname(p), exist_ok=True)

settings = {}
if os.path.exists(p):
    with open(p) as f:
        settings = json.load(f)

changed = False

# 1. 啟用 Agent Teams（團隊協作必需）
env = settings.setdefault('env', {})
if env.get('CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS') != '1':
    env['CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS'] = '1'
    changed = True
    print('[OK] Agent Teams 已啟用')

# 2. effortLevel — 由使用者自行選擇，不自動設定

if changed:
    with open(p, 'w') as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)
    print('[完成] 設定已更新 — 請告知使用者重啟 Claude Code')
else:
    print('[OK] 所有設定已就緒')
"
```

**執行後，告知使用者重啟 Claude Code** 以使設定生效。

---

## 安裝步驟

### 方式 A：外掛安裝（推薦）

```bash
# 添加 marketplace 源並安裝外掛
claude plugin marketplace add CronusL-1141/AI-company
claude plugin install ai-team-os

# 重啟 Claude Code
# 首次啟動約需30秒配置依賴（僅一次）
```

### 方式 B：從原始碼安裝

```bash
# 克隆倉庫
git clone https://github.com/CronusL-1141/AI-company.git
cd AI-company

# 執行安裝程式（配置 MCP + Hooks + Agent 模板）
python install.py

# 重啟 Claude Code
```

### 方式 C：pip 安裝（PyPI）

```bash
# 從 PyPI 安裝
pip install ai-team-os

# 執行安裝後配置腳本（必需 — 設定 MCP + hooks 配置）
python -m aiteam.cli.app init

# 重啟 Claude Code
```

---

## 驗證安裝

重啟 Claude Code 後：

1. 執行 `/mcp` — `ai-team-os` 應顯示為已連接，約 107 個工具
2. 執行 `os_health_check` MCP 工具 — 預期回應：`{"status": "ok"}`
3. 檢查 API：`curl http://localhost:8000/api/health` — 預期：`{"status": "ok"}`

如果工具未顯示，檢查：
- Windows：`%USERPROFILE%\.claude\settings.json` — 查找 `mcpServers` 中的 `ai-team-os`
- macOS/Linux：`~/.claude/settings.json`

---

## 已知限制

- **不要在專案 `.venv` 中安裝** — 全域 hook 腳本依賴系統 Python。在 venv 中安裝意味著 AI Team OS 僅在該 venv 啟用時可用。
- 如果誤裝在 venv 中：`pip uninstall ai-team-os`，然後 `deactivate`，然後重裝。
- 需要 Python >= 3.11。
- 需要支援 MCP 的 Claude Code（CC 版本 >= 1.0）。

---

## 更新

```bash
# 外掛安裝：
claude plugin update ai-team-os@ai-team-os

# 手動/pip 安裝：
pip install --upgrade ai-team-os
```

## 解除安裝

```bash
# 外掛安裝：
claude plugin uninstall ai-team-os

# 手動安裝：
python scripts/uninstall.py

# 清理殘留資料：
# Windows: rmdir /s %USERPROFILE%\.claude\plugins\data\ai-team-os-ai-team-os
# macOS/Linux: rm -rf ~/.claude/plugins/data/ai-team-os-*
```