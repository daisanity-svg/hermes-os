#!/usr/bin/env python3
"""CoS Operating Runtime CLI — python -m hermes_os.cos_runtime."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from hermes_os.cos_runtime import CosRuntime


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m hermes_os.cos_runtime",
        description="ADO OS CoS Operating Runtime v1",
    )
    sub = parser.add_subparsers(dest="command")

    run_once_p = sub.add_parser("run-once", help="執行一個 cycle（最多 max_tasks_per_cycle 個任務）")
    run_once_p.add_argument("--next-tasks", type=Path, default=None, help="next_tasks.yaml 路徑")
    run_once_p.add_argument("--project-code", type=str, default=None)
    run_once_p.add_argument("--project-name", type=str, default=None)
    run_once_p.add_argument("--max-tasks", type=int, default=2)

    status_p = sub.add_parser("status", help="顯示 CoS Runtime 狀態")
    status_p.add_argument("--next-tasks", type=Path, default=None)

    progress_p = sub.add_parser("progress", help="Chairman Progress Report")
    progress_p.add_argument("--next-tasks", type=Path, default=None)

    list_p = sub.add_parser("next-tasks", help="列出 backlog 候選任務")
    list_p.add_argument("--next-tasks", type=Path, default=None)

    daemon_p = sub.add_parser("daemon", help="持續循環調度")
    daemon_p.add_argument("--interval", type=int, default=60, help="cycle 間隔秒數")
    daemon_p.add_argument("--max-tasks", type=int, default=2, help="每 cycle 上限")
    daemon_p.add_argument("--max-tasks-per-session", type=int, default=10, help="整場 session 總任務上限")
    daemon_p.add_argument("--stop-on-failure", action="store_true", default=True, help="遇到失敗即停止")
    daemon_p.add_argument("--no-stop-on-failure", action="store_false", dest="stop_on_failure", help="遇失敗不停止")
    daemon_p.add_argument("--stop-on-founder-decision", action="store_true", default=True, help="遇到 Founder 決策即停止")
    daemon_p.add_argument("--no-stop-on-founder-decision", action="store_false", dest="stop_on_founder_decision", help="遇 Founder 決策不停止")
    daemon_p.add_argument("--next-tasks", type=Path, default=None)
    daemon_p.add_argument("--project-code", type=str, default=None)
    daemon_p.add_argument("--project-name", type=str, default=None)

    return parser


def _resolve_next_tasks(args: argparse.Namespace) -> Optional[Path]:
    if getattr(args, "next_tasks", None):
        return args.next_tasks
    return None


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0

    next_tasks_path = _resolve_next_tasks(args)

    if args.command == "next-tasks":
        rt = CosRuntime(next_tasks_path=next_tasks_path)
        tasks = rt.list_next_tasks()
        print(json.dumps(tasks, ensure_ascii=False, indent=2))
        return 0

    rt = CosRuntime(
        next_tasks_path=next_tasks_path,
        max_tasks_per_cycle=getattr(args, "max_tasks", 2),
        max_tasks_per_session=getattr(args, "max_tasks_per_session", 10),
        stop_on_failure=getattr(args, "stop_on_failure", True),
        stop_on_founder_decision=getattr(args, "stop_on_founder_decision", True),
        project_code=getattr(args, "project_code", None),
        project_name=getattr(args, "project_name", None),
    )

    if args.command == "run-once":
        result = rt.run_once()
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return 0

    if args.command == "daemon":
        result = rt.daemon_run(
            interval=getattr(args, "interval", 60),
        )
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return 0

    if args.command == "status":
        result = rt.status()
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return 0

    if args.command == "progress":
        result = rt.progress()
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
