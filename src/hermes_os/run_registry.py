"""SQLite-backed run registry for durable run_id persistence."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


class RunRegistry:
    """Durable run registry backed by SQLite."""

    def __init__(self, storage_path: Optional[Path] = None) -> None:
        base = storage_path or (Path(__file__).resolve().parents[1] / "var" / "runs.db")
        self.storage_path = base
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.storage_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._initialize()

    def _initialize(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
              run_id TEXT PRIMARY KEY,
              status TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              task_name TEXT,
              input_json TEXT,
              output_json TEXT,
              error_json TEXT,
              artifacts_json TEXT,
              terminal INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        self._conn.commit()

    def upsert(
        self,
        run_id: str,
        status: str,
        created_at: Optional[datetime] = None,
        task_name: Optional[str] = None,
        input_json: Optional[Dict[str, Any]] = None,
        output_json: Optional[Dict[str, Any]] = None,
        error_json: Optional[Dict[str, Any]] = None,
        artifacts_json: Optional[Dict[str, Any]] = None,
        terminal: bool = False,
    ) -> Dict[str, Any]:
        """Create or update a run record with terminal-state protection."""
        now = created_at or datetime.utcnow()
        now_iso = now.isoformat()
        existing = self._conn.execute(
            "SELECT status, terminal FROM runs WHERE run_id = ?", (run_id,)
        ).fetchone()

        if existing and existing["terminal"]:
            return dict(
                run_id=run_id,
                status=existing["status"],
                created_at=existing["created_at"],
                updated_at=existing["updated_at"],
                task_name=existing["task_name"],
                input_json=existing["input_json"],
                output_json=existing["output_json"],
                error_json=existing["error_json"],
                artifacts_json=existing["artifacts_json"],
                terminal=existing["terminal"],
            )

        if existing:
            self._conn.execute(
                """
                UPDATE runs
                SET status = ?, updated_at = ?, task_name = coalesce(?, task_name),
                    input_json = coalesce(?, input_json),
                    output_json = coalesce(?, output_json),
                    error_json = coalesce(?, error_json),
                    artifacts_json = coalesce(?, artifacts_json),
                    terminal = ?
                WHERE run_id = ?
                """,
                (
                    status,
                    now_iso,
                    task_name,
                    self._dump_json(input_json),
                    self._dump_json(output_json),
                    self._dump_json(error_json),
                    self._dump_json(artifacts_json),
                    1 if terminal else 0,
                    run_id,
                ),
            )
        else:
            self._conn.execute(
                """
                INSERT INTO runs
                  (run_id, status, created_at, updated_at, task_name, input_json,
                   output_json, error_json, artifacts_json, terminal)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    status,
                    now_iso,
                    now_iso,
                    task_name,
                    self._dump_json(input_json),
                    self._dump_json(output_json),
                    self._dump_json(error_json),
                    self._dump_json(artifacts_json),
                    1 if terminal else 0,
                ),
            )
        self._conn.commit()
        return self.get(run_id)

    def get(self, run_id: str) -> Dict[str, Any]:
        row = self._conn.execute(
            "SELECT * FROM runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        if row is None:
            return {}
        return self._row_to_dict(row)

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        data = dict(row)
        return {
            "run_id": data["run_id"],
            "status": data["status"],
            "created_at": data["created_at"],
            "updated_at": data["updated_at"],
            "task_name": data["task_name"],
            "input_json": self._load_json(data["input_json"]),
            "output_json": self._load_json(data["output_json"]),
            "error_json": self._load_json(data["error_json"]),
            "artifacts_json": self._load_json(data["artifacts_json"]),
            "terminal": bool(data["terminal"]),
        }

    @staticmethod
    def _dump_json(value: Optional[Dict[str, Any]]) -> Optional[str]:
        if value is None:
            return None
        import json

        return json.dumps(value, ensure_ascii=False, sort_keys=True)

    @staticmethod
    def _load_json(value: Optional[str]) -> Optional[Dict[str, Any]]:
        if not value:
            return None
        import json

        try:
            return json.loads(value)
        except Exception:
            return None
