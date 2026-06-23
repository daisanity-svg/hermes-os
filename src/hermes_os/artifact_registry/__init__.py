"""Artifact Registry — disk-backed artifact storage bridge for Hermes OS.

Contracts are defined in ``hermes_os.types.ArtifactRef``.
"""

from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import List, Optional

from hermes_os.types import ArtifactRef


class ArtifactRegistry:
    """MVP storage bridge: artifacts are persisted under ``~/.hermes/artifacts/{run_id}/``.

    Design choices:
    - Canonical filename = filesystem filename under the run_dir.
    - File identity is ``{run_id}::{filename}`` — mirrors the API Server's
      delivery-system ``file_id`` convention so the runtime contract stays
      consistent across cores.
    - Empty / duplicate-safe writes are idempotent by design.
    """

    def __init__(self, artifacts_root: Optional[str] = None) -> None:
        self.artifacts_root = Path(
            artifacts_root or "~/artifacts"
        ).expanduser()

    def _run_dir(self, run_id: str) -> Path:
        return self.artifacts_root / run_id

    def _next_artifact_id(self, run_id: str, filename: str) -> str:
        raw = f"{run_id}::{filename}:{time.time_ns()}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]

    def register(
        self,
        run_id: str,
        filename: str,
        content_bytes: bytes,
        content_type: str = "application/octet-stream",
    ) -> ArtifactRef:
        safe_name = Path(filename).name
        if not safe_name:
            raise ValueError("filename must not be empty")

        run_dir = self._run_dir(run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        target = run_dir / safe_name
        target.write_bytes(content_bytes)

        artifact_id = f"{run_id}::{safe_name}"
        artifact = ArtifactRef(
            artifact_id=artifact_id,
            run_id=run_id,
            filename=safe_name,
            content_type=content_type,
            size_bytes=len(content_bytes),
            metadata={
                "path": str(target),
                "sha1": hashlib.sha1(content_bytes).hexdigest(),
            },
        )
        return artifact

    def get(self, artifact_id: str) -> Optional[ArtifactRef]:
        try:
            run_id, filename = artifact_id.split("::", 1)
        except ValueError:
            return None
        target = self._run_dir(run_id) / filename
        if not target.exists() or not target.is_file():
            return None
        content = target.read_bytes()
        return ArtifactRef(
            artifact_id=artifact_id,
            run_id=run_id,
            filename=filename,
            content_type="application/octet-stream",
            size_bytes=len(content),
            metadata={"path": str(target)},
        )

    def list_for_run(self, run_id: str) -> List[ArtifactRef]:
        run_dir = self._run_dir(run_id)
        if not run_dir.exists():
            return []
        entries: List[ArtifactRef] = []
        for path in sorted(run_dir.iterdir()):
            if path.is_file():
                content = path.read_bytes()
                entries.append(
                    ArtifactRef(
                        artifact_id=f"{run_id}::{path.name}",
                        run_id=run_id,
                        filename=path.name,
                        size_bytes=len(content),
                        metadata={"path": str(path)},
                    )
                )
        return entries

    def delete(self, artifact_id: str) -> bool:
        try:
            run_id, filename = artifact_id.split("::", 1)
        except ValueError:
            return False
        target = self._run_dir(run_id) / filename
        if target.exists():
            target.unlink()
            return True
        return False
