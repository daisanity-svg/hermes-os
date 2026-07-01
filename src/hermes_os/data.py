"""Hermes OS — centralized project metadata for project_code alignment."""

from __future__ import annotations

from typing import Dict, Optional

# Canonical project code for this Hermes OS workspace.
PROJECT_CODE: str = "hermes-os"

# Human-readable project name.
PROJECT_NAME: str = "Hermes OS"

# Alias map: alternate codes that resolve to the canonical project_code.
CODE_ALIASES: Dict[str, str] = {
    "hermes-os": PROJECT_CODE,
    "hermos-os": PROJECT_CODE,
    "hermes_os": PROJECT_CODE,
    "HERMES-OS": PROJECT_CODE,
}


def resolve_project_code(raw: Optional[str]) -> Optional[str]:
    """Normalize an input string to the canonical project_code."""
    if not raw:
        return PROJECT_CODE
    key = raw.strip().lower().replace("_", "-")
    return CODE_ALIASES.get(key, raw.strip())


def align_project_code(record: Dict[str, object]) -> Dict[str, object]:
    """Return a copy of *record* with project_code / project_name aligned."""
    aligned = dict(record)
    raw_code = aligned.get("project_code")
    aligned["project_code"] = resolve_project_code(str(raw_code) if raw_code is not None else PROJECT_CODE)
    if not aligned.get("project_name"):
        aligned["project_name"] = PROJECT_NAME
    return aligned
