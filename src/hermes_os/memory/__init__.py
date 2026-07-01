"""Memory Layer — SQLite-backed Local Knowledge store."""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class KnowledgeCategory(str, Enum):
    """Knowledge object categories."""

    NOTE = "note"
    DECISION = "decision"
    LESSON = "lesson"
    TEMPLATE = "template"
    CONTEXT = "context"


@dataclass(frozen=True)
class KnowledgeObject:
    """Markdown-friendly knowledge object."""

    object_id: str
    category: KnowledgeCategory
    title: str
    content: str
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_markdown(self) -> str:
        tags = ", ".join(self.tags) or "无"
        meta = ", ".join(f"{k}={v}" for k, v in self.metadata.items()) or "无"
        return "\n".join(
            [
                f"# {self.title}",
                "",
                f"- id: {self.object_id}",
                f"- category: {self.category.value}",
                f"- tags: {tags}",
                f"- created_at: {self.created_at.isoformat()}",
                f"- updated_at: {self.updated_at.isoformat()}",
                f"- metadata: {meta}",
                "",
                "## Content",
                "",
                self.content,
                "",
            ]
        )


class MemoryStore:
    """Minimal SQLite-backed Local Knowledge store."""

    def __init__(self, base_path: Optional[Path] = None) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        self.knowledge_dir = base_path or (repo_root / "docs" / "local-knowledge")
        self.knowledge_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.knowledge_dir / "knowledge.sqlite"
        self._init_schema()

    def _init_schema(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge_objects (
                    object_id TEXT PRIMARY KEY,
                    category TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tags TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}'
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge_index (
                    object_id TEXT PRIMARY KEY,
                    title TEXT,
                    tags TEXT,
                    category TEXT,
                    updated_at TEXT
                )
                """
            )
            conn.commit()

    def add(self, obj: KnowledgeObject) -> KnowledgeObject:
        now = datetime.utcnow().isoformat()
        tags_json = ",".join(obj.tags)
        metadata_json = repr(obj.metadata)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO knowledge_objects
                (object_id, category, title, content, tags, created_at, updated_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    obj.object_id,
                    obj.category.value,
                    obj.title,
                    obj.content,
                    tags_json,
                    obj.created_at.isoformat(),
                    now,
                    metadata_json,
                ),
            )
            conn.execute(
                """
                INSERT OR REPLACE INTO knowledge_index
                (object_id, title, tags, category, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    obj.object_id,
                    obj.title,
                    tags_json,
                    obj.category.value,
                    now,
                ),
            )
            conn.commit()
        self._write_markdown(obj)
        return obj

    def _write_markdown(self, obj: KnowledgeObject) -> None:
        md_path = self.knowledge_dir / f"{obj.object_id}.md"
        md_path.write_text(obj.to_markdown(), encoding="utf-8")

    def get(self, object_id: str) -> Optional[KnowledgeObject]:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT object_id, category, title, content, tags, created_at, updated_at, metadata FROM knowledge_objects WHERE object_id = ?",
                (object_id,),
            ).fetchone()
        if row is None:
            return None
        return KnowledgeObject(
            object_id=row[0],
            category=KnowledgeCategory(row[1]),
            title=row[2],
            content=row[3],
            tags=row[4].split(",") if row[4] else [],
            created_at=datetime.fromisoformat(row[5]),
            updated_at=datetime.fromisoformat(row[6]),
            metadata=eval(row[7]),  # noqa: S307 - stored as repr()
        )

    def search(self, query: str, category: Optional[KnowledgeCategory] = None) -> List[KnowledgeObject]:
        q = query.lower()
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT object_id, category, title, content, tags, created_at, updated_at, metadata
                FROM knowledge_objects
                WHERE lower(title) LIKE ? OR lower(content) LIKE ? OR lower(tags) LIKE ?
                """,
                (f"%{q}%", f"%{q}%", f"%{q}%"),
            ).fetchall()
        results = []
        for row in rows:
            if category is not None and row[1] != category.value:
                continue
            results.append(
                KnowledgeObject(
                    object_id=row[0],
                    category=KnowledgeCategory(row[1]),
                    title=row[2],
                    content=row[3],
                    tags=row[4].split(",") if row[4] else [],
                    created_at=datetime.fromisoformat(row[5]),
                    updated_at=datetime.fromisoformat(row[6]),
                    metadata=eval(row[7]),  # noqa: S307
                )
            )
        return results

    def list_all(self, category: Optional[KnowledgeCategory] = None, limit: int = 50) -> List[KnowledgeObject]:
        with sqlite3.connect(self.db_path) as conn:
            if category is not None:
                rows = conn.execute(
                    "SELECT object_id, category, title, content, tags, created_at, updated_at, metadata FROM knowledge_objects WHERE category = ? ORDER BY updated_at DESC LIMIT ?",
                    (category.value, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT object_id, category, title, content, tags, created_at, updated_at, metadata FROM knowledge_objects ORDER BY updated_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        results = []
        for row in rows:
            results.append(
                KnowledgeObject(
                    object_id=row[0],
                    category=KnowledgeCategory(row[1]),
                    title=row[2],
                    content=row[3],
                    tags=row[4].split(",") if row[4] else [],
                    created_at=datetime.fromisoformat(row[5]),
                    updated_at=datetime.fromisoformat(row[6]),
                    metadata=eval(row[7]),  # noqa: S307
                )
            )
        return results

    def delete(self, object_id: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("DELETE FROM knowledge_objects WHERE object_id = ?", (object_id,))
            conn.execute("DELETE FROM knowledge_index WHERE object_id = ?", (object_id,))
            conn.commit()
            changed = cur.rowcount > 0
        if changed:
            md_path = self.knowledge_dir / f"{object_id}.md"
            if md_path.exists():
                md_path.unlink()
        return changed
