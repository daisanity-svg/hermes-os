#!/usr/bin/env python3
"""Minimal Hermes OS runtime with a small command surface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from hermes_os.action_records import ActionRecords
from hermes_os.artifact_registry import ArtifactRegistry
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
        "actions": ActionRecords(),
        "artifacts": ArtifactRegistry(),
    }


def cmd_status(_args: argparse.Namespace, rt: dict) -> int:
    snap = rt["snapshot"].latest()
    if snap is None:
        print("No snapshot yet")
    else:
        print(snap)
    return 0


def cmd_actions(args: argparse.Namespace, rt: dict) -> int:
    store: ActionRecords = rt["actions"]
    sub = getattr(args, "sub", None)

    if sub == "history":
        limit_arg = getattr(args, "limit", None)
        for record in store.history(limit=limit_arg or 10):
            print(record)
        return 0

    if sub == "record":
        record = store.create(args.id, args.action_type, run_id=getattr(args, "run_id", None))
        print(f"recorded {record.action_id}")
        return 0

    if sub == "start":
        record = store.start(args.id)
        if record is None:
            print(f"unknown action: {args.id}")
            return 1
        print(f"started {record.action_id}")
        return 0

    if sub == "complete":
        payload = None
        if getattr(args, "output", None):
            payload = json.loads(args.output)
        record = store.complete(args.id, output_snapshot=payload)
        if record is None:
            print(f"unknown action: {args.id}")
            return 1
        print(f"completed {record.action_id}")
        return 0

    if sub == "fail":
        record = store.fail(args.id, error=getattr(args, "error", None))
        if record is None:
            print(f"unknown action: {args.id}")
            return 1
        print(f"failed {record.action_id}")
        return 0

    print("actions subcommands: record/start/complete/fail/history")
    return 0


def cmd_artifacts(args: argparse.Namespace, rt: dict) -> int:
    registry: ArtifactRegistry = rt["artifacts"]
    sub = getattr(args, "sub", None)

    if sub == "register":
        path = args.path
        content = Path(path).read_bytes()
        stored = registry.register(args.run_id, Path(path).name, content, content_type=args.content_type)
        print(stored)
        return 0

    if sub == "get":
        stored = registry.get(args.id)
        if stored is None:
            print(f"unknown artifact: {args.id}")
            return 1
        print(stored)
        return 0

    if sub == "verify":
        valid = registry.verify(args.id)
        print(f"verify {args.id} -> {valid}")
        return 0 if valid else 1

    if sub == "list":
        items = registry.list_for_run(args.run_id)
        for item in items:
            print(item)
        return 0

    if sub == "delete":
        ok = registry.delete(args.id)
        print(f"delete {args.id} -> {ok}")
        return 0 if ok else 1

    print("artifacts subcommands: register/get/verify/list/delete")
    return 0


def cmd_queue(args: argparse.Namespace, rt: dict) -> int:
    sub = getattr(args, "sub", None)
    if sub == "submit":
        rt["adapter"].submit({"id": args.id, "type": "task", "priority": args.priority or 0})
        print(f"submitted {args.id}")
    elif sub == "drain":
        drained = rt["adapter"].drain(args.limit or 1)
        print(f"drained={len(drained)}")
        for item in drained:
            print(item)
    elif sub == "peek":
        item = rt["queue"].peek()
        print(item)
    elif sub == "cancel":
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


def cmd_runs(_args: argparse.Namespace, _rt: dict) -> int:
    print("runs:")
    return 0


def build_parser(spec: "CLISpec") -> argparse.ArgumentParser:  # type: ignore[name-defined]
    parser = argparse.ArgumentParser(prog=spec.binary_name)
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("status", help="Show system snapshot")
    subparsers.add_parser("runs", help="List known runs")

    actions_p = subparsers.add_parser("actions", help="Manage action records")
    acts_sub = actions_p.add_subparsers(dest="sub")
    acts_sub.add_parser("history", help="List recent actions")
    record_p = acts_sub.add_parser("record", help="Record a new action")
    record_p.add_argument("id")
    record_p.add_argument("action_type")
    record_p.add_argument("--run-id")
    for name in ("start", "complete", "fail"):
        sub = acts_sub.add_parser(name, help=f"{name.capitalize()} an action")
        sub.add_argument("id")
        sub.add_argument("--output")
        sub.add_argument("--error")

    artifacts_p = subparsers.add_parser("artifacts", help="Manage artifacts")
    art_sub = artifacts_p.add_subparsers(dest="sub")
    art_sub.add_parser("list", help="List artifacts for a run")
    art_get = art_sub.add_parser("get", help="Get artifact by id")
    art_get.add_argument("id")
    art_register = art_sub.add_parser("register", help="Register a local file")
    art_register.add_argument("run_id")
    art_register.add_argument("path")
    art_register.add_argument("--content-type", default="application/octet-stream")
    art_verify = art_sub.add_parser("verify", help="Verify checksum")
    art_verify.add_argument("id")
    art_del = art_sub.add_parser("delete", help="Delete artifact")
    art_del.add_argument("id")

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
        "artifacts": cmd_artifacts,
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
