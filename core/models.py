"""
Core Data Models
==================
Plain data structures shared between Planner, Executor, Verifier, and
Orchestrator. Kept dependency-free (no imports from other core modules)
so any module can import these without risk of circular imports.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


@dataclass
class TaskStep:
    """A single unit of work inside a Plan.

    `action_type` maps directly to a key in the Executor's action
    registry (e.g. "chat", "open_app", "set_alarm", "notify",
    "web_search"). Adding a new capability later = adding a new
    action_type + a new IActionExecutor implementation. Nothing here
    needs to change.
    """
    step_id: str
    action_type: str
    params: dict = field(default_factory=dict)
    status: StepStatus = StepStatus.PENDING


@dataclass
class Plan:
    """An ordered list of steps produced by the Planner from one user
    request. MVP plans are single-step (the LLM returns one intent at
    a time) — the structure already supports multi-step plans for when
    the Planner is extended to decompose complex requests.
    """
    original_request: str
    steps: List[TaskStep] = field(default_factory=list)
    reply_hint: str = ""  # natural-language reply drafted by the LLM


@dataclass
class StepResult:
    """Outcome of executing one TaskStep."""
    step_id: str
    success: bool
    output: str
    error: Optional[str] = None


@dataclass
class ExecutionReport:
    """Full outcome of executing a Plan — this is what the Verifier
    inspects and what the Orchestrator uses to build the final reply.
    """
    plan: Plan
    results: List[StepResult] = field(default_factory=list)

    @property
    def all_succeeded(self) -> bool:
        return all(r.success for r in self.results) if self.results else True
