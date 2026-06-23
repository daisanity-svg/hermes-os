"""Pydantic governance validation tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from hermes_os.action_records import ActionRecords
from hermes_os.lifecycle_records import LifecycleRecords
from hermes_os.ownership_records import OwnershipRecords
from hermes_os.types import RunStatus
from hermes_os.validation import (
    ActionRecordModel,
    ArtifactRefModel,
    LifecycleEventModel,
    OwnershipRecordModel,
)


def test_artifact_ref_validates_path_traversal() -> None:
    with pytest.raises(ValidationError):
        ArtifactRefModel(artifact_id="a1", filename="../../etc/passwd")


def test_lifecycle_event_validates_known_status() -> None:
    with pytest.raises(ValidationError):
        LifecycleEventModel(event_id="e1", subject_id="r1", to_status="bogus")


def test_ownership_record_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        OwnershipRecordModel(
            record_id="o1", subject_id="r1", owner="u1", source="test", injected=123
        )


def test_action_record_validates_error_empty() -> None:
    with pytest.raises(ValidationError):
        ActionRecordModel(action_id="a1", action_type="x", error="   ")


def test_ownership_records_persists_models() -> None:
    ledger = OwnershipRecords()
    rec = ledger.grant("subj", "owner:1", "api")
    assert rec.owner == "owner:1"
    assert len(ledger.get_for_subject("subj")) == 1


def test_lifecycle_records_accepts_valid_statuses() -> None:
    log = LifecycleRecords()
    e = log.record_transition("r1", to_status=RunStatus.RUNNING.value)
    assert e.to_status == "running"
    assert log.current_status("r1") == "running"
