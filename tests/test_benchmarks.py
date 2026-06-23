"""Benchmark runner tests."""

from __future__ import annotations

from scripts.run_benchmarks import main


def test_queue_benchmark_reports_results() -> None:
    assert main(["--suite", "queue", "--iterations", "10"]) == 0


def test_memory_benchmark_reports_results() -> None:
    assert main(["--suite", "memory", "--iterations", "10"]) == 0


def test_all_benchmark_reports_results() -> None:
    assert main(["--suite", "all", "--iterations", "10"]) == 0
