#!/usr/bin/env python3
"""Minimal Hermes OS runtime with a small command surface."""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from hermes_os.control_center_snapshot import ControlCenterSnapshotStore
from hermes_os.minimal_cli_spec import DEFAULT_CLI_SPEC
from hermes_os.operational_memory_log import OperationalMemoryLog
from hermes_os.process_adapter import ProcessAdapter
from hermes_os.workforce_queue import WorkforceQueue


def _build_runtime() -> dict:
    return {
        "adapter": ProcessAdapter(),
        "queue": WorkforceQueue(),
        "memory": OperationalMemoryLog(),
        "snapshot": ControlCenterSnapshotStore(),
    }


def cmd_status(_args: argparse.Namespace, rt: dict) -> int:
    snap = rt["snapshot"].latest()
    if snap is None:
        print("No snapshot yet")
    else:
        print(snap)
    return 0


def cmd_runs(_args: argparse.Namespace, _rt: dict) -> int:
    print("runs:")
    return 0


def cmd_actions(_args: argparse.Namespace, _rt: dict) -> int:
    print("actions:")
    return 0


def cmd_queue(args: argparse.Namespace, rt: dict) -> int:
    if args.sub == "submit":
        rt["adapter"].submit({"id": args.id, "type": "task", "priority": args.priority or 0})
        print(f"submitted {args.id}")
    elif args.sub == "drain":
        drained = rt["adapter"].drain(args.limit or 1)
        print(f"drained={len(drained)}")
        for item in drained:
            print(item)
    elif args.sub == "peek":
        item = rt["queue"].peek()
        print(item)
    elif args.sub == "cancel":
        item = rt["queue"].cancel(args.id)
        if item is None:
            print(f"unknown queue id: {args.id}")
            return 1
        print(f"cancelled {args.id}")
    else:
        print("queue subcommands: submit|drain|peek|cancel")
        return 0
    return 0


def cmd_memory(args: argparse.Namespace, rt: dict) -> int:
    results = rt["memory"].query(
        source=args.source,
        category=args.category,
        since=args.since,
        until=args.until,
        contains=args.contains,
    )
    for entry in results:
        print(entry)
    return 0


def build_parser(spec: "CLISpec") -> argparse.ArgumentParser:  # type: ignore[name-defined]
    parser = argparse.ArgumentParser(prog=spec.binary_name)
    subparsers = parser.add_subparsers(dest="command")

    status_p = subparsers.add_parser("status", help="Show system snapshot")
    runs_p = subparsers.add_parser("runs", help="List known runs")
    actions_p = subparsers.add_parser("actions", help="List recent action records")

    q_p = subparsers.add_parser("queue", help="Workforce queue")
    q_sub = q_p.add_subparsers(dest="sub")
    q_sub.add_parser("peek", help="Show next item")
    submit_p = q_sub.add_parser("submit", help="Submit item by id")
    submit_p.add_argument("id")
    submit_p.add_argument("--priority", type=int, default=0)
    drain_p = q_sub.add_parser("drain", help="Drain queue items")
    drain_p.add_argument("--limit", type=int, default=1)
    cancel_p = q_sub.add_parser("cancel", help="Cancel queued item")
    cancel_p.add_argument("id")

    mem_p = subparsers.add_parser("memory", help="Query operational memory log")
    mem_p.add_argument("--source")
    mem_p.add_argument("--category")
    mem_p.add_argument("--since")
    mem_p.add_argument("--until")
    mem_p.add_argument("--contains")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    rt = _build_runtime()
    parser = build_parser(DEFAULT_CLI_SPEC)
    args, _unknown = parser.parse_known_args(argv)
    if args.command is None:
        return parser.print_help()

    dispatch = {
        "status": cmd_status,
        "runs": cmd_runs,
        "actions": cmd_actions,
        "queue": cmd_queue,
        "memory": cmd_memory,
    }
    handler = dispatch.get(args.command)
    if handler is None:
        print(f"unknown command: {args.command}")
        return 1
    return handler(args, rt)


if __name__ == "__main__":
    raise SystemExit(main())
