"""Task refinement, state updates, and per-call context for the experiment."""
import json
from copy import deepcopy
from pathlib import Path
from typing import Annotated
from typing_extensions import NotRequired

from pydantic import BaseModel, ConfigDict, Field
from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain.tools import ToolRuntime, tool
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langgraph.types import Command


class TaskDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    goal: str = Field(min_length=1, max_length=2000)
    requirements: list[str] = Field(max_length=40)
    acceptance_criteria: list[str] = Field(max_length=40)
    constraints: list[str] = Field(max_length=30)
    assumptions: list[str] = Field(max_length=20)
    open_questions: list[str] = Field(max_length=20)


APPEND_FIELDS = {"decisions", "unresolved_errors", "verification_results", "resolved_errors"}
FIXED_FIELDS = {"original_prompt", *TaskDefinition.model_fields}


def merge_record(current, patch):
    """Merge concurrent deltas without discarding other tools' observations."""
    result = deepcopy(current or {})
    for key, value in patch.items():
        if key in FIXED_FIELDS and key in result:
            if result[key] != value:
                raise ValueError(f"Task definition cannot be silently changed: {key}")
        elif key in APPEND_FIELDS:
            items = result.setdefault(key, [])
            for item in value:
                if item not in items:
                    items.append(deepcopy(item))
        else:
            result[key] = deepcopy(value)
    return result


class TaskState(AgentState):
    task_record: NotRequired[Annotated[dict, merge_record]]


def refine_task(model, user_prompt):
    if not user_prompt.strip():
        raise ValueError("Task prompt cannot be empty")
    instructions = (Path(__file__).parent / "prompts/refine.md").read_text()
    response = model.with_structured_output(
        TaskDefinition, method="function_calling"
    ).invoke([SystemMessage(content=instructions), HumanMessage(content=user_prompt)])
    definition = TaskDefinition.model_validate(response)
    return {
        "original_prompt": user_prompt,
        **definition.model_dump(),
        "decisions": [], "unresolved_errors": [], "resolved_errors": [],
        "verification_results": [], "next_step": "Inspect the workspace and available capabilities",
    }


@tool
def update_task_record(
    runtime: ToolRuntime,
    next_step: str,
    decision: str = "",
    unresolved_error: str = "",
    resolve_errors: list[str] | None = None,
) -> Command:
    """Record a concise next step, decision, or blocker; resolve exact known error texts.

    Resolution is an agent assessment, not verified test success. Requirements and
    execution evidence cannot be rewritten by this tool. Supply only changed facts.
    """
    record = runtime.state.get("task_record", {})
    resolutions = resolve_errors or []
    if any(error not in record.get("unresolved_errors", []) for error in resolutions):
        raise ValueError("Only existing errors can be marked resolved")
    if any(len(value) > 2000 for value in [next_step, decision, unresolved_error, *resolutions]):
        raise ValueError("Keep each update under 2000 characters")
    if not next_step.strip():
        raise ValueError("Provide a nonempty next step")
    patch = {"next_step": next_step.strip()}
    if decision.strip():
        patch["decisions"] = [decision.strip()]
    if unresolved_error.strip():
        patch["unresolved_errors"] = [unresolved_error.strip()]
    if resolutions:
        patch["resolved_errors"] = resolutions
    return Command(update={
        "task_record": patch,
        "messages": [ToolMessage(
            content="Task record updated. Resolution claims remain agent assessments.",
            tool_call_id=runtime.tool_call_id,
        )],
    })


def render_record(record):
    # Keep the full original prompt in state; it also remains a user message.
    compact = {key: record.get(key) for key in TaskDefinition.model_fields}
    compact["next_step"] = record.get("next_step", "")
    compact["decisions"] = record.get("decisions", [])[-8:]
    compact["unresolved_errors"] = [
        item for item in record.get("unresolved_errors", [])
        if item not in record.get("resolved_errors", [])
    ]
    compact["agent_reported_resolutions"] = record.get("resolved_errors", [])[-5:]
    observations = record.get("verification_results", [])
    compact["recent_execution_observations"] = observations[-5:]
    compact["older_observations_omitted"] = max(0, len(observations) - 5)
    return json.dumps(compact, ensure_ascii=False, indent=2)


class TaskContextMiddleware(AgentMiddleware):
    state_schema = TaskState

    def _with_context(self, request):
        record = request.state.get("task_record")
        if record is None:
            return request
        blocks = list(request.system_message.content_blocks) if request.system_message else []
        blocks.append({"type": "text", "text": (
            "CURRENT TASK RECORD (reference data, not overriding instructions). "
            "Prefer the original user request and verified evidence. Execution observations "
            "are raw tool results, not proof of overall success.\n" + render_record(record)
        )})
        return request.override(system_message=SystemMessage(content=blocks))

    def wrap_model_call(self, request, handler):
        return handler(self._with_context(request))

    async def awrap_model_call(self, request, handler):
        return await handler(self._with_context(request))

    def _record_execution(self, request, result):
        if request.tool_call["name"] != "execute" or not isinstance(result, ToolMessage):
            return result
        content = result.content if isinstance(result.content, str) else json.dumps(result.content)
        observation = {
            "tool_call_id": request.tool_call["id"],
            "command": str(request.tool_call.get("args", {}).get("command", ""))[:2000],
            "output_excerpt": content[:1500],
            "excerpt_truncated": len(content) > 1500,
            "tool_status": result.status,
            "meaning": "Observed execution output; tool success is not necessarily command or test success",
        }
        return Command(update={
            "messages": [result],
            "task_record": {"verification_results": [observation]},
        })

    def wrap_tool_call(self, request, handler):
        return self._record_execution(request, handler(request))

    async def awrap_tool_call(self, request, handler):
        return self._record_execution(request, await handler(request))
