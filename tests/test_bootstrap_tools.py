"""tests for ADO bootstrap tools."""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
PYTHON = REPO / ".venv" / "bin" / "python"
CONTRACTS_DIR = REPO / "docs" / "contracts"
INDEX_FILE = REPO / "docs" / "sso" / "contracts-index.yaml"
PROJECT_STATUS = REPO / "docs" / "sso" / "project-status.yaml"
LOG_FILE = REPO / "docs" / "sso" / "watchdog-log.yaml"
TODAY = f"{datetime.now(timezone.utc):%Y%m%d}"


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, check=False)


def _remove(path: Path) -> None:
    if path.exists():
        path.unlink()


def test_new_work_unit_creates_contract() -> None:
    created = None
    index_backup = None
    try:
        if INDEX_FILE.exists():
            index_backup = INDEX_FILE.read_bytes()
        result = run([
            str(PYTHON),
            "scripts/new_work_unit.py",
            "create",
            "--title",
            "bootstrap test",
            "--slug",
            "bootstrap-test",
            "--owner",
            "hermes-engineer",
        ])
        assert result.returncode == 0, result.stderr
        created = next(CONTRACTS_DIR.glob(f"{TODAY}-bootstrap-test.yaml"), None)
        assert created is not None, "契約未建立"
    finally:
        if created is not None:
            _remove(created)
        if index_backup is not None and INDEX_FILE.exists():
            INDEX_FILE.write_bytes(index_backup)


def test_contract_tooling_rejects_duplicate_slug() -> None:
    first = CONTRACTS_DIR / f"{TODAY}-dup-slug.yaml"
    index_backup = None
    try:
        if INDEX_FILE.exists():
            index_backup = INDEX_FILE.read_bytes()
        result = run([
            str(PYTHON),
            "scripts/new_work_unit.py",
            "create",
            "--title",
            "dup",
            "--slug",
            "dup-slug",
            "--owner",
            "hermes",
        ])
        assert result.returncode == 0, result.stderr
        assert first.exists()
        result = run([
            str(PYTHON),
            "scripts/new_work_unit.py",
            "create",
            "--title",
            "dup",
            "--slug",
            "dup-slug",
            "--owner",
            "hermes",
        ])
        assert result.returncode != 0
    finally:
        _remove(first)
        if index_backup is not None and INDEX_FILE.exists():
            INDEX_FILE.write_bytes(index_backup)


def test_watchdog_writes_log_when_status_ok() -> None:
    backup = None
    if LOG_FILE.exists():
        backup = LOG_FILE.read_bytes()
        _remove(LOG_FILE)
    try:
        result = run([str(PYTHON), "scripts/watchdog.py"])
        assert result.returncode == 0, result.stdout + result.stderr
        assert LOG_FILE.exists(), "watchdog-log.yaml 未建立"
        content = LOG_FILE.read_text(encoding="utf-8")
        assert "ssot.project_status" in content
        assert "ssot.contracts_index" in content
    finally:
        _remove(LOG_FILE)
        if backup is not None:
            LOG_FILE.write_bytes(backup)


def test_contracts_index_matches_actual() -> None:
    actual = len(list(CONTRACTS_DIR.glob("*.yaml")))
    text = INDEX_FILE.read_text(encoding="utf-8")
    declared = 0
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("total_contracts:"):
            try:
                declared = int(line.split(":", 1)[1].strip())
            except ValueError:
                declared = 0
            break
    assert actual == declared, f"契約數量不一致：預計 {actual}，索引宣告 {declared}"
