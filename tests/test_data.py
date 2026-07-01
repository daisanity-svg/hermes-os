"""Tests for hermes_os.data module."""

from __future__ import annotations

import pytest

from hermes_os.data import PROJECT_CODE, PROJECT_NAME, CODE_ALIASES, resolve_project_code, align_project_code


class TestProjectCodeAlignment:
    def test_canonical_project_code(self) -> None:
        assert PROJECT_CODE == "hermes-os"

    def test_canonical_project_name(self) -> None:
        assert PROJECT_NAME == "Hermes OS"

    def test_resolve_none_returns_default(self) -> None:
        assert resolve_project_code(None) == PROJECT_CODE

    def test_resolve_empty_returns_default(self) -> None:
        assert resolve_project_code("") == PROJECT_CODE

    def test_resolve_canonical_passthrough(self) -> None:
        assert resolve_project_code("hermes-os") == PROJECT_CODE

    def test_resolve_underscore_alias(self) -> None:
        assert resolve_project_code("hermes_os") == PROJECT_CODE

    def test_resolve_uppercase_alias(self) -> None:
        assert resolve_project_code("HERMES-OS") == PROJECT_CODE

    def test_resolve_unknown_returns_raw(self) -> None:
        assert resolve_project_code("other-project") == "other-project"

    @pytest.mark.parametrize(
        "raw,expected",
        [
            (None, PROJECT_CODE),
            ("", PROJECT_CODE),
            ("hermes-os", PROJECT_CODE),
            ("HERMES-OS", PROJECT_CODE),
            ("hermes_os", PROJECT_CODE),
            ("  hermes-os  ", PROJECT_CODE),
            ("unknown", "unknown"),
        ],
    )
    def test_resolve_project_code_parametrized(self, raw, expected) -> None:
        assert resolve_project_code(raw) == expected

    def test_align_project_code_sets_default(self) -> None:
        record = {"task_name": "demo"}
        out = align_project_code(record)
        assert out["project_code"] == PROJECT_CODE
        assert out["project_name"] == PROJECT_NAME
        assert out["task_name"] == "demo"

    def test_align_project_code_presets_explicit_name(self) -> None:
        record = {"project_code": "hermes-os", "project_name": "Custom Name"}
        out = align_project_code(record)
        assert out["project_code"] == PROJECT_CODE
        assert out["project_name"] == "Custom Name"

    def test_align_project_code_does_not_mutate_input(self) -> None:
        record: dict = {"project_code": None}
        align_project_code(record)
        assert "project_code" not in record or record["project_code"] is None
