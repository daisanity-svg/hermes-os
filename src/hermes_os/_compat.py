"""Compatibility shims for older Python runtimes."""

try:
    from enum import StrEnum  # type: ignore[assignment]
except ImportError:  # pragma: no cover - Python < 3.11 fallback
    from enum import Enum

    class StrEnum(str, Enum):  # type: ignore[no-redef]
        """Minimal StrEnum fallback for Python < 3.11."""
