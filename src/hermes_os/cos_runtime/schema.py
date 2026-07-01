"""CoS Runtime Status Schema v1.

統一三路（GPT / Hermes Assistant / CLI）的共同輸出格式。
"""
from __future__ import annotations

from typing import Any, Dict, Optional

SCHEMA_VERSION = "cos-runtime/status/v1"


def empty_status(project_code: Optional[str] = None) -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": "",
        "project": {
            "code": project_code or "",
            "name": "",
        },
        "cos_state": "idle",
        "operational_status": "idle",
        "idle_reason": None,
        "session": {
            "total_executed": 0,
            "max_tasks_per_session": 10,
            "stop_reason": "none",
            "reports": [],
            "founder_tickets": [],
        },
        "current_cycle": {
            "in_progress": {},
            "next_up": {},
        },
        "progress": {
            "completed": [],
            "founder_tickets": [],
        },
        "heartbeat": {
            "pid": None,
            "uptime_seconds": None,
            "last_tick": "",
        },
        "sources": {
            "next_tasks_path": "",
            "journal_path": "",
            "founder_inbox_path": "",
        },
    }
