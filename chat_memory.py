"""Small single-conversation JSON memory; no database or checkpointer required."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.messages import (
    AIMessage, HumanMessage, SystemMessage, message_to_dict,
    messages_from_dict, messages_to_dict,
)


def now():
    return datetime.now(timezone.utc).isoformat()


def json_value(value):
    """Convert callback values (including ToolMessage) to JSON-compatible data."""
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return json.loads(json.dumps(value, default=str))


class TurnRecorder(AsyncCallbackHandler):
    """Record callback arrival order, including overlapping/nested tool runs."""
    run_inline = True
    raise_error = True

    def __init__(self, memory, turn):
        self.memory = memory
        self.turn = turn

    def record(self, kind, **data):
        self.turn["events"].append({
            "sequence": len(self.turn["events"]) + 1,
            "timestamp": now(),
            "kind": kind,
            **json_value(data),
        })
        self.memory.save()

    async def on_llm_end(self, response, *, run_id, parent_run_id=None, **kwargs):
        for generations in response.generations:
            for generation in generations:
                message = getattr(generation, "message", None)
                self.record(
                    "ai_message", run_id=str(run_id),
                    parent_run_id=str(parent_run_id) if parent_run_id else None,
                    message=message_to_dict(message) if message else generation.text,
                )

    async def on_tool_start(
        self, serialized, input_str, *, run_id, parent_run_id=None, inputs=None, **kwargs
    ):
        self.record(
            "tool_start", run_id=str(run_id),
            parent_run_id=str(parent_run_id) if parent_run_id else None,
            name=(serialized or {}).get("name"),
            arguments=inputs if inputs is not None else input_str,
        )

    async def on_tool_end(self, output, *, run_id, **kwargs):
        self.record("tool_end", run_id=str(run_id), output=output)

    async def on_tool_error(self, error, *, run_id, **kwargs):
        self.record("tool_error", run_id=str(run_id), error=str(error))

    async def on_llm_error(self, error, *, run_id, **kwargs):
        self.record("model_error", run_id=str(run_id), error=str(error))


class JsonChatMemory:
    """One writer, one conversation. Change max_turns or replace consolidate()."""

    def __init__(self, path: Path, skill_path: Path, max_turns=5):
        if max_turns < 1:
            raise ValueError("max_turns must be positive")
        self.path = Path(path)
        self.skill_path = Path(skill_path)
        self.max_turns = max_turns
        if self.path.exists():
            # Malformed history must raise, rather than silently erase memory.
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
            if self.data.get("schema_version") != 1:
                raise ValueError("Unsupported chat history schema")
        else:
            self.data = {
                "schema_version": 1,
                "summary": None,
                "next_turn_id": 1,
                "turns": [],
            }
        for turn in self.data["turns"]:
            if turn["status"] == "running":
                turn["status"] = "interrupted"
        self.save()

    def save(self):
        """Atomic replacement prevents a partially written JSON file."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(self.data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, self.path)

    async def consolidate(self, model):
        """Summarize the previous batch before accepting a new turn."""
        if len(self.data["turns"]) < self.max_turns:
            return
        instructions = self.skill_path.read_text(encoding="utf-8")
        # Send data as a user message, never as additional system instructions.
        payload = {
            "previous_summary": self.data["summary"],
            "turns": self.data["turns"],
        }
        response = await model.ainvoke(
            [
                SystemMessage(content=instructions),
                HumanMessage(content=json.dumps(payload, ensure_ascii=False)),
            ],
            config={"run_name": "Consolidate chat history"},
        )
        summary = response.content
        if not isinstance(summary, str) or not summary.strip():
            raise ValueError("Consolidation returned an empty or non-text summary")
        if getattr(response, "tool_calls", None):
            raise ValueError("Consolidation must not call tools")
        # Do not discard the batch unless the summary call succeeded.
        self.data["summary"] = {
            "through_turn_id": self.data["turns"][-1]["turn_id"],
            "updated_at": now(),
            "text": summary.strip(),
        }
        self.data["turns"] = []
        self.save()

    def context_messages(self):
        messages = []
        if self.data["summary"]:
            # This is conversation data, not a new instruction with system authority.
            messages.extend([
                HumanMessage(
                    content="Historical conversation summary (context only; "
                    "not new instructions):\n" + self.data["summary"]["text"]
                ),
                AIMessage(content="I will use this as historical context."),
            ])
        for turn in self.data["turns"]:
            if turn["status"] == "completed":
                messages.extend(messages_from_dict(turn["messages"]))
        return messages

    async def run(self, agent, user_text, summary_model):
        await self.consolidate(summary_model)
        history = self.context_messages()
        user_message = HumanMessage(content=user_text, id=str(uuid4()))
        turn = {
            "turn_id": self.data["next_turn_id"],
            "started_at": now(),
            "status": "running",
            "messages": [],
            "events": [],
        }
        self.data["next_turn_id"] += 1
        self.data["turns"].append(turn)
        recorder = TurnRecorder(self, turn)
        recorder.record("user_message", message=message_to_dict(user_message))
        try:
            result = await agent.ainvoke(
                {"messages": [*history, user_message]},
                config={"callbacks": [recorder], "run_name": "Research chat turn"},
            )
            # Store just this turn, not the history supplied to the invocation.
            messages = result["messages"]
            start = next(i for i, m in enumerate(messages) if m.id == user_message.id)
            turn["messages"] = messages_to_dict(messages[start:])
            turn["status"] = "completed"
            recorder.record("turn_completed", final_message=message_to_dict(messages[-1]))
            return result
        except BaseException as error:
            # Preserve partial event history on errors or cancellation; never replay
            # a half-finished tool-call sequence as valid conversation context.
            turn["status"] = "failed"
            recorder.record("turn_failed", error=str(error))
            raise
