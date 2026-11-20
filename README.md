# Deep Agents learning project

Two independent agents for learning coding tools, MCP, execution backends, and
context management. The Docker experiment has not been integrated into `agent.py`.

| | Main agent | Sandbox experiment |
|---|---|---|
| Entry point | `agent.py` | `python -m sandbox_agent.sand_test` |
| Task input | Edit `coding_task` in the source | Command-line argument or one input prompt |
| Files | `/workspace/` routes to local `agent_workspace/` | Container `/workspace` mounts `sandbox_agent/sandbox_workspace/` |
| Execution | No shell execution backend | Python and shell commands in local Docker |
| External tools | Configured MCP servers and Tavily | Container tools and `update_task_record`; no MCP/Tavily wiring |
| Instructions | Inline prompt plus `/workspace/agents.md` and skills | `sandbox_agent/prompts/coding.md` |
| Progress | Completed agent-step messages | Generated text chunks, tool activity, and task-state snapshots |
| Task record | None | Initial LLM refinement, middleware injection, structured updates |

Neither entry point currently provides an interactive multi-turn chat loop or a
checkpointer for conversation continuity. Files persist, but that is not chat memory.

## Setup in Ubuntu / WSL

Use Python 3.13+ and `uv`. In this checkout:

```bash
cd /home/sweet/deep_agents_lang
uv sync --locked
```

From Windows, the project is at
`\\wsl.localhost\Ubuntu-22.04\home\sweet\deep_agents_lang`.

Create `.env` in the project root:

```dotenv
CAMPUSAI_API_URL=https://your-provider.example/v1
CAMPUSAI_MODEL=your-model-name
CAMPUSAI_API_KEY=your-model-api-key
TAVILY_API_KEY=your-tavily-api-key
```

Use an OpenAI-compatible model that supports tool calling. The sandbox's refinement
call also requires structured tool-call output. The main agent imports the Tavily
client at startup and therefore needs its key even when no search is used. The
sandbox experiment does not import Tavily and needs only the model variables.
Existing exported environment variables take precedence over `.env` values.
Never commit real credentials. Neither local workflow requires LangSmith hosted
sandbox authentication; `langsmith` remains a project dependency from earlier work.

## Use the main agent

1. Edit `coding_task` inside `agent.py` with the requested task.
2. Run from the project root:

```bash
uv run agent.py
```

This makes real model calls and connects to enabled MCP servers. The current sample
request replaces `/workspace/perfume.txt`; change it before running if unwanted.
It prints completed model/tool messages with `astream(stream_mode="updates")`.
It does not print each model token as it is generated.

The composite backend routes `/workspace/` to `agent_workspace/`. For example,
`/workspace/index.html` writes `agent_workspace/index.html`. Other paths use
`StateBackend` and are transient across launches. The instruction file is configured
as `memory=["/workspace/agents.md"]`, and skills are loaded from
`/workspace/skills/`. This file context does not provide conversation replay.
The main backend offers filesystem operations, not shell execution.

Configure MCP servers in `tools/mcp/test_mcp.py`. Currently only `perfume-finder`
is enabled; LangChain and FastMCP documentation servers are commented out. Server
names prefix discovered tools. Connections stay open through the agent invocation.
To inspect available remote tools (requires network access):

```bash
uv run python -m tools.mcp.test_mcp
```

The prompt discourages web search without explicit authorization, but Tavily is
still available as a tool; this is an instruction, not a programmatic restriction.

## Use the sandbox agent

Enable Docker Desktop's WSL 2 engine and integration for `Ubuntu-22.04`, apply the
settings, then verify in Ubuntu:

```bash
docker info
docker run --rm hello-world
```

Use Linux containers. The Python process invokes the Docker CLI; no Docker Python
SDK or LangSmith sandbox service is used.

Run a small example from the project root:

```bash
uv run python -m sandbox_agent.sand_test "Create /workspace/addition_demo/add.py with an add(a, b) function. Add unittest checks for positive numbers, negative numbers, and zero. Execute them and report the results. Use only the standard library."
```

Or omit the argument to enter one task interactively:

```bash
uv run python -m sandbox_agent.sand_test
```

This is one task per launch, not a chat loop. The first model call refines the request,
then the coding agent operates inside a new container. See
[sandbox setup, architecture, and middleware](sandbox_agent/README.md) for the full
flow, record schema, limitations, and troubleshooting.

Generated code is saved under `sandbox_agent/sandbox_workspace/`. The container
shares this directory directly: writes, edits, and deletions affect those local
files. Container cleanup preserves them. Inspect a saved task record using the
exact path printed by the runner:

```bash
uv run python -m json.tool sandbox_agent/runs/REPLACE_WITH_RUN_ID.json
```

Each launch gets a new record and container but reuses the same output directory.
There is no automatic resume from the JSON snapshot.

## Repository map

- `agent.py`: original filesystem/MCP agent.
- `agent_workspace/`: main agent's persistent files and instructions.
- `tools/`: web search and MCP configuration.
- `sandbox_agent/`: separate Docker agent, backend, prompts, middleware, and tests.
- `tests/`: main agent offline tests.
- `src/deep_agents_lang/`: placeholder package command, not either agent runner.
- `pyproject.toml` and `uv.lock`: reproducible project dependencies.
- `requirements.txt`: unpinned alternative dependency list; prefer `uv sync --locked`.

The old `agent2.py` and root-level `sand_test.py` are not current entry points.

## Verification

Run both offline suites from the root:

```bash
uv run python -m unittest discover -s tests -v
uv run python -m unittest discover -s sandbox_agent/tests -v
```

These use fake models and local temporary files, not live model/MCP requests or
Docker. They check streaming, instruction routing, task refinement, state merging,
context injection, update tools, and JSON snapshots. They do not establish that a
particular model will reliably complete a complex task or that Docker is configured.

## Local artifacts and scope

`.env`, `.venv`, Python caches, sandbox run records, and generated sandbox workspaces
are ignored by Git. Selected main-agent example files remain tracked. Review files
before deliberately adding generated deliverables.

The task record is an experiment in current-task context. Episodic/semantic memory,
Qdrant, Mem0, cross-session chat persistence, and automatic skill creation are not
implemented. Middleware does not automatically expand or compress the context window.
