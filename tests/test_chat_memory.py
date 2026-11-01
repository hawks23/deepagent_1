"""Offline tests: run .venv/bin/python -m unittest discover -s tests -v."""
import json
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, LLMResult

from chat_memory import JsonChatMemory


class SummaryModel:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    async def ainvoke(self, messages, config=None):
        self.calls.append(messages)
        if self.fail:
            raise RuntimeError("summary unavailable")
        return AIMessage(content="User wants woody perfume. Tool reported cedar; source retained.")


class ToolAgent:
    """Exercise callbacks and normal LangChain message serialization without APIs."""
    async def ainvoke(self, inputs, config):
        recorder = config["callbacks"][0]
        request = AIMessage(
            content="", id=str(uuid4()),
            tool_calls=[
                {"name": "lookup", "args": {"name": "A"}, "id": "call-a", "type": "tool_call"},
                {"name": "lookup", "args": {"name": "B"}, "id": "call-b", "type": "tool_call"},
            ],
        )
        await recorder.on_llm_end(
            LLMResult(generations=[[ChatGeneration(message=request)]]), run_id=uuid4()
        )
        a, b = uuid4(), uuid4()
        await recorder.on_tool_start({"name": "lookup"}, "A", run_id=a)
        await recorder.on_tool_start({"name": "lookup"}, "B", run_id=b)
        result_b = ToolMessage(content="No match", tool_call_id="call-b")
        result_a = ToolMessage(content="Cedar", tool_call_id="call-a")
        # Deliberately complete B first. Replay order may still be A then B.
        await recorder.on_tool_end(result_b, run_id=b)
        await recorder.on_tool_end(result_a, run_id=a)
        answer = AIMessage(content="Found cedar.", id=str(uuid4()))
        await recorder.on_llm_end(
            LLMResult(generations=[[ChatGeneration(message=answer)]]), run_id=uuid4()
        )
        return {"messages": [*inputs["messages"], request, result_a, result_b, answer]}


class MemoryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "chat_history.json"
        self.skill = Path(self.temp.name) / "SKILL.md"
        self.skill.write_text("Summarize the supplied conversation.")
        self.memory = JsonChatMemory(self.path, self.skill)

    async def test_reload_and_actual_callback_order(self):
        await self.memory.run(ToolAgent(), "Find perfume", SummaryModel())
        data = json.loads(self.path.read_text())
        events = data["turns"][0]["events"]
        self.assertEqual([e["sequence"] for e in events], list(range(1, 9)))
        starts = [e for e in events if e["kind"] == "tool_start"]
        ends = [e for e in events if e["kind"] == "tool_end"]
        self.assertEqual(ends[0]["run_id"], starts[1]["run_id"])
        reloaded = JsonChatMemory(self.path, self.skill)
        messages = reloaded.context_messages()
        self.assertEqual(messages[0].content, "Find perfume")
        self.assertEqual(messages[1].tool_calls[0]["id"], messages[2].tool_call_id)

    async def test_sixth_turn_and_recursive_summary(self):
        model = SummaryModel()
        for i in range(5):
            await self.memory.run(ToolAgent(), f"query {i}", model)
        self.assertEqual(len(model.calls), 0)
        await self.memory.run(ToolAgent(), "sixth", model)
        self.assertEqual(len(model.calls), 1)
        self.assertEqual(self.memory.data["summary"]["through_turn_id"], 5)
        self.assertEqual(len(self.memory.data["turns"]), 1)
        self.assertEqual(self.memory.data["turns"][0]["turn_id"], 6)
        self.assertEqual(self.memory.context_messages()[2].content, "sixth")
        for i in range(5):
            await self.memory.run(ToolAgent(), f"next {i}", model)
        self.assertEqual(len(model.calls), 2)
        payload = json.loads(model.calls[-1][1].content)
        self.assertEqual(payload["previous_summary"]["through_turn_id"], 5)
        self.assertEqual(self.memory.data["summary"]["through_turn_id"], 10)

    async def test_failed_summary_preserves_batch(self):
        for i in range(5):
            await self.memory.run(ToolAgent(), str(i), SummaryModel())
        before = self.path.read_bytes()
        with self.assertRaisesRegex(RuntimeError, "summary unavailable"):
            await self.memory.run(ToolAgent(), "sixth", SummaryModel(fail=True))
        self.assertEqual(self.path.read_bytes(), before)

    async def test_failed_turn_is_logged_but_not_replayed(self):
        class BrokenAgent:
            async def ainvoke(self, inputs, config):
                await config["callbacks"][0].on_tool_start(
                    {"name": "lookup"}, "A", run_id=uuid4()
                )
                raise RuntimeError("network down")

        with self.assertRaises(RuntimeError):
            await self.memory.run(BrokenAgent(), "Find perfume", SummaryModel())
        self.assertEqual(self.memory.data["turns"][0]["status"], "failed")
        self.assertEqual(self.memory.context_messages(), [])
        self.assertEqual(self.memory.data["turns"][0]["events"][-1]["kind"], "turn_failed")

    async def test_real_deep_agent_callback_integration(self):
        from deepagents import create_deep_agent
        from deepagents.backends import FilesystemBackend
        from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel

        class FakeToolModel(FakeMessagesListChatModel):
            def bind_tools(self, tools, **kwargs):
                return self

        model = FakeToolModel(responses=[
            AIMessage(content="", tool_calls=[{
                "name": "read_file", "args": {"file_path": "/note.txt"},
                "id": "read-note", "type": "tool_call",
            }]),
            AIMessage(content="The note says cedar."),
        ])
        Path(self.temp.name, "note.txt").write_text("cedar")
        agent = create_deep_agent(
            model=model,
            backend=FilesystemBackend(root_dir=self.temp.name, virtual_mode=True),
        )
        result = await self.memory.run(agent, "Read the note", SummaryModel())
        self.assertEqual(result["messages"][-1].content, "The note says cedar.")
        kinds = [e["kind"] for e in self.memory.data["turns"][0]["events"]]
        self.assertEqual(kinds, [
            "user_message", "ai_message", "tool_start", "tool_end",
            "ai_message", "turn_completed",
        ])

    def test_corrupt_file_not_overwritten(self):
        self.path.write_text("{invalid")
        with self.assertRaises(json.JSONDecodeError):
            JsonChatMemory(self.path, self.skill)
        self.assertEqual(self.path.read_text(), "{invalid")


if __name__ == "__main__":
    unittest.main()
