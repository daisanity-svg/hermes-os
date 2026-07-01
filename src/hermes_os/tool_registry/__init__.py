"""Tool Registry — abstract interfaces and security rules for Agent tools."""

from __future__ import annotations

import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class RiskLevel(str, Enum):
    """Tool risk classification."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class ToolSecurityPolicy:
    """Security constraints enforced before tool execution."""

    allowed_paths: List[Path] = field(default_factory=list)
    blocked_paths: List[Path] = field(default_factory=list)
    blocked_commands: List[str] = field(default_factory=list)
    max_execution_seconds: float = 30.0
    allow_network: bool = False
    allow_filesystem_write: bool = False
    allow_system_shell: bool = False

    def is_path_allowed(self, path: Path) -> bool:
        resolved = path.resolve()
        for blocked in self.blocked_paths:
            try:
                resolved.relative_to(blocked.resolve())
                return False
            except ValueError:
                pass
        if not self.allowed_paths:
            return True
        for allowed in self.allowed_paths:
            try:
                resolved.relative_to(allowed.resolve())
                return True
            except ValueError:
                pass
        return False

    def is_command_allowed(self, command: str) -> bool:
        cmd_lower = command.lower().strip()
        for blocked in self.blocked_commands:
            if blocked.lower() in cmd_lower:
                return False
        return True


class BaseTool(ABC):
    """Abstract base tool definition."""

    name: str = "base_tool"
    description: str = ""
    risk_level: RiskLevel = RiskLevel.LOW

    def __init__(self, policy: Optional[ToolSecurityPolicy] = None) -> None:
        self.policy = policy or ToolSecurityPolicy()

    @abstractmethod
    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        """Run the tool and return a result dict."""

    def pre_check(self, **kwargs: Any) -> Dict[str, Any]:
        """Optional pre-flight security check."""
        return {"allowed": True, "reason": "default"}

    def _result(self, status: str, **kwargs: Any) -> Dict[str, Any]:
        return {"tool": self.name, "status": status, "risk_level": self.risk_level.value, **kwargs}


class BrowserTool(BaseTool):
    name = "browser"
    description = "Navigate and interact with web pages."
    risk_level = RiskLevel.LOW

    def pre_check(self, **kwargs: Any) -> Dict[str, Any]:  # noqa: ARG002
        if not self.policy.allow_network:
            return {"allowed": False, "reason": "network access disabled by policy"}
        return {"allowed": True, "reason": "network allowed"}

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        action = kwargs.get("action", "navigate")
        if action == "navigate":
            return self._result("ok", url=kwargs.get("url", ""), title="mock-page")
        if action == "snapshot":
            return self._result("ok", snapshot="<mock-dom />")
        if action == "click":
            return self._result("ok", clicked=kwargs.get("ref", ""))
        return self._result("error", error=f"unsupported browser action: {action}")


class FinderTool(BaseTool):
    name = "finder"
    description = "Browse filesystem and report file locations."
    risk_level = RiskLevel.LOW

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        target = Path(kwargs.get("path", "."))
        if not self.policy.is_path_allowed(target):
            return self._result("error", error="path blocked by policy")
        if not target.exists():
            return self._result("error", error="path not found")
        entries = []
        try:
            for child in target.iterdir():
                entries.append(
                    {
                        "name": child.name,
                        "is_dir": child.is_dir(),
                        "size": child.stat().st_size if child.is_file() else 0,
                    }
                )
        except PermissionError as exc:
            return self._result("error", error=str(exc))
        return self._result("ok", path=str(target), entries=entries)


class TerminalTool(BaseTool):
    name = "terminal"
    description = "Execute read-only shell commands with safety guardrails."
    risk_level = RiskLevel.MEDIUM

    def pre_check(self, **kwargs: Any) -> Dict[str, Any]:  # noqa: ARG002
        if not self.policy.allow_system_shell:
            return {"allowed": False, "reason": "shell execution disabled by policy"}
        command = str(kwargs.get("command", ""))
        if not self.policy.is_command_allowed(command):
            return {"allowed": False, "reason": "command blocked by policy"}
        return {"allowed": True, "reason": "command allowed"}

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        command = kwargs.get("command", "")
        read_only_ok = any(command.strip().startswith(prefix) for prefix in ("ls ", "cat ", "find ", "git status", "git diff", "pytest", "python -m pytest"))
        if not read_only_ok:
            return self._result("blocked", error="only read-only commands are allowed")
        return self._result("ok", stdout=f"[mock] executed: {command}", exit_code=0)


class AppleScriptTool(BaseTool):
    name = "applescript"
    description = "Run AppleScript snippets on macOS for automation."
    risk_level = RiskLevel.HIGH

    def pre_check(self, **kwargs: Any) -> Dict[str, Any]:  # noqa: ARG002
        if not self.policy.allow_system_shell:
            return {"allowed": False, "reason": "system automation disabled by policy"}
        return {"allowed": True, "reason": "policy allows system automation"}

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        script = kwargs.get("script", "")
        if not script:
            return self._result("error", error="empty script")
        return self._result("ok", output=f"[mock] ran AppleScript (length={len(script)})")


class OCRTool(BaseTool):
    name = "ocr"
    description = "Extract text from images or PDFs."
    risk_level = RiskLevel.LOW

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        target = Path(kwargs.get("path", ""))
        if not self.policy.is_path_allowed(target):
            return self._result("error", error="path blocked by policy")
        return self._result("ok", text="[mock OCR output]", confidence=0.95)


class SpeechTool(BaseTool):
    name = "speech"
    description = "Text-to-speech / speech-to-text operations."
    risk_level = RiskLevel.LOW

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        action = kwargs.get("action", "tts")
        text = kwargs.get("text", "")
        if action == "tts":
            return self._result("ok", output=f"[mock tts] {text}")
        if action == "stt":
            return self._result("ok", transcript="[mock transcript]")
        return self._result("error", error=f"unsupported speech action: {action}")


class ToolRegistry:
    """Central registry for tools with security enforcement."""

    def __init__(self, policy: Optional[ToolSecurityPolicy] = None) -> None:
        self.policy = policy or ToolSecurityPolicy()
        self._tools: Dict[str, BaseTool] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        defaults = [
            BrowserTool(policy=self.policy),
            FinderTool(policy=self.policy),
            TerminalTool(policy=self.policy),
            AppleScriptTool(policy=self.policy),
            OCRTool(policy=self.policy),
            SpeechTool(policy=self.policy),
        ]
        for tool in defaults:
            self._tools[tool.name] = tool

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name)

    def list_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "risk_level": t.risk_level.value,
            }
            for t in self._tools.values()
        ]

    def execute(self, name: str, **kwargs: Any) -> Dict[str, Any]:
        tool = self._tools.get(name)
        if tool is None:
            return {"tool": name, "status": "error", "error": "tool not found"}
        check = tool.pre_check(**kwargs)
        if not check.get("allowed", False):
            return {"tool": name, "status": "blocked", "reason": check.get("reason", "policy")}
        return tool.execute(**kwargs)
