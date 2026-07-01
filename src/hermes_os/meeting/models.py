"""Meeting models for Hermes OS."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class HatRole(str, Enum):
    WHITE = "white"
    YELLOW = "yellow"
    RED = "red"
    BLACK = "black"
    GREEN = "green"
    BLUE = "blue"


@dataclass
class HatTask:
    role: HatRole
    prompt: str
    context: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[HatRole] = field(default_factory=list)


@dataclass
class MeetingTemplate:
    name: str
    hats: List[HatTask]
    chairman_prompt: str
    allow_parallel: bool = False


@dataclass
class HatOutput:
    role: HatRole
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MeetingResult:
    meeting_id: str
    template_name: str
    topic: str
    outputs: Dict[HatRole, HatOutput]
    decision: str
    status: str
    artifacts: List[Dict[str, Any]] = field(default_factory=list)
