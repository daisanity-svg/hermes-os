"""Shared validation layer — pydantic schemas for governance records."""

from __future__ import annotations


class TagMixin:
    tag: str | None = None
