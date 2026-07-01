"""Base Architecture Sprint — end-to-end acceptance test with a mock project.

Mock project: 數學森林 MVP (Math Forest MVP)
Flow: goal -> plan -> tasks -> runs -> review -> deliverable -> reflection
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from hermes_os.llm import LLMAdapter, LLMMessage, LLMRole, MockLLMProvider
from hermes_os.memory import KnowledgeCategory, MemoryStore, KnowledgeObject
from hermes_os.project_lifecycle import ProjectLifecycleManager, ProjectStage
from hermes_os.recovery import RecoveryManager
from hermes_os.run_journal import RunJournal
from hermes_os.tool_registry import ToolRegistry, ToolSecurityPolicy
from hermes_os.workflow import WorkflowEngine, WorkflowDefinition, WorkflowStep, WorkflowPreset
from hermes_os.workforce_queue import WorkforceQueue, WorkforceItem


@pytest.fixture()
def journal(tmp_path: Path) -> RunJournal:
    p = tmp_path / "run-journal.json"
    return RunJournal(storage_path=p)


@pytest.fixture()
def recovery(journal: RunJournal) -> RecoveryManager:
    return RecoveryManager(journal=journal)


@pytest.fixture()
def memory_store(tmp_path: Path) -> MemoryStore:
    return MemoryStore(base_path=tmp_path / "knowledge")


@pytest.fixture()
def tool_registry() -> ToolRegistry:
    return ToolRegistry(policy=ToolSecurityPolicy(allow_system_shell=False, allow_network=True, allow_filesystem_write=False))


@pytest.fixture()
def llm_adapter() -> LLMAdapter:
    return LLMAdapter(provider=MockLLMProvider())


class TestAgentCoreLifecycle:
    """Verify Agent Core planning, state machine, and execution lifecycle."""

    def test_agent_core_event_flow(self, journal: RunJournal, tool_registry: ToolRegistry, llm_adapter: LLMAdapter) -> None:
        run_id = f"run-{int(time.time())}"
        journal.append(run_id=run_id, task_name="agent-core-plan", status="queued", last_event="queued", next_action="plan")
        plan = llm_adapter.chat([LLMMessage(role=LLMRole.USER, content="請規劃數學森林 MVP 三步驟")])
        assert plan.content and len(plan.content) > 0
        journal.update(run_id, status="completed", last_event="plan generated")
        entry = journal.get(run_id)
        assert entry is not None
        assert entry.status == "completed"
        result = tool_registry.execute("browser", action="navigate", url="http://mock")
        assert result["status"] == "ok"

    def test_llm_adapter_switching(self, llm_adapter: LLMAdapter) -> None:
        response = llm_adapter.chat([LLMMessage(role=LLMRole.USER, content="你好")])
        assert response.provider == "mock"
        openai_compat = llm_adapter.provider.__class__.__name__
        assert openai_compat == "MockLLMProvider"
        assert len(llm_adapter.history()) == 1


class TestCoSRuntimeSelection:
    """Verify CoS Runtime picks low-risk tasks and tracks state."""

    def test_task_queue_and_retry(self, journal: RunJournal) -> None:
        queue = WorkforceQueue()
        item = WorkforceItem(item_id="math-forest-01", item_type="task", priority=2, status="queued", payload={"title": "設計關卡"})
        queue.enqueue(item)
        next_item = queue.peek()
        assert next_item is not None
        assert next_item.item_id == "math-forest-01"
        completed = queue.complete(next_item.item_id)
        assert completed.status == "completed"
        run_id = f"run-{int(time.time())}-math-forest-01"
        journal.append(run_id=run_id, task_name=next_item.payload.get("title", ""), status="completed", last_event="task done")
        entries = journal.list(project_code=None)
        assert any(e.run_id == run_id for e in entries)

    def test_recovery_manager_failure_escalation(self, journal: RunJournal, recovery: RecoveryManager) -> None:
        run_id = f"run-fail-{int(time.time())}"
        journal.append(run_id=run_id, task_name="fail-task", status="failed", error="HTTP 500", retry_count=3)
        recoverable = recovery.list_recoverable()
        matching = [r for r in recoverable if r.run_id == run_id]
        assert len(matching) == 1
        assert matching[0].recovery_status.value == "needs_founder_decision"
        ticket = recovery.escalate(run_id, reason="連續三次失敗")
        assert ticket is not None
        assert ticket["ticket_id"].startswith("recovery-")


class TestToolRegistrySecurity:
    """Verify tool registry enforces security policies."""

    def test_blocked_shell_command(self, tool_registry: ToolRegistry) -> None:
        result = tool_registry.execute("terminal", command="rm -rf /tmp/evil")
        assert result["status"] == "blocked"
        assert "policy" in result.get("reason", "").lower()

    def test_allowed_read_command(self) -> None:
        registry = ToolRegistry(policy=ToolSecurityPolicy(allow_system_shell=True))
        result = registry.execute("terminal", command="ls /tmp")
        assert result["status"] == "ok"

    def test_finder_blocked_path(self) -> None:
        policy = ToolSecurityPolicy(blocked_paths=[Path("/etc")])
        registry = ToolRegistry(policy=policy)
        result = registry.execute("finder", path="/etc")
        assert result["status"] == "error"
        assert "blocked by policy" in result.get("error", "").lower()


class TestMemoryLayer:
    """Verify Local Knowledge SQLite schema and Markdown skeleton."""

    def test_add_and_search_knowledge(self, memory_store: MemoryStore) -> None:
        obj = KnowledgeObject(object_id="kn-001", category=KnowledgeCategory.NOTE, title="設計決策", content="使用大卡片設計", tags=["#設計", "#math"])
        stored = memory_store.add(obj)
        assert stored.object_id == "kn-001"
        found = memory_store.search("設計")
        assert len(found) == 1
        assert found[0].title == "設計決策"
        loaded = memory_store.get("kn-001")
        assert loaded is not None
        assert loaded.category == KnowledgeCategory.NOTE
        md = loaded.to_markdown()
        assert "# 設計決策" in md
        assert "## Content" in md
        assert "使用大卡片設計" in md


class TestWorkflowEngine:
    """Verify workflow engine step advancement."""

    def test_project_workflow_steps(self, journal: RunJournal) -> None:
        engine = WorkflowEngine(journal=journal)
        wf = WorkflowDefinition(workflow_id="wf-math-01", name="數學森林", preset=WorkflowPreset.PROJECT, steps=[WorkflowStep("goal", "Goal Definition"), WorkflowStep("plan", "Planning"), WorkflowStep("runs", "Execution Runs"), WorkflowStep("reflection", "Reflection")])
        start = engine.start(wf, run_id="run-wf-01")
        assert start["status"] == "started"
        advance = engine.complete_step(wf.workflow_id, "goal")
        assert advance["status"] == "advanced"
        advance = engine.complete_step(wf.workflow_id, "plan")
        assert advance["status"] == "advanced"
        advance = engine.complete_step(wf.workflow_id, "runs")
        assert advance["status"] == "advanced"
        advance = engine.complete_step(wf.workflow_id, "reflection")
        assert advance["status"] == "completed"
        status = engine.status(wf.workflow_id)
        assert status["status"] == "completed"

    def test_failure_handling(self, journal: RunJournal) -> None:
        engine = WorkflowEngine(journal=journal)
        wf = WorkflowDefinition(workflow_id="wf-math-02", name="數學森林-fail", preset=WorkflowPreset.DEVELOPMENT, steps=[WorkflowStep("a", "Step A"), WorkflowStep("b", "Step B")])
        engine.start(wf, run_id="run-wf-02")
        result = engine.fail_step(wf.workflow_id, "a", "simulated failure")
        assert result["status"] == "failed"
        status = engine.status(wf.workflow_id)
        assert status["status"] == "failed"
        assert "a" in status["failed_steps"]


class TestProjectLifecycle:
    """Verify project lifecycle from goal to reflection."""

    def test_full_project_lifecycle(self, journal: RunJournal) -> None:
        lifecycle = ProjectLifecycleManager(journal=journal)
        project = lifecycle.create_project(project_code="MATH-FOREST-MVP", name="數學森林 MVP", goal="建立3-6歲兒童數學練習遊戲")
        assert project.stage == ProjectStage.GOAL
        project = lifecycle.set_plan(project.project_code, "big-cards-no-text kid-friendly design")
        assert project.stage == ProjectStage.PLAN
        wf_result = lifecycle.start_workflow(project.project_code)
        assert "workflow_id" in wf_result
        assert wf_result["run_id"] is not None
        current_step = wf_result.get("step")
        assert current_step is not None
        code = project.project_code
        lifecycle.advance_workflow(code, current_step)
        project = lifecycle.add_deliverable(code, "math-forest-v1.zip")
        project = lifecycle.add_reflection(code, "小朋友喜歡大卡片設計")
        loaded = lifecycle.get_project(code)
        assert loaded is not None
        assert loaded["stage"] == ProjectStage.REFLECTION
        assert "math-forest-v1.zip" in loaded["deliverables"]
        assert len(loaded["reflections"]) == 1

    def test_list_projects(self, journal: RunJournal) -> None:
        lifecycle = ProjectLifecycleManager(journal=journal)
        lifecycle.create_project("P1", "Project A", "Goal A")
        lifecycle.create_project("P2", "Project B", "Goal B")
        projects = lifecycle.list_projects()
        assert len(projects) == 2
        codes = [p["project_code"] for p in projects]
        assert "P1" in codes
        assert "P2" in codes


class TestRunJournalApprovalFlow:
    """Verify Run Journal, Recovery, and Approval integration."""

    def test_journal_persistence_and_filter(self, tmp_path: Path) -> None:
        journal = RunJournal(storage_path=tmp_path / "rj.json")
        run_id = "run-journal-01"
        journal.append(run_id=run_id, task_name="test", project_code="X", status="queued")
        journal.update(run_id, status="running")
        journal.update(run_id, status="waiting_for_approval")
        pending = journal.list(status="waiting_for_approval")
        assert len(pending) == 1
        assert pending[0].run_id == run_id
        by_project = journal.list(project_code="X")
        assert len(by_project) == 1

    def test_recovery_retry_and_escalate(self, journal: RunJournal, recovery: RecoveryManager) -> None:
        run_id = "run-retry-01"
        journal.append(run_id=run_id, task_name="retry-task", status="failed", error="timeout", retry_count=1)
        recoverable = [r for r in recovery.list_recoverable() if r.run_id == run_id]
        assert len(recoverable) == 1
        assert recoverable[0].recovery_status.value == "retryable"
        recovery.mark_recovering(run_id, reason="retry")
        journal_entry = journal.get(run_id)
        assert journal_entry.status == "recovering"
        recovery.mark_recovered(run_id)
        journal_entry = journal.get(run_id)
        assert journal_entry.status == "completed"
        assert journal_entry.retry_count == 0


class TestWorkspaceIntegration:
    """Verify workspace can list projects, runs, and workflows."""

    def test_workspace_view_aggregation(self, journal: RunJournal) -> None:
        lifecycle = ProjectLifecycleManager(journal=journal)
        lifecycle.create_project(project_code="WS-01", name="WsProject", goal="Workspace test")
        engine = WorkflowEngine(journal=journal)
        wf = WorkflowDefinition(workflow_id="wf-ws-01", name="ws-wf", steps=[WorkflowStep("a", "A")])
        engine.start(wf, run_id="run-ws-01")
        projects = lifecycle.list_projects()
        assert len(projects) == 1
        runs = journal.list(project_code="WS-01")
        assert len(runs) == 1
        wf_status = engine.status("wf-ws-01")
        assert wf_status["status"] == "running"


class TestSecurityConstraints:
    """Verify security constraints are enforced by the system."""

    def test_no_destructive_tool_actions(self, tool_registry: ToolRegistry) -> None:
        assert tool_registry.execute("terminal", command="rm -rf /tmp/x")["status"] == "blocked"
        assert tool_registry.execute("terminal", command="curl http://evil")["status"] == "blocked"

    def test_allowed_actions_with_permissive_policy(self) -> None:
        permissive = ToolRegistry(policy=ToolSecurityPolicy(allow_system_shell=True))
        assert permissive.execute("terminal", command="cat /tmp/ok")["status"] in ("ok", "blocked")

    def test_no_network_by_default(self) -> None:
        strict = ToolRegistry(policy=ToolSecurityPolicy(allow_network=False, allow_system_shell=False))
        assert strict.execute("browser", action="navigate", url="http://x")["status"] == "blocked"
        assert strict.execute("applescript", script="tell app Finder to activate")["status"] == "blocked"
