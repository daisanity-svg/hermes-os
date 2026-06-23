# ADR-001: Hermes OS → Hermes Agent Task Adapter Format

## Status
Accepted

## Context
Hermes OS 需要一個穩定的格式將 `WorkforceQueue` 的工作項目送到 Hermes Agent 執行。

## Decision
採用 `APTask` dataclass 作為唯一外部 contract：
- `task_id`：唯一識別
- `task_type`：分類
- `priority`：Execution priority
- `status`：TaskStatus enum
- `payload`：自由結構 dict
- `metadata`：補充欄位

## Consequences
- Hermes OS 只产出 `APTask`，不关心 Hermes Agent 內部如何排程
- Hermes Agent 端只需實作 `APTask` 的 consume 介面
