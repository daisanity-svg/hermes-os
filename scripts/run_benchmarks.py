#!/usr/bin/env python3
"""Minimal Hermes OS benchmark runner."""

from __future__ import annotations

import argparse
import time
from typing import List


def _run_queue_benchmark(iterations: int) -> dict:
    from hermes_os.workforce_queue import WorkforceQueue
    from hermes_os.types import WorkforceItem

    queue = WorkforceQueue()
    start = time.perf_counter()
    for index in range(iterations):
        queue.enqueue(WorkforceItem(item_id=f"task_{index}", item_type="task", priority=index % 5, payload={}))
    enqueue_seconds = time.perf_counter() - start

    start = time.perf_counter()
    drained = 0
    while True:
        if queue.dequeue() is None:
            break
        drained += 1
    drain_seconds = time.perf_counter() - start

    return {
        "iterations": iterations,
        "enqueue_seconds": round(enqueue_seconds, 6),
        "drain_seconds": round(drain_seconds, 6),
        "drained": drained,
    }


def _run_memory_benchmark(iterations: int) -> dict:
    from hermes_os.operational_memory_log import OperationalMemoryLog

    memory = OperationalMemoryLog()
    start = time.perf_counter()
    for index in range(iterations):
        memory.append(source="bench", category="perf", content=f"event {index}")
    append_seconds = time.perf_counter() - start

    start = time.perf_counter()
    memory.query(source="bench", category="perf")
    query_seconds = time.perf_counter() - start

    return {
        "iterations": iterations,
        "append_seconds": round(append_seconds, 6),
        "query_seconds": round(query_seconds, 6),
    }


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Hermes OS benchmark runner")
    parser.add_argument("--iterations", type=int, default=1000)
    parser.add_argument("--suite", choices=["all", "queue", "memory"], default="all")
    args = parser.parse_args(argv)

    results = []
    if args.suite in {"all", "queue"}:
        results.append(_run_queue_benchmark(args.iterations))
    if args.suite in {"all", "memory"}:
        results.append(_run_memory_benchmark(args.iterations))

    for result in results:
        print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
