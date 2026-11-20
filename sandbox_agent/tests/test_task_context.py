import tempfile
import contextlib
import io
import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from langchain.tools import tool
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage

from sandbox_agent.task_context import (
    TaskDefinition, TaskContextMiddleware, merge_record, refine_task, update_task_record,
)


class ToolModel(FakeMessagesListChatModel):
    def bind_tools(self, tools, **kwargs):
        return self


class Capture(BaseCallbackHandler):
    def __init__(self):
        self.inputs = []

    def on_chat_model_start(self, serialized, messages, **kwargs):
        self.inputs.extend(messages)


def initial_record():
    return {
        "goal": "Build calculator", "requirements": ["Validate input"],
        "acceptance_criteria": ["Invalid input produces a useful error"],
        "constraints": [], "assumptions": [], "open_questions": [],
        "original_prompt": "Build calculator; validate input.",
        "decisions": [], "unresolved_errors": [], "resolved_errors": [],
        "verification_results": [], "next_step": "Inspect",
    }


class TaskTests(unittest.TestCase):
    def test_refinement_preserves_request_and_schema(self):
        model = MagicMock()
        model.with_structured_output.return_value.invoke.return_value = TaskDefinition(
            **{key: initial_record()[key] for key in TaskDefinition.model_fields}
        )
        record = refine_task(model, "Keep this exact request")
        self.assertEqual(record["original_prompt"], "Keep this exact request")
        self.assertEqual(record["verification_results"], [])
        sent = model.with_structured_output.return_value.invoke.call_args.args[0]
        self.assertEqual(sent[1].content, "Keep this exact request")
        self.assertIn("Do not replace", sent[0].content)

    def test_invalid_refinement_fails(self):
        model = MagicMock()
        model.with_structured_output.return_value.invoke.return_value = {"goal": ""}
        with self.assertRaises(ValueError):
            refine_task(model, "Build something")
        with self.assertRaises(ValueError):
            refine_task(model, "  ")

    def test_merge_preserves_parallel_updates_and_definition(self):
        record = initial_record()
        merged = merge_record(merge_record(record, {"decisions": ["A"]}), {"decisions": ["B"]})
        self.assertEqual(merged["decisions"], ["A", "B"])
        self.assertEqual(record["decisions"], [])
        with self.assertRaises(ValueError):
            merge_record(record, {"requirements": []})

    def test_real_graph_updates_and_injects_on_every_call(self):
        @tool
        def execute(command: str) -> str:
            """Execute a simulated offline check."""
            return "Exit code: 1; invalid input test failed"

        model = ToolModel(responses=[
            AIMessage(content="", tool_calls=[
                {"name": "update_task_record", "args": {
                    "next_step": "Fix invalid input", "decision": "Separate parsing",
                    "unresolved_error": "Invalid input crashes",
                }, "id": "update-1", "type": "tool_call"},
                {"name": "execute", "args": {"command": "python tests.py"},
                 "id": "exec-1", "type": "tool_call"},
            ]),
            AIMessage(content="", tool_calls=[{
                "name": "update_task_record", "args": {"next_step": "Inspect traceback"},
                "id": "update-2", "type": "tool_call",
            }]),
            AIMessage(content="The test failed; work remains."),
        ])
        capture = Capture()
        with tempfile.TemporaryDirectory() as folder:
            agent = create_deep_agent(
                model=model, tools=[execute, update_task_record],
                middleware=[TaskContextMiddleware()],
                system_prompt="BASE INSTRUCTIONS",
                backend=FilesystemBackend(root_dir=folder, virtual_mode=True),
            )
            result = agent.invoke({
                "messages": [{"role": "user", "content": "Build calculator; validate input."}],
                "task_record": initial_record(),
            }, config={"callbacks": [capture]})
        record = result["task_record"]
        self.assertEqual(record["decisions"], ["Separate parsing"])
        self.assertEqual(record["next_step"], "Inspect traceback")
        self.assertEqual(record["requirements"], ["Validate input"])
        self.assertEqual(len(record["verification_results"]), 1)
        self.assertIn("Exit code: 1", record["verification_results"][0]["output_excerpt"])
        self.assertEqual(len(capture.inputs), 3)
        texts = []
        for messages in capture.inputs:
            text = "\n".join(b["text"] for b in messages[0].content_blocks if b["type"] == "text")
            self.assertEqual(text.count("CURRENT TASK RECORD"), 1)
            self.assertIn("BASE INSTRUCTIONS", text)
            self.assertIn("Validate input", text)
            texts.append(text)
        self.assertNotIn("Separate parsing", texts[0])
        self.assertIn("Separate parsing", texts[1])
        self.assertIn("Exit code: 1", texts[1])
        self.assertIn("Inspect traceback", texts[2])
        self.assertFalse(any("CURRENT TASK RECORD" in str(m.content) for m in result["messages"]))

    def test_runner_streams_and_saves_latest_record(self):
        from sandbox_agent.sand_test import run_task
        model = ToolModel(responses=[
            AIMessage(content="", tool_calls=[{
                "name": "update_task_record", "args": {
                    "next_step": "Review deliverables", "decision": "Use standard library",
                }, "id": "runner-update", "type": "tool_call",
            }]),
            AIMessage(content="Ready for review."),
        ])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "record.json"
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                run_task(model, FilesystemBackend(root_dir=folder, virtual_mode=True),
                         "Build calculator", initial_record(), path)
            saved = json.loads(path.read_text())
            self.assertEqual(saved["next_step"], "Review deliverables")
            self.assertEqual(saved["decisions"], ["Use standard library"])
            self.assertIn("Ready for review.", output.getvalue())
            self.assertIn("[Tool call: update_task_record]", output.getvalue())
            self.assertFalse(path.with_suffix(".tmp").exists())


if __name__ == "__main__":
    unittest.main()
