# Independent Docker coding agent

This experiment is separate from `agent.py`. It adds local execution and an explicit
current-task record. The original user request remains authoritative throughout.

## Setup and commands

From the project root, install dependencies with `uv sync --locked`. Configure
`CAMPUSAI_API_URL`, `CAMPUSAI_MODEL`, and `CAMPUSAI_API_KEY` in the root `.env`.
Use a model/provider supporting tool calls and structured output. The root `.venv`
is shared; there is no second installation or copied credential file.

Start Docker Desktop, enable its WSL 2 engine and Ubuntu-22.04 integration, and
use Linux containers. In WSL, `docker info` must report a working server. Verify
container startup with `docker run --rm hello-world`. Initial runs may download images.

```bash
cd /home/sweet/deep_agents_lang
uv run python -m sandbox_agent.sand_test "Build a small command-line calculator. Handle invalid input clearly."
```

Omit the argument for a single interactive prompt. Both forms exit after one task;
there is no continuing chat session. Previous sample requests are preserved in
`example_tasks.json`. The `deep-agents-lang` package command is a placeholder,
not this runner.

## What happens during a run

1. The runner loads credentials and accepts the original user prompt.
2. A separate model call uses `prompts/refine.md` and
   `with_structured_output(TaskDefinition, method="function_calling")`.
3. Pydantic validates the returned structure. Invalid refinement stops the run
   before a container is allocated. Validation does not guarantee faithful interpretation.
4. The definition, original prompt, and empty progress fields initialize `task_record`.
   The record is printed and saved to a unique `runs/<id>.json` file.
5. `DockerSandbox` starts one container and the coding agent receives the unchanged
   user prompt, record, coding instructions, container tools, and update tool.
6. Middleware supplies the current record before each model call and captures
   execution observations after tool calls. The agent can explicitly update progress.
7. Streaming prints model text and tool activity; state events update the JSON snapshot.
8. The context manager removes the container on normal completion or Python exception.
   Host termination or daemon failure may prevent cleanup; inspect `docker ps -a`
   for leftover uniquely named `coding-agent-*` containers before manually removing one.

The initial refinement response is not token-streamed. During coding, `messages`
prints text chunks immediately, `updates` prints tool calls/results, and `values`
saves task state. Text chunks may contain multiple tokens. These are observable
outputs and execution traces, not a guarantee of access to private model reasoning.

## Docker backend and files

`docker_backend.py` implements Deep Agents' `BaseSandbox` using Python's subprocess
module and the installed Docker CLI. No Python Docker SDK is needed. Its container
ID connects file operations and execution to the same environment throughout a run.

| Setting | Current behavior |
|---|---|
| Image | `python:3.13-slim` |
| Working directory | `/workspace` |
| Writable bind mount | Local `sandbox_agent/sandbox_workspace/` to `/workspace` |
| Scratch directory, HOME, TMPDIR | `/tmp/agent` |
| User | Calling WSL user's numeric UID/GID |
| Resources | 1 GiB RAM, 2 CPUs, 128 processes |
| Security options | All capabilities dropped; no new privileges |
| Execution | Fresh noninteractive `sh -c` per command |
| Default timeout | 120 seconds; timeout argument can change it |
| Returned command output | First 30,000 characters; truncation flag when applicable |
| Networking | Available; package downloads are possible |

The backend does not mount the repository root, credentials, home folder, or Docker
socket into the container. Isolation is limited by configuration: the workspace is
writable host data and networking is enabled. Output is captured in host memory
before truncation, so redirect very large output to scratch files yourself.

Changes to `/workspace` immediately affect local files, and survive container removal.
Files, installed dependencies, and scratch data elsewhere disappear with the container.
One new container is created per invocation, not per command. Output files are shared
across launches; there is no automatic per-task output directory or file cleanup.

Use `/tmp/agent/venv` for Python dependencies. Shell activation and `cd` do not carry
across commands; use absolute executable paths or repeat setup in each command.
The image does not promise Java, Node.js, a graphical desktop, or an interactive TTY.
Test interactive programs with bounded checks where possible and run exported code
in a suitable user terminal for full interaction. No desktop window opens automatically.

## Task definition and evolving record

`task_context.py` defines our own Pydantic `TaskDefinition`; this is not a built-in
LangChain task schema. Fields are:

