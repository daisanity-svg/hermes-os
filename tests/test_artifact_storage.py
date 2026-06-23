"""Artifact storage bridge tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from hermes_os.artifact_registry import ArtifactRegistry


def test_register_persists_under_run_dir(tmp_path: Path) -> None:
    registry = ArtifactRegistry(artifacts_root=str(tmp_path))
    registry.register("run_a", "report.pdf", b"%PDF-1.4", content_type="application/pdf")
    run_dir = tmp_path / "runs" / "run_a"
    assert run_dir.exists()
    assert (run_dir / "report.pdf").exists()


def test_register_roundtrip_via_get(tmp_path: Path) -> None:
    registry = ArtifactRegistry(artifacts_root=str(tmp_path))
    stored = registry.register("run_a", "summary.txt", b"hello")
    fetched = registry.get("run_a::summary.txt")
    assert fetched is not None
    assert fetched.run_id == "run_a"
    assert fetched.filename == "summary.txt"
    assert fetched.size_bytes == 5
    assert Path(fetched.absolute_path).read_bytes() == b"hello"


def test_delete_removes_artifact(tmp_path: Path) -> None:
    registry = ArtifactRegistry(artifacts_root=str(tmp_path))
    registry.register("run_a", "temp.txt", b"x")
    assert registry.delete("run_a::temp.txt") is True
    assert registry.get("run_a::temp.txt") is None


def test_register_is_idempotent_by_overwrite(tmp_path: Path) -> None:
    registry = ArtifactRegistry(artifacts_root=str(tmp_path))
    registry.register("run_a", "out.txt", b"v1")
    registry.register("run_a", "out.txt", b"v2")
    fetched = registry.get("run_a::out.txt")
    assert fetched is not None
    assert Path(fetched.absolute_path).read_bytes() == b"v2"
