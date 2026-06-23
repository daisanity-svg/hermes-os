# Hermes OS Architecture

## 組件圖

```
Hermes Agent OS Runtime
 ├── artifact_registry        ---- 對接 ~/.hermes/artifacts/runs/{run_id}
 ├── ownership_records
 ├── lifecycle_records
 ├── action_records
 ├── workforce_queue          ---- 優先佇列 + cancel/peek
 ├── control_center_snapshot  ---- control_center_snapshot/bridge.py
 ├── operational_memory_log   ---- 查詢 DSL（source/category/since/until/contains）
 ├── process_adapter          ---- Hermes OS → Hermes Agent
 │    └── ap_task             ---- TaskStatus + APTask payload schema
 └── minimal_cli_spec/cli.py  ---- status / runs / actions / queue / memory
```

## Sequence: submit → drain → Hermes Agent

```
Client
  │ submit(item)
  ▼
ProcessAdapter.submit()
  │ enqueue(WorkforceItem)
  ▼
WorkforceQueue
  │ dequeue()
  ▼
ProcessAdapter.drain(limit)
  │ APTask(...)
  ▼
Hermes Agent runtime
```
