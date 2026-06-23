"""Minimal CLI Spec — CLI surface and command contracts for Hermes OS."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class CommandSpec:
    """Minimal CLI command specification."""

    name: str
    description: str
    parameters: List[str] = field(default_factory=list)
    output_format: str = "text"


@dataclass(frozen=True)
class CLISpec:
    """Top-level CLI contract."""

    binary_name: str = "hermes-os"
    version: str = "0.1.0"
    commands: Dict[str, CommandSpec] = field(default_factory=dict)

    def register(self, command: CommandSpec) -> None:
        self.commands[command.name] = command

    def list_commands(self) -> List[str]:
        return sorted(self.commands.keys())


DEFAULT_CLI_SPEC = CLISpec()
for _cmd_spec in [
    CommandSpec("status", "Show system snapshot"),
    CommandSpec("runs", "List known runs"),
    CommandSpec("actions", "List recent action records"),
    CommandSpec("queue", "Inspect workforce queue"),
    CommandSpec("memory", "Query operational memory log"),
]:
    DEFAULT_CLI_SPEC.register(_cmd_spec)
