# Hermes OS v0.1 MVP

Hermes OS 是 Hermes Agent Organization 的執行層 Runtime。
本目錄為 v0.1 MVP Skeleton（Task-061），包含八個核心模組與最小 CLI。

## 安裝套件

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## 建置 Wheel

```bash
python -m build --wheel --no-isolation
pip install dist/*.whl
```

## Docker

```bash
docker build -t hermes-os:latest .
docker run -p 8765:8765 hermes-os:latest
```

## Chairman Desktop（Command Center）

### 快速開始（本機）

```bash
make command-center
```

或手動啟動：

```bash
source .venv/bin/activate
PYTHONPATH=src python scripts/start_command_center.py
```

瀏覽器開啟 `http://127.0.0.1:8765/` 即可使用 Chairman Desktop。

### 跨裝置存取（同 Wi-Fi / 區域網路）

若需要從手機、iPad 或其他電腦存取，可綁定所有網路介面：

```bash
make command-center
# 等效手動指令：
source .venv/bin/activate
PYTHONPATH=src python scripts/start_command_center.py --host 0.0.0.0 --port 8765
```

啟動時會顯示本機與區網 URL，例如：

- 本機：`http://127.0.0.1:8765/`
- 同 Wi-Fi 手機：`http://192.168.1.42:8765/`

**安全限制：**
- 僅限同一 Wi-Fi / 區域網路內裝置可存取。
- 請勿將此服務暴露到公網，亦不得搭配 Cloudflare Tunnel、反向代理或無-auth 的 HTTPS 上線。
- 若需外網或行動通知，需額外建立 FounderDecisionTicket 並經 Founder 授權。

## MVP Modules

| 路徑 | 責任 |
|------|------|
| `src/hermes_os/artifact_registry` | artifact 儲存與查詢 (CRUD) |
| `src/hermes_os/ownership_records` | 所有权 / 負責人歸屬記錄 |
| `src/hermes_os/lifecycle_records` | run / entity 生命週期事件 log |
| `src/hermes_os/action_records` | operational action audit trail |
| `src/hermes_os/workforce_queue` |  workforce 任務佇列 |
| `src/hermes_os/control_center_snapshot` | system snapshot 快照 |
| `src/hermes_os/operational_memory_log` | operational memory 追加紀錄 |
| `src/hermes_os/minimal_cli_spec` | CLI 命令規格與合約 |
| `src/hermes_os/watchdog` | Supervisor MVP：停滯偵測、GPT 決策、安全執行 |
| `src/hermes_os/tool_registry` | Tool Registry：介面與安全規則（Browser/Finder/Terminal/AppleScript/OCR/Speech） |
| `src/hermes_os/memory` | Memory Layer：Local Knowledge 目錄、SQLite schema、Markdown knowledge object |
| `src/hermes_os/workflow` | Workflow Engine：可定義 project / research / development workflow |
| `src/hermes_os/project_lifecycle` | Project Lifecycle：goal→plan→tasks→runs→review→deliverable→reflection |
| `src/hermes_os/llm` | LLM Adapter 抽象：多 provider 支援，保留未來替換模型能力 |

## 設計約束

- 最小修改優於重構
- 模組間介面以 `src/hermes_os/types.py` 為契約
- 不依賴 Hermes Agent 核心，可獨立安裝測試
