"""Artifact signature tests."""

from __future__ import annotations

from pathlib import Path

from hermes_os.artifact_registry import ArtifactRegistry


def test_register_with_signature_stores_field() -> None:
    registry = ArtifactRegistry()
    stored = registry.register("run-1", "report.json", b"hello", signature="sig-123")
    assert stored.signature == "sig-123"
    reloaded = registry.get(stored.artifact_id)
    assert reloaded.signature == "sig-123"


def test_legacy_index_without_signature_loads_as_none() -> None:
    registry = ArtifactRegistry()
    meta = registry.root / "runs" / "legacy" / ".report.json.meta"
    meta.parent.mkdir(parents=True, exist_ok=True)
    meta.write_text("\t".join(["legacy::report.json", "report.json", "application/json", "5", "abc", "2024-01-01T00:00:00Z", "/tmp/report.json"]))
    registry._load_index()
    artifact = registry.get("legacy::report.json")
    assert artifact is not None
    assert artifact.signature is None
