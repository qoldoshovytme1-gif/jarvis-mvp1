"""
Executor
==========
Responsibility: run each TaskStep in a Plan by dispatching it to the
registered IActionExecutor for its `action_type`, and publish events
on the Event Bus at every stage so any other part of the system
(logging, future UI, future automations) can observe execution without
being directly coupled to the Executor.

Single Responsibility: Executor ONLY executes. It does not decide
WHAT to do (that's the Planner) and does not decide whether the
result was acceptable (that's the Verifier).

Strategy Pattern: the `registry` dict maps action_type -> concrete
IActionExecutor strategy. Swapping/adding a strategy never touches
this class.
"""

from __future__ import annotations

from core.interfaces import IEventBus, IActionExecutor
from core.models import Plan, StepResult, ExecutionReport, StepStatus
from core.logger import get_logger

log = get_logger("core.executor")


class Executor:
    def __init__(self, registry: dict[str, IActionExecutor], event_bus: IEventBus):
        self._registry = registry
        self._event_bus = event_bus

    def execute(self, plan: Plan) -> ExecutionReport:
        report = ExecutionReport(plan=plan)

        for step in plan.steps:
            step.status = StepStatus.RUNNING
            self._event_bus.publish("step.started", {"step_id": step.step_id, "action_type": step.action_type})

            executor = self._registry.get(step.action_type)
            if executor is None:
                error = f"No executor registered for action_type '{step.action_type}'"
                log.error(error)
                step.status = StepStatus.FAILED
                result = StepResult(step_id=step.step_id, success=False, output="", error=error)
                self._event_bus.publish("step.failed", {"step_id": step.step_id, "error": error})
                report.results.append(result)
                continue

            try:
                output = executor.execute(step.params)
                step.status = StepStatus.DONE
                result = StepResult(step_id=step.step_id, success=True, output=output)
                self._event_bus.publish("step.completed", {"step_id": step.step_id, "output": output})
                log.info("Step %s (%s) completed.", step.step_id, step.action_type)

            except Exception as e:
                step.status = StepStatus.FAILED
                result = StepResult(step_id=step.step_id, success=False, output="", error=str(e))
                self._event_bus.publish("step.failed", {"step_id": step.step_id, "error": str(e)})
                log.exception("Step %s (%s) raised an exception.", step.step_id, step.action_type)

            report.results.append(result)

        return report
