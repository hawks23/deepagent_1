"""Offline checks for direct agent execution and filesystem tools."""
import contextlib
import importlib
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend, CompositeBackend, StateBackend
from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage


class ToolModel(FakeMessagesListChatModel):
    def bind_tools(self, tools, **kwargs):
        return self


class ModelInputRecorder(AsyncCallbackHandler):
    def __init__(self):
        self.inputs = []

    async def on_chat_model_start(self, serialized, messages, **kwargs):
        self.inputs.extend(messages)


class AgentTests(unittest.IsolatedAsyncioTestCase):
    async def test_entry_point_invokes_and_prints_each_request(self):
        with patch.dict(os.environ, {"TAVILY_API_KEY": "offline-test-key"}):
            entry = importlib.import_module("agent")

        @contextlib.asynccontextmanager
        async def local_tools():
            yield []

        graph = MagicMock()
        async def stream_result(*args, **kwargs):
            yield {"model": {"messages": [AIMessage(content="Ready.")]}}
        graph.astream.side_effect = stream_result
        output = io.StringIO()
        with (
            patch.object(entry, "ChatOpenAI"),
            patch.object(entry, "load_mcp_tools", local_tools),
            patch.object(entry, "create_deep_agent", return_value=graph) as create_agent,
            contextlib.redirect_stdout(output),
        ):
            await entry.main()
            await entry.main()

        self.assertEqual(create_agent.call_args.kwargs["memory"], ["/workspace/agents.md"])
        self.assertEqual(graph.astream.call_count, 2)
        for call in graph.astream.call_args_list:
            self.assertEqual(len(call.args[0]["messages"]), 1)
            self.assertEqual(call.args[0]["messages"][0]["role"], "user")
            self.assertTrue(call.args[0]["messages"][0]["content"])
            self.assertEqual(call.kwargs, {"stream_mode": "updates"})
        self.assertEqual(output.getvalue().count("Ready."), 2)

    async def test_graph_reads_workspace_file(self):
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, "example.py").write_text("print('hello')")
            instructions = (
                Path(__file__).resolve().parents[1] / "agent_workspace/agents.md"
            ).read_text()
            Path(folder, "agents.md").write_text(instructions)
            recorder = ModelInputRecorder()
            model = ToolModel(responses=[
                AIMessage(content="", tool_calls=[{
                    "name": "read_file",
                    "args": {"file_path": "/workspace/example.py"},
                    "id": "read-example",
                    "type": "tool_call",
                }]),
                AIMessage(content="The script prints hello."),
            ])
            agent = create_deep_agent(
                model=model,
                memory=["/workspace/agents.md"],
                backend=CompositeBackend(
                    default=StateBackend(),
                    routes={"/workspace/": FilesystemBackend(root_dir=folder, virtual_mode=True)},
                ),
            )
            result = await agent.ainvoke({"messages": [{
                "role": "user", "content": "Read /workspace/example.py",
            }]}, config={"callbacks": [recorder]})
            self.assertTrue(recorder.inputs)
            system_content = recorder.inputs[0][0].content
            if isinstance(system_content, list):
                system_content = "\n".join(
                    block if isinstance(block, str) else block.get("text", "")
                    for block in system_content
                )
            self.assertIn(instructions.strip(), system_content)
            self.assertEqual(result["messages"][-1].content, "The script prints hello.")
            results = [m for m in result["messages"] if m.type == "tool"]
            self.assertEqual(len(results), 1)
            self.assertIn("print('hello')", results[0].content)


if __name__ == "__main__":
    unittest.main()
