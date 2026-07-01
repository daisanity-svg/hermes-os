"""Project Lifecycle — manage projects from goal to reflection."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from hermes_os.run_journal import RunJournal
from hermes_os.workflow import WorkflowEngine, WorkflowDefinition, WorkflowPreset


class ProjectStage(str, Enum):
    GOAL = "goal"
    PLAN = "plan"
    TASKS = "tasks"
    RUNS = "runs"
    REVIEW = "review"
    DELIVERABLE = "deliverable"
    REFLECTION = "reflection"
    COMPLETED = "completed"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class Project:
    project_code: str
    name: str
    goal: str
    stage: ProjectStage = ProjectStage.GOAL
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    plan: Optional[str] = None
    deliverables: List[str] = field(default_factory=list)
    reflections: List[str] = field(default_factory=list)


class ProjectLifecycleManager:
    """Manage project lifecycle and track progress."""

    def __init__(self, journal: Optional[RunJournal] = None, workflow_engine: Optional[WorkflowEngine] = None) -> None:
        self.journal = journal or RunJournal()
        self.workflow_engine = workflow_engine or WorkflowEngine(journal=self.journal)
        self._projects: Dict[str, Project] = {}

    def create_project(self, project_code: str, name: str, goal: str, metadata: Optional[Dict[str, Any]] = None) -> Project:
        project = Project(
            project_code=project_code,
            name=name,
            goal=goal,
            stage=ProjectStage.GOAL,
            metadata=metadata or {},
        )
        self._projects[project_code] = project
        self.journal.append(
            run_id=f"proj-{project_code}",
            task_name=f"project:{name}",
            project_code=project_code,
            project_name=name,
            status="queued",
            last_event="project created",
            next_action="define plan",
        )
        return project

    def set_plan(self, project_code: str, plan_text: str) -> Optional[Project]:
        project = self._projects.get(project_code)
        if project is None:
            return None
        project = Project(
            project_code=project.project_code,
            name=project.name,
            goal=project.goal,
            stage=ProjectStage.PLAN,
            created_at=project.created_at,
            updated_at=datetime.utcnow(),
            metadata=project.metadata,
            plan=plan_text,
            deliverables=project.deliverables,
            reflections=project.reflections,
        )
        self._projects[project_code] = project
        self.journal.append(
            run_id=f"proj-{project_code}",
            task_name=f"project:{project.name}",
            project_code=project_code,
            project_name=project.name,
            status="running",
            last_event="plan defined",
            next_action="breakdown tasks",
        )
        return project

    def start_workflow(self, project_code: str, preset: WorkflowPreset = WorkflowPreset.DEVELOPMENT) -> Dict[str, Any]:
        project = self._projects.get(project_code)
        if project is None:
            return {"error": "project not found"}
        workflow_def = WorkflowEngine.preset_project(name=project.name) if preset == WorkflowPreset.PROJECT else WorkflowEngine.preset_research(name=project.name)
        run_id = f"run-{project_code}-{int(time.time())}"
        result = self.workflow_engine.start(workflow_def, run_id=run_id)
        project = Project(
            project_code=project.project_code,
            name=project.name,
            goal=project.goal,
            stage=ProjectStage.RUNS,
            created_at=project.created_at,
            updated_at=datetime.utcnow(),
            metadata={**project.metadata, "workflow_id": workflow_def.workflow_id, "run_id": run_id},
            plan=project.plan,
            deliverables=project.deliverables,
            reflections=project.reflections,
        )
        self._projects[project_code] = project
        return {"project": project.project_code, "workflow_id": workflow_def.workflow_id, "run_id": run_id, "step": self.workflow_engine._active[workflow_def.workflow_id]["current_step"] if workflow_def.workflow_id in self.workflow_engine._active else None}

    def advance_workflow(self, project_code: str, step_id: str) -> Dict[str, Any]:
        project = self._projects.get(project_code)
        if project is None:
            return {"error": "project not found"}
        workflow_id = project.metadata.get("workflow_id")
        if not workflow_id:
            return {"error": "no active workflow"}
        result = self.workflow_engine.complete_step(workflow_id, step_id)
        stage_map = {
            "goal": ProjectStage.GOAL,
            "plan": ProjectStage.PLAN,
            "tasks": ProjectStage.TASKS,
            "runs": ProjectStage.RUNS,
            "review": ProjectStage.REVIEW,
            "deliverable": ProjectStage.DELIVERABLE,
            "reflection": ProjectStage.REFLECTION,
        }
        next_stage = stage_map.get(result.get("next_step", ""), ProjectStage.RUNS)
        project = Project(
            project_code=project.project_code,
            name=project.name,
            goal=project.goal,
            stage=next_stage,
            created_at=project.created_at,
            updated_at=datetime.utcnow(),
            metadata=project.metadata,
            plan=project.plan,
            deliverables=project.deliverables,
            reflections=project.reflections,
        )
        self._projects[project_code] = project
        if result.get("status") == "completed":
            project = Project(
                project_code=project.project_code,
                name=project.name,
                goal=project.goal,
                stage=ProjectStage.COMPLETED,
                created_at=project.created_at,
                updated_at=datetime.utcnow(),
                metadata=project.metadata,
                plan=project.plan,
                deliverables=project.deliverables,
                reflections=project.reflections,
            )
            self._projects[project_code] = project
        return {"project": project.project_code, "stage": project.stage.value, "workflow_result": result}

    def add_deliverable(self, project_code: str, item: str) -> Optional[Project]:
        project = self._projects.get(project_code)
        if project is None:
            return None
        deliverables = [*project.deliverables, item]
        project = Project(
            project_code=project.project_code,
            name=project.name,
            goal=project.goal,
            stage=ProjectStage.DELIVERABLE,
            created_at=project.created_at,
            updated_at=datetime.utcnow(),
            metadata=project.metadata,
            plan=project.plan,
            deliverables=deliverables,
            reflections=project.reflections,
        )
        self._projects[project_code] = project
        return project

    def add_reflection(self, project_code: str, text: str) -> Optional[Project]:
        project = self._projects.get(project_code)
        if project is None:
            return None
        reflections = [*project.reflections, text]
        project = Project(
            project_code=project.project_code,
            name=project.name,
            goal=project.goal,
            stage=ProjectStage.REFLECTION,
            created_at=project.created_at,
            updated_at=datetime.utcnow(),
            metadata=project.metadata,
            plan=project.plan,
            deliverables=project.deliverables,
            reflections=reflections,
        )
        self._projects[project_code] = project
        return project

    def get_project(self, project_code: str) -> Optional[Dict[str, Any]]:
        project = self._projects.get(project_code)
        if project is None:
            return None
        return {
            "project_code": project.project_code,
            "name": project.name,
            "goal": project.goal,
            "stage": project.stage.value,
            "created_at": project.created_at.isoformat(),
            "updated_at": project.updated_at.isoformat(),
            "plan": project.plan,
            "deliverables": project.deliverables,
            "reflections": project.reflections,
            "metadata": project.metadata,
        }

    def list_projects(self) -> List[Dict[str, Any]]:
        results = []
        for code in self._projects:
            proj = self.get_project(code)
            if proj is not None:
                results.append(proj)
        return results
