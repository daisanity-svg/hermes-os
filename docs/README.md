# Hermes OS

Hermes Agent Organization 的執行層 Runtime。
本目錄為 v0.1 MVP，包含八個核心模組、CLI 規格、Process Adapter 與 CI 流程。

## 快速開始

```bash
cd ~/AI-Workspace/hermes-os
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m pytest tests/ -q
```

## 對接 Hermes Agent

```bash
# 在 hermes-agent repo 內執行
PYTHONPATH=~/AI-Workspace/hermes-os/src python scripts/run_hermes_os.py demo-task-1
```

## 模組責任表

| 模組 | 責任 |
|------|------|
| `artifact_registry` | artifact 儲存與查詢，對接 `~/.hermes/artifacts/runs/{run_id}/` |
| `ownership_records` | artifact/run 的 owner attribution ledger |
| `lifecycle_records` | 狀態轉換事件記錄 |
| `action_records` | operational action 生命週期 |
| `workforce_queue` | 優先 Work item 佇列 |
| `control_center_snapshot` | Control Center 狀態 snapshot |
| `operational_memory_log` | append-only 記憶體日誌，支援 DSL 查詢 |
| `minimal_cli_spec` | CLI 命令規格與 `hermes-os` 指令實作 |
| `process_adapter` | Hermes OS → Hermes Agent 橋接器 |
| `ap_task` | Hermes Agent AP Task payload schema |

## 測試

```bash
python -m pytest tests/ -q
```

## CI

 pushes 與 pull request 會自動觸發 `.github/workflows/ci.yml`。
