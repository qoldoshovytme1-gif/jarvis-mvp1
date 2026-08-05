"""
Internal Event Bus (MVP: in-memory)
======================================
Implements `IEventBus`. This is intentionally the simplest possible
correct implementation — synchronous, in-process, dict-of-lists
pub/sub. It exists so that Planner/Executor/Verifier/Orchestrator
NEVER call each other directly; they only publish and subscribe to
named events.

Why this matters (see architecture doc, section 1): today this is one
Python process. Tomorrow, if any module needs to run as its own
service, only this file gets replaced (e.g. `RedisEventBus`,
`NatsEventBus` implementing the same `IEventBus` interface) — every
publisher/subscriber elsewhere in the codebase is untouched.

Event naming convention used across Core:
    "plan.created"
    "step.started"
    "step.completed"
    "step.failed"
    "plan.verified"
"""

from collections import defaultdict
from typing import Callable, Any, Dict, List

from core.interfaces import IEventBus
from core.logger import get_logger

log = get_logger("core.event_bus")


class InMemoryEventBus(IEventBus):
    def __init__(self):
        self._subscribers: Dict[str, List[Callable[[dict], Any]]] = defaultdict(list)

    def publish(self, event_type: str, payload: dict) -> None:
        log.debug("Event published: %s | %s", event_type, payload)
        for handler in self._subscribers.get(event_type, []):
            try:
                handler(payload)
            except Exception:
                log.exception("Handler for event '%s' raised an exception", event_type)

    def subscribe(self, event_type: str, handler: Callable[[dict], Any]) -> None:
        self._subscribers[event_type].append(handler)
        log.debug("Handler subscribed to event: %s", event_type)
