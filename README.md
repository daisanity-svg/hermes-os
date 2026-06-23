# Hermes OS v0.1 MVP

Hermes OS 是 Hermes Agent Organization 的執行層 Runtime。
本目錄為 v0.1 MVP Skeleton（Task-061），包含八個核心模組與最小 CLI。

## 快速開始

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m pytest
hermes-os --help
```

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

## 設計約束

- 最小修改優於重構
- 模組間介面以 `src/hermes_os/types.py` 為契約
- 不依賴 Hermes Agent 核心，可獨立安裝測試