| Field | Meaning |
|---|---|
| `goal` | Intended outcome |
| `requirements` | Requested features and deliverables |
| `acceptance_criteria` | Observable completion conditions |
| `constraints` | Explicit restrictions |
| `assumptions` | Tentative interpretations, not new mandatory requirements |
| `open_questions` | Remaining ambiguity |

The refinement prompt asks the model to preserve scope, avoid inventing requirements,
and expose ambiguity. The response is converted to a dictionary and augmented with
`original_prompt`, `decisions`, `unresolved_errors`, `resolved_errors`,
`verification_results`, and `next_step`. Pydantic validates the initial definition;
the entire evolving record is not a Pydantic model. Tool validation and the reducer
control subsequent updates.

`TaskState` extends `AgentState` with a record field using the `merge_record` reducer.
It combines list deltas without duplicates and preserves concurrent tool observations.
The last applied `next_step` wins if concurrent updates specify it. Initial definition
fields and the original request cannot be silently rewritten through the reducer.
There is no user-confirmed requirement revision workflow yet; start a new task if needed.

## Middleware and update tool

`TaskContextMiddleware` implements synchronous and asynchronous model/tool hooks.
Before a model call it copies existing system-message blocks, appends a labelled task
briefing, and passes a modified request to the handler. It does not append a permanent
briefing message to conversation history, replace existing instructions, or perform
another summarization LLM call.

The briefing includes all definition fields, the next step, eight recent decisions,
all active blockers, five recent agent-reported resolutions, and five recent execution
observations. It reports how many older observations were omitted. Full observations
remain in state/snapshots, but each stored output is itself only an excerpt. There is
no strict token budget; large requirements or unresolved errors can grow the briefing.

The `update_task_record` tool accepts a nonempty `next_step`, optional `decision`,
optional `unresolved_error`, and optional `resolve_errors` containing exact existing
error strings. It returns a LangGraph `Command` with a state delta and matching tool
acknowledgment. It cannot rewrite the initial task definition or directly add execution
results. Resolutions are agent assessments, not independently proven fixes. Resolved
errors remain in the record; the briefing filters them from active blockers. This
prototype has no explicit reopening operation for the exact same error string.

After an `execute` tool returns a `ToolMessage`, middleware records its call ID,
command (up to 2,000 characters), output excerpt (up to 1,500 characters), truncation
flag, and tool status. These live in `verification_results` for historical naming,
but are raw execution observations. Tool success does not prove command success,
tests passing, or requirement completion. File reads/edits are not automatically
logged there. Exceptions that do not produce a tool message are not captured as an
execution observation. Relevant decisions and blockers require explicit tool updates.

## Snapshots, prompts, and memory boundaries

`runs/<id>.json` is atomically replaced after state events. It is a current task-record
snapshot, not an append-only event log, full transcript, or graph checkpoint.
The runner does not automatically restore it. Each launch begins a fresh record.
The file can contain user text and tool output; it is ignored by Git.

`prompts/coding.md` is the coding system prompt and `prompts/refine.md` governs the
first model call. This experiment does not configure `memory=[...]` or skills, so
main-agent `agents.md`, `memory.md`, and skills are not automatically injected.
No episodic/semantic memory, vector database, or cross-session conversation replay
is implemented. Task context injection alone does not shorten existing chat history.

## Offline tests

```bash
uv run python -m unittest discover -s sandbox_agent/tests -v
```

The tests exercise refinement validation, original-prompt preservation, merging,
immutable definition fields, actual Deep Agents graph execution with a fake model,
updated briefings on subsequent calls, no duplicated briefings in history, execution
observations, streamed output, and snapshot saving. They use temporary filesystem
backends, not Docker or external model APIs.

## Troubleshooting

- Docker server unavailable: start Docker Desktop and check Ubuntu WSL integration.
- Permission denied writing output: inspect workspace ownership and the WSL UID/GID;
  the container deliberately runs as that user, not root.
- Refinement/structured-output failure: check provider tool-call support, model
  configuration, and returned schema. Do not silently bypass validation.
- `401` from model provider: verify CampusAI credentials/endpoint. LangSmith sandbox
  credentials are unrelated to this local Docker runner.
- Missing runtime or interactive display: the default image only promises Python;
  use an appropriate image/environment for other languages or desktop testing.
- A model stops early or hits its context/step limit: snapshots preserve the latest
  recorded task state, but no automatic resume or success guarantee is provided.
