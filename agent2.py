"""Research agent using local search and multiple remote MCP servers."""
import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend

from tools.mcp.test_mcp import load_mcp_tools
from tools.web import internet_search
from chat_memory import JsonChatMemory
from langchain_core.messages import messages_from_dict

load_dotenv(Path(__file__).with_name(".env"))

# Local folder the agent will read from and write to.
workspace = Path(__file__).resolve().parent / "agent_workspace"
workspace.mkdir(parents=True, exist_ok=True)


research_instructions = """You are a research assistant. Find reliable information
and present clear, well-organized answers.

Tool selection:
- Use internet_search for general web research.
- Use langchain_docs tools for LangChain documentation.
- Use fastmcp_docs tools for FastMCP documentation.
- Use perfume-finder tools for perfume-related searches and recommendations.
- Read each tool's description and choose the tools relevant to the question.

Research guidelines:
- Prefer authoritative sources and verify important claims.
- Base recommendations on the user's needs and preferences.
- Do not invent facts, sources, prices, or product availability.
- State clearly when information is missing or uncertain.

For perfume questions, read and follow /skills/perfume-extraction/SKILL.md.
Use only perfume-finder MCP tools for perfume information; never use web search.

Response style:
- Answer the question directly.
- Use concise explanations, with headings or lists when helpful.
- Include source links when available.
- Match the level of detail to the request.
"""


async def main():
    llm = ChatOpenAI(
        base_url=os.getenv("CAMPUSAI_API_URL"),
        model=os.getenv("CAMPUSAI_MODEL"),
        api_key=os.getenv("CAMPUSAI_API_KEY"),
    )

    # text = """What are the notes of perfume Rasasi Hawas Fire ? After your research, write a structured extraction that contains Name of perfume, 
    # and lists of all the notes in the 3 layers separately into a file called perfume_hawas.txt in agent workspace."""

    # text = """What is a good woody, spicy yet comfortable daily indoor perfume I can use during winters in Copenhagen ? It should conform to
    # the usual Danish standards."""
    text = """What did we talk about previously ?"""

    chat_memory = JsonChatMemory(
        path=Path(__file__).with_name("chat_history.json"),
        skill_path=workspace / "skills/chat-consolidation/SKILL.md",
        max_turns=5,
    )

    async with load_mcp_tools() as mcp_tools:
        # print("Loaded MCP tools:", ", ".join(tool.name for tool in mcp_tools))
        print("\nMCP Loaded succesfully\n")
        agent = create_deep_agent(
            model=llm,
            tools=[internet_search, *mcp_tools],
            system_prompt=research_instructions,
            backend=FilesystemBackend(
                root_dir=workspace,
                virtual_mode=True,
            ),
            memory=["/AGENTS.md", "/memory.md"],
            skills=["/skills/"],
        )

        result = await chat_memory.run(agent, text, summary_model=llm)

        # Display only the new turn; older turns remain available in JSON.
        current_messages = messages_from_dict(chat_memory.data["turns"][-1]["messages"])
        for message in current_messages:
            message.pretty_print()

        


if __name__ == "__main__":
    asyncio.run(main())