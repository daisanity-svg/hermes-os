"""Append-only JSONL run journal fallback."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


class JsonlRunJournal:
    """Minimal JSONL journal used as a third persistence layer."""

    def __init__(self, storage_path: Optional[Path] = None) -> None:
        base = storage_path or (Path(__file__).resolve().parents[1] / "var" / "runs.journal.jsonl")
        self.storage_path = base
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

    def append(
        self,
        run_id: str,
        status: str = "queued",
        occurred_at: Optional[datetime] = None,
        event: str = "submitted",
        task_name: Optional[str] = None,
        output_json: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        artifacts_json: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        now = occurred_at or datetime.utcnow()
        payload = {
            "run_id": run_id,
            "status": status,
            "occurred_at": now.isoformat(),
            "event": event,
            "task_name": task_name,
            "output_json": output_json,
            "error": error,
            "artifacts_json": artifacts_json,
        }
        with self.storage_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return payload

    def list_events(self, run_id: str) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        if not self.storage_path.exists():
            return events
        with self.storage_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if payload.get("run_id") == run_id:
                    events.append(payload)
        return events

    def latest(self, run_id: str) -> Optional[Dict[str, Any]]:
        events = self.list_events(run_id)
        return events[-1] if events else None
