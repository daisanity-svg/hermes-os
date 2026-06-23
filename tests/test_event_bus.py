"""Event bus tests."""

from __future__ import annotations

from datetime import datetime

from hermes_os.event_bus import DomainEvent, EventBus


def test_subscribe_and_publish() -> None:
    bus = EventBus()
    received: list[DomainEvent] = []
    bus.subscribe("task.created", lambda event: received.append(event))
    bus.publish(DomainEvent(name="task.created", source="adapter", occurred_at=datetime.utcnow(), payload={"task_id": "task-1"}))
    assert len(received) == 1
    assert received[0].payload["task_id"] == "task-1"


def test_replay_reexecutes_handlers() -> None:
    bus = EventBus()
    received: list[DomainEvent] = []
    bus.subscribe("task.created", lambda event: received.append(event))
    bus.publish(DomainEvent(name="task.created", source="adapter", occurred_at=datetime.utcnow(), payload={"task_id": "task-1"}))
    bus.publish(DomainEvent(name="task.created", source="adapter", occurred_at=datetime.utcnow(), payload={"task_id": "task-2"}))
    received.clear()
    bus.replay(lambda event: received.append(event))
    assert len(received) == 2


def test_replay_limit_controls_window() -> None:
    bus = EventBus()
    received: list[DomainEvent] = []
    bus.subscribe("task.created", lambda event: received.append(event))
    bus.publish(DomainEvent(name="task.created", source="adapter", occurred_at=datetime.utcnow(), payload={"task_id": "task-1"}))
    bus.publish(DomainEvent(name="task.created", source="adapter", occurred_at=datetime.utcnow(), payload={"task_id": "task-2"}))
    received.clear()
    bus.replay(lambda event: received.append(event), limit=1)
    assert len(received) == 1
    assert received[0].payload["task_id"] == "task-2"
