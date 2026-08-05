"""
Planner (skeleton)
====================
Responsibility: turn one user request into a `Plan` (ordered TaskSteps)
by asking the LLM to classify intent + extract parameters.

MVP scope: the underlying LLM prompt (see `core/llm_client.py`)
currently returns ONE intent per call, so today's Plan is always
single-step. The data model (`Plan.steps: List[TaskStep]`) and this
class's structure already support multi-step plans — extending this
is the next increment (e.g. updating the LLM system prompt to return
a JSON array of steps for compound requests like "check my calendar
AND set a reminder"), without changing Executor, Verifier, or
Orchestrator.

Single Responsibility: Planner ONLY plans. It never executes actions
and never touches memory storage directly (it receives context as a
plain string, already built by whoever calls it).
"""

import uuid

from core.interfaces import ILanguageModel
from core.models import Plan, TaskStep, StepStatus
from core.logger import get_logger

log = get_logger("core.planner")


class Planner:
    def __init__(self, llm: ILanguageModel):
        self._llm = llm

    def create_plan(self, user_text: str, context: str = "") -> Plan:
        log.info("Planning for request: %s", user_text)

        llm_result = self._llm.ask(user_text, context=context)

        intent = llm_result.get("intent", "chat")
        params = dict(llm_result.get("action_params", {}))
        reply_hint = llm_result.get("reply", "")

        # "chat" steps carry the reply forward so ChatActionExecutor
        # (see core/adapters.py) can just pass it through.
        if intent == "chat":
            params["reply"] = reply_hint

        step = TaskStep(
            step_id=str(uuid.uuid4())[:8],
            action_type=intent,
            params=params,
            status=StepStatus.PENDING,
        )

        plan = Plan(original_request=user_text, steps=[step], reply_hint=reply_hint)
        log.info("Plan created: 1 step, action_type=%s", intent)
        return plan
