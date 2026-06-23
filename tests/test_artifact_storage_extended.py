"""Artifact registry extended checksum tests."""

from __future__ import annotations

import hashlib

from hermes_os.artifact_registry import ArtifactRegistry


def test_verify_detects_tampered_content(tmp_path: str) -> None:
    registry = ArtifactRegistry(artifacts_root=str(tmp_path))
    registry.register("run_1", "report.pdf", b"%PDF-1.4", content_type="application/pdf")
    artifact_id = "run_1::report.pdf"
    assert registry.verify(artifact_id) is True
    tampered = bytearray(b"%PDF-1.4")
    tampered[0] = 0x00
    target = registry.root / "runs" / "run_1" / "report.pdf"
    target.write_bytes(bytes(tampered))
    assert registry.verify(artifact_id) is False


def test_verify_returns_false_when_file_missing(tmp_path: str) -> None:
    registry = ArtifactRegistry(artifacts_root=str(tmp_path))
    registry.register("run_1", "report.pdf", b"%PDF-1.4")
    target = registry.root / "runs" / "run_1" / "report.pdf"
    target.unlink()
    assert registry.verify("run_1::report.pdf") is False


def test_verify_returns_false_for_unknown_artifact(tmp_path: str) -> None:
    registry = ArtifactRegistry(artifacts_root=str(tmp_path))
    assert registry.verify("run_1::missing.pdf") is False
