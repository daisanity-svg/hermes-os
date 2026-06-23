"""Artifact retention tests."""

from __future__ import annotations

from pathlib import Path
import tempfile

from hermes_os.artifact_registry import ArtifactRegistry


def _make_registry() -> ArtifactRegistry:
    temp_dir = tempfile.mkdtemp()
    return ArtifactRegistry(artifacts_root=temp_dir)


def test_expire_old_artifacts_removes_entries() -> None:
    registry = _make_registry()
    registry.register("run-1", "old.txt", b"old")
    old = registry._artifacts[list(registry._artifacts.keys())[0]]
    old.created_at = "2000-01-01T00:00:00Z"
    registry._save_index(old)
    registry.register("run-1", "new.txt", b"new")
    released = registry.expire_older_than("2001-01-01T00:00:00Z")
    assert len(released) == 1
    assert len(registry._artifacts) == 1


def test_list_expired_empty_when_none_old_enough() -> None:
    registry = _make_registry()
    registry.register("run-1", "new.txt", b"new")
    expired = registry.list_expired(older_than="2000-01-01T00:00:00Z")
    assert expired == []
