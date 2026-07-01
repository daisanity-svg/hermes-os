"""Workflow Engine — definable project / research / development workflows."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum

from hermes_os.run_journal import RunJournal
from hermes_os.types import RunJournalEntry


class StepStatus(str):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class WorkflowPreset(str, Enum):
    PROJECT = "project"
    RESEARCH = "research"
    DEVELOPMENT = "development"


@dataclass(frozen=True)
class WorkflowStep:
    step_id: str
    name: str
    assignee: str = "hermes"
    condition: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WorkflowDefinition:
    workflow_id: str
    name: str
    preset: WorkflowPreset = WorkflowPreset.DEVELOPMENT
    steps: List[WorkflowStep] = field(default_factory=list)
    current_step_index: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class WorkflowEngine:
    """Skeleton workflow engine that advances step-by-step."""

    def __init__(self, journal: Optional[RunJournal] = None) -> None:
        self.journal = journal or RunJournal()
        self._active: Dict[str, Dict[str, Any]] = {}

    def start(self, workflow: WorkflowDefinition, run_id: str) -> Dict[str, Any]:
        if workflow.current_step_index >= len(workflow.steps):
            return {"status": StepStatus.COMPLETED, "workflow_id": workflow.workflow_id}
        first = workflow.steps[workflow.current_step_index]
        self._active[workflow.workflow_id] = {
            "definition": workflow,
            "run_id": run_id,
            "status": StepStatus.RUNNING,
            "current_step": first.step_id,
            "completed_steps": [],
            "failed_steps": [],
        }
        self.journal.append(
            run_id=run_id,
            task_name=f"workflow:{workflow.name}",
            status="running",
            last_event=f"workflow start -> step {first.step_id}",
            next_action=f"execute {first.step_id}",
        )
        return {
            "status": "started",
            "workflow_id": workflow.workflow_id,
            "run_id": run_id,
            "current_step": first.step_id,
        }

    def complete_step(self, workflow_id: str, step_id: str, result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        active = self._active.get(workflow_id)
        if active is None:
            return {"status": StepStatus.FAILED, "error": "workflow not active"}
        definition: WorkflowDefinition = active["definition"]
        current = definition.steps[definition.current_step_index]
        if current.step_id != step_id:
            return {"status": StepStatus.FAILED, "error": f"step mismatch: expected {current.step_id}, got {step_id}"}
        active["completed_steps"].append(step_id)
        active["current_step"] = ""
        definition = WorkflowDefinition(
            workflow_id=definition.workflow_id,
            name=definition.name,
            preset=definition.preset,
            steps=definition.steps,
            current_step_index=definition.current_step_index + 1,
            metadata=definition.metadata,
        )
        active["definition"] = definition
        active["current_step"] = ""
        self.journal.append(
            run_id=active["run_id"],
            task_name=f"workflow:{definition.name}",
            status="running",
            last_event=f"step done -> {step_id}",
            next_action="advance workflow",
        )
        if definition.current_step_index >= len(definition.steps):
            active["status"] = StepStatus.COMPLETED
            self.journal.append(
                run_id=active["run_id"],
                task_name=f"workflow:{definition.name}",
                status="completed",
                last_event="workflow completed",
                next_action="none",
            )
            return {"status": StepStatus.COMPLETED, "workflow_id": workflow_id, "run_id": active["run_id"]}
        next_step = definition.steps[definition.current_step_index]
        active["current_step"] = next_step.step_id
        active["status"] = StepStatus.RUNNING
        self.journal.append(
            run_id=active["run_id"],
            task_name=f"workflow:{definition.name}",
            status="running",
            last_event=f"step done -> {step_id}, next -> {next_step.step_id}",
            next_action=f"execute {next_step.step_id}",
        )
        return {
            "status": "advanced",
            "workflow_id": workflow_id,
            "next_step": next_step.step_id,
        }

    def fail_step(self, workflow_id: str, step_id: str, error: str) -> Dict[str, Any]:
        active = self._active.get(workflow_id)
        if active is None:
            return {"status": StepStatus.FAILED, "error": "workflow not active"}
        active["failed_steps"].append(step_id)
        active["status"] = StepStatus.FAILED
        self.journal.append(
            run_id=active["run_id"],
            task_name=f"workflow:{active['definition'].name}",
            status="failed",
            last_event=f"step failed -> {step_id}: {error}",
            next_action="retry or escalate",
            error=error,
        )
        return {"status": StepStatus.FAILED, "workflow_id": workflow_id, "error": error}

    def status(self, workflow_id: str) -> Dict[str, Any]:
        active = self._active.get(workflow_id)
        if active is None:
            return {"status": "not_found"}
        definition: WorkflowDefinition = active["definition"]
        return {
            "status": active["status"],
            "workflow_id": workflow_id,
            "run_id": active["run_id"],
            "current_step": active["current_step"],
            "completed_steps": active["completed_steps"],
            "failed_steps": active["failed_steps"],
            "total_steps": len(definition.steps),
            "current_index": definition.current_step_index,
        }

    @staticmethod
    def preset_project(name: str = "project") -> WorkflowDefinition:
        return WorkflowDefinition(
            workflow_id=f"wf-{int(time.time())}",
            name=name,
            preset=WorkflowPreset.PROJECT,
            steps=[
                WorkflowStep(step_id="goal", name="Goal Definition"),
                WorkflowStep(step_id="plan", name="Planning"),
                WorkflowStep(step_id="tasks", name="Task Breakdown"),
                WorkflowStep(step_id="runs", name="Execution Runs"),
                WorkflowStep(step_id="review", name="Review"),
                WorkflowStep(step_id="deliverable", name="Deliverable"),
                WorkflowStep(step_id="reflection", name="Reflection"),
            ],
        )

    @staticmethod
    def preset_research(name: str = "research") -> WorkflowDefinition:
        return WorkflowDefinition(
            workflow_id=f"wf-{int(time.time())}",
            name=name,
            preset=WorkflowPreset.RESEARCH,
            steps=[
                WorkflowStep(step_id="question", name="Research Question"),
                WorkflowStep(step_id="sources", name="Source Collection"),
                WorkflowStep(step_id="analysis", name="Analysis"),
                WorkflowStep(step_id="findings", name="Findings"),
                WorkflowStep(step_id="review", name="Review"),
            ],
        )
