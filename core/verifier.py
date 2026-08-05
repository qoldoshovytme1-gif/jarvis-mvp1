"""
Verifier
==========
Responsibility: inspect an ExecutionReport and decide whether the plan
truly succeeded, applying retry policy where sensible. This is what
stops JARVIS from confidently reporting success when an action module
actually failed silently.

Single Responsibility: Verifier ONLY judges outcomes. It does not plan
and does not execute — retries are delegated back through the
Executor it was given, keeping each class focused.

MVP policy: retry a failed step once (configurable via
`JarvisConfig.max_retries`), then accept failure and let the
Orchestrator surface an honest error message instead of pretending
success.
"""

from core.interfaces import IEventBus
from core.models import ExecutionReport, StepStatus
from core.logger import get_logger

log = get_logger("core.verifier")


class Verifier:
    def __init__(self, executor, event_bus: IEventBus, max_retries: int = 1):
        # `executor` is intentionally untyped here to avoid a circular
        # import with core.executor; duck-typing on `.execute(plan)`
        # is enough for this narrow use.
        self._executor = executor
        self._event_bus = event_bus
        self._max_retries = max_retries

    def verify(self, report: ExecutionReport) -> ExecutionReport:
        if report.all_succeeded:
            self._event_bus.publish("plan.verified", {"success": True})
            return report

        failed_steps = [r for r in report.results if not r.success]
        log.warning("%d step(s) failed verification.", len(failed_steps))

        retries_left = self._max_retries
        while retries_left > 0 and not report.all_succeeded:
            retries_left -= 1
            log.info("Retrying failed steps (%d retr(y/ies) left).", retries_left)

            retry_plan = report.plan
            for step in retry_plan.steps:
                step.status = StepStatus.PENDING

            report = self._executor.execute(retry_plan)

        self._event_bus.publish("plan.verified", {"success": report.all_succeeded})
        if not report.all_succeeded:
            log.error("Plan verification failed after retries.")

        return report
