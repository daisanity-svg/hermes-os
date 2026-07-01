"""Hermes OS Watchdog — SQLite storage for audit_records and task_states tables."""

from __future__ import annotations

import json as _json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional

from hermes_os.watchdog.schemas import (
    AuditRecord,
    TaskState,
    WatchdogDecision,
)


class WatchdogStorage:
    """唯儲存取層，負責 persist task_states / audit_records。"""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        base = db_path or (Path.home() / ".hermes" / "watchdog" / "state.db")
        base.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = base
        self._conn = sqlite3.connect(str(base), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self) -> None:
        cur = self._conn.cursor()
        cur.executescript(
            """
            PRAGMA journal_mode=WAL;

            CREATE TABLE IF NOT EXISTS task_states (
                task_id   TEXT PRIMARY KEY,
                project   TEXT NOT NULL,
                status    TEXT NOT NULL,
                last_activity_ts        TEXT NOT NULL,
                last_user_reply_ts      TEXT,
                consecutive_idle_checks INTEGER NOT NULL DEFAULT 0,
                error_summary           TEXT,
                blockers                TEXT NOT NULL DEFAULT '[]',
                current_action          TEXT,
                owner                   TEXT
            );

            CREATE TABLE IF NOT EXISTS audit_records (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                ts        TEXT NOT NULL,
                task_id   TEXT NOT NULL,
                trigger   TEXT NOT NULL,
                state_snapshot   TEXT NOT NULL,
                decision   TEXT,
                action_taken    TEXT,
                result    TEXT NOT NULL,
                error     TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_audit_task_id
              ON audit_records(task_id);
            CREATE INDEX IF NOT EXISTS idx_audit_trigger
              ON audit_records(trigger);
            """
        )
        self._conn.commit()

    # --- task_states CRUD ---

    def upsert_task_state(self, state: TaskState) -> None:
        cur = self._conn.cursor()
        cur.execute(
            """
            INSERT INTO task_states (
                task_id, project, status, last_activity_ts,
                last_user_reply_ts, consecutive_idle_checks,
                error_summary, blockers, current_action, owner
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(task_id) DO UPDATE SET
                project                = excluded.project,
                status                = excluded.status,
                last_activity_ts      = excluded.last_activity_ts,
                last_user_reply_ts    = excluded.last_user_reply_ts,
                consecutive_idle_checks = excluded.consecutive_idle_checks,
                error_summary         = excluded.error_summary,
                blockers              = excluded.blockers,
                current_action        = excluded.current_action,
                owner                  = excluded.owner
            """,
            (
                state.task_id,
                state.project,
                state.status,
                state.last_activity_ts.isoformat(),
                state.last_user_reply_ts.isoformat() if state.last_user_reply_ts else None,
                state.consecutive_idle_checks,
                state.error_summary,
                _json_dumps(state.blockers),
                state.current_action,
                state.owner,
            ),
        )
        self._conn.commit()

    def get_task_state(self, task_id: str) -> Optional[TaskState]:
        cur = self._conn.cursor()
        cur.execute("SELECT * FROM task_states WHERE task_id = ?", (task_id,))
        row = cur.fetchone()
        if row is None:
            return None
        return _row_to_task_state(row)

    def list_task_states(self) -> List[TaskState]:
        cur = self._conn.cursor()
        cur.execute("SELECT * FROM task_states")
        return [_row_to_task_state(r) for r in cur.fetchall()]

    # --- audit_records ---

    def add_audit(self, record: AuditRecord) -> int:
        cur = self._conn.cursor()
        cur.execute(
            """
            INSERT INTO audit_records (
                ts, task_id, trigger, state_snapshot,
                decision, action_taken, result, error
            ) VALUES (?,?,?,?,?,?,?,?)
            """,
            (
                record.ts.isoformat(),
                record.task_id,
                record.trigger,
                record.state_snapshot.model_dump_json(),
                record.decision.model_dump_json() if record.decision else None,
                record.action_taken,
                record.result,
                record.error,
            ),
        )
        self._conn.commit()
        last_id = cur.lastrowid
        return int(last_id) if last_id is not None else 0

    def list_audit_for_task(
        self, task_id: str, limit: int = 50
    ) -> List[AuditRecord]:
        cur = self._conn.cursor()
        cur.execute(
            """
            SELECT * FROM audit_records
            WHERE task_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (task_id, limit),
        )
        return [_row_to_audit(r) for r in cur.fetchall()]

    def list_recent_audit(self, limit: int = 100) -> List[AuditRecord]:
        cur = self._conn.cursor()
        cur.execute(
            """
            SELECT * FROM audit_records
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [_row_to_audit(r) for r in cur.fetchall()]


# --- helpers ---

def _json_dumps(value: Any) -> str:
    return _json.dumps(value, ensure_ascii=False, default=str)


def _row_to_task_state(row: sqlite3.Row) -> TaskState:
    return TaskState(
        task_id=row["task_id"],
        project=row["project"],
        status=row["status"],
        last_activity_ts=datetime.fromisoformat(row["last_activity_ts"]),
        last_user_reply_ts=(
            datetime.fromisoformat(row["last_user_reply_ts"])
            if row["last_user_reply_ts"]
            else None
        ),
        consecutive_idle_checks=int(row["consecutive_idle_checks"]),
        error_summary=row["error_summary"],
        blockers=_json.loads(row["blockers"] or "[]"),
        current_action=row["current_action"],
        owner=row["owner"],
    )


def _row_to_audit(row: sqlite3.Row) -> AuditRecord:
    state = TaskState.model_validate_json(row["state_snapshot"])
    decision = None
    if row["decision"]:
        decision = WatchdogDecision.model_validate_json(row["decision"])
    return AuditRecord(
        ts=datetime.fromisoformat(row["ts"]),
        task_id=row["task_id"],
        trigger=row["trigger"],
        state_snapshot=state,
        decision=decision,
        action_taken=row["action_taken"],
        result=row["result"],
        error=row["error"],
    )
