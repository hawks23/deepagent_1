# Deep Agents Project

Base project for building a coding agent with Python, LangChain, and Deep Agents.
The current entry point is `agent2.py`. Existing research tools and the filesystem
workspace remain available while the coding-agent requirements are developed.

## Project location

On Ubuntu / WSL: `/home/sweet/deep_agents_lang`.

From Windows: `\\wsl.localhost\Ubuntu-22.04\home\sweet\deep_agents_lang`.

## Setup

Python 3.13 or newer and `uv` are required.

```bash
cd /home/sweet/deep_agents_lang
uv sync --locked
```

Create `.env` in the project root with your provider configuration:

```dotenv
CAMPUSAI_API_URL=https://your-provider.example/v1
CAMPUSAI_MODEL=your-model-name
CAMPUSAI_API_KEY=your-model-api-key
TAVILY_API_KEY=your-tavily-api-key
```

Use a model that supports tool calling. The web tool currently requires
`TAVILY_API_KEY` at import time. Keep credentials out of version control.

## Run

Edit the `coding_task` variable in `agent2.py`, then run from the project root:

```bash
uv run agent2.py
```

Each launch sends the current request directly to the agent and prints its
returned messages. There is no interactive input loop or command-line prompt
argument yet.

## Existing components

- `agent2.py`: asynchronous entry point with MCP tools and a local filesystem backend.
- `agent.py`: standalone coding entry point with web search.
- `tools/web.py`: Tavily web search.
- `tools/mcp/test_mcp.py`: MCP configuration and tool discovery.
- `agent_workspace/`: local files accessible through the agent's filesystem tools.
- `agent_workspace/skills/`: reusable task instructions.
- `src/deep_agents_lang/__init__.py`: placeholder package command.
- `tests/`: offline execution checks.

MCP servers currently provide LangChain documentation, FastMCP documentation,
and perfume lookup. The perfume extraction skill uses the perfume server's
results. Tool connections remain open for the duration of the request.

Filesystem tool paths are rooted in `agent_workspace`: `/example.txt` maps to
`agent_workspace/example.txt`. The existing output files are retained.

## Agent instructions

Both entry points use `memory=["/agents.md"]`. The filesystem backend resolves
that path to `agent_workspace/agents.md`, whose coding instructions are loaded
into the model's context. This is the only configured memory source.

The default task creates a small Python function and explains how to run it.
`memory.md`, `skills.md`, episodic/semantic/procedural retrieval, Qdrant, and Mem0
are not implemented yet; these will be introduced step by step.

## Validation

```bash
.venv/bin/python -m unittest discover -s tests -v
```

The checks use fake models and tools, without external API requests.
