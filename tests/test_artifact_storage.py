"""Storage bridge tests for artifact_registry."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from hermes_os.artifact_registry import ArtifactRegistry


@pytest.fixture()
def tmp_root(tmp_path: Path) -> str:
    return str(tmp_path / "artifacts")


def test_register_persists_under_run_dir(tmp_root: str) -> None:
    registry = ArtifactRegistry(artifacts_root=tmp_root)
    registry.register("run_a", "report.pdf", b"%PDF-1.4", content_type="application/pdf")
    run_dir = Path(tmp_root) / "run_a"
    assert run_dir.exists()
    assert (run_dir / "report.pdf").exists()


def test_register_roundtrip_via_get(tmp_root: str) -> None:
    registry = ArtifactRegistry(artifacts_root=tmp_root)
    stored = registry.register("run_a", "summary.txt", b"hello")
    fetched = registry.get("run_a::summary.txt")
    assert fetched is not None
    assert fetched.run_id == "run_a"
    assert fetched.filename == "summary.txt"
    assert fetched.size_bytes == 5
    assert fetched.metadata["path"] == str(stored.metadata["path"])


def test_list_for_run(tmp_root: str) -> None:
    registry = ArtifactRegistry(artifacts_root=tmp_root)
    registry.register("run_a", "a.txt", b"1")
    registry.register("run_a", "b.txt", b"22")
    registry.register("run_b", "c.txt", b"333")
    entries = {e.filename: e for e in registry.list_for_run("run_a")}
    assert set(entries.keys()) == {"a.txt", "b.txt"}
    assert entries["a.txt"].size_bytes == 1


def test_delete_removes_artifact(tmp_root: str) -> None:
    registry = ArtifactRegistry(artifacts_root=tmp_root)
    registry.register("run_a", "temp.txt", b"x")
    assert registry.delete("run_a::temp.txt") is True
    assert registry.get("run_a::temp.txt") is None
    assert (Path(tmp_root) / "run_a" / "temp.txt").exists() is False


def test_register_is_idempotent_by_overwrite(tmp_root: str) -> None:
    registry = ArtifactRegistry(artifacts_root=tmp_root)
    registry.register("run_a", "out.txt", b"v1")
    registry.register("run_a", "out.txt", b"v2")
    fetched = registry.get("run_a::out.txt")
    assert fetched is not None
    # Content should reflect the latest write without raising.
    assert Path(fetched.metadata["path"]).read_bytes() == b"v2"
