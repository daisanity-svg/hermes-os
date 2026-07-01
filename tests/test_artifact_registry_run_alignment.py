"""Artifact registry run-alignment verification."""

from pathlib import Path

from hermes_os.artifact_registry import ArtifactRegistry


def _build_registry(tmp_path: Path) -> ArtifactRegistry:
    return ArtifactRegistry(str(tmp_path / "artifacts"))


def test_register_and_list_by_run(tmp_path):
    registry = _build_registry(tmp_path)
    stored = registry.register("run-1", "note.txt", b"hello", content_type="text/plain")
    stored2 = registry.register("run-2", "note.txt", b"world", content_type="text/plain")

    run1_items = registry.list_for_run("run-1")
    assert len(run1_items) == 1
    assert run1_items[0].artifact_id == stored.artifact_id

    run2_items = registry.list_for_run("run-2")
    assert len(run2_items) == 1
    assert run2_items[0].artifact_id == stored2.artifact_id


def test_missing_run_returns_empty(tmp_path):
    registry = _build_registry(tmp_path)
    assert registry.list_for_run("missing-run") == []
