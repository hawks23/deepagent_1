# Deep Agents Research Assistant

A small Python research agent built with LangChain and Deep Agents. It connects to remote MCP tools, follows reusable skills, saves requested research files, and remembers recent conversations in a local JSON file.

The project is designed for learning and experimenting with agent memory. The main application is **`agent2.py`**.

## Contents

- [Quick start](#quick-start)
- [Ask a question](#ask-a-question)
- [Project structure](#project-structure)
- [How a request runs](#how-a-request-runs)
- [Tools and MCP servers](#tools-and-mcp-servers)
- [Instructions, skills, and memory](#instructions-skills-and-memory)
- [Conversation history and consolidation](#conversation-history-and-consolidation)
- [Inspect tool calls](#inspect-tool-calls)
- [Change or extend the agent](#change-or-extend-the-agent)
- [Tests](#tests)
- [Troubleshooting](#troubleshooting)
- [Credentials and Git](#credentials-and-git)

## Quick start

These commands assume Ubuntu or WSL and that `uv` is installed. The project selects Python 3.13 in `.python-version` and declares Python 3.13 or newer in `pyproject.toml`.

### 1. Open the project and install dependencies

For a new checkout:

```bash
git clone https://github.com/hawks23/deepagent_1.git
cd deepagent_1
uv sync --locked
```

For an existing checkout, enter that directory instead. Its local name may be `deep_agents_lang`.

`uv sync --locked` installs dependencies into `.venv` using the committed lockfile and checks that it agrees with the project configuration.

### 2. Create your local environment file

Create a file named `.env` in the project root:

```dotenv
CAMPUSAI_API_URL=https://your-provider.example/v1
CAMPUSAI_MODEL=your-model-name
CAMPUSAI_API_KEY=your-model-api-key
TAVILY_API_KEY=your-tavily-api-key
```

Replace these placeholders with your own configuration.

| Variable | Purpose |
|---|---|
| `CAMPUSAI_API_URL` | Base URL of the OpenAI-compatible model service. |
| `CAMPUSAI_MODEL` | Model identifier accepted by that service. |
| `CAMPUSAI_API_KEY` | Credential for model calls, including consolidation. |
| `TAVILY_API_KEY` | Credential for the general web-search tool. |

Choose a model/service that supports tool calling.

**The current code requires `TAVILY_API_KEY` at startup**, even for a perfume query. `tools/web.py` constructs the Tavily client when imported. This does not mean the agent should use web search for perfume questions.

Run commands from the project root so the imported web module can find the local `.env`.

### 3. Run the agent

```bash
uv run agent2.py
```

Alternatively, after installation:

```bash
source .venv/bin/activate
python agent2.py
```

The script connects to the configured MCP servers, runs its query, records the turn, and prints the new turn's messages.

There is currently **no interactive input loop or command-line question argument**. Each launch runs the `text` variable inside `main()`.

## Ask a question

Edit `text` in `agent2.py`, then run the script.

For a perfume extraction:

```python
text = """What are the top, heart, and base notes of
Jean Paul Gaultier Le Male Le Parfum?
Save the structured result to /perfume.txt."""
```

When the lookup succeeds and the agent saves the requested file, `/perfume.txt` maps to:

```text
agent_workspace/perfume.txt
```

For a follow-up, change the query and run again:

```python
text = "What did we talk about previously?"
```

The same `chat_history.json` is loaded across launches. The current checked-in query is a conversation-recall question; a fresh checkout with no history has no earlier conversation to recall.

## Project structure

```text
.
├── agent2.py                       Main research agent
├── agent.py                        Earlier web-search experiment
├── chat_memory.py                  JSON history, events, and consolidation
├── consolidation.md                Detailed memory design and references
├── pyproject.toml                  Python package and dependencies
├── uv.lock                         Locked dependency versions
├── .env                            Local credentials; ignored by Git
├── chat_history.json               Generated conversation history; ignored
├── tools/
│   ├── web.py                      Tavily internet_search tool
│   └── mcp/
│       └── test_mcp.py              MCP configuration and discovery check
├── agent_workspace/
│   ├── AGENTS.md                   Standing research instructions
│   ├── memory.md                   Curated project facts and preferences
│   └── skills/
│       ├── perfume-extraction/
│       │   └── SKILL.md
│       └── chat-consolidation/
│           └── SKILL.md
├── tests/
│   └── test_chat_memory.py         Offline memory tests
└── src/deep_agents_lang/
    └── __init__.py                 Package entry-point placeholder
```

Use `agent2.py` for the workflow documented here. `agent.py` is an older experiment with different configuration. The installed `deep-agents-lang` command currently prints a greeting; it does not launch the research agent.

## How a request runs

```text
Start agent2.py
    ↓
Configure the model and load local chat history
    ↓
Discover MCP tools and keep their connections open
    ↓
Build the Deep Agent with tools, instructions, and skills
    ↓
Consolidate the previous batch if it contains five turns
    ↓
Supply summary + recent completed turns + new user query
    ↓
Run the agent and record model/tool events
    ↓
Save the completed turn and print its messages
    ↓
Close MCP connections
```

The model chooses relevant tools from their descriptions. Deep Agents supplies the agent framework and filesystem capabilities; this project's code adds tool configuration, task instructions, and a small persistent conversation store.

### Why the code uses async

- `async def main()` allows the function to await network operations.
- `async with load_mcp_tools()` manages MCP connection setup and cleanup.
- `await agent.ainvoke(...)` waits for the agent to finish while allowing other scheduled async work to proceed.
- `asyncio.run(main())` starts the event loop.

`await` does not skip ahead to the next line, and `async` alone does not force tools to run in parallel.

## Tools and MCP servers

The remote servers are configured in `tools/mcp/test_mcp.py`:

| Server | Configured endpoint | Intended use |
|---|---|---|
| `langchain_docs` | `https://docs.langchain.com/mcp` | LangChain documentation |
| `fastmcp_docs` | `https://gofastmcp.com/mcp` | FastMCP documentation |
| `perfume-finder` | `https://mcp.10ml.com/mcp` | Perfume information |

The MCP adapter discovers tool names, descriptions, and argument schemas at runtime. Server names prefix their tools. Availability and returned data depend on the remote services.

To inspect discovery independently:

```bash
uv run python -m tools.mcp.test_mcp
```

This contacts the configured servers and prints their tools and schemas. It does not run a research query.

General web research uses `internet_search` from `tools/web.py`, backed by Tavily.

### Perfume lookup rules

The perfume skill instructs the agent to:

1. Use only the `perfume-finder` MCP server for perfume information.
2. Correct obvious spelling mistakes or recognizable brand abbreviations when searching.
3. Confirm the fragrance and variant rather than substitute a similarly named product.
4. Extract all notes into top, heart/middle, and base layers.
5. Mark unavailable layers explicitly rather than guess.
6. Save a structured extraction when requested and data is available.

Three layers does **not** mean exactly three individual notes.

When successful queries find no information, the required response is:

> The perfume-finder MCP server doesn't contain any information about [perfume name].

A server connection/tool failure has a different response:

> The perfume-finder MCP server could not be queried, so I couldn't retrieve information about [perfume name].

The skill forbids falling back to web search or supplying notes from model memory. These are model instructions; the web-search tool remains available for other tasks, so this is not a programmatic tool-access restriction.

## Instructions, skills, and memory

| Component | Question it answers | How it is used |
|---|---|---|
| `research_instructions` in Python | What is the agent's general role? | Passed as the system prompt. |
| `AGENTS.md` | How should the agent behave in this project? | Loaded through Deep Agents' `memory=` configuration. |
| `memory.md` | What confirmed facts/preferences should persist? | Also loaded through `memory=`; updated through explicit edits. |
| `perfume-extraction/SKILL.md` | How should perfume extraction work? | The agent is instructed to read it for perfume questions. |
| `chat-consolidation/SKILL.md` | How should old conversation be summarized? | Python reads it for a separate summarization call. |
| `chat_history.json` | What happened in this conversation? | Python automatically records, reloads, and consolidates it. |

Both Markdown memory files are context files from Deep Agents' perspective. Their different roles come from their contents.

The filesystem backend uses `agent_workspace` as its virtual root:

```text
Agent path /AGENTS.md       → agent_workspace/AGENTS.md
Agent path /memory.md       → agent_workspace/memory.md
Agent path /skills/...      → agent_workspace/skills/...
Agent path /perfume.txt     → agent_workspace/perfume.txt
```

`chat_history.json` lives beside `agent2.py`, outside this virtual filesystem. The Python memory manager owns it.

## Conversation history and consolidation

### What counts as a turn?

One turn includes the user query, intermediate model responses, tool calls/results, and final answer. Ten tool calls in one reply still count as one turn.

The initial history file has this shape:

```json
{
  "schema_version": 1,
  "summary": null,
  "next_turn_id": 1,
  "turns": []
}
```

Each turn contains its ID, start time, status, serialized LangChain `messages`, and numbered `events`.

### What happens on turn six?

Before processing the sixth request:

1. Python reads the consolidation skill.
2. A separate model call receives the previous summary and turns 1–5.
3. The model returns a new summary.
4. Python saves the summary and clears the old raw batch.
5. The research agent receives that summary plus query six.

The summary covers goals, constraints, confirmed facts, corrections, tool findings, artifacts, and unfinished work. It retains useful exact details and sources while compressing repetition.

For turn seven, the input is:

```text
Summary of turns 1–5
Full messages from turn 6
New query for turn 7
```

Before turn eleven, the previous summary and turns 6–10 are merged into a summary covering turns 1–10.

This is a **five-turn batch policy**, not a sliding window that always retains the latest five raw turns. Summaries are supplied as historical conversation data rather than new system instructions.

### Persistence and limitations

- Events are saved as they arrive using a temporary file and atomic replacement.
- Failed or interrupted turns retain their events but are excluded from raw replay.
- Failed/interrupted attempts still count toward the batch threshold.
- A failed or empty consolidation response leaves the old batch on disk and stops the new request.
- Successful consolidation removes the old raw batch. The summary is lossy and is not a permanent audit log.
- Five turns can still contain large tool results; there is no explicit token-budget limit here.
- One JSON file supports one conversation and one writer. It is not a database or a LangGraph checkpointer.

Read [consolidation.md](consolidation.md) for the full implementation strategy, source references, and tradeoffs.

## Inspect tool calls

The terminal prints the completed turn using LangChain's `pretty_print()`. To examine execution order, open `chat_history.json` and inspect a turn's `events`.

A typical sequence is:

```text
1 user_message
2 ai_message        requests tool calls
3 tool_start        tool A starts
4 tool_start        tool B starts
5 tool_end          tool B completes
6 tool_end          tool A completes
7 ai_message        final answer
8 turn_completed
```

`TurnRecorder` is registered through `config={"callbacks": [recorder]}`. LangChain calls its model/tool event methods. Every event gets the next sequence number and a UTC timestamp.

The callback `run_id` matches a tool's start to its completion. LangChain messages separately retain `tool_call_id` values linking requested calls to tool responses.

Sequence records callback arrival order. Parallel tools can finish in a different order from their requests. Read `(turn_id, sequence)` as the event's position across the conversation. This does not expose hidden model reasoning or remote server internals.

## Change or extend the agent

| Experiment | Where to change it |
|---|---|
| Ask a different question | `text` in `agent2.py` |
| Change the research model | Model settings in `.env` |
| Change the batch size | `max_turns=5` in `agent2.py` |
| Change what summaries preserve | `chat-consolidation/SKILL.md` |
| Use a different summarizer model | Pass another chat model as `summary_model` |
| Try another consolidation policy | `JsonChatMemory.consolidate()` |
| Change persistent storage | `JsonChatMemory` in `chat_memory.py` |
| Add a remote MCP server | `MCP_SERVERS` in `tools/mcp/test_mcp.py` |
| Change perfume behavior | `perfume-extraction/SKILL.md` |

To add a skill, create `agent_workspace/skills/<skill-name>/SKILL.md` with YAML `name` and `description` fields followed by the procedure. Add a routing instruction if it must be read for a specific task.

To start a fresh conversation, stop the agent and move `chat_history.json` to a backup location outside the repository. The next run creates an empty history. This does not clear the separate facts in `memory.md`.

## Tests

Run the offline test suite:

```bash
uv run python -m unittest discover -s tests -v
```

It covers persistence and reload, tool-event ordering, the sixth-turn trigger, repeated consolidation, summary failures, failed turns, malformed JSON, and integration with a real Deep Agents graph using a fake model and local file tool.

These tests do not call the remote model or MCP servers. They validate the memory mechanics, not the quality of a real generated summary.

## Troubleshooting

| Symptom | What to check |
|---|---|
| `KeyError: TAVILY_API_KEY` | Put the variable in the root `.env` and run from that directory. The web module reads it during import. |
| Model authentication or model-not-found error | Verify the provider URL, model name, key, and tool-calling support. |
| MCP connection/discovery fails | Run the standalone MCP check. The current loader initializes all configured servers, so an unavailable server can prevent startup. |
| Agent does not remember an older conversation | Confirm the same project/history file is being used. Failed turns are not replayed; old details may have been compressed. |
| Sixth request fails during consolidation | Check the model error and skill path. The old five-turn batch remains available after a failed summary call. |
| `Unsupported chat history schema` or JSON parsing error | Inspect or restore the history file. The code intentionally refuses to silently replace invalid history. |
| Requested output is not next to the script | Look in `agent_workspace`; agent file paths resolve there. |
| Package command only prints a greeting | Run `uv run agent2.py`; the package entry point is still a placeholder. |

## Credentials and Git

`.env`, `.venv`, and `chat_history.json` are ignored by Git. History contains raw user/tool content; it is not automatically redacted. Research output files under `agent_workspace` are not all ignored, so review them before committing.

Check both ignore rules and tracking state:

```bash
git check-ignore .env
git ls-files -- .env
```

The second command should print nothing. An ignore rule does not stop tracking a file already in Git. If necessary, remove it from the index while preserving the local copy:

```bash
git rm --cached -- .env
```

Review staged filenames before committing:

```bash
git diff --cached --name-status
```

If credentials have already been pushed, revoke or rotate them. Removing the latest file does not remove earlier copies from Git history. History cleanup is a separate operation.
