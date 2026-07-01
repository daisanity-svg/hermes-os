"""Tests for ADO-CON-003: Organizational Learner boundary schemas, rules, and brief filter."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List

import pytest

from hermes_os.org_learning.brief import build_executive_brief
from hermes_os.org_learning.rules import (
    OrgLearningRuleResult,
    check_org_memory_consistency,
    check_retrospective_delta_required,
)
from hermes_os.org_learning.schemas import (
    AppliedStatus,
    ContractRetrospective,
    OrgMemoryEntry,
    ProcessDelta,
    ProcessRule,
)


# === fixtures ===


@pytest.fixture()
def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _make_memory(memory_id: str, *, confidence: float = 1.0, category: str = "ops") -> OrgMemoryEntry:
    return OrgMemoryEntry(
        memory_id=memory_id,
        category=category,
        content=f"content-{memory_id}",
        source_contract_ids=[],
        confidence=confidence,
        created_at=datetime.now(timezone.utc),
    )


def _make_delta(delta_id: str, contract_id: str, status: AppliedStatus = AppliedStatus.APPLIED, confidence: float = 0.9) -> ProcessDelta:
    return ProcessDelta(
        delta_id=delta_id,
        source_contract_id=contract_id,
        change_description=f"change-{delta_id}",
        confidence=confidence,
        applied_status=status,
        created_at=datetime.now(timezone.utc),
    )


def _make_retro(retro_id: str, contract_id: str) -> ContractRetrospective:
    return ContractRetrospective(
        retrospective_id=retro_id,
        contract_id=contract_id,
        summary="summary",
        lessons_learned=[],
        created_at=datetime.now(timezone.utc),
        tags=[],
    )


# === schemas ===


class TestSchemas:
    def test_org_memory_defaults(self, _utcnow: datetime) -> None:
        entry = OrgMemoryEntry(
            memory_id="mem-1",
            category="ops",
            content="內容",
            created_at=_utcnow,
        )
        assert entry.confidence == 1.0
        assert entry.access_count == 0
        assert entry.source_contract_ids == []

    def test_process_rule_defaults(self, _utcnow: datetime) -> None:
        rule = ProcessRule(
            rule_id="rule-1",
            name="test",
            description="desc",
            trigger_condition="A 發生",
            action="通知",
            created_at=_utcnow,
        )
        assert rule.confidence_threshold == 0.85
        assert rule.active is True

    def test_process_delta_enum(self, _utcnow: datetime) -> None:
        delta = ProcessDelta(
            delta_id="d1",
            source_contract_id="c1",
            change_description="變更",
            confidence=0.95,
            applied_status=AppliedStatus.APPLIED,
            created_at=_utcnow,
        )
        assert delta.applied_status == "applied"

    def test_contract_retrospective_roundtrip(self, _utcnow: datetime) -> None:
        retro = _make_retro("r1", "c1")
        dumped = retro.model_dump_json()
        restored = ContractRetrospective.model_validate_json(dumped)
        assert restored.retrospective_id == "r1"


# === rules ===


class TestOrgMemoryConsistency:
    def test_pass_clean_entries(self) -> None:
        entries = [
            _make_memory("m1", confidence=0.8, category="ops"),
            _make_memory("m2", confidence=1.0, category="qa"),
        ]
        result = check_org_memory_consistency(entries)
        assert result.rule_name == "org_memory.consistency"
        assert result.passed is True

    def test_fail_confidence_out_of_range(self) -> None:
        entries = [OrgMemoryEntry(
            memory_id="m1",
            category="ops",
            content="x",
            created_at=datetime.now(timezone.utc),
            confidence=1.5,
        )]
        result = check_org_memory_consistency(entries)
        assert result.passed is False
        assert "m1" in result.detail

    def test_fail_empty_category(self) -> None:
        entries = [OrgMemoryEntry(
            memory_id="m1",
            category="   ",
            content="x",
            created_at=datetime.now(timezone.utc),
        )]
        result = check_org_memory_consistency(entries)
        assert result.passed is False

    def test_fail_negative_access_count(self) -> None:
        entries = [OrgMemoryEntry(
            memory_id="m1",
            category="ops",
            content="x",
            created_at=datetime.now(timezone.utc),
            access_count=-1,
        )]
        result = check_org_memory_consistency(entries)
        assert result.passed is False
        assert "m1" in result.detail


class TestRetrospectiveDeltaRequired:
    def test_pass_with_related_applied_deltas(self) -> None:
        retro = _make_retro("r1", "c1")
        deltas = [
            _make_delta("d1", "c1", AppliedStatus.APPLIED),
            _make_delta("d2", "c1", AppliedStatus.REJECTED),
        ]
        result = check_retrospective_delta_required(retro, deltas)
        assert result.passed is True

    def test_fail_no_related_deltas(self) -> None:
        retro = _make_retro("r1", "c1")
        deltas = [_make_delta("d1", "c99")]
        result = check_retrospective_delta_required(retro, deltas)
        assert result.passed is False
        assert "c1" in result.detail

    def test_fail_related_but_none_applied(self) -> None:
        retro = _make_retro("r1", "c1")
        deltas = [_make_delta("d1", "c1", AppliedStatus.REJECTED)]
        result = check_retrospective_delta_required(retro, deltas)
        assert result.passed is False

    def test_pass_none_retrospective(self) -> None:
        result = check_retrospective_delta_required(None, [])
        assert result.passed is True
        assert result.detail == "無 retrospective，規則不適用"


# === executive brief ===


class TestExecutiveBrief:
    def test_filters_high_confidence_applied_only(self, _utcnow: datetime) -> None:
        deltas = [
            _make_delta("d1", "c1", AppliedStatus.APPLIED, 0.95),
            _make_delta("d2", "c1", AppliedStatus.APPLIED, 0.80),
            _make_delta("d3", "c1", AppliedStatus.PENDING, 0.99),
            _make_delta("d4", "c1", AppliedStatus.REJECTED, 0.90),
            _make_delta("d5", "c1", AppliedStatus.APPLIED, 0.85),
        ]
        brief = build_executive_brief(deltas)
        assert len(brief) == 2
        assert {d.delta_id for d in brief} == {"d1", "d5"}

    def test_empty_input(self) -> None:
        assert build_executive_brief([]) == []


# === contracts-index dumper / parser ===


class TestContractsIndexDumper:
    def test_dumper_includes_retrospective_id_when_present(self) -> None:
        from scripts.new_work_unit import dump_yaml

        data = {
            "generated_at": "2026-06-25T00:00:00Z",
            "total_contracts": 1,
            "contracts": [
                {
                    "id": "wu-20260625-001",
                    "slug": "ssot-bootstrap",
                    "path": "docs/contracts/20260625-ssot-bootstrap.yaml",
                    "sha256": "abc",
                    "signed": True,
                    "status": "done",
                    "retrospective_id": "retro-20260625-001",
                }
            ],
        }
        text = dump_yaml(data)
        assert "retrospective_id: retro-20260625-001" in text
        assert "total_contracts: 1" in text

    def test_dumper_skips_none_retrospective_id(self) -> None:
        from scripts.new_work_unit import dump_yaml

        data = {
            "generated_at": "2026-06-25T00:00:00Z",
            "total_contracts": 1,
            "contracts": [
                {
                    "id": "wu-20260625-001",
                    "slug": "ssot-bootstrap",
                    "path": "docs/contracts/20260625-ssot-bootstrap.yaml",
                    "sha256": "abc",
                    "signed": True,
                    "status": "done",
                }
            ],
        }
        text = dump_yaml(data)
        assert "retrospective_id" not in text
        assert "total_contracts: 1" in text

    def test_parser_still_reads_total_contracts_with_retrospective_id(self) -> None:
        from scripts.new_work_unit import _safe_load_yaml

        text = """\
generated_at: "2026-06-25T00:00:00Z"
total_contracts: 2
contracts:
- id: wu-20260625-001
  slug: ssot-bootstrap
  retrospective_id: retro-20260625-001
- id: wu-20260625-002
  slug: demo
"""
        data = _safe_load_yaml(text)
        # parser only needs to preserve total_contracts for existing test
        assert data.get("total_contracts") == 2
