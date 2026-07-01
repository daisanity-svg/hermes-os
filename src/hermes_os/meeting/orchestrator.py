"""Meeting orchestrator for Hermes OS."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from hermes_os.event_bus import EventBus, DomainEvent
from hermes_os.llm import LLMAdapter
from hermes_os.meeting.models import HatOutput, MeetingResult, MeetingTemplate
from hermes_os.process_adapter import ProcessAdapter
from hermes_os.run_journal_jsonl import JsonlRunJournal
from hermes_os.run_registry import RunRegistry


class StructuredMeeting:
    def __init__(
        self,
        template: MeetingTemplate,
        adapter: Optional[ProcessAdapter] = None,
        registry: Optional[RunRegistry] = None,
        journal: Optional[JsonlRunJournal] = None,
        llm: Optional[LLMAdapter] = None,
        event_bus: Optional[EventBus] = None,
    ) -> None:
        self.template = template
        self.adapter = adapter or ProcessAdapter()
        self.registry = registry or RunRegistry()
        self.journal = journal or JsonlRunJournal()
        self.llm = llm or LLMAdapter()
        self.event_bus = event_bus or EventBus()
        self.meeting_id: Optional[str] = None
        self.parent_run_id: Optional[str] = None

    def _publish(self, name: str, payload: Dict[str, Any]) -> None:
        event = DomainEvent(
            name=name,
            source="meeting",
            occurred_at=datetime.now(timezone.utc),
            payload=payload,
        )
        self.event_bus.publish(event)

    def _render_chairman_prompt(self, topic: str, outputs: Dict[Any, HatOutput]) -> str:
        sections = []
        for role, output in outputs.items():
            sections.append(f"[{role.value}帽]\n{output.content}\n")
        assembled = "\n".join(sections)
        return f"{self.template.chairman_prompt}\n\n=== 會議記錄 ===\n{assembled}"

    def run(
        self,
        topic: str,
        parent_run_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> MeetingResult:
        self.parent_run_id = parent_run_id
        self.meeting_id = f"meeting-{uuid.uuid4().hex}"
        context = context or {}

        self._publish(
            "meeting.started",
            {"meeting_id": self.meeting_id, "topic": topic, "template": self.template.name},
        )

        outputs: Dict[Any, HatOutput] = {}
        for hat_task in self.template.hats:
            prompt = hat_task.prompt
            if hat_task.context:
                prompt = f"{prompt}\n\n參考上下文：{hat_task.context}"

            response = self.llm.complete(prompt=prompt)
            outputs[hat_task.role] = HatOutput(role=hat_task.role, content=response.content)
            self._publish(
                "hat.completed",
                {
                    "meeting_id": self.meeting_id,
                    "role": hat_task.role.value,
                    "content": response.content,
                },
            )

        chairman_prompt = self._render_chairman_prompt(topic, outputs)
        chairman_response = self.llm.complete(prompt=chairman_prompt)
        decision = chairman_response.content

        payload = {
            "meeting_id": self.meeting_id,
            "status": "completed",
            "topic": topic,
            "decision": decision,
            "outputs": {
                role.value: output.content for role, output in outputs.items()
            },
        }
        self.registry.upsert(self.meeting_id, "completed", output_json=payload, terminal=True)
        self.journal.append(
            self.meeting_id,
            "meeting.completed",
            occurred_at=datetime.now(timezone.utc),
            artifacts_json={"artifacts": []},
        )

        self._publish(
            "meeting.completed",
            {
                "meeting_id": self.meeting_id,
                "status": "completed",
                "outputs": list(payload["outputs"].keys()),
            },
        )

        return MeetingResult(
            meeting_id=self.meeting_id,
            template_name=self.template.name,
            topic=topic,
            outputs=outputs,
            decision=decision,
            status="completed",
            artifacts=[],
        )
