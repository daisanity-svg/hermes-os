"""Persistent Run Journal — minimal reliability tracking module."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from hermes_os.types import RunJournalEntry


class RunJournal:
    """最小 Persistent Run Journal，提供 append / update / list 能力。"""

    def __init__(self, storage_path: Optional[Path] = None) -> None:
        base = storage_path or (Path(__file__).resolve().parents[2] / "docs" / "sso" / "run-journal.json")
        self.storage_path = base
        self._entries: Dict[str, RunJournalEntry] = {}
        self._load()

    def _load(self) -> None:
        if not self.storage_path.exists():
            return
        try:
            data = json.loads(self.storage_path.read_text(encoding="utf-8"))
            for raw in data.get("entries", []):
                entry = RunJournalEntry(
                    run_id=raw["run_id"],
                    task_name=raw["task_name"],
                    status=raw.get("status", "queued"),
                    created_at=datetime.fromisoformat(raw["created_at"]),
                    updated_at=datetime.fromisoformat(raw["updated_at"]),
                    last_event=raw.get("last_event"),
                    error=raw.get("error"),
                    project_code=raw.get("project_code"),
                    project_name=raw.get("project_name"),
                    next_action=raw.get("next_action"),
                    retry_count=raw.get("retry_count", 0),
                )
                self._entries[entry.run_id] = entry
        except Exception:
            # 若讀取失敗，以空 journal 繼續，不要阻斷流程
            self._entries = {}

    def _persist(self) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "total_entries": len(self._entries),
            "entries": [
                {
                    "run_id": e.run_id,
                    "task_name": e.task_name,
                    "status": e.status,
                    "created_at": e.created_at.isoformat().replace("+00:00", "Z"),
                    "updated_at": e.updated_at.isoformat().replace("+00:00", "Z"),
                    "last_event": e.last_event,
                    "error": e.error,
                    "project_code": e.project_code,
                    "project_name": e.project_name,
                    "next_action": e.next_action,
                    "retry_count": e.retry_count,
                }
                for e in self._entries.values()
            ],
        }
        self.storage_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def append(
        self,
        run_id: str,
        task_name: str,
        project_code: Optional[str] = None,
        project_name: Optional[str] = None,
        status: str = "queued",
        last_event: Optional[str] = None,
        error: Optional[str] = None,
        next_action: Optional[str] = None,
        retry_count: int = 0,
    ) -> RunJournalEntry:
        """建立或更新一筆 run record。"""
        now = datetime.utcnow()
        if run_id in self._entries:
            entry = self._entries[run_id]
            entry = RunJournalEntry(
                run_id=entry.run_id,
                task_name=entry.task_name,
                status=status or entry.status,
                created_at=entry.created_at,
                updated_at=now,
                last_event=last_event if last_event is not None else entry.last_event,
                error=error if error is not None else entry.error,
                project_code=project_code if project_code is not None else entry.project_code,
                project_name=project_name if project_name is not None else entry.project_name,
                next_action=next_action if next_action is not None else entry.next_action,
                retry_count=retry_count,
            )
        else:
            entry = RunJournalEntry(
                run_id=run_id,
                task_name=task_name,
                status=status,
                created_at=now,
                updated_at=now,
                last_event=last_event,
                error=error,
                project_code=project_code,
                project_name=project_name,
                next_action=next_action,
                retry_count=retry_count,
            )
        self._entries[run_id] = entry
        self._persist()
        return entry

    def update(self, run_id: str, **updates: Any) -> Optional[RunJournalEntry]:
        """依 run_id 更新欄位，自動維護 updated_at。"""
        if run_id not in self._entries:
            return None
        entry = self._entries[run_id]
        now = datetime.utcnow()
        new_entry = RunJournalEntry(
            run_id=entry.run_id,
            task_name=updates.get("task_name", entry.task_name),
            status=updates.get("status", entry.status),
            created_at=entry.created_at,
            updated_at=updates.get("updated_at", now),
            last_event=updates.get("last_event", entry.last_event),
            error=updates.get("error", entry.error),
            project_code=updates.get("project_code", entry.project_code),
            project_name=updates.get("project_name", entry.project_name),
            next_action=updates.get("next_action", entry.next_action),
            retry_count=updates.get("retry_count", entry.retry_count),
        )
        self._entries[run_id] = new_entry
        self._persist()
        return new_entry

    def list(
        self,
        *,
        project_code: Optional[str] = None,
        status: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[RunJournalEntry]:
        """列出 run entries，支援依 project_code / status 過濾。"""
        results = list(self._entries.values())
        if project_code is not None:
            results = [r for r in results if r.project_code == project_code]
        if status is not None:
            results = [r for r in results if r.status == status]
        if limit is not None:
            results = results[-limit:]
        return results

    def get(self, run_id: str) -> Optional[RunJournalEntry]:
        """取單一 run record。"""
        return self._entries.get(run_id)
