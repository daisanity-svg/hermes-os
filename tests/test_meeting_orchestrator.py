"""Meeting verification."""

from hermes_os.event_bus import EventBus
from hermes_os.llm import LLMAdapter
from hermes_os.meeting.models import HatRole, MeetingResult
from hermes_os.meeting.orchestrator import StructuredMeeting
from hermes_os.meeting.templates.six_thinking_hats import six_thinking_hats
from hermes_os.run_journal_jsonl import JsonlRunJournal
from hermes_os.run_registry import RunRegistry


class DummyRegistry(RunRegistry):
    def upsert(self, *args, **kwargs):
        return {"status": kwargs.get("status", "queued")}


class DummyJournal(JsonlRunJournal):
    def __init__(self):
        self.events = []

    def append(self, *args, **kwargs):
        self.events.append(kwargs)


class DummyLLM(LLMAdapter):
    def __init__(self):
        self.calls = []

    def complete(self, prompt, **kwargs):
        self.calls.append(prompt)
        from hermes_os.llm import LLMResponse
        return LLMResponse(content="模擬會議結論", model="dummy", provider="dummy")


class DummyEventBus(EventBus):
    def __init__(self):
        super().__init__()
        self.events = []

    def publish(self, event):
        self.events.append(event)
        super().publish(event)


def test_meeting_completes_known_hooks():
    registry = DummyRegistry()
    journal = DummyJournal()
    llm = DummyLLM()
    bus = DummyEventBus()
    meeting = StructuredMeeting(
        template=six_thinking_hats("新產品定位"),
        adapter=None,
        registry=registry,
        journal=journal,
        llm=llm,
        event_bus=bus,
    )
    result: MeetingResult = meeting.run("新產品定位")
    assert result.status == "completed"
    assert result.topic == "新產品定位"
    assert set(result.outputs.keys()) == {
        HatRole.WHITE,
        HatRole.YELLOW,
        HatRole.RED,
        HatRole.BLACK,
        HatRole.GREEN,
    }
    assert len(llm.calls) == 6


def test_meeting_publishes_events():
    registry = DummyRegistry()
    journal = DummyJournal()
    llm = DummyLLM()
    bus = DummyEventBus()
    meeting = StructuredMeeting(
        template=six_thinking_hats("品牌命名"),
        registry=registry,
        journal=journal,
        llm=llm,
        event_bus=bus,
    )
    meeting.run("品牌命名")
    event_names = [event.name for event in bus.events]
    assert "meeting.started" in event_names
    assert "meeting.completed" in event_names
    assert event_names.count("hat.completed") == 5
