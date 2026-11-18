"""Coding agent using a local workspace and remote MCP tools."""
import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend

from tools.mcp.test_mcp import load_mcp_tools
from tools.web import internet_search

load_dotenv(Path(__file__).with_name(".env"))

# Local folder the agent will read from and write to.
coding_workspace = Path(__file__).resolve().parent / "agent_workspace"
coding_workspace.mkdir(parents=True, exist_ok=True)


coding_instructions = """You are a coding assistant. Help the user understand, write, debug, and improve code.
Use the available filesystem and documentation tools when relevant.
Explain your changes and reasoning clearly so the user can learn alongside you."""


async def main():
    coding_model = ChatOpenAI(
        base_url=os.getenv("CAMPUSAI_API_URL"),
        model=os.getenv("CAMPUSAI_MODEL"),
        api_key=os.getenv("CAMPUSAI_API_KEY"),
    )

    coding_task = 'Create /hello.py with a greet(name: str) -> str function and a simple example that calls it. Explain how the code works and how I can run it.'

    async with load_mcp_tools() as mcp_tools:
        print("\nMCP tools loaded successfully\n")
        coding_agent = create_deep_agent(
            model=coding_model,
            tools=[internet_search, *mcp_tools],
            system_prompt=coding_instructions,
            backend=FilesystemBackend(
                root_dir=coding_workspace,
                virtual_mode=True,
            ),
            memory=["/agents.md"],
            skills=["/skills/"],
        )

        result = await coding_agent.ainvoke(
            {"messages": [{"role": "user", "content": coding_task}]}
        )
        for message in result["messages"]:
            message.pretty_print()


if __name__ == "__main__":
    asyncio.run(main())
