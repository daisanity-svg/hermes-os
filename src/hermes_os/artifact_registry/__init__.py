"""Artifact Registry — disk-backed artifact storage bridge for Hermes OS."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class StoredArtifact:
    artifact_id: str
    run_id: str
    filename: str
    content_type: str
    size_bytes: int
    sha256: str
    created_at: str
    absolute_path: str
    metadata: dict = field(default_factory=dict)


class ArtifactRegistry:
    def __init__(self, artifacts_root: Optional[str] = None) -> None:
        self.root = Path(artifacts_root or Path.home() / ".hermes" / "artifacts")
        self.root.mkdir(parents=True, exist_ok=True)
        self._artifacts: dict[str, StoredArtifact] = {}
        self._load_index()

    def _run_dir(self, run_id: str) -> Path:
        return self.root / "runs" / run_id

    def _artifact_id(self, run_id: str, filename: str) -> str:
        return f"{run_id}::{filename}"

    def _index_path(self, run_id: str, filename: str) -> Path:
        return self._run_dir(run_id) / f".{filename}.meta"

    def register(
        self,
        run_id: str,
        filename: str,
        content: bytes,
        content_type: str = "application/octet-stream",
    ) -> StoredArtifact:
        run_dir = self._run_dir(run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        target = run_dir / filename
        target.write_bytes(content)
        artifact_id = self._artifact_id(run_id, filename)
        stored = StoredArtifact(
            artifact_id=artifact_id,
            run_id=run_id,
            filename=filename,
            content_type=content_type,
            size_bytes=target.stat().st_size,
            sha256=hashlib.sha256(content).hexdigest(),
            created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            absolute_path=str(target),
        )
        self._artifacts[artifact_id] = stored
        self._save_index(stored)
        return stored

    def get(self, artifact_id: str) -> Optional[StoredArtifact]:
        return self._artifacts.get(artifact_id)

    def list_for_run(self, run_id: str) -> list[StoredArtifact]:
        return [item for item in self._artifacts.values() if item.run_id == run_id]

    def verify(self, artifact_id: str) -> bool:
        stored = self._artifacts.get(artifact_id)
        if stored is None:
            return False
        target = Path(stored.absolute_path)
        if not target.exists():
            return False
        return hashlib.sha256(target.read_bytes()).hexdigest() == stored.sha256

    def delete(self, artifact_id: str) -> bool:
        stored = self._artifacts.pop(artifact_id, None)
        if stored is None:
            return False
        target = Path(stored.absolute_path)
        if target.exists():
            target.unlink()
        meta = self._index_path(stored.run_id, stored.filename)
        if meta.exists():
            meta.unlink()
        return True

    def _load_index(self) -> None:
        if not self.root.exists():
            return
        for meta in self.root.glob("runs/*/.*.meta"):
            run_dir = meta.parent
            run_id = run_dir.name
            for line in meta.read_text().splitlines():
                if not line.strip():
                    continue
                artifact_id, filename, content_type, size_bytes, sha256, created_at, absolute_path = line.split("\t")
                self._artifacts[artifact_id] = StoredArtifact(
                    artifact_id=artifact_id,
                    run_id=run_id,
                    filename=filename,
                    content_type=content_type,
                    size_bytes=int(size_bytes),
                    sha256=sha256,
                    created_at=created_at,
                    absolute_path=absolute_path,
                )

    def _save_index(self, stored: StoredArtifact) -> None:
        meta = self._index_path(stored.run_id, stored.filename)
        meta.parent.mkdir(parents=True, exist_ok=True)
        meta.write_text(
            "\t".join(
                [
                    stored.artifact_id,
                    stored.filename,
                    stored.content_type,
                    str(stored.size_bytes),
                    stored.sha256,
                    stored.created_at,
                    stored.absolute_path,
                ]
            )
        )
