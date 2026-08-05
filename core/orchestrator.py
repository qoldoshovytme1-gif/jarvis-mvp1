"""
Core Orchestrator
====================
THE central coordinating class of JARVIS. Everything the system does
for a single user request flows through `Orchestrator.handle()`.

The Orchestrator itself contains ZERO business logic for individual
capabilities -- it does not know HOW to search the internet, open an
app, or store memory. Its only job is coordination:

    1. Pull context from Memory
    2. Ask the Planner to turn the request into a Plan
    3. Ask the Executor to run the Plan
    4. Ask the Verifier to confirm the outcome (with retries if needed)
    5. Persist the exchange to Memory
    6. Return the final reply

This is Clean Architecture's "use case" layer: it depends only on
interfaces (`core.interfaces`), never on concrete modules directly.
Dependency Injection: every collaborator is passed into the
constructor. `Orchestrator()` with no arguments still works -- it
self-wires sane defaults via the Composition Root logic below -- but
every dependency can be swapped for a test double or an alternative
implementation without touching this file.
"""

from typing import Optional

from core.interfaces import IMemoryRepository, IEventBus
from core.models import Plan, ExecutionReport
from core.planner import Planner
from core.executor import Executor
from core.verifier import Verifier
from core.event_bus import InMemoryEventBus
from core.adapters import LLMClientAdapter, MemoryRepositoryAdapter, build_default_action_registry
from core.config import get_config
from core.logger import get_logger

log = get_logger("core.orchestrator")


class Orchestrator:
    def __init__(
        self,
        planner: Optional[Planner] = None,
        executor: Optional[Executor] = None,
        verifier: Optional[Verifier] = None,
        memory: Optional[IMemoryRepository] = None,
        event_bus: Optional[IEventBus] = None,
    ):
        # Composition Root: if a dependency wasn't injected, build the
        # default production wiring here. Tests / future entry points
        # (Gateway, Windows app, etc.) can inject alternatives instead.
        self.event_bus = event_bus or InMemoryEventBus()
        self.memory = memory or MemoryRepositoryAdapter()

        llm = LLMClientAdapter()
        self.planner = planner or Planner(llm=llm)

        registry = build_default_action_registry(memory=self.memory)
        self.executor = executor or Executor(registry=registry, event_bus=self.event_bus)

        config = get_config()
        self.verifier = verifier or Verifier(
            executor=self.executor, event_bus=self.event_bus, max_retries=config.max_retries
        )

    def handle(self, user_text: str) -> str:
        log.info("Handling request: %s", user_text)

        context = self.memory.build_context_string()

        plan: Plan = self.planner.create_plan(user_text, context=context)
        self.event_bus.publish("plan.created", {"steps": len(plan.steps)})

        report: ExecutionReport = self.executor.execute(plan)
        report = self.verifier.verify(report)

        final_reply = self._build_final_reply(plan, report)

        self.memory.add_message("user", user_text)
        self.memory.add_message("jarvis", final_reply)
        self._record_command_history(plan, report)

        log.info("Request handled successfully: %s", report.all_succeeded)
        return final_reply

    def _build_final_reply(self, plan: Plan, report: ExecutionReport) -> str:
        """Combines the LLM's drafted reply with any action output.
        MVP is single-step, so this is a simple join -- this is the
        seam where multi-step reply synthesis will be extended later.
        """
        if not report.results:
            return plan.reply_hint or "I couldn't process that."

        result = report.results[0]

        if not result.success:
            return f"Something went wrong: {result.error}"

        step = plan.steps[0]
        if step.action_type == "chat":
            return result.output

        # For action steps, prefer the LLM's natural-language reply,
        # falling back to the raw action output if none was drafted.
        return plan.reply_hint or result.output

    def _record_command_history(self, plan: Plan, report: ExecutionReport) -> None:
        """Logs every non-"chat" step into Memory's command_history table.
        Keeps the audit trail (what device actions actually ran) separate
        from the plain conversation transcript. Never lets a logging
        failure break the user-facing reply.
        """
        for step, result in zip(plan.steps, report.results):
            if step.action_type == "chat":
                continue
            try:
                self.memory.add_command(
                    step.action_type, step.params, result.output or result.error or "", result.success
                )
            except Exception:
                log.exception("Failed to record command history for step %s", step.step_id)
