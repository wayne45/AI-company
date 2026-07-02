# 開發機遷移指南（Windows → Mac / VS Code）

把 AI Team OS 的開發環境從 Windows 遷到 Mac。代碼本身全跨平台，**沒有版本兼容問題**；
要處理的只是「不隨 git 走」的三樣東西：未推送的提交、數據庫、本機專屬配置。

## 跨平台現狀（已核實）

| 項 | 狀態 |
|---|---|
| Python | 要求 `>=3.11`（`pyproject.toml`），Mac 裝 3.11+ 即可 |
| Plugin hooks | 全用 `${CLAUDE_PLUGIN_ROOT}` + `python`，完全可移植 |
| API 自啟動 `_autostart.py` | 已分別處理 win32 / unix（端口探測用 netstat/taskkill ↔ fuser/lsof/kill） |
| `.mcp.json` 生成 | `install.py` 用 `sys.executable` 寫入，Mac 上自動寫 Mac 的 python 路徑 |

## 不隨 git 走、必須手動處理的三樣

1. **未推送的提交** —— 換機前在舊機 `git push origin master`（否則 Mac clone 缺最新代碼）。
2. **數據庫 `aiteam.db`** —— 在 `~/.claude/data/ai-team-os/aiteam.db`（約 76MB，**不在倉庫**）。
   要帶現有團隊 / 項目 / 任務數據，必須手動拷到 Mac 同路徑。
3. **本機專屬配置** —— `.mcp.json` 和 `.claude/settings.json` 都被 `.gitignore`，不隨倉庫：
    - `.mcp.json`：`install.py` 在 Mac 會重新生成（正確的 Mac python 路徑），無需手動。
    - `.claude/settings.json`：里面那個 `pwsh + inject-context.ps1` 鉤子是 **Windows 專屬**，
      Mac 上要麼不用，要麼換成 bash/python 等價實現。

## Mac 上的步驟

```bash
# 0)（在舊 Windows 機）先推送，確保 GitHub 有最新代碼
git push origin master

# 1)（Mac）克隆並安裝 Python 包（需 Python 3.11+）
git clone https://github.com/CronusL-1141/AI-company.git
cd AI-company          # 倉庫目錄
pip install -e .

# 2) 安裝前端依賴並構建
cd dashboard && npm install && npm run build && cd ..

# 3) 注冊 MCP + hooks（自動生成 Mac 版 .mcp.json）
python install.py

# 4)（可選，要保留現有數據）從舊機拷數據庫到 Mac
#    舊機文件： ~/.claude/data/ai-team-os/aiteam.db
mkdir -p ~/.claude/data/ai-team-os
cp /path/to/aiteam.db ~/.claude/data/ai-team-os/aiteam.db

# 5)（可選，要用 Playwright 截圖/E2E）
pip install playwright && playwright install
```

VS Code：裝 Python 擴展即可，無其它特殊要求。

## 注意

- **換行符**：倉庫走 autocrlf，Mac 用 LF，無功能影響。
- **`dashboard/dist`**：構建產物，Mac 上需重新 `npm run build`（`.gitignore` 已忽略其 JS/CSS）。
- **數據隔離**：不拷 `aiteam.db` 的話，Mac 是一套全新空庫（團隊/項目/任務從零開始）。
